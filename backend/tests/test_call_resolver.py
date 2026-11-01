"""Tests for Phase 2's deterministic call and hierarchy resolver (CS-022)."""

from __future__ import annotations

from app.analysis.call_resolver import build_class_hierarchy
from app.analysis.calls import RawClassBases
from app.analysis.models import ImportBinding, ResolutionStatus


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
