"""Own complete, bounded, blob-verified snapshots for one consumer lifetime."""

from __future__ import annotations

import base64
import binascii
import hashlib
import unicodedata
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from app.ingestion.github import GitHubClient, fail, sha
from app.ingestion.models import ChangedFile, IngestionError, PullRequestRef, SnapshotPair
from app.ingestion.settings import Settings


def _unsafe_path() -> IngestionError:
    return IngestionError(
        "unsafe_repository_path", "The repository contains unsafe or colliding paths.", 422,
    )


def _path(value: Any) -> str:
    if not isinstance(value, str):
        raise _unsafe_path()
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        raise _unsafe_path() from None
    if (
        not value or len(encoded) > 4096 or "\\" in value
        or any(unicodedata.category(character) == "Cc" for character in value)
        or any(part in ("", ".", "..") or len(part.encode("utf-8")) > 255
               for part in value.split("/"))
    ):
        raise _unsafe_path()
    return value


def _portable(value: str) -> str:
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", value).casefold())


@dataclass(frozen=True)
class _Blob:
    sha: str
    size: int
    mode: str


def _inventory(
    client: GitHubClient, repository: str, revision: str, settings: Settings,
    check_budget: Callable[[], None],
) -> dict[str, _Blob]:
    check_budget()
    commit = client.get_json(f"/repos/{repository}/git/commits/{revision}")
    try:
        if sha(commit["sha"]) != revision:
            raise fail()
        tree_sha = sha(commit["tree"]["sha"])
        tree = client.get_json(f"/repos/{repository}/git/trees/{tree_sha}", {"recursive": "1"})
        if sha(tree["sha"]) != tree_sha or tree["truncated"] is not False:
            raise fail()
        entries = tree["tree"]
    except (KeyError, TypeError):
        raise fail() from None
    if not isinstance(entries, list):
        raise fail()
    if len(entries) > settings.limits.max_tree_entries:
        raise fail("resource_limit")
    paths: set[str] = set()
    portable: dict[str, str] = {}
    files: dict[str, _Blob] = {}
    directories: set[str] = set()
    try:
        for entry in entries:
            check_budget()
            path = _path(entry["path"])
            if path in paths:
                raise _unsafe_path()
            paths.add(path)
            # Check all prefixes too: Dir/a.py and dir/b.py collide on macOS
            # even though their normalized full file paths differ.
            parts = path.split("/")
            for index in range(1, len(parts) + 1):
                prefix = "/".join(parts[:index])
                key = _portable(prefix)
                if key in portable and portable[key] != prefix:
                    raise _unsafe_path()
                portable[key] = prefix
            mode, kind = entry["mode"], entry["type"]
            digest = sha(entry["sha"])
            if mode == "040000" and kind == "tree":
                directories.add(path)
                continue
            if mode not in ("100644", "100755") or kind != "blob":
                raise IngestionError(
                    "unsupported_repository_entry",
                    "Repositories with symlinks, submodules or unsupported entries are excluded.",
                    422,
                )
            size = entry["size"]
            if type(size) is not int or size < 0:
                raise fail()
            files[path] = _Blob(digest, size, mode)
        for path in paths:
            check_budget()
            parts = path.split("/")
            if path in directories and path in files:
                raise _unsafe_path()
            if any("/".join(parts[:index]) in files for index in range(1, len(parts))):
                raise _unsafe_path()
    except (KeyError, TypeError):
        raise fail() from None
    python_files = [blob for path, blob in files.items() if path.endswith(".py")]
    if (
        len(python_files) > settings.limits.max_python_files_per_revision
        or any(blob.size > settings.limits.max_source_file_bytes for blob in python_files)
    ):
        raise fail("resource_limit")
    return files


def _verify_changes(
    base: dict[str, _Blob], head: dict[str, _Blob], files: list[ChangedFile],
    check_budget: Callable[[], None],
) -> list[ChangedFile]:
    # Compare blob identities AND modes, across every language. Directory tree
    # hashes reflect descendants and are intentionally not themselves changes.
    old_changed = {path for path in base if base[path] != head.get(path)}
    new_changed = {path for path in head if head[path] != base.get(path)}
    old_seen: set[str] = set()
    new_seen: set[str] = set()
    verified = []
    for file in files:
        check_budget()
        old, new = file.old_path, file.new_path
        if old is not None:
            _path(old)
            if old not in old_changed or old in old_seen:
                raise fail()
            old_seen.add(old)
            if file.old_blob_sha is not None and file.old_blob_sha != base[old].sha:
                raise fail()
        if new is not None:
            _path(new)
            if new not in new_changed or new in new_seen:
                raise fail()
            new_seen.add(new)
            if file.new_blob_sha is not None and file.new_blob_sha != head[new].sha:
                raise fail()
        if (
            (file.status == "added" and new in base)
            or (file.status == "removed" and old in head)
            or (file.status == "modified" and old != new)
            or (file.status == "renamed" and old == new)
        ):
            raise fail()
        verified.append(file.model_copy(update={
            "old_blob_sha": base[old].sha if old is not None else None,
            "new_blob_sha": head[new].sha if new is not None else None,
        }))
    if old_seen != old_changed or new_seen != new_changed:
        raise fail()
    return verified


def _blob_bytes(
    client: GitHubClient, repository: str, blob: _Blob, settings: Settings,
    check_budget: Callable[[], None],
) -> bytes:
    check_budget()
    if blob.size > settings.limits.max_source_file_bytes:
        raise fail("resource_limit")
    data = client.get_json(f"/repos/{repository}/git/blobs/{blob.sha}")
    try:
        if (
            sha(data["sha"]) != blob.sha or type(data["size"]) is not int
            or data["size"] != blob.size or data["encoding"] != "base64"
            or not isinstance(data["content"], str)
        ):
            raise fail()
        check_budget()
        encoded = data["content"].encode("ascii")
        # GitHub wraps Base64 with line breaks. Only ASCII whitespace is allowed;
        # validate=True then rejects all other non-alphabet characters.
        encoded = b"".join(encoded.split())
        if len(encoded) > 4 * ((blob.size + 2) // 3):
            raise fail()
        check_budget()
        source = base64.b64decode(encoded, validate=True)
        check_budget()
        if len(source) != blob.size:
            raise fail()
        if hashlib.sha1(
            b"blob " + str(len(source)).encode("ascii") + b"\0" + source,
            usedforsecurity=False,
        ).hexdigest() != blob.sha:
            raise fail()
        check_budget()
        return source
    except (KeyError, TypeError, UnicodeError, binascii.Error):
        raise fail() from None


def _materialize(
    root: Path, repository: str, inventory: dict[str, _Blob], client: GitHubClient,
    settings: Settings, cache: dict[str, bytes], check_budget: Callable[[], None],
) -> None:
    for path, blob in sorted(inventory.items()):
        check_budget()
        if not path.endswith(".py"):
            continue
        source = cache.get(blob.sha)
        if source is None:
            source = _blob_bytes(client, repository, blob, settings, check_budget)
            cache[blob.sha] = source
        elif len(source) != blob.size:
            raise fail()
        check_budget()
        destination = root.joinpath(*_path(path).split("/"))
        if not destination.resolve().is_relative_to(root.resolve()):
            raise _unsafe_path()
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        check_budget()
        # Fresh private roots, validated non-colliding regular files, no archive
        # extraction and no permissions copied from executable git file modes.
        with destination.open("xb") as output:
            destination.chmod(0o600)
            output.write(source)
        check_budget()


@contextmanager
def fetch_snapshots(
    ref: PullRequestRef, client: GitHubClient, settings: Settings, *,
    check_budget: Callable[[], None] = lambda: None,
    on_stage: Callable[[str], None] = lambda stage: None,
) -> Iterator[SnapshotPair]:
    """Yield all verified Python source, deleting both roots on every exit path."""
    check_budget()
    on_stage("metadata")
    metadata, files = client.pin_pull_request(ref)
    check_budget()
    on_stage("sources")
    # Both directories are owned for the entire consumer context. Exceptions at
    # any subsequent network, decode, filesystem or consumer step clean both.
    with TemporaryDirectory(prefix="codescope-base-") as base_directory, \
            TemporaryDirectory(prefix="codescope-head-") as head_directory:
        base_root, head_root = Path(base_directory), Path(head_directory)
        check_budget()
        base = _inventory(client, metadata.base_repository, metadata.analysis_base_sha,
                          settings, check_budget)
        head = _inventory(client, metadata.head_repository, metadata.head_sha,
                          settings, check_budget)
        files = _verify_changes(base, head, files, check_budget)
        total = sum(blob.size for inventory in (base, head)
                    for path, blob in inventory.items() if path.endswith(".py"))
        if total > settings.limits.max_total_source_bytes:
            raise fail("resource_limit")
        cache: dict[str, bytes] = {}
        _materialize(
            base_root, metadata.base_repository, base, client, settings, cache, check_budget,
        )
        _materialize(
            head_root, metadata.head_repository, head, client, settings, cache, check_budget,
        )
        cache.clear()
        check_budget()
        client.verify_pull_request(metadata)
        check_budget()
        diagnostics = [
            "Excluded non-Python change from symbol analysis."
            for file in files
            if not any(path and path.endswith(".py") for path in (file.old_path, file.new_path))
        ]
        yield SnapshotPair(metadata, base_root, head_root, files, diagnostics)
