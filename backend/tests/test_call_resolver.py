"""Tests for Phase 2's deterministic call and hierarchy resolver (CS-022)."""

from __future__ import annotations

from app.analysis.call_resolver import build_class_hierarchy, resolve_file_calls
from app.analysis.calls import RawCall, RawClassBases
from app.analysis.models import ImportBinding, ResolutionStatus, Symbol, SymbolKind


def _bases(qualified_name: str, bases: list[str]) -> RawClassBases:
    return RawClassBases(
        qualified_name=qualified_name,
        bases=bases,
        file_path="services/auth.py",
    )


def _binding(imported_name: str, status: ResolutionStatus) -> ImportBinding:
    return ImportBinding(
        imported_name=imported_name,
        source_module="services.base",
        source_name=imported_name,
        status=status,
        file_path="services/auth.py",
        line=1,
    )


def _symbol(
    qualified_name: str,
    module_path: str,
    parent_qualified_name: str | None = None,
) -> Symbol:
    return Symbol(
        name=qualified_name.rsplit(".", 1)[-1],
        qualified_name=qualified_name,
        kind=SymbolKind.METHOD if parent_qualified_name else SymbolKind.FUNCTION,
        file_path=f"{module_path.replace('.', '/')}.py",
        module_path=module_path,
        start_line=1,
        end_line=1,
        parent_qualified_name=parent_qualified_name,
    )


def _call(receiver_kind: str, expression: str, enclosing_symbol: str = "caller") -> RawCall:
    return RawCall(
        enclosing_symbol=enclosing_symbol,
        receiver_kind=receiver_kind,
        expression=expression,
        line=7,
        file_path="services/auth.py",
    )


def _resolved_binding(
    imported_name: str,
    source_module: str,
    source_name: str | None,
) -> ImportBinding:
    return ImportBinding(
        imported_name=imported_name,
        source_module=source_module,
        source_name=source_name,
        status=ResolutionStatus.RESOLVED,
        file_path="services/auth.py",
        line=1,
    )


def test_hierarchy_resolves_same_module_base_without_import() -> None:
    result = build_class_hierarchy(
        {
            "services.auth": [
                _bases("BaseService", []),
                _bases("AuthService", ["BaseService"]),
            ]
        },
        {"services.auth": []},
    )

    assert result == {"services.auth:AuthService": ["services.auth:BaseService"]}


def test_hierarchy_resolves_cross_module_base_from_binding() -> None:
    result = build_class_hierarchy(
        {"services.auth": [_bases("AuthService", ["BaseService"])]},
        {"services.auth": [_binding("BaseService", ResolutionStatus.RESOLVED)]},
    )

    assert result == {"services.auth:AuthService": ["services.base:BaseService"]}


def test_hierarchy_omits_external_or_unresolved_bases() -> None:
    result = build_class_hierarchy(
        {"services.auth": [_bases("AuthService", ["SomeExternalMixin"])]},
        {"services.auth": [_binding("SomeExternalMixin", ResolutionStatus.UNRESOLVED)]},
    )

    assert result == {}


def test_hierarchy_omits_class_without_bases() -> None:
    result = build_class_hierarchy(
        {"services.auth": [_bases("AuthService", [])]},
        {"services.auth": []},
    )

    assert result == {}


def test_resolves_self_call_to_own_class_method() -> None:
    resolved, unresolved = resolve_file_calls(
        [_call("self", "self.check_password", "AuthService.login")],
        "services.auth",
        [],
        {
            "services.auth": [
                _symbol("AuthService.login", "services.auth", "AuthService"),
                _symbol("AuthService.check_password", "services.auth", "AuthService"),
            ]
        },
        {},
    )

    assert [(call.caller, call.callee) for call in resolved] == [
        ("services.auth:AuthService.login", "services.auth:AuthService.check_password")
    ]
    assert unresolved == []


def test_resolves_self_call_to_inherited_base_method() -> None:
    resolved, unresolved = resolve_file_calls(
        [_call("self", "self.audit", "AuthService.login")],
        "services.auth",
        [],
        {
            "services.auth": [_symbol("AuthService.login", "services.auth", "AuthService")],
            "services.base": [_symbol("BaseService.audit", "services.base", "BaseService")],
        },
        {"services.auth:AuthService": ["services.base:BaseService"]},
    )

    assert [call.callee for call in resolved] == ["services.base:BaseService.audit"]
    assert unresolved == []


def test_self_call_without_matching_method_is_unresolved() -> None:
    resolved, unresolved = resolve_file_calls(
        [_call("self", "self.missing", "AuthService.login")],
        "services.auth",
        [],
        {"services.auth": [_symbol("AuthService.login", "services.auth", "AuthService")]},
        {},
    )

    assert resolved == []
    assert unresolved[0].status == ResolutionStatus.UNRESOLVED
    assert unresolved[0].expression == "self.missing"


def test_resolves_bare_call_to_same_module_function() -> None:
    resolved, unresolved = resolve_file_calls(
        [_call("bare", "helper")],
        "services.auth",
        [],
        {"services.auth": [_symbol("helper", "services.auth")]},
        {},
    )

    assert [call.callee for call in resolved] == ["services.auth:helper"]
    assert unresolved == []


def test_resolves_bare_imported_class_construction_to_class() -> None:
    resolved, unresolved = resolve_file_calls(
        [_call("bare", "AuthService")],
        "routes.users",
        [_resolved_binding("AuthService", "services.auth", "AuthService")],
        {"services.auth": [_symbol("AuthService", "services.auth")]},
        {},
    )

    assert [call.callee for call in resolved] == ["services.auth:AuthService"]
    assert unresolved == []


def test_bare_call_without_candidate_is_unresolved() -> None:
    resolved, unresolved = resolve_file_calls(
        [_call("bare", "print")], "services.auth", [], {}, {}
    )

    assert resolved == []
    assert unresolved[0].status == ResolutionStatus.UNRESOLVED
    assert unresolved[0].candidates == []


def test_bare_call_with_two_targets_is_one_uncertain_entry() -> None:
    resolved, unresolved = resolve_file_calls(
        [_call("bare", "helper")],
        "routes.users",
        [
            _resolved_binding("helper", "services.one", "helper"),
            _resolved_binding("helper", "services.two", "helper"),
        ],
        {
            "services.one": [_symbol("helper", "services.one")],
            "services.two": [_symbol("helper", "services.two")],
        },
        {},
    )

    assert resolved == []
    assert len(unresolved) == 1
    assert unresolved[0].status == ResolutionStatus.UNCERTAIN
    assert len(unresolved[0].candidates) == 2
    assert unresolved[0].candidates == ["services.one:helper", "services.two:helper"]


def test_resolves_attribute_call_through_whole_module_alias() -> None:
    resolved, unresolved = resolve_file_calls(
        [_call("attribute", "auth_mod.get_current_user")],
        "routes.users",
        [_resolved_binding("auth_mod", "services.auth", None)],
        {"services.auth": [_symbol("get_current_user", "services.auth")]},
        {},
    )

    assert [call.callee for call in resolved] == ["services.auth:get_current_user"]
    assert unresolved == []


def test_attribute_call_on_constructor_assigned_local_is_unresolved() -> None:
    resolved, unresolved = resolve_file_calls(
        [_call("attribute", "auth.login", "get_user")],
        "routes.users",
        [_resolved_binding("AuthService", "services.auth", "AuthService")],
        {"services.auth": [_symbol("AuthService", "services.auth")]},
        {},
    )

    assert resolved == []
    assert unresolved[0].status == ResolutionStatus.UNRESOLVED
    assert unresolved[0].expression == "auth.login"


def test_attribute_call_on_unannotated_parameter_is_unresolved() -> None:
    resolved, unresolved = resolve_file_calls(
        [_call("attribute", "handler.process_item", "process")],
        "callers",
        [],
        {},
        {},
    )

    assert resolved == []
    assert unresolved[0].status == ResolutionStatus.UNRESOLVED
    assert unresolved[0].expression == "handler.process_item"
