"""Deterministic report assembly; retained sources are data and never executed."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.analysis.project_routes import ProjectImpactAnalysis
from app.ingestion.models import IngestionError, validate_path
from app.ingestion.source_links import source_reference
from app.reporting.models import (
    AnalysisReport,
    ControlledProvenance,
    ControlledReference,
    GitHubReference,
    ReportEdge,
    ReportFinding,
    ReportInput,
    ReportNode,
    ReportRoute,
    ReportUncertainty,
    Revision,
    RevisionReport,
    evidence_revision,
)


def canonical_json_bytes(value: BaseModel | dict | list) -> bytes:
    """Single shared JSON format, including exactly one final newline."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
        + b"\n"
    )


def _safe_path(root: Path, relative: str) -> Path:
    validate_path(relative)
    root = root.resolve(strict=True)
    path = root / relative
    cursor = root
    for segment in relative.split("/"):
        cursor = cursor / segment
        if cursor.is_symlink():
            raise ValueError("symlink source")
    path.resolve(strict=True).relative_to(root)
    if not path.is_file():
        raise ValueError("source is not a file")
    return path


def snapshot_digest(root: Path, relative_paths: list[str]) -> str:
    """Hash sorted unique length-prefixed paths and exact bytes, excluding roots."""
    digest = hashlib.sha256()
    for relative in sorted(set(relative_paths)):
        source = _safe_path(root, relative).read_bytes()
        name = relative.encode("utf-8")
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(len(source).to_bytes(8, "big"))
        digest.update(source)
    return digest.hexdigest()


def _invalid():
    return IngestionError("report_evidence_invalid", "Report source evidence is invalid.", 422)


def _reason(value):
    return value if re.fullmatch(r"[a-z][a-z0-9_]{0,79}", value) else "unsupported_analysis"


def _ordered(values):
    return [value for _, value in sorted({canonical_json_bytes(v): v for v in values}.items())]


def build_report(
    inputs: ReportInput,
    *,
    base: ProjectImpactAnalysis,
    head: ProjectImpactAnalysis,
    roots: dict[Revision, Path],
    max_report_bytes: int = 2097152,
    check_budget: Callable[[], None] = lambda: None,
) -> AnalysisReport:
    """Retain verified structures, explicit omissions and revision-correct evidence."""
    check_budget()
    try:
        inputs = ReportInput.model_validate(inputs.model_dump())
        if set(roots) != {"base", "head"}:
            raise ValueError("missing revision root")
        roots = {rev: root.resolve(strict=True) for rev, root in roots.items()}
    except (ValueError, OSError) as error:
        raise _invalid() from error
    uncertainties = []
    revisions = []

    def uncertainty(rev, category, reason, source=None, symbol_id=None, candidates=None):
        uncertainties.append(
            ReportUncertainty(
                revision=rev,
                category=category,
                reason=_reason(reason),
                source=source,
                symbol_id=symbol_id,
                candidates=sorted(set(candidates or [])),
            )
        )

    def relative(rev, path):
        raw = Path(path)
        # Do not resolve away symlinks before validating the lexical path.
        relative_path = raw.relative_to(roots[rev]).as_posix()
        _safe_path(roots[rev], relative_path)
        return relative_path

    def evidence(rev, path, start, end, *, required=True):
        check_budget()
        try:
            name = relative(rev, path)
            source = _safe_path(roots[rev], name).read_bytes()
            if (
                type(start) is not int
                or type(end) is not int
                or not 1 <= start <= end <= len(source.splitlines())
            ):
                raise ValueError("invalid source range")
            if isinstance(inputs.provenance, ControlledProvenance):
                return ControlledReference(
                    fixture_id=inputs.provenance.fixture_id,
                    revision=rev,
                    file_path=name,
                    start_line=start,
                    end_line=end,
                )
            return GitHubReference(
                source=source_reference(inputs.provenance.pull_request, rev, name, start, end)
            )
        except (ValueError, OSError) as error:
            if required:
                raise _invalid() from error
            uncertainty(rev, "invalid_evidence", "invalid_evidence")
            return None

    # Mapping references also require actual retained bytes, not merely valid URLs.
    for ref in [
        *(ref for change in inputs.changes for ref in (change.old, change.new) if ref),
        *inputs.unmapped_changes,
    ]:
        check_budget()
        location = ref.source if isinstance(ref, GitHubReference) else ref
        checked = evidence(
            evidence_revision(ref),
            roots[evidence_revision(ref)] / location.file_path,
            location.start_line,
            location.end_line,
        )
        if checked != ref:
            raise _invalid()

    for rev, analysis in (("base", base), ("head", head)):
        check_budget()
        project = analysis.project_graph
        graph = project.call_graph.graph
        if isinstance(inputs.provenance, ControlledProvenance):
            try:
                inventory = []
                for path in sorted(set(project.file_statuses) | set(analysis.routes.file_statuses)):
                    check_budget()
                    inventory.append(relative(rev, path))
                # The analysis inventory defines the case; sibling fixtures never enter it.
                actual = snapshot_digest(roots[rev], inventory)
                if actual != getattr(inputs.provenance, f"{rev}_digest"):
                    raise ValueError("snapshot digest mismatch")
            except (ValueError, OSError) as error:
                raise _invalid() from error
        nodes = []
        edges = []
        findings = []
        try:
            for symbol_id, node in sorted(graph.nodes(data=True)):
                check_budget()
                nodes.append(
                    ReportNode(
                        symbol_id=symbol_id,
                        kind=node["kind"],
                        source=evidence(
                            rev, node["file_path"], node["start_line"], node["end_line"]
                        ),
                    )
                )
            for caller, callee, edge in sorted(graph.edges(data=True)):
                check_budget()
                refs = [
                    evidence(rev, graph.nodes[caller]["file_path"], line, line)
                    for line in sorted(set(edge["lines"]))
                ]
                edges.append(ReportEdge(caller=caller, callee=callee, evidence=refs))
            edge_index = {(e.caller, e.callee): e for e in edges}
            for impact in analysis.impact.impacts:
                check_budget()
                registration = impact.route
                declaration = registration.declaration
                route = ReportRoute(
                    app_id=registration.app_id,
                    handler_id=registration.handler_id,
                    method=registration.method,
                    path=registration.path,
                    declaration=evidence(
                        rev, declaration.file_path, declaration.line, declaration.line
                    ),
                    handler=evidence(
                        rev,
                        declaration.file_path,
                        declaration.handler_line,
                        declaration.handler_end_line,
                    ),
                    registration_evidence=_ordered(
                        [
                            evidence(rev, fact.file_path, fact.line, fact.line)
                            for fact in registration.registration_evidence
                        ]
                    ),
                )
                path_edges = []
                for fact in impact.edges:
                    check_budget()
                    candidate = ReportEdge(
                        caller=fact.caller,
                        callee=fact.callee,
                        evidence=_ordered(
                            [evidence(rev, fact.file_path, line, line) for line in fact.lines]
                        ),
                    )
                    verified = edge_index.get((fact.caller, fact.callee))
                    if verified is None or set(
                        map(canonical_json_bytes, candidate.evidence)
                    ) != set(map(canonical_json_bytes, verified.evidence)):
                        raise ValueError("impact edge lacks graph evidence")
                    path_edges.append(verified)
                findings.append(
                    ReportFinding(
                        changed_symbol=impact.changed_symbol,
                        route=route,
                        symbols=impact.symbols,
                        edges=path_edges,
                    )
                )
        except (KeyError, ValueError, OSError, TypeError) as error:
            raise _invalid() from error

        for calls in project.call_graph.unresolved.values():
            for call in calls:
                check_budget()
                category = (
                    "uncertain_call" if call.status.value == "uncertain" else "unresolved_call"
                )
                uncertainty(
                    rev,
                    category,
                    category,
                    evidence(rev, call.file_path, call.line, call.line, required=False),
                    call.enclosing_symbol,
                    call.candidates,
                )
        for diagnostic in analysis.routes.diagnostics:
            check_budget()
            uncertainty(
                rev,
                "route_diagnostic",
                diagnostic.reason,
                evidence(
                    rev, diagnostic.file_path, diagnostic.line, diagnostic.line, required=False
                ),
            )
        for statuses in (project.file_statuses, analysis.routes.file_statuses):
            for path, status in sorted(statuses.items()):
                check_budget()
                if status not in {"ok", "empty"}:
                    uncertainty(
                        rev, "file_status", status, evidence(rev, path, 1, 1, required=False)
                    )
        for symbol in sorted(set(analysis.impact.unknown_symbols)):
            check_budget()
            uncertainty(rev, "unknown_symbol", "unknown_changed_symbol", symbol_id=symbol)
        flags = [
            ("unresolved_truncated", project.unresolved_truncated),
            ("routes_truncated", analysis.routes.truncated),
            ("impacts_truncated", analysis.impact.truncated),
        ]
        for reason, value in flags:
            if value:
                uncertainty(rev, "truncation", reason)
        partial = (
            analysis.partial
            or any(value for _, value in flags)
            or bool(analysis.impact.unknown_symbols)
            or bool(analysis.routes.diagnostics)
            or any(
                status not in {"ok", "empty"}
                for statuses in (project.file_statuses, analysis.routes.file_statuses)
                for status in statuses.values()
            )
            or any(u.revision == rev and u.category == "invalid_evidence" for u in uncertainties)
        )
        try:
            revisions.append(
                RevisionReport(
                    revision=rev,
                    nodes=nodes,
                    edges=edges,
                    findings=_ordered(findings),
                    partial=partial,
                )
            )
        except ValidationError as error:
            raise _invalid() from error
    for diagnostic in inputs.mapping_diagnostics:
        check_budget()
        uncertainty(None, "mapping", diagnostic)
    for ref in inputs.unmapped_changes:
        check_budget()
        uncertainty(evidence_revision(ref), "unmapped_change", "unmapped_change", ref)
    report = AnalysisReport(
        report_id=inputs.report_id,
        provenance=inputs.provenance,
        changes=_ordered(inputs.changes),
        revisions=revisions,
        unmapped_changes=_ordered(inputs.unmapped_changes),
        uncertainties=_ordered(uncertainties),
        partial=inputs.mapping_partial
        or bool(inputs.unmapped_changes)
        or any(r.partial for r in revisions),
    )
    check_budget()
    encoded = canonical_json_bytes(report)
    check_budget()
    if len(encoded) > max_report_bytes:
        raise IngestionError("result_limit_exceeded", "Report exceeds the result size limit.", 422)
    return report
