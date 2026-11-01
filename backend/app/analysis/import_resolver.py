"""Two-pass, evidence-preserving resolution of Python import bindings.

Pass 1 resolves direct, relative, and external imports. Pass 2 (added below)
will resolve one-hop package re-exports and expand in-repository star imports.
"""

from __future__ import annotations

from app.analysis.imports import RawImport
from app.analysis.models import ImportBinding, ResolutionStatus, Symbol


def resolve_file_imports(
    raw_imports: list[RawImport],
    importing_module: str,
    is_init_file: bool,
    symbol_table: dict[str, list[Symbol]],
) -> list[ImportBinding]:
    """Resolve one file's direct, relative, and external import bindings.

    The passed ``symbol_table`` is the complete authority for whether a module
    is in-repository. A target absent from it is known external; a present
    target with a missing requested symbol remains explicitly unresolved for
    the second pass to consider as a package re-export.
    """
    bindings: list[ImportBinding] = []

    for raw_import in raw_imports:
        target_module = _target_module(raw_import, importing_module, is_init_file)

        if raw_import.is_star:
            bindings.append(
                ImportBinding(
                    imported_name="*",
                    source_module=target_module,
                    source_name=None,
                    status=ResolutionStatus.UNRESOLVED,
                    file_path=raw_import.file_path,
                    line=raw_import.line,
                )
            )
            continue

        for name, alias in raw_import.names:
            imported_name = alias or name
            if target_module not in symbol_table:
                status = ResolutionStatus.RESOLVED_EXTERNAL
                source_name = name if raw_import.kind == "from_import" else None
            elif raw_import.kind == "import":
                status = ResolutionStatus.RESOLVED
                source_name = None
            elif _is_top_level_symbol(name, symbol_table[target_module]):
                status = ResolutionStatus.RESOLVED
                source_name = name
            else:
                status = ResolutionStatus.UNRESOLVED
                source_name = name

            bindings.append(
                ImportBinding(
                    imported_name=imported_name,
                    source_module=target_module,
                    source_name=source_name,
                    status=status,
                    file_path=raw_import.file_path,
                    line=raw_import.line,
                )
            )

    return bindings


def _target_module(
    raw_import: RawImport,
    importing_module: str,
    is_init_file: bool,
) -> str:
    if raw_import.relative_level == 0:
        return raw_import.module

    package = importing_module
    if not is_init_file:
        package = _parent_module(package)

    for _ in range(raw_import.relative_level - 1):
        package = _parent_module(package)

    if raw_import.module:
        return f"{package}.{raw_import.module}" if package else raw_import.module
    return package


def _parent_module(module_path: str) -> str:
    return module_path.rsplit(".", 1)[0] if "." in module_path else ""


def _is_top_level_symbol(name: str, symbols: list[Symbol]) -> bool:
    return any(symbol.name == name and symbol.parent_qualified_name is None for symbol in symbols)
