"""Public API for the Python symbol extraction and call-graph package.

This module only re-exports; all logic lives in ``models.py`` and
``python_symbols.py``.
"""

from app.analysis.models import (
    ParseResult,
    ParseStatus,
    Symbol,
    SymbolKind,
    SyntaxIssue,
    SyntaxIssueKind,
)
from app.analysis.python_symbols import extract_symbols, extract_symbols_from_file

# Preserve the existing Phase 1 import/export sequence above; Phase 2 entries
# are intentionally additive below it.
# ruff: noqa: I001
from app.analysis.call_graph import CallGraph, callees_of, callers_of, reverse_reachable_from
from app.analysis.project_graph import ProjectGraph, build_project_graph
from app.analysis.route_models import RouteRegistration, RouteInventory, ImpactPath, ImpactResult
from app.analysis.project_routes import ProjectImpactAnalysis, analyze_route_impacts

__all__ = [
    "extract_symbols",
    "extract_symbols_from_file",
    "Symbol",
    "SymbolKind",
    "SyntaxIssue",
    "SyntaxIssueKind",
    "ParseResult",
    "ParseStatus",
    "CallGraph",
    "ProjectGraph",
    "build_project_graph",
    "callers_of",
    "callees_of",
    "reverse_reachable_from",
    "RouteRegistration",
    "RouteInventory",
    "ImpactPath",
    "ImpactResult",
    "ProjectImpactAnalysis",
    "analyze_route_impacts",
]
