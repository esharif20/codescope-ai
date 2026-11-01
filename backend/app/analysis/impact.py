"""Canonical shortest supported paths from registered handlers to changed symbols.

These static paths describe potential impact, not runtime execution or every
possible call path. Unresolved calls never participate in the traversal.
"""

from collections import deque

from app.analysis.call_graph import CallGraph
from app.analysis.route_models import CallSiteEvidence, ImpactPath, ImpactResult, RouteRegistration


def find_affected_routes(
    call_graph: CallGraph,
    routes: list[RouteRegistration],
    changed_symbols: list[str],
) -> ImpactResult:
    """Find one deterministic shortest evidence path per registration/change pair."""
    graph = call_graph.graph
    changes = sorted(set(changed_symbols))
    result = ImpactResult(unknown_symbols=[symbol for symbol in changes if symbol not in graph])
    registrations = sorted(
        (route for route in routes if route.handler_id in graph),
        key=lambda route: (route.app_id, route.path, route.method, route.handler_id),
    )

    for changed in changes:
        if changed not in graph:
            continue
        parents: dict[str, str | None] = {changed: None}
        pending = deque([changed])
        while pending:
            callee = pending.popleft()
            for caller in sorted(graph.predecessors(callee)):
                if caller not in parents:
                    parents[caller] = callee
                    pending.append(caller)

        for route in registrations:
            if route.handler_id not in parents:
                continue
            symbols = [route.handler_id]
            edges = []
            while (callee := parents[symbols[-1]]) is not None:
                caller = symbols[-1]
                edges.append(CallSiteEvidence(
                    caller=caller,
                    callee=callee,
                    file_path=graph.nodes[caller]["file_path"],
                    lines=sorted(set(graph.edges[caller, callee]["lines"])),
                ))
                symbols.append(callee)
            result.impacts.append(ImpactPath(
                changed_symbol=changed, route=route, symbols=symbols, edges=edges,
            ))
    return result
