"""End-to-end, hand-written call-graph expectations for the sample fixture."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.analysis import build_project_graph, callers_of
from app.analysis.project_graph import ProjectGraph

FIXTURE_ROOT = str(Path(__file__).resolve().parents[2] / "fixtures" / "sample_fastapi_repo")

EXPECTED_RESOLVED_EDGES: set[tuple[str, str, tuple[int, ...]]] = {
    ("services.auth:AuthService.login", "services.base:BaseService.audit", (8,)),
    ("services.auth:AuthService.login", "services.auth:AuthService.check_password", (9,)),
    ("routes.users:get_user", "services.auth:get_current_user", (13,)),
    ("routes.users:get_user", "services.auth:AuthService", (14,)),
    ("routes.users:update_user", "services.auth:get_current_user", (21,)),
    ("routes.users:update_user", "callers:dispatch", (22,)),
    ("callers:call_get_user_directly", "routes.users:get_user", (10,)),
    ("callers:warm_cache", "services.auth:get_current_user", (14,)),
    ("callers:call_twice", "services.auth:get_current_user", (18, 19)),
    ("tests.test_services:test_login_succeeds", "services.auth:AuthService", (7,)),
}


@pytest.fixture(scope="module")
def project_graph() -> ProjectGraph:
    """Build once because the read-only fixture is constant across this module."""
    return build_project_graph(FIXTURE_ROOT)


def test_fixture_contains_each_predicted_resolved_edge(project_graph: ProjectGraph) -> None:
    graph = project_graph.call_graph.graph

    for caller, callee, lines in EXPECTED_RESOLVED_EDGES:
        assert graph.has_edge(caller, callee), f"missing edge: {caller} -> {callee}"
        assert sorted(graph.edges[caller, callee]["lines"]) == sorted(lines)


def test_fixture_has_no_unpredicted_resolved_edges(project_graph: ProjectGraph) -> None:
    actual_count = project_graph.call_graph.graph.number_of_edges()

    assert actual_count == len(EXPECTED_RESOLVED_EDGES), (
        f"expected {len(EXPECTED_RESOLVED_EDGES)} resolved edges, got {actual_count}"
    )


def test_fixture_resolves_inherited_method_through_public_query(
    project_graph: ProjectGraph,
) -> None:
    assert callers_of(project_graph.call_graph, "services.base:BaseService.audit") == [
        "services.auth:AuthService.login"
    ]
