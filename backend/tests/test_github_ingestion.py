"""All upstream traffic is in-memory; no GitHub credentials or network needed."""

import io
import json
from copy import deepcopy
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest

from app.ingestion.github import GitHubClient
from app.ingestion.models import IngestionError, PullRequestRef
from app.ingestion.settings import Limits, Settings

BASE, MERGE, HEAD = "a" * 40, "b" * 40, "c" * 40
BLOB = "d" * 40
REF = PullRequestRef(owner="org", repo="repo", number=7)


class Response(io.BytesIO):
    def __init__(self, data, status=200, headers=None):
        super().__init__(data if isinstance(data, bytes) else json.dumps(data).encode())
        self.status = status
        self.headers = headers or {}


class FakeTransport:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []
        self.responses = []

    def __call__(self, request, *, timeout):
        assert urlsplit(request.full_url).netloc == "api.github.com"
        assert 0 < timeout <= 10
        self.calls.append(request)
        key = urlsplit(request.full_url).path
        result = self.routes[key]
        if callable(result):
            result = result(request)
        if isinstance(result, Exception):
            raise result
        response = result if isinstance(result, Response) else Response(result)
        self.responses.append(response)
        return response


def repository(name="org/repo", **changes):
    return {"full_name": name, "private": False, "visibility": "public", "id": 1, **changes}


def metadata(**changes):
    return {
        "number": 7, "title": "A PR", "changed_files": 1,
        "base": {"sha": BASE, "repo": repository()},
        "head": {"sha": HEAD, "repo": repository()}, **changes,
    }


def routes(pr=None):
    file = {"filename": "app.py", "status": "modified", "sha": BLOB}
    return {
        "/repos/org/repo": repository(),
        "/repos/org/repo/pulls/7": metadata() if pr is None else pr,
        f"/repos/org/repo/compare/{BASE}...{HEAD}": {
            "base_commit": {"sha": BASE}, "merge_base_commit": {"sha": MERGE},
        },
        f"/repos/org/repo/compare/{MERGE}...{HEAD}": {
            "base_commit": {"sha": MERGE}, "merge_base_commit": {"sha": MERGE},
            "files": [file],
        },
        "/repos/org/repo/pulls/7/files": [file],
    }


def client(data=None, **kwargs):
    transport = FakeTransport(routes() if data is None else data)
    settings = kwargs.pop("settings", Settings(allowed_repositories={"org/repo"}))
    return GitHubClient(settings, transport=transport, **kwargs), transport


def test_pins_merge_base_and_immutable_files_then_rechecks_metadata():
    github, fake = client()
    pinned, files = github.pin_pull_request(REF)
    assert (pinned.target_base_sha, pinned.analysis_base_sha, pinned.head_sha) == (
        BASE, MERGE, HEAD,
    )
    assert files[0].new_path == "app.py"
    assert files[0].new_blob_sha == BLOB
    assert sum(urlsplit(r.full_url).path.endswith("pulls/7") for r in fake.calls) == 2
    files_call = next(r for r in fake.calls if urlsplit(r.full_url).path.endswith("/files"))
    assert parse_qs(urlsplit(files_call.full_url).query) == {"page": ["1"], "per_page": ["100"]}
    assert all(response.closed for response in fake.responses)


def test_public_metadata_identified_fork_gets_pinned_provenance():
    pr = metadata(head={"sha": HEAD, "repo": repository("contributor/fork", id=2)})
    data = routes(pr)
    data["/repos/contributor/fork"] = repository("contributor/fork", id=2)
    github, _ = client(data)
    pinned, _ = github.pin_pull_request(REF)
    assert pinned.head_repository == "contributor/fork"


@pytest.mark.parametrize("change", [
    {"private": True}, {"visibility": "private"}, {"full_name": "evil/other"},
])
def test_rechecks_base_visibility_and_identity(change):
    data = routes()
    data["/repos/org/repo"] = repository(**change)
    github, _ = client(data)
    with pytest.raises(IngestionError):
        github.pin_pull_request(REF)


@pytest.mark.parametrize("head", [None, {"private": True, "full_name": "a/b"}, {}])
def test_missing_private_or_deleted_head_fails(head):
    github, _ = client(routes(metadata(head={"sha": HEAD, "repo": head})))
    with pytest.raises(IngestionError):
        github.pin_pull_request(REF)


@pytest.mark.parametrize("field", ["sha", "repo", "changed_files"])
def test_mutable_metadata_race_is_explicit(field):
    first = metadata()
    second = deepcopy(first)
    if field == "sha":
        second["head"]["sha"] = "e" * 40
    elif field == "repo":
        second["head"]["repo"] = repository("other/fork", id=4)
    else:
        second["changed_files"] = 2
    data = routes()
    calls = iter([first, second])
    data["/repos/org/repo/pulls/7"] = lambda request: next(calls)
    github, _ = client(data)
    with pytest.raises(IngestionError, match="changed") as error:
        github.pin_pull_request(REF)
    assert error.value.code == "pr_changed"


@pytest.mark.parametrize("records", [[], [{"filename": "app.py", "status": "modified"}] * 2])
def test_incomplete_duplicate_or_excess_mutable_inventory_fails(records):
    data = routes()
    data["/repos/org/repo/pulls/7/files"] = records
    github, _ = client(data)
    with pytest.raises(IngestionError):
        github.pin_pull_request(REF)


def test_changed_file_limit_checked_before_comparison():
    github, fake = client(routes(metadata(changed_files=101)))
    with pytest.raises(IngestionError) as error:
        github.pin_pull_request(REF)
    assert error.value.code == "resource_limit"
    assert not any("/compare/" in request.full_url for request in fake.calls)


@pytest.mark.parametrize("status,headers,code", [
    (301, {"Location": "https://evil.invalid/"}, "github_redirect"),
    (401, {}, "github_authentication"), (404, {}, "github_not_found"),
    (403, {}, "github_permission_denied"),
    (403, {"X-RateLimit-Remaining": "0"}, "github_rate_limited"),
    (429, {"Retry-After": "999999"}, "github_rate_limited"),
    (503, {}, "github_unavailable"),
])
def test_safe_upstream_errors_close_body(status, headers, code):
    response = Response(b"UPSTREAM SECRET", status, headers)
    github, fake = client({"/repos/org/repo": response})
    with pytest.raises(IngestionError) as error:
        github.get_json("/repos/org/repo")
    assert error.value.code == code
    assert "SECRET" not in str(error.value)
    assert response.closed and len(fake.calls) == 1
    if status == 429:
        assert error.value.retry_after_seconds == 3600


@pytest.mark.parametrize("body,headers,code", [
    (b"{", {}, "github_invalid_response"),
    (b"\xff", {}, "github_invalid_response"),
    (b" " * 101, {}, "resource_limit"),
    (b"{}", {"Content-Length": "101"}, "resource_limit"),
])
def test_json_and_streaming_body_limits(body, headers, code):
    response = Response(body, headers=headers)
    github, _ = client({"/repos/org/repo": response}, settings=Settings(
        allowed_repositories={"org/repo"}, limits=Limits(max_json_bytes=100),
    ))
    with pytest.raises(IngestionError) as error:
        github.get_json("/repos/org/repo")
    assert error.value.code == code
    assert response.closed


@pytest.mark.parametrize("path", [
    "https://evil.invalid/repos/org/repo", "//evil.invalid/", "/repos/org/repo/../x",
    "/repos/other/repo", "/repos/org/repo/contents/app.py?ref=main",
    "/repos/org/repo/git/blobs/main", "/repos/org/repo%2fother",
])
def test_only_constructed_validated_api_paths_can_reach_transport(path):
    github, fake = client()
    with pytest.raises(IngestionError):
        github.get_json(path)
    assert fake.calls == []


def test_request_limit_and_deadline_and_headers_do_not_use_caller_secret():
    settings = Settings(allowed_repositories={"org/repo"}, github_token="upstream",
                        live_access_token="caller", limits=Limits(max_http_requests=1))
    github, fake = client(settings=settings, remaining_seconds=lambda: 0.25)
    github.get_json("/repos/org/repo")
    headers = {key.lower(): value for key, value in fake.calls[0].header_items()}
    assert headers["authorization"] == "Bearer upstream"
    assert headers["x-github-api-version"] == "2026-03-10"
    assert "caller" not in str(headers)
    with pytest.raises(IngestionError) as error:
        github.get_json("/repos/org/repo")
    assert error.value.code == "resource_limit"
    assert len(fake.calls) == 1


def test_network_error_and_urllib_http_error_are_safe():
    for failure, code in [
        (URLError("private internal detail"), "github_unavailable"),
        (HTTPError("url", 404, "detail", {}, io.BytesIO(b"secret")), "github_not_found"),
    ]:
        github, _ = client({"/repos/org/repo": failure})
        with pytest.raises(IngestionError) as error:
            github.get_json("/repos/org/repo")
        assert error.value.code == code
        assert "detail" not in str(error.value)


def test_budget_checked_during_body_read():
    checks = []

    def check():
        checks.append(1)
        if len(checks) == 4:
            raise IngestionError("analysis_timeout", "Analysis timed out.", 504)

    github, fake = client(check_budget=check)
    with pytest.raises(IngestionError) as error:
        github.get_json("/repos/org/repo")
    assert error.value.code == "analysis_timeout"
    assert all(response.closed for response in fake.responses)
