"""Bounded GitHub REST reads. Repository-supplied URLs are never followed."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import ValidationError

from app.ingestion.models import (
    ChangedFile,
    IngestionError,
    PinnedPullRequest,
    PullRequestRef,
    validate_repository,
)
from app.ingestion.settings import Settings

_SHA = r"[0-9a-f]{40}"
_SUFFIX = re.compile(
    rf"(?:/pulls/[1-9][0-9]*(?:/files)?|/compare/{_SHA}\.\.\.{_SHA}"
    rf"|/git/(?:commits|trees|blobs)/{_SHA})?"
)


def fail(code: str = "github_invalid_response") -> IngestionError:
    """Never include upstream content, URLs or credentials in public errors."""
    messages = {
        "github_invalid_response": ("GitHub returned invalid or incomplete data.", 502),
        "resource_limit": ("The repository exceeds the configured analysis limits.", 422),
        "repository_not_allowed": ("This repository is not approved.", 403),
        "unsupported_repository": (
            "Only public repositories with available heads are supported.", 422,
        ),
        "pr_changed": ("The pull request changed during collection; please try again.", 409),
        "github_redirect": ("GitHub redirected a request; collection was stopped.", 502),
        "github_authentication": ("GitHub authentication failed.", 502),
        "github_permission_denied": ("GitHub denied access to this resource.", 502),
        "github_not_found": ("The requested GitHub resource was not found.", 404),
        "github_rate_limited": ("GitHub is rate limiting requests; please try later.", 503),
        "github_unavailable": ("GitHub is temporarily unavailable.", 502),
        "analysis_timeout": ("The analysis timed out.", 504),
    }
    message, status = messages[code]
    return IngestionError(code, message, status)


def sha(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(_SHA, value) is None:
        raise fail()
    return value


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHubClient:
    """One analysis's request budget and explicit public-repository authorization.

    A transport is a callable receiving ``Request`` and keyword-only ``timeout``;
    its response has status, headers, read(size), close(). Production uses urllib
    with redirects disabled, while tests supply an in-memory response stream.
    """

    def __init__(
        self, settings: Settings, transport=None,
        check_budget: Callable[[], None] = lambda: None,
        remaining_seconds: Callable[[], float] = lambda: 60.0,
    ):
        self.settings = settings
        self._transport = transport or build_opener(_NoRedirect()).open
        self.check_budget = check_budget
        self.remaining_seconds = remaining_seconds
        self._requests = 0
        self._repositories = set(settings.allowed_repositories)
        self._identities: dict[tuple[str, str, int], tuple] = {}

    def _url(self, path: str, query: Mapping[str, Any] | None) -> str:
        if not isinstance(path, str):
            raise fail()
        match = re.fullmatch(r"/repos/([^/]+/[^/]+)(/.*)?", path)
        if match is None:
            raise fail()
        repository, suffix = match[1], match[2] or ""
        try:
            canonical = validate_repository(repository)
        except ValueError:
            raise fail() from None
        if canonical != repository or canonical not in self._repositories:
            raise fail("repository_not_allowed")
        if _SUFFIX.fullmatch(suffix) is None:
            raise fail()
        query = dict(query or {})
        if suffix.endswith("/files"):
            valid = (
                set(query) == {"page", "per_page"}
                and type(query["page"]) is int and 1 <= query["page"] <= 2
                and query["per_page"] == 100
            )
        elif "/git/trees/" in suffix:
            valid = query == {"recursive": "1"}
        else:
            valid = not query
        if not valid:
            raise fail()
        return "https://api.github.com" + path + ("?" + urlencode(query) if query else "")

    @staticmethod
    def _status_error(status: int, headers: Mapping) -> IngestionError:
        lowered = {key.lower(): str(value) for key, value in headers.items()}
        if 300 <= status < 400:
            return fail("github_redirect")
        if status == 401:
            return fail("github_authentication")
        if status == 404:
            return fail("github_not_found")
        if status == 429 or (
            status == 403 and (
                lowered.get("x-ratelimit-remaining") == "0" or "retry-after" in lowered
            )
        ):
            error = fail("github_rate_limited")
            retry = lowered.get("retry-after", "")
            if retry.isascii() and retry.isdecimal() and len(retry) < 20:
                error.retry_after_seconds = min(int(retry), 3600)
            return error
        if status == 403:
            return fail("github_permission_denied")
        return fail("github_unavailable")

    def get_json(self, path: str, query: Mapping[str, Any] | None = None) -> Any:
        url = self._url(path, query)
        self.check_budget()
        remaining = self.remaining_seconds()
        if not math.isfinite(remaining) or remaining <= 0:
            raise fail("analysis_timeout")
        if self._requests >= self.settings.limits.max_http_requests:
            raise fail("resource_limit")
        self._requests += 1
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "CodeScope-AI",
        }
        if self.settings.github_token is not None:
            headers["Authorization"] = "Bearer " + self.settings.github_token.get_secret_value()
        response = None
        try:
            response = self._transport(
                Request(url, headers=headers, method="GET"),
                timeout=min(self.settings.limits.http_timeout_seconds, remaining),
            )
            self.check_budget()
            if response.status != 200:
                raise self._status_error(response.status, response.headers)
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            content_length = response_headers.get("content-length")
            if content_length is not None:
                try:
                    length = int(content_length)
                except (ValueError, TypeError):
                    raise fail() from None
                if length < 0:
                    raise fail()
                if length > self.settings.limits.max_json_bytes:
                    raise fail("resource_limit")
            body = bytearray()
            while True:
                self.check_budget()
                remaining = self.remaining_seconds()
                if remaining <= 0:
                    raise fail("analysis_timeout")
                # urllib exposes the underlying socket here; shorten every read's
                # timeout as the analysis deadline approaches (never lengthen it).
                fp = getattr(response, "fp", None)
                stream_socket = getattr(getattr(fp, "raw", None), "_sock", None)
                if stream_socket is not None:
                    stream_socket.settimeout(
                        min(self.settings.limits.http_timeout_seconds, remaining)
                    )
                chunk = response.read(
                    min(65536, self.settings.limits.max_json_bytes - len(body) + 1)
                )
                self.check_budget()
                if not chunk:
                    break
                if len(body) + len(chunk) > self.settings.limits.max_json_bytes:
                    raise fail("resource_limit")
                body.extend(chunk)
            self.check_budget()
            try:
                result = json.loads(body.decode("utf-8"))
            except (ValueError, UnicodeError, RecursionError):
                raise fail() from None
            self.check_budget()
            return result
        except HTTPError as error:
            try:
                raise self._status_error(error.code, error.headers or {}) from None
            finally:
                error.close()
        except TimeoutError:
            self.check_budget()
            raise fail("github_unavailable") from None
        except (URLError, OSError):
            self.check_budget()
            raise fail("github_unavailable") from None
        finally:
            if response is not None:
                response.close()

    @staticmethod
    def _public_repository(data: Any, expected: str | None = None) -> tuple[str, int]:
        if not isinstance(data, dict) or data.get("private") is not False:
            raise fail("unsupported_repository")
        if data.get("visibility", "public") != "public":
            raise fail("unsupported_repository")
        try:
            name = validate_repository(data["full_name"])
        except (KeyError, ValueError, TypeError, AttributeError):
            raise fail() from None
        if expected is not None and name != expected:
            raise fail("unsupported_repository")
        identifier = data.get("id")
        if type(identifier) is not int or identifier <= 0:
            raise fail()
        return name, identifier

    def _metadata(self, ref: PullRequestRef) -> tuple[dict, tuple]:
        repository = f"{ref.owner}/{ref.repo}"
        if repository not in self.settings.allowed_repositories:
            raise fail("repository_not_allowed")
        data = self.get_json(f"/repos/{repository}/pulls/{ref.number}")
        try:
            if type(data["number"]) is not int or data["number"] != ref.number:
                raise fail()
            base = self._public_repository(data["base"]["repo"], repository)
            head = self._public_repository(data["head"]["repo"])
            base_sha, head_sha = sha(data["base"]["sha"]), sha(data["head"]["sha"])
            count = data["changed_files"]
            if type(count) is not int or count < 0 or not isinstance(data["title"], str):
                raise fail()
            return data, (base, head, base_sha, head_sha, count)
        except (KeyError, TypeError):
            raise fail() from None

    def _check_repositories(self, identity: tuple) -> None:
        for name, identifier in dict.fromkeys(identity[:2]):
            # The only extra destination allowed is the PR's explicitly public
            # metadata-identified head repository, constructed from validated IDs.
            self._repositories.add(name)
            actual = self._public_repository(self.get_json(f"/repos/{name}"), name)
            if actual != (name, identifier):
                raise fail("pr_changed")

    @staticmethod
    def _changed_file(record: Any) -> ChangedFile:
        try:
            status, path = record["status"], record["filename"]
            if status == "added":
                values = {"new_path": path, "new_blob_sha": sha(record["sha"])}
            elif status == "removed":
                values = {"old_path": path, "old_blob_sha": sha(record["sha"])}
            elif status in {"modified", "renamed"}:
                values = {
                    "old_path": record["previous_filename"] if status == "renamed" else path,
                    "new_path": path, "new_blob_sha": sha(record["sha"]),
                }
            else:
                raise fail()
            return ChangedFile(status=status, **values)
        except (KeyError, TypeError, ValidationError):
            raise fail() from None

    def verify_pull_request(self, metadata: PinnedPullRequest) -> None:
        key = (metadata.ref.owner, metadata.ref.repo, metadata.ref.number)
        original = self._identities.get(key)
        if original is None:
            raise fail()
        _, current = self._metadata(metadata.ref)
        if current != original:
            raise fail("pr_changed")
        self._check_repositories(current)

    def pin_pull_request(self, ref: PullRequestRef) -> tuple[PinnedPullRequest, list[ChangedFile]]:
        data, identity = self._metadata(ref)
        base, head, target, head_sha, count = identity
        if count > self.settings.limits.max_changed_files:
            raise fail("resource_limit")
        self._check_repositories(identity)
        first = self.get_json(f"/repos/{base[0]}/compare/{target}...{head_sha}")
        try:
            if sha(first["base_commit"]["sha"]) != target:
                raise fail()
            merge = sha(first["merge_base_commit"]["sha"])
            compared = self.get_json(f"/repos/{base[0]}/compare/{merge}...{head_sha}")
            if (
                sha(compared["base_commit"]["sha"]) != merge
                or sha(compared["merge_base_commit"]["sha"]) != merge
            ):
                raise fail()
            records = compared["files"]
            if not isinstance(records, list) or len(records) != count:
                raise fail()
            files = [self._changed_file(record) for record in records]
        except (KeyError, TypeError):
            raise fail() from None
        paths = [(file.old_path, file.new_path) for file in files]
        if len(set(paths)) != len(paths):
            raise fail()
        mutable = []
        page = 1
        while True:
            self.check_budget()
            batch = self.get_json(f"/repos/{base[0]}/pulls/{ref.number}/files", {
                "page": page, "per_page": 100,
            })
            if not isinstance(batch, list) or len(batch) > 100:
                raise fail()
            mutable.extend(batch)
            if len(mutable) > count:
                raise fail()
            if len(batch) < 100 or len(mutable) == count:
                break
            page += 1
        if len(mutable) != count:
            raise fail()
        # PR patches/URLs are ignored. Only paths/status corroborate the immutable
        # comparison; they can never supply a rename or choose source bytes.
        try:
            mutable_paths = [(
                item["status"], item.get("previous_filename") if item["status"] == "renamed"
                else (None if item["status"] == "added" else item["filename"]),
                None if item["status"] == "removed" else item["filename"],
            ) for item in mutable]
        except (KeyError, TypeError):
            raise fail() from None
        immutable_paths = [(file.status, file.old_path, file.new_path) for file in files]
        if len(set(mutable_paths)) != count or set(mutable_paths) != set(immutable_paths):
            raise fail()
        metadata = PinnedPullRequest(
            ref=ref, title=data["title"], base_repository=base[0], head_repository=head[0],
            target_base_sha=target, analysis_base_sha=merge, head_sha=head_sha, changed_files=count,
        )
        self._identities[(ref.owner, ref.repo, ref.number)] = identity
        self.verify_pull_request(metadata)
        return metadata, files
