"""Evidence and determinism checks for reverse route impact traversal."""

from copy import deepcopy

import networkx as nx

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
