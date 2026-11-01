"""Whole-project, deterministic static-analysis orchestration (D-18/D-19)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.analysis.call_graph import CallGraph
from app.analysis.import_resolver import (
    extract_dunder_all,
    resolve_file_imports,
    resolve_reexports_and_stars,
)
from app.analysis.imports import extract_raw_imports
from app.analysis.models import ImportBinding, ParseStatus, Symbol
from app.analysis.module_paths import module_path_for
from app.analysis.python_symbols import extract_symbols_from_file

_MAX_FILES = 500
_MAX_UNRESOLVED_ENTRIES = 1000


@dataclass
class ProjectGraph:
    """The bounded result of analysing one directory tree."""

    call_graph: CallGraph
    file_statuses: dict[str, str] = field(default_factory=dict)
    import_bindings: dict[str, list[ImportBinding]] = field(default_factory=dict)
    unresolved_truncated: bool = False


def _build_symbols_and_bindings(
    root: str,
) -> tuple[
    dict[str, list[Symbol]],
    dict[str, list[ImportBinding]],
    dict[str, str],
    dict[str, bytes],
]:
    """Collect symbols and resolve imports project-wide before call resolution."""
    paths = sorted(Path(root).rglob("*.py"))
    processed_paths = paths[:_MAX_FILES]
    file_statuses = {str(path): "skipped_file_cap" for path in paths[_MAX_FILES:]}
    symbols_by_module: dict[str, list[Symbol]] = {}
    raw_imports_by_module = {}
    dunder_all_by_module = {}
    init_modules: dict[str, bool] = {}
    sources_by_module: dict[str, bytes] = {}

    for path in processed_paths:
        path_string = str(path)
        try:
            result = extract_symbols_from_file(path)
        except OSError:
            file_statuses[path_string] = "unreadable"
            continue

        file_statuses[path_string] = result.status.value
        if result.status == ParseStatus.DECODE_ERROR:
            continue

        try:
            source = path.read_bytes()
        except OSError:
            file_statuses[path_string] = "unreadable"
            continue

        module_path = module_path_for(path_string, root)
        symbols_by_module[module_path] = [
            symbol.model_copy(update={"module_path": module_path}) for symbol in result.symbols
        ]
        raw_imports_by_module[module_path] = extract_raw_imports(source, path_string)
        dunder_all_by_module[module_path] = extract_dunder_all(source, path_string)
        init_modules[module_path] = path.name == "__init__.py"
        sources_by_module[module_path] = source

    bindings_by_module = {
        module_path: resolve_file_imports(
            raw_imports_by_module[module_path],
            module_path,
            init_modules[module_path],
            symbols_by_module,
        )
        for module_path in sorted(symbols_by_module)
    }
    bindings_by_module = resolve_reexports_and_stars(
        bindings_by_module, symbols_by_module, dunder_all_by_module
    )
    return symbols_by_module, bindings_by_module, file_statuses, sources_by_module
