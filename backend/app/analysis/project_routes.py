"""Bounded, source-only project route inventory and potential impact analysis."""

from dataclasses import dataclass
from pathlib import Path

from app.analysis.impact import find_affected_routes
from app.analysis.imports import extract_raw_imports
from app.analysis.module_paths import module_path_for
from app.analysis.project_graph import ProjectGraph, build_project_graph
from app.analysis.route_models import ImpactResult, RouteDiagnostic, RouteInventory
from app.analysis.route_resolver import resolve_route_inventory
from app.analysis.routes import extract_route_syntax


@dataclass
class ProjectImpactAnalysis:
    """Keep verified results and every incompleteness indicator inspectable."""

    project_graph: ProjectGraph
    routes: RouteInventory
    impact: ImpactResult
    partial: bool


def analyze_route_impacts(root: str, changed_symbols: list[str]) -> ProjectImpactAnalysis:
    """Analyse retained files without importing source or adding inferred edges.

    Explicit unresolved calls remain available on the graph; their presence alone
    does not mark partial. File failures, unsupported route analysis and omitted
    work do. Only verified registrations participate in impact traversal.
    """
    project_graph = build_project_graph(root)
    statuses = dict(project_graph.file_statuses)
    syntax_by_module = {}
    raw_imports_by_module = {}
    init_modules: set[str] = set()
    diagnostics = []
    for file_path, status in sorted(project_graph.file_statuses.items()):
        if status not in {"ok", "empty", "syntax_errors"}:
            continue
        try:
            source = Path(file_path).read_bytes()
            source.decode("utf-8")
        except (OSError, UnicodeDecodeError) as error:
            reason = "decode_error" if isinstance(error, UnicodeDecodeError) else "unreadable"
            statuses[file_path] = reason
            diagnostics.append(RouteDiagnostic(
                file_path=file_path, line=1, expression="<source read>", reason=reason,
            ))
            continue
        module = module_path_for(file_path, root)
        syntax_by_module[module] = extract_route_syntax(source, file_path, module)
        raw_imports_by_module[module] = extract_raw_imports(source, file_path)
        if Path(file_path).name == "__init__.py":
            init_modules.add(module)

    routes = resolve_route_inventory(syntax_by_module, raw_imports_by_module, init_modules)
    routes.file_statuses = statuses
    routes.diagnostics.extend(diagnostics)
    impact = find_affected_routes(project_graph.call_graph, routes.registrations, changed_symbols)
    partial = (
        any(status not in {"ok", "empty"} for status in statuses.values())
        or bool(routes.diagnostics)
        or project_graph.unresolved_truncated
        or routes.truncated
        or impact.truncated
    )
    return ProjectImpactAnalysis(project_graph, routes, impact, partial)
