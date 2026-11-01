"""NetworkX call-graph assembly and queries implementing D-09 through D-12."""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from app.analysis.models import ResolvedCall, Symbol, UnresolvedCall


@dataclass
class CallGraph:
    """D-12 queryable result with raw graph access and explicit unresolved evidence."""

    graph: nx.DiGraph
    unresolved: dict[str, list[UnresolvedCall]] = field(default_factory=dict)


def build_call_graph(
    symbols_by_module: dict[str, list[Symbol]],
    resolved_calls: list[ResolvedCall],
    unresolved_calls: list[UnresolvedCall],
) -> CallGraph:
    """Assemble verified call edges and retain unresolved evidence outside the graph."""
    graph = nx.DiGraph()

    for module_path, symbols in symbols_by_module.items():
        for symbol in symbols:
            graph.add_node(
                f"{module_path}:{symbol.qualified_name}",
                kind=symbol.kind.value,
                file_path=symbol.file_path,
                start_line=symbol.start_line,
                end_line=symbol.end_line,
            )

    for call in resolved_calls:
        if call.caller not in graph or call.callee not in graph:
            continue

        if graph.has_edge(call.caller, call.callee):
            lines = graph.edges[call.caller, call.callee]["lines"]
            if call.line not in lines:
                lines.append(call.line)
                lines.sort()
        else:
            graph.add_edge(call.caller, call.callee, lines=[call.line])

    unresolved: dict[str, list[UnresolvedCall]] = {}
    for call in unresolved_calls:
        unresolved.setdefault(call.enclosing_symbol, []).append(call)

    return CallGraph(graph=graph, unresolved=unresolved)


def callers_of(call_graph: CallGraph, symbol_id: str) -> list[str]:
    """Return direct callers sorted alphabetically, or none for an unknown node."""
    if symbol_id not in call_graph.graph:
        return []
    return sorted(call_graph.graph.predecessors(symbol_id))


def callees_of(call_graph: CallGraph, symbol_id: str) -> list[str]:
    """Return direct callees sorted alphabetically, or none for an unknown node."""
    if symbol_id not in call_graph.graph:
        return []
    return sorted(call_graph.graph.successors(symbol_id))


def reverse_reachable_from(call_graph: CallGraph, symbol_id: str) -> list[str]:
    """Return every symbol that can reach ``symbol_id``, sorted alphabetically."""
    if symbol_id not in call_graph.graph:
        return []
    return sorted(nx.ancestors(call_graph.graph, symbol_id))
