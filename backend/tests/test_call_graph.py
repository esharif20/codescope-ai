"""Tests for deterministic call-graph assembly and queries."""

from __future__ import annotations

from app.analysis.call_graph import build_call_graph
from app.analysis.models import ResolutionStatus, ResolvedCall, Symbol, SymbolKind, UnresolvedCall


def _symbol(name: str, *, kind: SymbolKind = SymbolKind.FUNCTION) -> Symbol:
    return Symbol(
        name=name.rsplit(".", 1)[-1],
        qualified_name=name,
        kind=kind,
        file_path=f"{name}.py",
        module_path="sample",
        start_line=1,
        end_line=1,
    )


def _unresolved(enclosing_symbol: str, line: int) -> UnresolvedCall:
    return UnresolvedCall(
        enclosing_symbol=enclosing_symbol,
        file_path="sample.py",
        line=line,
        expression="dynamic.call",
        status=ResolutionStatus.UNRESOLVED,
    )


def test_build_call_graph_adds_symbols_and_call_site_lines() -> None:
    caller = "sample:caller"
    callee = "sample:callee"

    call_graph = build_call_graph(
        {"sample": [_symbol("caller"), _symbol("callee")]},
        [ResolvedCall(caller=caller, callee=callee, line=12)],
        [],
    )

    assert call_graph.graph.number_of_nodes() == 2
    assert call_graph.graph.number_of_edges() == 1
    assert call_graph.graph.edges[caller, callee]["lines"] == [12]


def test_build_call_graph_deduplicates_edges_and_sorts_lines() -> None:
    caller = "callers:call_twice"
    callee = "services.auth:get_current_user"

    call_graph = build_call_graph(
        {
            "callers": [_symbol("call_twice")],
            "services.auth": [_symbol("get_current_user")],
        },
        [
            ResolvedCall(caller=caller, callee=callee, line=8),
            ResolvedCall(caller=caller, callee=callee, line=4),
            ResolvedCall(caller=caller, callee=callee, line=8),
        ],
        [],
    )

    assert call_graph.graph.number_of_edges() == 1
    assert call_graph.graph.edges[caller, callee]["lines"] == [4, 8]


def test_build_call_graph_adds_class_nodes() -> None:
    class_symbol = _symbol("UserService", kind=SymbolKind.CLASS)

    call_graph = build_call_graph({"sample": [class_symbol]}, [], [])

    assert "sample:UserService" in call_graph.graph
    assert call_graph.graph.nodes["sample:UserService"] == {
        "kind": "class",
        "file_path": "UserService.py",
        "start_line": 1,
        "end_line": 1,
    }


def test_build_call_graph_keeps_unresolved_calls_outside_graph() -> None:
    call_graph = build_call_graph(
        {"sample": [_symbol("first"), _symbol("second")]},
        [],
        [
            _unresolved("sample:first", 3),
            _unresolved("sample:first", 4),
            _unresolved("sample:second", 5),
        ],
    )

    assert set(call_graph.unresolved) == {"sample:first", "sample:second"}
    assert len(call_graph.unresolved["sample:first"]) == 2
    assert len(call_graph.unresolved["sample:second"]) == 1
    assert call_graph.graph.number_of_edges() == 0


def test_build_call_graph_skips_unknown_resolved_endpoints() -> None:
    call_graph = build_call_graph(
        {"sample": [_symbol("caller")]},
        [ResolvedCall(caller="sample:caller", callee="missing:callee", line=7)],
        [],
    )

    assert call_graph.graph.number_of_nodes() == 1
    assert call_graph.graph.number_of_edges() == 0
