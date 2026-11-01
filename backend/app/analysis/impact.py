"""Canonical shortest supported paths from registered handlers to changed symbols.

These static paths describe potential impact, not runtime execution or every
possible call path. Unresolved calls never participate in the traversal.
"""

from collections import deque

from app.analysis.call_graph import CallGraph
from app.analysis.route_models import CallSiteEvidence, ImpactPath, ImpactResult, RouteRegistration

_MAX_VISITED_NODES = 10000
_MAX_IMPACT_PATHS = 1000


def find_affected_routes(
    call_graph: CallGraph,
    routes: list[RouteRegistration],
    changed_symbols: list[str],
) -> ImpactResult:
    """Find one deterministic shortest evidence path per registration/change pair.

    Each first discovery counts against an invocation-wide node budget, including
    roots and nodes reached again for another change. A limit marks truncation
    only when it omits work or a complete result; previously found chains remain.
    """
    graph = call_graph.graph
    changes = sorted(set(changed_symbols))
    result = ImpactResult(unknown_symbols=[symbol for symbol in changes if symbol not in graph])
    registrations = sorted(
        (route for route in routes if route.handler_id in graph),
        key=lambda route: (route.app_id, route.path, route.method, route.handler_id),
    )

    visited_count = 0
    for changed in changes:
        if changed not in graph:
            continue
        if visited_count >= _MAX_VISITED_NODES:
            result.truncated = True
            break
        parents: dict[str, str | None] = {changed: None}
        visited_count += 1
        pending = deque([changed])
        while pending:
            callee = pending.popleft()
            for caller in sorted(graph.predecessors(callee)):
                if caller not in parents:
                    if visited_count >= _MAX_VISITED_NODES:
                        result.truncated = True
                        break
                    parents[caller] = callee
                    visited_count += 1
                    pending.append(caller)

        for route in registrations:
            if route.handler_id not in parents:
                continue
            if len(result.impacts) >= _MAX_IMPACT_PATHS:
                result.truncated = True
                return result
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
