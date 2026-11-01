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


def syntax(source: str | bytes):
    from app.analysis.routes import extract_route_syntax

    return extract_route_syntax(source, "routes.py", "sample.routes")


@pytest.mark.parametrize(
    "method", ["get", "post", "put", "patch", "delete", "options", "head", "trace"]
)
def test_methods_and_exact_locations(method):
    result = syntax(
        f'router = APIRouter(prefix="/v")\n@router.{method}("/x")\n'
        '@router.post(path="/y")\nasync def handler():\n    pass\n'
    )
    assert [
        (d.method, d.path, d.line, d.handler_line, d.handler_end_line) for d in result.declarations
    ] == [(method.upper(), "/x", 2, 4, 5), ("POST", "/y", 3, 4, 5)]
    assert result.declarations[0].handler_id == "sample.routes:handler"
    assert result.receivers[0].prefix == "/v"


def test_constructors_includes_and_import_scope():
    result = syntax(
        "from fastapi import FastAPI as F, APIRouter\n"
        "if False: from fastapi import FastAPI\n"
        "def factory():\n    from fastapi import APIRouter as R\n"
        'app = F()\nrouter = APIRouter()\napp.include_router(router, prefix="/v")\n'
    )
    assert [(r.name, r.constructor, r.prefix, r.line) for r in result.receivers] == [
        ("app", "F", "", 5),
        ("router", "APIRouter", "", 6),
    ]
    assert [(r.receiver, r.child, r.prefix, r.line) for r in result.includes] == [
        ("app", "router", "/v", 7)
    ]
    assert len(result.eligible_imports) == 1
    assert result.eligible_imports[0].names == [("FastAPI", "F"), ("APIRouter", None)]
    assert result.binding_counts["FastAPI"] == 1
    assert "R" not in result.binding_counts


def test_same_line_imports_keep_structural_eligibility():
    result = syntax(
        "import fastapi as f;\ndef factory(): import fastapi as f\nif False: import fastapi as g\n"
    )
    assert [(i.names, i.line) for i in result.eligible_imports] == [([("fastapi", "f")], 1)]
    assert result.binding_counts == {"f": 1, "factory": 1, "g": 1}


def test_module_binding_counts_cover_control_flow_and_targets():
    result = syntax(
        "from fastapi import FastAPI\nFastAPI = fake\napp = FastAPI()\n"
        "app = other\nif flag:\n    app = other\napp += other\n"
        "for a, b in xs: pass\nwith f() as c: pass\n"
        "try: pass\nexcept Error as d: pass\nclass C: app = 1\n"
        "def f(): app = 1\n"
    )
    assert result.binding_counts == {
        "FastAPI": 2,
        "app": 4,
        "a": 1,
        "b": 1,
        "c": 1,
        "d": 1,
        "C": 1,
        "f": 1,
    }


@pytest.mark.parametrize("expression", ['f"/x"', 'b"/x"', '"/x" + suffix', '"/x" "/y"', "PATH"])
def test_dynamic_paths_are_diagnosed(expression):
    result = syntax(f"@router.get({expression})\ndef handler(): pass\n")
    assert not result.declarations
    assert result.diagnostics[0].line == 1
    assert result.diagnostics[0].file_path == "routes.py"
    assert expression in result.diagnostics[0].expression


@pytest.mark.parametrize("arguments", ["**options", "*args"])
@pytest.mark.parametrize("construct", ["constructor", "decorator", "include"])
def test_unpacking_invalidates_entire_record(arguments, construct):
    source = {
        "constructor": f"router = APIRouter({arguments})\n",
        "decorator": f'@router.get("/x", {arguments})\ndef handler(): pass\n',
        "include": f"app.include_router(router, {arguments})\n",
    }[construct]
    result = syntax(source + "safe = FastAPI()\n")
    assert [r.name for r in result.receivers] == ["safe"]
    assert not result.declarations and not result.includes
    assert result.diagnostics[0].reason == "argument_unpacking_unsupported"
    assert result.diagnostics[0].line == 1


def test_dynamic_prefix_retained_as_unknown():
    result = syntax('router = APIRouter(prefix=PREFIX)\napp.include_router(router, prefix=f"/x")\n')
    assert result.receivers[0].prefix is None
    assert result.includes[0].prefix is None
    assert [d.line for d in result.diagnostics] == [1, 2]


def test_unsupported_scopes_and_forms_have_evidence():
    result = syntax(
        "if flag:\n    router = APIRouter()\n"
        "obj.router = APIRouter()\nrouter = make_router()\n"
        'def factory():\n    @router.get("/x")\n    def nested(): pass\n'
        '@router.api_route("/x")\ndef generic(): pass\n'
        '@router.websocket("/ws")\ndef socket(): pass\n'
    )
    assert not result.declarations
    assert not any(r.name == "router" and r.constructor == "APIRouter" for r in result.receivers)
    assert {2, 3, 6, 8, 10} <= {d.line for d in result.diagnostics}
    assert all(d.expression and d.reason and d.file_path == "routes.py" for d in result.diagnostics)


def test_empty_and_decode_error_and_syntax_error_are_safe():
    assert syntax("").declarations == []
    assert syntax(b"\xff").diagnostics
    assert syntax('@router.get("/x")\ndef broken(\n').declarations == []


def test_unsupported_bare_route_decorator_is_diagnosed():
    result = syntax("@router.get\ndef handler(): pass\n")
    assert not result.declarations
    assert result.diagnostics[0].reason == "route_arguments_unsupported"


def test_sample_fixture_is_read_as_data_only():
    from pathlib import Path

    from app.analysis.routes import extract_route_syntax

    root = Path(__file__).resolve().parents[2] / "fixtures" / "sample_fastapi_repo"
    users = extract_route_syntax(
        (root / "routes/users.py").read_bytes(), "routes/users.py", "routes.users"
    )
    main = extract_route_syntax((root / "main.py").read_bytes(), "main.py", "main")
    assert [(d.handler_id, d.method, d.path) for d in users.declarations] == [
        ("routes.users:get_user", "GET", "/users/me"),
        ("routes.users:update_user", "PUT", "/users/{user_id}"),
    ]
    assert main.file_path == "main.py"
    assert main.receivers[0].constructor == "FastAPI"
    assert main.includes[0].child == "router"
