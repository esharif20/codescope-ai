from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from app.ingestion.models import AnalysisRequest, AnalysisSummary, IngestionError
from app.ingestion.runtime import AnalysisRegistry, Deadline
from app.ingestion.settings import Limits, Settings


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
    registry.complete(item.analysis_id, AnalysisSummary())
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
    registry.reserve(first)
    registry.complete(first.analysis_id, AnalysisSummary())
    registry.release(first.analysis_id)
    registry.reserve(second)
    with pytest.raises(IngestionError) as caught:
        registry.complete(second.analysis_id, AnalysisSummary(diagnostics=["x" * 201]))
    assert caught.value.code == "result_limit_exceeded"
    registry.fail(second.analysis_id, caught.value)
    registry.release(second.analysis_id)
    with pytest.raises(IngestionError):
        registry.get(first.analysis_id)
    assert registry.get(second.analysis_id).state == "error"
