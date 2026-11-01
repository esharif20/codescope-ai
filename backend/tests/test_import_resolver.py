"""Tests for Phase 2's deterministic two-pass import resolver (CS-022)."""

from __future__ import annotations

from app.analysis.import_resolver import resolve_file_imports
from app.analysis.imports import RawImport
from app.analysis.models import ResolutionStatus, Symbol, SymbolKind


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
