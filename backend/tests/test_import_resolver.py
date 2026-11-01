"""Tests for Phase 2's deterministic two-pass import resolver (CS-022)."""

from __future__ import annotations

from app.analysis.import_resolver import (
    extract_dunder_all,
    resolve_file_imports,
    resolve_reexports_and_stars,
)
from app.analysis.imports import RawImport
from app.analysis.models import ImportBinding, ResolutionStatus, Symbol, SymbolKind


def _symbol(name: str, module_path: str) -> Symbol:
    return Symbol(
        name=name,
        qualified_name=name,
        kind=SymbolKind.CLASS,
        file_path=f"{module_path.replace('.', '/')}.py",
        module_path=module_path,
        start_line=1,
        end_line=1,
    )


def test_resolves_external_plain_import() -> None:
    result = resolve_file_imports(
        [
            RawImport(
                kind="import",
                module="os",
                relative_level=0,
                names=[("os", None)],
                is_star=False,
                line=1,
                file_path="main.py",
            )
        ],
        importing_module="main",
        is_init_file=False,
        symbol_table={},
    )

    assert result[0].imported_name == "os"
    assert result[0].source_module == "os"
    assert result[0].source_name is None
    assert result[0].status == ResolutionStatus.RESOLVED_EXTERNAL


def test_resolves_top_level_symbol_from_in_repo_module() -> None:
    result = resolve_file_imports(
        [
            RawImport(
                kind="from_import",
                module="services.base",
                relative_level=0,
                names=[("BaseService", None)],
                is_star=False,
                line=1,
                file_path="main.py",
            )
        ],
        importing_module="main",
        is_init_file=False,
        symbol_table={"services.base": [_symbol("BaseService", "services.base")]},
    )

    assert result[0].status == ResolutionStatus.RESOLVED
    assert result[0].source_module == "services.base"
    assert result[0].source_name == "BaseService"


def test_resolves_relative_import_from_containing_package() -> None:
    result = resolve_file_imports(
        [
            RawImport(
                kind="from_import",
                module="base",
                relative_level=1,
                names=[("BaseService", None)],
                is_star=False,
                line=1,
                file_path="services/auth.py",
            )
        ],
        importing_module="services.auth",
        is_init_file=False,
        symbol_table={"services.base": [_symbol("BaseService", "services.base")]},
    )

    assert result[0].status == ResolutionStatus.RESOLVED
    assert result[0].source_module == "services.base"


def test_keeps_in_repo_missing_symbol_unresolved_for_reexport_pass() -> None:
    result = resolve_file_imports(
        [
            RawImport(
                kind="from_import",
                module="app.services",
                relative_level=0,
                names=[("auth", None)],
                is_star=False,
                line=1,
                file_path="main.py",
            )
        ],
        importing_module="main",
        is_init_file=False,
        symbol_table={"app.services": []},
    )

    assert result[0].status == ResolutionStatus.UNRESOLVED
    assert result[0].source_module == "app.services"
    assert result[0].source_name == "auth"


def test_keeps_relative_star_import_unresolved_for_expansion_pass() -> None:
    result = resolve_file_imports(
        [
            RawImport(
                kind="from_import",
                module="services",
                relative_level=2,
                names=[("*", None)],
                is_star=True,
                line=1,
                file_path="routes/__init__.py",
            )
        ],
        importing_module="routes",
        is_init_file=True,
        symbol_table={"services": []},
    )

    assert result[0].imported_name == "*"
    assert result[0].status == ResolutionStatus.UNRESOLVED
    assert result[0].source_module == "services"
    assert result[0].source_name is None


def test_extract_dunder_all_from_literal_top_level_list() -> None:
    assert extract_dunder_all(
        '__all__ = ["AuthService", "get_current_user"]\n',
        "services/__init__.py",
    ) == ["AuthService", "get_current_user"]


def test_extract_dunder_all_rejects_computed_or_missing_values() -> None:
    assert extract_dunder_all('__all__ = sorted(["b", "a"])\n', "x.py") is None
    assert extract_dunder_all("x = 1\n", "x.py") is None


def test_resolves_one_hop_package_reexport() -> None:
    bindings = {
        "services": [
            ImportBinding(
                imported_name="auth",
                source_module="app.services",
                source_name="auth",
                status=ResolutionStatus.UNRESOLVED,
                file_path="services.py",
                line=1,
            )
        ],
        "app.services": [
            ImportBinding(
                imported_name="auth",
                source_module="app.services.auth",
                source_name="auth",
                status=ResolutionStatus.RESOLVED,
                file_path="app/services/__init__.py",
                line=1,
            )
        ],
    }

    result = resolve_reexports_and_stars(bindings, {}, {})

    assert result["services"][0].status == ResolutionStatus.RESOLVED
    assert result["services"][0].source_module == "app.services.auth"
    assert result["services"][0].source_name == "auth"
    assert bindings["services"][0].status == ResolutionStatus.UNRESOLVED


def test_expands_in_repo_star_import_using_literal_dunder_all() -> None:
    bindings = {"routes": [_star_binding("services")]}
    symbols = {
        "services": [
            _symbol("AuthService", "services"),
            _symbol("get_current_user", "services"),
        ]
    }

    result = resolve_reexports_and_stars(
        bindings,
        symbols,
        {"services": ["AuthService", "get_current_user"]},
    )

    resolved_bindings = [
        (binding.imported_name, binding.source_name, binding.status)
        for binding in result["routes"]
    ]
    assert resolved_bindings == [
        ("AuthService", "AuthService", ResolutionStatus.RESOLVED),
        ("get_current_user", "get_current_user", ResolutionStatus.RESOLVED),
    ]


def test_expands_in_repo_star_import_to_top_level_symbols_without_dunder_all() -> None:
    bindings = {"routes": [_star_binding("services")]}
    symbols = {
        "services": [
            _symbol("AuthService", "services"),
            _symbol("get_current_user", "services"),
            Symbol(
                name="inner",
                qualified_name="outer.<locals>.inner",
                kind=SymbolKind.NESTED_FUNCTION,
                file_path="services.py",
                module_path="services",
                start_line=2,
                end_line=2,
                parent_qualified_name="outer",
            ),
        ]
    }

    result = resolve_reexports_and_stars(bindings, symbols, {"services": None})

    assert [binding.imported_name for binding in result["routes"]] == [
        "AuthService",
        "get_current_user",
    ]


def test_leaves_external_star_import_unresolved() -> None:
    star = _star_binding("external_package")

    result = resolve_reexports_and_stars({"main": [star]}, {}, {})

    assert result == {"main": [star]}


def _star_binding(source_module: str) -> ImportBinding:
    return ImportBinding(
        imported_name="*",
        source_module=source_module,
        source_name=None,
        status=ResolutionStatus.UNRESOLVED,
        file_path="routes/__init__.py",
        line=1,
    )
