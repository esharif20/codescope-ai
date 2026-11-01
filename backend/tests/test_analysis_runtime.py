from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from app.ingestion.models import (
    AnalysisRequest, AnalysisSummary, IngestionError, PinnedPullRequest, PullRequestRef,
)
from app.ingestion.runtime import AnalysisRegistry, Deadline
from app.ingestion.settings import Limits, Settings
from app.reporting.builder import canonical_json_bytes
from app.reporting.models import AnalysisReport, GitHubProvenance, RevisionReport


def report_for(item):
    return AnalysisReport(
        report_id=str(item.analysis_id),
        provenance=GitHubProvenance(pull_request=PinnedPullRequest(
            ref=PullRequestRef(owner="a", repo="b", number=1), title="test",
            base_repository="a/b", head_repository="a/b", target_base_sha="a" * 40,
            analysis_base_sha="b" * 40, head_sha="c" * 40, changed_files=0,
        )),
        revisions=[RevisionReport(revision="base"), RevisionReport(revision="head")],
    )


def prepare(registry, item):
    registry.reserve(item)
    report = report_for(item)
    registry.update(item.analysis_id, "mapping", revisions=report.provenance.pull_request)
    return report


def request():
    return AnalysisRequest(analysis_id=uuid4(), pr_url="https://github.com/a/b/pull/1")


def test_deadline_exact_boundary():
    now = [10.0]
    deadline = Deadline(2, clock=lambda: now[0])
    assert deadline.remaining_seconds() == 2
    now[0] = 12
    with pytest.raises(IngestionError, match="timed out") as caught:
        deadline.check()
    assert caught.value.code == "analysis_timeout"
    assert deadline.remaining_seconds() == 0


def test_admission_race_duplicate_and_defensive_snapshot():
    registry = AnalysisRegistry(Settings())
    item = request()

    def attempt(_):
        try:
            return registry.reserve(item).analysis_id
        except IngestionError as error:
            return error.code

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert results.count(item.analysis_id) == 1
    assert results.count("analysis_id_conflict") == 1
    snapshot = registry.get(item.analysis_id)
    snapshot.stage = "finished"
    assert registry.get(item.analysis_id).stage == "accepted"
    with pytest.raises(IngestionError) as caught:
        registry.reserve(request())
    assert caught.value.code == "analysis_busy"


def test_terminal_invariants_and_expiry_hold_slot_until_cleanup():
    now = [0.0]
    registry = AnalysisRegistry(
        Settings(limits=Limits(terminal_ttl_seconds=2)), clock=lambda: now[0]
    )
    item = request()
    registry.reserve(item)
    registry.update(item.analysis_id, "mapping")
    registry.update(item.analysis_id, "metadata")
    assert registry.get(item.analysis_id).stage == "mapping"
    registry.fail(item.analysis_id, IngestionError("analysis_timeout", "timed out", 504))
    registry.complete(item.analysis_id, AnalysisSummary(), report=report_for(item))
    now[0] = 3
    assert registry.get(item.analysis_id).state == "timeout"
    with pytest.raises(IngestionError):
        registry.reserve(request())
    registry.release(item.analysis_id)
    with pytest.raises(IngestionError) as caught:
        registry.get(item.analysis_id)
    assert caught.value.code == "analysis_not_found"
    registry.reserve(request())


def test_retention_and_output_limit():
    registry = AnalysisRegistry(
        Settings(limits=Limits(max_terminal_records=1, max_summary_bytes=200))
    )
    first, second = request(), request()
    report = prepare(registry, first)
    registry.complete(first.analysis_id, AnalysisSummary(), report=report)
    registry.release(first.analysis_id)
    report = prepare(registry, second)
    with pytest.raises(IngestionError) as caught:
        registry.complete(
            second.analysis_id, AnalysisSummary(diagnostics=["x" * 201]), report=report
        )
    assert caught.value.code == "result_limit_exceeded"
    registry.fail(second.analysis_id, caught.value)
    registry.release(second.analysis_id)
    with pytest.raises(IngestionError):
        registry.get(first.analysis_id)
    assert registry.get(second.analysis_id).state == "error"


def test_report_read_states_and_defensive_copies():
    registry = AnalysisRegistry(Settings())
    item = request()
    registry.reserve(item)
    with pytest.raises(IngestionError) as caught:
        registry.get_report(item.analysis_id)
    assert (caught.value.code, caught.value.http_status) == ("report_not_ready", 409)
    report = report_for(item)
    registry.update(item.analysis_id, "mapping", revisions=report.provenance.pull_request)
    registry.complete(item.analysis_id, AnalysisSummary(), report=report)
    report.provenance.pull_request.title = "mutated"
    snapshot = registry.get_report(item.analysis_id)
    assert snapshot.provenance.pull_request.title == "test"
    snapshot.revisions.clear()
    assert len(registry.get_report(item.analysis_id).revisions) == 2
    registry.fail(item.analysis_id, IngestionError("internal_error", "failed", 500))
    assert registry.get(item.analysis_id).state == "complete"


@pytest.mark.parametrize("fault", ["id", "provenance", "changes", "routes", "missing_revisions"])
def test_invalid_report_never_publishes_and_can_fail(fault):
    registry = AnalysisRegistry(Settings())
    item = request()
    report = prepare(registry, item)
    summary = AnalysisSummary()
    if fault == "id":
        report.report_id = str(uuid4())
    elif fault == "provenance":
        report.provenance.pull_request.head_sha = "d" * 40
    elif fault == "changes":
        # A summary with a missing change cannot be published with the report.
        from app.ingestion.models import ChangedSymbol
        from app.ingestion.source_links import source_reference
        summary.changed_symbols = [ChangedSymbol(
            status="added", symbol_id="x:f", kind="function",
            new=source_reference(report.provenance.pull_request, "head", "x.py", 1, 1),
        )]
    elif fault == "routes":
        summary.affected_routes_base = 1
    else:
        registry._records[item.analysis_id].revisions = None
    with pytest.raises(IngestionError) as caught:
        registry.complete(item.analysis_id, summary, report=report)
    assert caught.value.code == "report_evidence_invalid"
    assert registry.get(item.analysis_id).state == "running"
    with pytest.raises(IngestionError, match="not ready"):
        registry.get_report(item.analysis_id)
    registry.fail(item.analysis_id, caught.value)
    with pytest.raises(IngestionError) as unavailable:
        registry.get_report(item.analysis_id)
    assert (unavailable.value.code, unavailable.value.http_status) == ("report_unavailable", 409)


@pytest.mark.parametrize("delta", [0, -1])
def test_report_byte_boundary_includes_canonical_newline(delta):
    item = request()
    report = report_for(item)
    size = len(canonical_json_bytes(report))
    registry = AnalysisRegistry(Settings(limits=Limits(max_report_bytes=size + delta)))
    prepare(registry, item)
    if delta:
        with pytest.raises(IngestionError) as caught:
            registry.complete(item.analysis_id, AnalysisSummary(), report=report)
        assert caught.value.code == "result_limit_exceeded"
        assert registry.get(item.analysis_id).state == "running"
        assert item.analysis_id not in registry._reports
    else:
        registry.complete(item.analysis_id, AnalysisSummary(), report=report)
        assert registry.get_report(item.analysis_id) == report


def test_reports_expire_and_evict_with_status_active_owner_protected():
    now = [0.0]
    registry = AnalysisRegistry(
        Settings(limits=Limits(max_terminal_records=1, terminal_ttl_seconds=2)),
        clock=lambda: now[0],
    )
    first, second = request(), request()
    report = prepare(registry, first)
    registry.complete(first.analysis_id, AnalysisSummary(), report=report)
    now[0] = 3
    assert registry.get_report(first.analysis_id) == report
    registry.release(first.analysis_id)
    with pytest.raises(IngestionError) as caught:
        registry.get_report(first.analysis_id)
    assert (caught.value.code, caught.value.http_status) == ("analysis_not_found", 404)
    assert first.analysis_id not in registry._reports
    now[0] = 4
    for item in (first, second):
        report = prepare(registry, item)
        registry.complete(item.analysis_id, AnalysisSummary(), report=report)
        registry.release(item.analysis_id)
    assert first.analysis_id not in registry._reports
    assert registry.get_report(second.analysis_id) == report


@pytest.mark.parametrize("value", [0, -1, 2097153, True, 1.5])
def test_report_limit_is_strict_positive_lower_only(value):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Limits(max_report_bytes=value)


def test_report_limit_env_override():
    assert Limits().max_report_bytes == 2097152
    assert Settings.from_env({"CODESCOPE_MAX_REPORT_BYTES": "100"}).limits.max_report_bytes == 100
    with pytest.raises(ValueError):
        Settings.from_env({"CODESCOPE_MAX_REPORT_BYTES": "2097153"})
