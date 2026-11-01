"""Immutable, independently validated public source references."""

import pytest

from app.ingestion.models import PinnedPullRequest
from app.ingestion.source_links import source_reference


def metadata():
    return PinnedPullRequest(
        ref={"owner": "target", "repo": "repo", "number": 1}, title="PR",
        base_repository="target/repo", head_repository="fork/repo",
        target_base_sha="a" * 40, analysis_base_sha="b" * 40,
        head_sha="c" * 40, changed_files=1,
    )


@pytest.mark.parametrize("revision,repository,sha", [
    ("base", "target/repo", "b" * 40), ("head", "fork/repo", "c" * 40),
])
def test_revision_links(revision, repository, sha):
    ref = source_reference(metadata(), revision, "src/a.py", 2, 4)
    assert ref.url == f"https://github.com/{repository}/blob/{sha}/src/a.py#L2-L4"
    assert (ref.repository, ref.commit_sha, ref.revision) == (repository, sha, revision)


def test_encoded_segments_and_single_line():
    ref = source_reference(metadata(), "base", "space dir/é#?.py", 1, 1)
    assert ref.url == (
        "https://github.com/target/repo/blob/" + "b" * 40
        + "/space%20dir/%C3%A9%23%3F.py#L1"
    )


@pytest.mark.parametrize("path", ["/a.py", "../a.py", "a//b.py", "a/./b.py", "", "a\\b.py", "a\n.py", "https://x/a.py"])
def test_reject_paths(path):
    with pytest.raises(ValueError):
        source_reference(metadata(), "base", path, 1, 2)


@pytest.mark.parametrize("start,end", [(0, 1), (2, 1), (True, 2), (1, 1.5)])
def test_reject_ranges(start, end):
    with pytest.raises(ValueError):
        source_reference(metadata(), "head", "a.py", start, end)


def test_revalidate_constructed_metadata():
    raw = metadata().model_copy(update={"analysis_base_sha": "main"})
    with pytest.raises(ValueError):
        source_reference(raw, "base", "a.py", 1, 1)
    with pytest.raises(ValueError):
        source_reference(metadata(), "other", "a.py", 1, 1)
