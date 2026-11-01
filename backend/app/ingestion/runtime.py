"""Thread-safe ephemeral status and cooperative deadlines; no background execution."""

import time
from datetime import UTC, datetime
from threading import RLock
from uuid import UUID

from app.ingestion.models import (
    AnalysisError,
    AnalysisRequest,
    AnalysisStatus,
    AnalysisSummary,
    IngestionError,
)
from app.ingestion.settings import Settings

_STAGES = ("accepted", "metadata", "sources", "mapping", "impact_base", "impact_head", "finished")
_TERMINAL = {"complete", "error", "timeout"}


class Deadline:
    def __init__(self, seconds: float, *, clock=time.monotonic):
        self._clock = clock
        self._end = clock() + seconds

    def remaining_seconds(self) -> float:
        return max(0.0, self._end - self._clock())

    def check(self) -> None:
        if self.remaining_seconds() <= 0:
            raise IngestionError("analysis_timeout", "Analysis timed out.", 504)


class AnalysisRegistry:
    def __init__(self, settings: Settings, *, clock=time.monotonic):
        self._limits = settings.limits
        self._clock = clock
        self._lock = RLock()
        self._records: dict[UUID, AnalysisStatus] = {}
        self._finished: dict[UUID, float] = {}
        self._active: UUID | None = None

    def _prune(self):
        for key, finished in list(self._finished.items()):
            if (
                key != self._active
                and self._clock() - finished >= self._limits.terminal_ttl_seconds
            ):
                self._records.pop(key, None)
                del self._finished[key]
        candidates = [key for key in self._finished if key != self._active]
        while len(self._finished) > self._limits.max_terminal_records and candidates:
            key = candidates.pop(0)
            del self._finished[key]
            self._records.pop(key, None)

    def _record(self, analysis_id):
        self._prune()
        if analysis_id not in self._records:
            raise IngestionError("analysis_not_found", "Analysis was not found.", 404)
        return self._records[analysis_id]

    def reserve(self, request: AnalysisRequest) -> AnalysisStatus:
        with self._lock:
            self._prune()
            if request.analysis_id in self._records:
                raise IngestionError("analysis_id_conflict", "Analysis ID already exists.", 409)
            if self._active is not None:
                raise IngestionError("analysis_busy", "An analysis is already running.", 409)
            now = datetime.now(UTC)
            status = AnalysisStatus(
                analysis_id=request.analysis_id,
                state="pending",
                stage="accepted",
                created_at=now,
                updated_at=now,
            )
            self._records[request.analysis_id] = status
            self._active = request.analysis_id
            return status.model_copy(deep=True)

    def update(self, analysis_id, stage, revisions=None):
        with self._lock:
            status = self._record(analysis_id)
            if status.state in _TERMINAL:
                return
            if _STAGES.index(stage) < _STAGES.index(status.stage):
                return
            changes = dict(state="running", stage=stage, updated_at=datetime.now(UTC))
            if revisions is not None:
                changes["revisions"] = revisions.model_copy(deep=True)
            self._records[analysis_id] = status.model_copy(update=changes)

    def complete(self, analysis_id, summary: AnalysisSummary):
        with self._lock:
            status = self._record(analysis_id)
            if status.state in _TERMINAL:
                return
            if len(summary.model_dump_json().encode("utf-8")) > self._limits.max_summary_bytes:
                raise IngestionError(
                    "result_limit_exceeded", "Analysis result exceeds limits.", 422
                )
            self._records[analysis_id] = status.model_copy(
                update=dict(
                    state="complete",
                    stage="finished",
                    summary=summary.model_copy(deep=True),
                    updated_at=datetime.now(UTC),
                )
            )
            self._finished[analysis_id] = self._clock()
            self._prune()

    def fail(self, analysis_id, error: IngestionError):
        with self._lock:
            status = self._record(analysis_id)
            if status.state in _TERMINAL:
                return
            self._records[analysis_id] = status.model_copy(
                update=dict(
                    state="timeout" if error.code == "analysis_timeout" else "error",
                    stage="finished",
                    updated_at=datetime.now(UTC),
                    error=AnalysisError(
                        code=error.code,
                        message=error.public_message,
                        retry_after_seconds=error.retry_after_seconds,
                    ),
                )
            )
            self._finished[analysis_id] = self._clock()
            self._prune()

    def get(self, analysis_id) -> AnalysisStatus:
        with self._lock:
            return self._record(analysis_id).model_copy(deep=True)

    def release(self, analysis_id):
        """Only the owner calls this, after work and source cleanup have exited."""
        with self._lock:
            if self._active == analysis_id:
                self._active = None
            self._prune()
