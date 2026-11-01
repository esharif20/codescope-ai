"""Immutable tree/blob fixtures exercise safe source materialization and cleanup."""

import base64
import hashlib
import tempfile
from copy import deepcopy
from pathlib import Path

import pytest

from app.ingestion.models import IngestionError
from app.ingestion.settings import Limits, Settings
from app.ingestion.snapshots import fetch_snapshots
from test_github_ingestion import BASE, HEAD, MERGE, REF, client, metadata, repository, routes

BASE_TREE, HEAD_TREE = "e" * 40, "f" * 40


def blob_sha(content):
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


def entry(path, content=b"", mode="100644", type="blob"):
    return {"path": path, "mode": mode, "type": type, "size": len(content),
            "sha": blob_sha(content)}


def snapshot_fixture(base=None, head=None, records=None, fork=False):
    base = {"app.py": b"def f():\n    return 1\n", "caller.py": b"from app import f\nf()\n"} \
        if base is None else base
    head = {**base, "app.py": b"def f():\n    return 2\n"} if head is None else head
    if records is None:
        records = []
        for path in sorted(base.keys() | head.keys()):
            if base.get(path) == head.get(path) and path in base and path in head:
                continue
            status = "added" if path not in base else "removed" if path not in head else "modified"
            content = head[path] if path in head else base[path]
            records.append({"status": status, "filename": path, "sha": blob_sha(content)})
    pr = metadata(changed_files=len(records))
    head_repo = "contributor/fork" if fork else "org/repo"
    if fork:
        pr["head"] = {"sha": HEAD, "repo": repository(head_repo, id=2)}
    data = routes(pr)
    if fork:
        data[f"/repos/{head_repo}"] = repository(head_repo, id=2)
    data[f"/repos/org/repo/compare/{MERGE}...{HEAD}"]["files"] = records
    data["/repos/org/repo/pulls/7/files"] = deepcopy(records)
    for repo, commit, tree, sources in [
        ("org/repo", MERGE, BASE_TREE, base), (head_repo, HEAD, HEAD_TREE, head),
    ]:
        data[f"/repos/{repo}/git/commits/{commit}"] = {"sha": commit, "tree": {"sha": tree}}
        data[f"/repos/{repo}/git/trees/{tree}"] = {
            "sha": tree, "truncated": False,
            "tree": [entry(path, content) for path, content in sorted(sources.items())],
        }
        for content in sources.values():
            digest = blob_sha(content)
            data[f"/repos/{repo}/git/blobs/{digest}"] = {
                "sha": digest, "size": len(content), "encoding": "base64",
                "content": base64.encodebytes(content).decode(),
            }
    return data


def settings(**limits):
    return Settings(allowed_repositories={"org/repo"}, limits=Limits(**limits))


def test_complete_pinned_snapshots_include_unchanged_callers_and_cleanup():
    github, fake = client(snapshot_fixture())
    stages = []
    with fetch_snapshots(REF, github, settings(), on_stage=stages.append) as pair:
        roots = pair.base_root, pair.head_root
        assert (pair.base_root / "app.py").read_bytes() == b"def f():\n    return 1\n"
        assert (pair.head_root / "caller.py").read_bytes() == b"from app import f\nf()\n"
        assert pair.metadata.analysis_base_sha == MERGE
        assert pair.files[0].old_blob_sha == blob_sha(b"def f():\n    return 1\n")
        assert all(root.stat().st_mode & 0o077 == 0 for root in roots)
        assert all(path.stat().st_mode & 0o111 == 0 for root in roots for path in root.rglob("*.py"))
    assert stages == ["metadata", "sources"]
    assert all(not root.exists() for root in roots)
    assert not any(f"git/commits/{BASE}" in request.full_url for request in fake.calls)
    assert sum(request.full_url.endswith("pulls/7") for request in fake.calls) == 3


def test_added_deleted_renamed_empty_and_non_python_files_without_patches():
    base = {"gone.py": b"def gone(): pass\n", "old.py": b"", "README.md": b"old"}
    head = {"new.py": b"", "added.py": b"def added(): pass\n", "README.md": b"new"}
    records = [
        {"filename": "gone.py", "status": "removed", "sha": blob_sha(base["gone.py"])},
        {"filename": "new.py", "previous_filename": "old.py", "status": "renamed",
         "sha": blob_sha(b"")},
        {"filename": "added.py", "status": "added", "sha": blob_sha(head["added.py"])},
        {"filename": "README.md", "status": "modified", "sha": blob_sha(head["README.md"])},
    ]
    data = snapshot_fixture(base, head, records, fork=True)
    # Missing, incorrect or malicious patches and raw URLs are never source authority.
    for record in data["/repos/org/repo/pulls/7/files"]:
        record.update(patch="@@ invalid partial patch", raw_url="https://evil.invalid/secret")
    github, fake = client(data)
    with fetch_snapshots(REF, github, settings()) as pair:
        assert (pair.base_root / "gone.py").exists()
        assert (pair.head_root / "new.py").read_bytes() == b""
        assert not (pair.head_root / "README.md").exists()
        assert pair.diagnostics
        assert pair.metadata.head_repository == "contributor/fork"
    calls = [request.full_url for request in fake.calls]
    assert not any(blob_sha(b"new") in url or blob_sha(b"old") in url for url in calls)
    assert any(f"/repos/contributor/fork/git/commits/{HEAD}" in url for url in calls)


@pytest.mark.parametrize("path", [
    "/escape.py", "../escape.py", "a/../escape.py", "a//b.py", "./a.py", "a\\b.py",
    "a\0b.py", "a\x85b.py", "a/", "x" * 256 + ".py",
])
def test_unsafe_tree_paths_fail_before_writing(path):
    data = snapshot_fixture()
    data[f"/repos/org/repo/git/trees/{BASE_TREE}"]["tree"].append(entry(path))
    github, _ = client(data)
    with pytest.raises(IngestionError) as error:
        with fetch_snapshots(REF, github, settings()):
            pytest.fail("unsafe snapshot yielded")
    assert error.value.code == "unsafe_repository_path"


@pytest.mark.parametrize("first,second", [
    ("same.py", "same.py"), ("App.py", "app.py"), ("caf\u00e9.py", "cafe\u0301.py"),
    ("Dir/a.py", "dir/b.py"), ("app.py", "app.py/nested.py"),
])
def test_duplicate_case_unicode_and_file_directory_collisions(first, second):
    data = snapshot_fixture()
    data[f"/repos/org/repo/git/trees/{BASE_TREE}"]["tree"] = [entry(first), entry(second)]
    github, _ = client(data)
    with pytest.raises(IngestionError) as error:
        with fetch_snapshots(REF, github, settings()):
            pytest.fail("collision yielded")
    assert error.value.code == "unsafe_repository_path"


@pytest.mark.parametrize("mode,type", [("120000", "blob"), ("160000", "commit")])
def test_symlinks_and_submodules_rejected_including_non_python(mode, type):
    data = snapshot_fixture()
    data[f"/repos/org/repo/git/trees/{BASE_TREE}"]["tree"].append(
        entry("external", mode=mode, type=type),
    )
    github, _ = client(data)
    with pytest.raises(IngestionError) as error:
        with fetch_snapshots(REF, github, settings()):
            pytest.fail("unsupported entry yielded")
    assert error.value.code == "unsupported_repository_entry"


@pytest.mark.parametrize("change", ["truncated", "tree_sha", "commit_sha", "missing_change"])
def test_truncated_wrong_identity_or_incomplete_inventory_fails_closed(change):
    data = snapshot_fixture()
    tree = data[f"/repos/org/repo/git/trees/{BASE_TREE}"]
    if change == "truncated":
        tree["truncated"] = True
    elif change == "tree_sha":
        tree["sha"] = "0" * 40
    elif change == "commit_sha":
        data[f"/repos/org/repo/git/commits/{MERGE}"]["sha"] = "0" * 40
    else:
        tree["tree"].append(entry("omitted.txt"))
    github, _ = client(data)
    with pytest.raises(IngestionError):
        with fetch_snapshots(REF, github, settings()):
            pytest.fail("incomplete snapshot yielded")


@pytest.mark.parametrize("field,value", [
    ("sha", "0" * 40), ("size", 999), ("encoding", "utf-8"),
    ("content", "not valid base64!"), ("content", base64.b64encode(b"wrong bytes").decode()),
])
def test_blob_sha_length_encoding_base64_and_content_hash_verified(field, value):
    data = snapshot_fixture()
    digest = blob_sha(b"def f():\n    return 1\n")
    data[f"/repos/org/repo/git/blobs/{digest}"][field] = value
    github, _ = client(data)
    with pytest.raises(IngestionError):
        with fetch_snapshots(REF, github, settings()):
            pytest.fail("unverified blob yielded")


@pytest.mark.parametrize("limit,value", [
    ("max_tree_entries", 1), ("max_python_files_per_revision", 1),
    ("max_source_file_bytes", 1), ("max_total_source_bytes", 1),
])
def test_snapshot_resource_limits(limit, value):
    config = settings(**{limit: value})
    github, _ = client(snapshot_fixture(), settings=config)
    with pytest.raises(IngestionError) as error:
        with fetch_snapshots(REF, github, config):
            pytest.fail("over-limit snapshot yielded")
    assert error.value.code == "resource_limit"


def test_exact_file_tree_and_source_byte_limits_allow_empty_python_files():
    data = snapshot_fixture({"empty.py": b""}, {"empty.py": b"x"})
    config = settings(max_tree_entries=1, max_python_files_per_revision=1,
                      max_source_file_bytes=1, max_total_source_bytes=1)
    github, _ = client(data, settings=config)
    with fetch_snapshots(REF, github, config) as pair:
        assert (pair.base_root / "empty.py").read_bytes() == b""
        assert (pair.head_root / "empty.py").read_bytes() == b"x"


@pytest.mark.parametrize("failure", ["consumer", "upstream", "timeout", "race"])
def test_both_temp_roots_removed_on_every_failure(monkeypatch, failure):
    import app.ingestion.snapshots as snapshots

    roots = []
    original = tempfile.TemporaryDirectory

    def temporary(*args, **kwargs):
        directory = original(*args, **kwargs)
        roots.append(Path(directory.name))
        return directory

    monkeypatch.setattr(snapshots, "TemporaryDirectory", temporary)
    data = snapshot_fixture()
    if failure == "upstream":
        data[f"/repos/org/repo/git/blobs/{blob_sha(b'def f():\n    return 1\n')}"] = \
            IngestionError("github_unavailable", "GitHub unavailable.", 502)
    if failure == "race":
        pr = metadata()
        changed = metadata(head={"sha": "0" * 40, "repo": repository()})
        versions = iter([pr, pr, changed])
        data["/repos/org/repo/pulls/7"] = lambda request: next(versions)
    github, _ = client(data)

    def check():
        if failure == "timeout" and roots:
            raise IngestionError("analysis_timeout", "Analysis timed out.", 504)

    with pytest.raises((IngestionError, RuntimeError)):
        with fetch_snapshots(REF, github, settings(), check_budget=check):
            raise RuntimeError("consumer failed")
    assert len(roots) == 2
    assert all(not root.exists() for root in roots)


def test_regular_executable_git_files_materialize_without_execution_bits():
    data = snapshot_fixture()
    for tree in (BASE_TREE, HEAD_TREE):
        data[f"/repos/org/repo/git/trees/{tree}"]["tree"][0]["mode"] = "100755"
    github, _ = client(data)
    with fetch_snapshots(REF, github, settings()) as pair:
        assert (pair.head_root / "app.py").stat().st_mode & 0o111 == 0
