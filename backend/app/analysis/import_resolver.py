"""Two-pass, evidence-preserving resolution of Python import bindings.

Pass 1 resolves direct, relative, and external imports. Pass 2 (added below)
will resolve one-hop package re-exports and expand in-repository star imports.
"""

from __future__ import annotations

import tree_sitter_python
from tree_sitter import Language, Parser

from app.analysis.imports import RawImport
from app.analysis.models import ImportBinding, ResolutionStatus, Symbol

_LANGUAGE = Language(tree_sitter_python.language())


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


def resolve_reexports_and_stars(
    bindings_by_module: dict[str, list[ImportBinding]],
    symbol_table: dict[str, list[Symbol]],
    dunder_all_by_module: dict[str, list[str] | None],
) -> dict[str, list[ImportBinding]]:
    """Resolve one-hop re-exports and in-repository star imports (pass 2)."""
    resolved: dict[str, list[ImportBinding]] = {}

    for module_path, bindings in bindings_by_module.items():
        updated: list[ImportBinding] = []
        for binding in bindings:
            if _is_expandable_star(binding, symbol_table):
                names = dunder_all_by_module.get(binding.source_module)
                if names is None:
                    names = [
                        symbol.name
                        for symbol in symbol_table[binding.source_module]
                        if symbol.parent_qualified_name is None
                    ]
                updated.extend(
                    binding.model_copy(
                        update={
                            "imported_name": name,
                            "source_name": name,
                            "status": ResolutionStatus.RESOLVED,
                        }
                    )
                    for name in names
                )
                continue

            updated.append(_resolve_reexport_once(binding, bindings_by_module))
        resolved[module_path] = updated

    return resolved


def _is_expandable_star(
    binding: ImportBinding,
    symbol_table: dict[str, list[Symbol]],
) -> bool:
    return (
        binding.imported_name == "*"
        and binding.status == ResolutionStatus.UNRESOLVED
        and binding.source_module in symbol_table
    )


def _resolve_reexport_once(
    binding: ImportBinding,
    bindings_by_module: dict[str, list[ImportBinding]],
) -> ImportBinding:
    if (
        binding.status != ResolutionStatus.UNRESOLVED
        or binding.imported_name == "*"
        or binding.source_module not in bindings_by_module
    ):
        return binding.model_copy()

    for hop in bindings_by_module[binding.source_module]:
        if (
            hop.imported_name == binding.source_name
            and hop.status
            in {ResolutionStatus.RESOLVED, ResolutionStatus.RESOLVED_EXTERNAL}
        ):
            return binding.model_copy(
                update={
                    "status": hop.status,
                    "source_module": hop.source_module,
                    "source_name": hop.source_name,
                }
            )

    return binding.model_copy()


def extract_dunder_all(source: str | bytes, file_path: str) -> list[str] | None:
    """Extract exactly one literal module-level ``__all__`` assignment, if present."""
    data = source.encode("utf-8") if isinstance(source, str) else source
    root = Parser(_LANGUAGE).parse(data).root_node
    assignments = []

    for statement in root.named_children:
        if statement.type != "expression_statement":
            continue
        assignment = next(
            (child for child in statement.named_children if child.type == "assignment"),
            None,
        )
        if assignment is None:
            continue
        left = assignment.child_by_field_name("left")
        if left is not None and left.text == b"__all__":
            assignments.append(assignment)

    if len(assignments) != 1:
        return None

    right = assignments[0].child_by_field_name("right")
    if right is None or right.type != "list":
        return None

    values: list[str] = []
    for child in right.named_children:
        if child.type != "string" or child.text is None:
            return None
        text = child.text.decode("utf-8")
        if len(text) < 2 or text[0] not in "'\"" or text[-1] != text[0]:
            return None
        values.append(text[1:-1])
    return values
