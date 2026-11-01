"""Source-only route extraction and evidence contracts."""

import pytest
from pydantic import ValidationError

from app.analysis.route_models import (
    CallSiteEvidence,
    ImpactPath,
    ImpactResult,
    RouteDeclaration,
    RouteDiagnostic,
    RouteInventory,
    RouteRegistration,
)


def test_models_round_trip() -> None:
    declaration = RouteDeclaration(
        receiver_id="routes:router",
        handler_id="routes:handler",
        method="GET",
        path="/x",
        file_path="routes.py",
        line=3,
        handler_line=4,
        handler_end_line=6,
    )
    route = RouteRegistration(
        app_id="main:app",
        handler_id="routes:handler",
        method="GET",
        path="/api/x",
        declaration=declaration,
        registration_evidence=[
            RouteDiagnostic(
                file_path="main.py", line=line, expression="include_router", reason="literal prefix"
            )
            for line in [5, 8]
        ],
    )
    impact = ImpactResult(
        impacts=[
            ImpactPath(
                changed_symbol="service:helper",
                route=route,
                symbols=["routes:handler", "service:helper"],
                edges=[
                    CallSiteEvidence(
                        caller="routes:handler",
                        callee="service:helper",
                        file_path="routes.py",
                        lines=[5, 6],
                    )
                ],
            )
        ]
    )
    assert ImpactResult.model_validate_json(impact.model_dump_json()) == impact
    assert impact.impacts[0].route.registration_evidence[1].line == 8


def test_models_defaults_are_independent() -> None:
    first, second = RouteInventory(), RouteInventory()
    first.file_statuses["x"] = "ok"
    first.diagnostics.append(RouteDiagnostic(file_path="x", line=1, expression="x", reason="x"))
    assert second.file_statuses == {}
    assert second.diagnostics == []
    result = ImpactResult()
    result.unknown_symbols.append("x")
    assert ImpactResult().unknown_symbols == []


def test_models_reject_zero_lines() -> None:
    with pytest.raises(ValidationError):
        RouteDiagnostic(file_path="x", line=0, expression="x", reason="x")
    with pytest.raises(ValidationError):
        CallSiteEvidence(caller="a", callee="b", file_path="x", lines=[0])
