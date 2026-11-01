"""Hand-labelled positive and negative route impacts; fixture code is never run."""

from pathlib import Path

import pytest

from app.analysis import ProjectImpactAnalysis, analyze_route_impacts

FIXTURE_ROOT = str(Path(__file__).resolve().parents[2] / "fixtures" / "sample_fastapi_repo")


@pytest.fixture(scope="module")
def analysis() -> ProjectImpactAnalysis:
    return analyze_route_impacts(FIXTURE_ROOT, [
        "services.auth:get_current_user",
        "services.base:BaseService.audit",
        "callers:call_twice",
        "routes.users:get_user",
        "missing:symbol",
    ])


def test_exact_registered_inventory(analysis: ProjectImpactAnalysis) -> None:
    assert [
        (r.app_id, r.method, r.path, r.handler_id) for r in analysis.routes.registrations
    ] == [
        ("main:app", "GET", "/users/me", "routes.users:get_user"),
        ("main:app", "PUT", "/users/{user_id}", "routes.users:update_user"),
    ]


def test_auth_helper_reaches_exact_two_routes(analysis: ProjectImpactAnalysis) -> None:
    paths = [p for p in analysis.impact.impacts
             if p.changed_symbol == "services.auth:get_current_user"]
    assert [(p.route.method, p.route.path, p.symbols) for p in paths] == [
        ("GET", "/users/me", ["routes.users:get_user", "services.auth:get_current_user"]),
        ("PUT", "/users/{user_id}", ["routes.users:update_user", "services.auth:get_current_user"]),
    ]
    assert [p.edges[0].lines for p in paths] == [[13], [21]]
    for path in paths:
        assert path.edges[0].file_path == str(Path(FIXTURE_ROOT) / "routes" / "users.py")
        assert path.edges[0].caller == path.symbols[0]
        assert path.edges[0].callee == path.symbols[1]
        assert path.route.declaration.line in {11, 19}
        assert [(Path(f.file_path).relative_to(FIXTURE_ROOT).as_posix(), f.line, f.reason)
                for f in path.route.registration_evidence] == [
            ("main.py", 7, "constructor_verified"),
            ("main.py", 8, "include_verified"),
            ("routes/users.py", 8, "constructor_verified"),
        ]


@pytest.mark.parametrize("changed", ["services.base:BaseService.audit", "callers:call_twice"])
def test_unrelated_or_unsupported_only_change_has_no_routes(analysis, changed) -> None:
    assert [p for p in analysis.impact.impacts if p.changed_symbol == changed] == []
    assert changed not in analysis.impact.unknown_symbols


def test_handler_change_reaches_own_route(analysis: ProjectImpactAnalysis) -> None:
    [path] = [p for p in analysis.impact.impacts if p.changed_symbol == "routes.users:get_user"]
    assert path.symbols == ["routes.users:get_user"]
    assert path.edges == []
    assert path.route.path == "/users/me"


def test_unknown_symbols_are_separate(analysis: ProjectImpactAnalysis) -> None:
    assert analysis.impact.unknown_symbols == ["missing:symbol"]


def test_original_graph_inventory_and_uncertainty_remain(analysis: ProjectImpactAnalysis) -> None:
    graph = analysis.project_graph.call_graph
    assert graph.graph.number_of_edges() == 10
    unresolved = [entry for entries in graph.unresolved.values() for entry in entries]
    assert len(unresolved) == 7
    assert any(entry.expression == "auth.login" and entry.line == 15 for entry in unresolved)
    assert graph.graph.has_edge(
        "services.auth:AuthService.login", "services.base:BaseService.audit"
    )
    assert len(analysis.routes.file_statuses) == 10
    # Conservative syntax diagnostics include unverified call-result assignments.
    assert analysis.partial
    assert {d.reason for d in analysis.routes.diagnostics} == {
        "receiver_scope_or_assignment_unsupported", "receiver_unproven_or_shadowed"
    }
    assert not analysis.routes.truncated
    assert not analysis.impact.truncated
