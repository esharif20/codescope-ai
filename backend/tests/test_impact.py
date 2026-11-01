"""Evidence and determinism checks for reverse route impact traversal."""

from copy import deepcopy

import networkx as nx
import pytest

from app.analysis import impact as impact_module
from app.analysis.call_graph import CallGraph
from app.analysis.impact import find_affected_routes
from app.analysis.models import ResolutionStatus, UnresolvedCall
from app.analysis.route_models import RouteDeclaration, RouteDiagnostic, RouteRegistration


def _graph(edges: list[tuple[str, str]], isolated: tuple[str, ...] = ()) -> CallGraph:
    graph = nx.DiGraph()
    for name in dict.fromkeys([name for edge in edges for name in edge] + list(isolated)):
        graph.add_node(name, kind="function", file_path=f"{name}.py", start_line=1, end_line=30)
    for caller, callee in edges:
        graph.add_edge(caller, callee, lines=[12, 4, 12])
    return CallGraph(graph)


def _route(handler: str = "handler", method: str = "GET", path: str = "/items",
           app_id: str = "main:app") -> RouteRegistration:
    return RouteRegistration(
        app_id=app_id, handler_id=handler, method=method, path=path,
        declaration=RouteDeclaration(
            receiver_id="routes:router", handler_id=handler, method=method, path="/items",
            file_path="routes.py", line=2, handler_line=3, handler_end_line=9,
        ),
        registration_evidence=[RouteDiagnostic(
            file_path="main.py", line=5, expression="app.include_router(router)",
            reason="verified router registration",
        )],
    )


def test_path_retains_registration_and_every_call_site() -> None:
    graph = _graph([("handler", "service"), ("service", "helper")])
    route = _route()
    result = find_affected_routes(graph, [route], ["helper"])

    assert not result.truncated
    assert result.unknown_symbols == []
    assert len(result.impacts) == 1
    impact = result.impacts[0]
    assert impact.changed_symbol == "helper"
    assert impact.route == route
    assert impact.symbols == ["handler", "service", "helper"]
    assert [edge.model_dump() for edge in impact.edges] == [
        {"caller": "handler", "callee": "service", "file_path": "handler.py", "lines": [4, 12]},
        {"caller": "service", "callee": "helper", "file_path": "service.py", "lines": [4, 12]},
    ]


def test_direct_handler_path_has_no_edges() -> None:
    result = find_affected_routes(_graph([], ("handler",)), [_route()], ["handler"])
    assert result.impacts[0].symbols == ["handler"]
    assert result.impacts[0].edges == []


def test_unknown_and_disconnected_symbols_have_no_path() -> None:
    result = find_affected_routes(
        _graph([], ("handler", "unrelated")), [_route(), _route("missing")],
        ["unrelated", "z:unknown", "a:unknown", "z:unknown"],
    )
    assert result.impacts == []
    assert result.unknown_symbols == ["a:unknown", "z:unknown"]
    assert not result.truncated


def test_unresolved_candidates_never_create_paths() -> None:
    graph = _graph([], ("handler", "helper"))
    graph.unresolved["handler"] = [UnresolvedCall(
        enclosing_symbol="handler", file_path="handler.py", line=4, expression="helper",
        status=ResolutionStatus.UNRESOLVED,
    )]
    assert find_affected_routes(graph, [_route()], ["helper"]).impacts == []


def test_paths_preserve_distinct_methods_mounts_and_apps() -> None:
    routes = [_route(method="POST"), _route(path="/v2/items"), _route(app_id="other:app"), _route()]
    result = find_affected_routes(_graph([], ("handler",)), routes, ["handler"])
    assert [impact.route for impact in result.impacts] == sorted(
        routes, key=lambda route: (route.app_id, route.path, route.method, route.handler_id),
    )


def test_path_json_is_independent_of_insertion_order_and_inputs_are_unchanged() -> None:
    edges = [("handler", "service"), ("service", "helper"), ("other", "helper")]
    graph = _graph(edges)
    routes = [_route("other"), _route()]
    snapshot = deepcopy((nx.node_link_data(graph.graph), graph.unresolved, routes))
    result = find_affected_routes(graph, routes, ["service", "helper"])
    assert result.model_dump_json() == find_affected_routes(
        _graph(list(reversed(edges))), list(reversed(routes)), ["helper", "service"],
    ).model_dump_json()
    assert (nx.node_link_data(graph.graph), graph.unresolved, routes) == snapshot


def test_cycles_and_self_loops_terminate_with_shortest_paths() -> None:
    graph = _graph([
        ("helper", "helper"), ("service", "helper"), ("helper", "service"),
        ("handler", "service"), ("handler", "handler"),
    ])
    result = find_affected_routes(graph, [_route()], ["helper", "helper"])
    assert len(result.impacts) == 1
    assert result.impacts[0].symbols == ["handler", "service", "helper"]
    assert not result.truncated


def test_diamond_path_uses_sorted_first_discovery_and_prefers_shortest() -> None:
    edges = [
        ("handler", "z"), ("z", "helper"), ("handler", "a"), ("a", "helper"),
        ("direct", "helper"), ("direct", "handler"),
    ]
    routes = [_route(), _route("direct")]
    result = find_affected_routes(_graph(edges), routes, ["helper"])
    assert [item.symbols for item in result.impacts] == [
        ["direct", "helper"], ["handler", "a", "helper"],
    ]
    assert result == find_affected_routes(_graph(list(reversed(edges))), routes, ["helper"])


@pytest.mark.parametrize("cap,expected,truncated", [
    (0, [], True), (1, ["helper"], True), (2, ["helper", "service"], True),
    (3, ["handler", "helper", "service"], False),
])
def test_node_cap_preserves_only_complete_paths(monkeypatch, cap, expected, truncated) -> None:
    monkeypatch.setattr(impact_module, "_MAX_VISITED_NODES", cap)
    result = find_affected_routes(
        _graph([("handler", "service"), ("service", "helper")]),
        [_route("helper"), _route("service"), _route()], ["helper"],
    )
    assert [item.route.handler_id for item in result.impacts] == expected
    assert result.truncated is truncated
    for item in result.impacts:
        assert item.symbols[0] == item.route.handler_id
        assert item.symbols[-1] == "helper"
        assert len(item.edges) == len(item.symbols) - 1
        assert all(edge.lines == [4, 12] for edge in item.edges)


def test_node_cap_is_invocation_wide_counts_roots_and_deduplicates_changes(monkeypatch) -> None:
    monkeypatch.setattr(impact_module, "_MAX_VISITED_NODES", 1)
    graph = _graph([], ("a", "b"))
    result = find_affected_routes(graph, [_route("b"), _route("a")], ["b", "a", "a"])
    assert [item.changed_symbol for item in result.impacts] == ["a"]
    assert result.truncated
    exact = find_affected_routes(graph, [_route("a")], ["a", "a"])
    assert len(exact.impacts) == 1
    assert not exact.truncated


def test_node_cap_counts_revisited_nodes_for_separate_changes(monkeypatch) -> None:
    monkeypatch.setattr(impact_module, "_MAX_VISITED_NODES", 2)
    result = find_affected_routes(
        _graph([("handler", "helper")]), [_route()], ["handler", "helper"],
    )
    assert [item.changed_symbol for item in result.impacts] == ["handler"]
    assert result.truncated


@pytest.mark.parametrize("cap,route_count,expected,truncated", [
    (0, 0, 0, False), (0, 1, 0, True), (1, 1, 1, False), (1, 2, 1, True),
    (2, 2, 2, False),
])
def test_path_cap_marks_only_actual_omissions(monkeypatch, cap, route_count, expected, truncated):
    monkeypatch.setattr(impact_module, "_MAX_IMPACT_PATHS", cap)
    result = find_affected_routes(
        _graph([], ("handler",)), [_route(path=f"/{i}") for i in range(route_count)], ["handler"],
    )
    assert len(result.impacts) == expected
    assert result.truncated is truncated
    assert all(item.symbols == ["handler"] and not item.edges for item in result.impacts)


def test_path_cap_applies_across_changes_and_keeps_unknown_symbols(monkeypatch) -> None:
    monkeypatch.setattr(impact_module, "_MAX_IMPACT_PATHS", 1)
    result = find_affected_routes(
        _graph([], ("a", "b")), [_route("b"), _route("a")], ["unknown", "b", "a"],
    )
    assert [item.changed_symbol for item in result.impacts] == ["a"]
    assert result.unknown_symbols == ["unknown"]
    assert result.truncated


def test_exact_node_cap_with_cycles_has_no_omitted_work(monkeypatch) -> None:
    monkeypatch.setattr(impact_module, "_MAX_VISITED_NODES", 1)
    result = find_affected_routes(_graph([("handler", "handler")]), [_route()], ["handler"])
    assert len(result.impacts) == 1
    assert not result.truncated


def test_zero_node_cap_with_only_unknown_or_no_changes_has_no_omitted_work(monkeypatch) -> None:
    monkeypatch.setattr(impact_module, "_MAX_VISITED_NODES", 0)
    graph = _graph([], ("handler",))
    assert not find_affected_routes(graph, [_route()], []).truncated
    result = find_affected_routes(graph, [_route()], ["unknown"])
    assert result.unknown_symbols == ["unknown"]
    assert not result.truncated


def test_truncated_results_are_repeatable_and_do_not_mutate_inputs(monkeypatch) -> None:
    monkeypatch.setattr(impact_module, "_MAX_VISITED_NODES", 3)
    edges = [("handler", "a"), ("a", "helper"), ("other", "helper")]
    graph = _graph(edges)
    routes = [_route("other"), _route()]
    snapshot = deepcopy((nx.node_link_data(graph.graph), graph.unresolved, routes))
    result = find_affected_routes(graph, routes, ["helper"])
    assert result.truncated
    assert result == find_affected_routes(graph, routes, ["helper"])
    assert result == find_affected_routes(_graph(list(reversed(edges))), routes[::-1], ["helper"])
    assert (nx.node_link_data(graph.graph), graph.unresolved, routes) == snapshot


def test_path_cap_exact_bound_allows_later_changes_with_no_impacts(monkeypatch) -> None:
    monkeypatch.setattr(impact_module, "_MAX_IMPACT_PATHS", 1)
    result = find_affected_routes(_graph([], ("handler", "unrelated")), [_route()],
                                  ["handler", "unrelated", "unknown"])
    assert len(result.impacts) == 1
    assert not result.truncated
    assert result.unknown_symbols == ["unknown"]


def test_deep_path_is_iterative_and_preserves_all_edges() -> None:
    symbols = [f"symbol_{i}" for i in range(1100)]
    result = find_affected_routes(
        _graph(list(zip(symbols, symbols[1:]))), [_route(symbols[0])], [symbols[-1]],
    )
    assert result.impacts[0].symbols == symbols
    assert len(result.impacts[0].edges) == len(symbols) - 1
    assert not result.truncated
