"""Pinned provenance and ingestion boundary invariants."""

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ingestion.models import (
    AnalysisError,
    AnalysisRequest,
    AnalysisStatus,
    AnalysisSummary,
    ChangedFile,
    ChangedSymbol,
    IngestionError,
    MappingResult,
    PinnedPullRequest,
    PullRequestRef,
    SnapshotPair,
    SourceReference,
)


def reference(**overrides):
    return SourceReference.model_validate(
        dict(
            revision="base",
            repository="owner/repo",
            commit_sha="a" * 40,
            file_path="src/app.py",
            start_line=1,
            end_line=4,
            url="https://github.com/owner/repo/blob/" + "a" * 40 + "/src/app.py#L1-L4",
        )
        | overrides
    )


def metadata(**overrides):
    return PinnedPullRequest.model_validate(
        dict(
            ref=PullRequestRef(owner="owner", repo="repo", number=1),
            title="Change",
            base_repository="owner/repo",
            head_repository="fork/repo",
            target_base_sha="a" * 40,
            analysis_base_sha="b" * 40,
            head_sha="c" * 40,
            changed_files=1,
        )
        | overrides
    )


@pytest.mark.parametrize("sha", ["a" * 39, "a" * 41, "A" * 40, "g" * 40, ""])
def test_sha_validation(sha):
    for field in ("target_base_sha", "analysis_base_sha", "head_sha"):
        with pytest.raises(ValidationError):
            metadata(**{field: sha})
    with pytest.raises(ValidationError):
        reference(commit_sha=sha)
    with pytest.raises(ValidationError):
        ChangedFile(status="added", new_path="a.py", new_blob_sha=sha)


@pytest.mark.parametrize(
    "overrides",
    [
        {"start_line": 0},
        {"end_line": 0},
        {"start_line": 5, "end_line": 4},
        {"file_path": "../a.py"},
        {"file_path": "/a.py"},
        {"file_path": "a\\b.py"},
        {"file_path": "a/./b.py"},
        {"file_path": "a//b.py"},
        {"repository": "../repo"},
    ],
)
def test_source_validation(overrides):
    with pytest.raises(ValidationError):
        reference(**overrides)


@pytest.mark.parametrize(
    "status,old,new,valid",
    [
        (
            s,
            o,
            n,
            (s == "modified" and o and n)
            or (s == "added" and not o and n)
            or (s == "removed" and o and not n),
        )
        for s in ("added", "modified", "removed")
        for o in (False, True)
        for n in (False, True)
    ],
)
def test_changed_symbol_combinations(status, old, new, valid):
    values = dict(
        status=status,
        symbol_id="app:f",
        kind="function",
        old=reference() if old else None,
        new=reference(revision="head") if new else None,
    )
    if valid:
        assert ChangedSymbol(**values).status == status
    else:
        with pytest.raises(ValidationError):
            ChangedSymbol(**values)


def test_wrong_reference_side_rejected():
    with pytest.raises(ValidationError):
        ChangedSymbol(status="added", symbol_id="a:f", kind="function", new=reference())


@pytest.mark.parametrize("state", ["pending", "running", "complete", "error", "timeout"])
@pytest.mark.parametrize(
    "has_summary,has_error", [(False, False), (True, False), (False, True), (True, True)]
)
def test_status_invariants(state, has_summary, has_error):
    summary = AnalysisSummary() if has_summary else None
    error = AnalysisError(code="failed", message="Analysis failed") if has_error else None
    valid = (
        (state == "complete" and has_summary and not has_error)
        or (state in ("error", "timeout") and has_error and not has_summary)
        or (state in ("pending", "running") and not has_summary and not has_error)
    )
    args = dict(
        analysis_id=uuid4(),
        state=state,
        stage="accepted",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        summary=summary,
        error=error,
    )
    if valid:
        assert AnalysisStatus(**args).state == state
    else:
        with pytest.raises(ValidationError):
            AnalysisStatus(**args)


@pytest.mark.parametrize("same_base", [False, True])
def test_json_roundtrip(same_base, tmp_path):
    pinned = metadata(analysis_base_sha="a" * 40) if same_base else metadata()
    status = AnalysisStatus(
        analysis_id=uuid4(),
        state="complete",
        stage="finished",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        revisions=pinned,
        summary=AnalysisSummary(),
    )
    assert AnalysisStatus.model_validate_json(status.model_dump_json()) == status
    assert json.loads(status.model_dump_json())["created_at"].endswith("Z")
    pair = SnapshotPair(pinned, tmp_path / "base", tmp_path / "head", [], [])
    assert isinstance(pair.base_root, Path)
    assert "base_root" not in status.model_dump_json()


def test_defaults_and_request_boundary():
    first, second = MappingResult(), MappingResult()
    first.diagnostics.append("partial")
    assert second.diagnostics == []
    first_summary, second_summary = AnalysisSummary(), AnalysisSummary()
    first_summary.diagnostics.append("partial")
    assert second_summary.diagnostics == []
    for extra in ({"extra": True}, {"pr_url": "x" * 2049}):
        with pytest.raises(ValidationError):
            AnalysisRequest.model_validate(
                dict(analysis_id=uuid4(), pr_url="https://github.com") | extra
            )
    with pytest.raises(ValidationError):
        PullRequestRef(owner="owner", repo="repo", number=0)
    with pytest.raises(ValidationError):
        metadata(changed_files=-1)
    with pytest.raises(ValidationError):
        AnalysisError(code="x", message="Safe", retry_after_seconds=-1)
    with pytest.raises(ValidationError):
        AnalysisSummary(affected_routes_base=-1)


def test_ingestion_error_and_framework_independence():
    error = IngestionError("rate_limit", "Try again later", 429, 30)
    assert (error.code, error.public_message, error.http_status, error.retry_after_seconds) == (
        "rate_limit",
        "Try again later",
        429,
        30,
    )
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import app.ingestion.models; assert 'fastapi' not in sys.modules",
        ],
        check=True,
    )
