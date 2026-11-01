"""Synchronous source-only analysis with one owned slot through actual cleanup.

Deadlines are cooperative: a native parser call may overrun until it returns.
The caller must run this function to completion even if its HTTP client disconnects;
cancelling an await does not stop a request thread or release admission.
"""

import re
from pathlib import Path

from app.analysis.project_routes import analyze_route_impacts
from app.ingestion.diff_mapping import map_snapshot_changes
from app.ingestion.github import GitHubClient
from app.ingestion.models import (
    AnalysisRequest,
    AnalysisStatus,
    AnalysisSummary,
    IngestionError,
    validate_path,
)
from app.ingestion.runtime import AnalysisRegistry, Deadline
from app.ingestion.settings import Settings
from app.ingestion.snapshots import fetch_snapshots
from app.ingestion.urls import parse_pr_url


def _diagnostics(analysis, root, revision):
    """Publish reason/location only; source expressions and private paths stay local."""
    result = set()

    def location(path):
        try:
            return validate_path(Path(path).resolve().relative_to(Path(root).resolve()).as_posix())
        except (ValueError, OSError):
            return None

    def reason(value):
        return value if re.fullmatch(r"[a-z][a-z0-9_]{0,79}", value) else "unsupported_analysis"

    statuses = analysis.project_graph.file_statuses | analysis.routes.file_statuses
    for path, status in statuses.items():
        if status not in {"ok", "empty"}:
            relative = location(path)
            if relative:
                result.add(f"{revision}:{relative}:{reason(status)}")
    for diagnostic in analysis.routes.diagnostics:
        relative = location(diagnostic.file_path)
        if relative:
            result.add(f"{revision}:{relative}:{diagnostic.line}:{reason(diagnostic.reason)}")
    for flag, value in (
        ("unresolved_truncated", analysis.project_graph.unresolved_truncated),
        ("routes_truncated", analysis.routes.truncated),
        ("impacts_truncated", analysis.impact.truncated),
        ("unknown_changed_symbols", bool(analysis.impact.unknown_symbols)),
    ):
        if value:
            result.add(f"{revision}:{flag}")
    return result


def _route_count(analysis):
    return len(
        {
            (p.route.app_id, p.route.handler_id, p.route.method, p.route.path)
            for p in analysis.impact.impacts
        }
    )


def run_analysis(
    request: AnalysisRequest,
    registry: AnalysisRegistry,
    settings: Settings,
    *,
    client_factory=GitHubClient,
) -> AnalysisStatus:
    """Reserve atomically, publish only complete evidence and release after cleanup."""
    registry.reserve(request)  # Conflicts are request-level errors, never overwrite records.
    analysis_id = request.analysis_id
    deadline = Deadline(settings.limits.analysis_timeout_seconds)
    try:
        settings.require_live_enabled()
        ref = parse_pr_url(request.pr_url, settings.allowed_repositories)
        client = client_factory(
            settings, check_budget=deadline.check, remaining_seconds=deadline.remaining_seconds
        )
        with fetch_snapshots(
            ref,
            client,
            settings,
            check_budget=deadline.check,
            on_stage=lambda stage: registry.update(analysis_id, stage),
        ) as pair:
            deadline.check()
            registry.update(analysis_id, "mapping", revisions=pair.metadata)
            mapping = map_snapshot_changes(pair, check_budget=deadline.check)
            deadline.check()
            registry.update(analysis_id, "impact_base")
            base = analyze_route_impacts(
                str(pair.base_root),
                sorted({change.symbol_id for change in mapping.changes if change.old}),
                check_budget=deadline.check,
            )
            deadline.check()
            registry.update(analysis_id, "impact_head")
            head = analyze_route_impacts(
                str(pair.head_root),
                sorted({change.symbol_id for change in mapping.changes if change.new}),
                check_budget=deadline.check,
            )
            deadline.check()
            diagnostics = set(mapping.diagnostics)
            diagnostics.update(_diagnostics(base, pair.base_root, "base"))
            diagnostics.update(_diagnostics(head, pair.head_root, "head"))
            ordered = sorted(diagnostics)
            if len(ordered) > 1000:
                ordered = ordered[:999] + ["diagnostics_truncated"]
            summary = AnalysisSummary(
                changed_symbols=mapping.changes,
                affected_routes_base=_route_count(base),
                affected_routes_head=_route_count(head),
                partial=mapping.partial or base.partial or head.partial or len(diagnostics) > 1000,
                diagnostics=ordered,
            )
        # Cleanup must succeed before a success is observable.
        deadline.check()
        registry.complete(analysis_id, summary)
    except IngestionError as error:
        registry.fail(analysis_id, error)
    except Exception:
        registry.fail(
            analysis_id, IngestionError("internal_error", "Analysis could not complete.", 500)
        )
    finally:
        registry.release(analysis_id)
    return registry.get(analysis_id)
