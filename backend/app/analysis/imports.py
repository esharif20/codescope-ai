"""Tree-sitter based raw import extractor for Python source files (CS-021, import half).

This module is a second, independent traversal over the same Tree-sitter parse
tree that ``python_symbols.py`` walks for definitions -- it follows the
``_collect_syntax_issues``-as-second-pass convention rather than touching
``_walk_symbols``. It performs extraction only: no resolution, no filesystem
lookups, no concept of "the repo" at all. ``backend/app/analysis/module_paths.py``
and Plan 05's import resolver consume this module's output.

This module is intentionally free of any web-framework dependency (see
``AGENTS.md``: parsing stays independent of FastAPI), matching the convention
set by ``python_symbols.py``.
"""

from __future__ import annotations

import tree_sitter_python
from pydantic import BaseModel
from tree_sitter import Language, Node, Parser

# Built once at import time -- `Language` objects are safe to share. A fresh
# `Parser` is created on every call to `extract_raw_imports` instead of
# reusing a module-level instance, matching `python_symbols.py`'s
# concurrency-safety convention (Parser instances are not documented as
# thread-safe).
_LANGUAGE = Language(tree_sitter_python.language())


class RawImport(BaseModel):
    kind: str  # "import" or "from_import"
    module: str  # dotted module text as written, e.g. "os.path"; "" for `from . import x`
    relative_level: int  # 0 for absolute imports; 1 for ".", 2 for "..", etc.
    names: list[tuple[str, str | None]]  # (name, alias_or_None); [("*", None)] for a star import
    is_star: bool
    line: int
    file_path: str


def extract_raw_imports(source: str | bytes, file_path: str) -> list[RawImport]:
    """Extract every import statement in `source` as a raw, unresolved record.

    ``file_path`` is used verbatim (never resolved or normalized), matching
    ``extract_symbols``'s convention in ``python_symbols.py``.
    """
    if isinstance(source, str):
        data = source.encode("utf-8")
    else:
        data = source

    if not data.strip():
        return []

    parser = Parser(_LANGUAGE)
    tree = parser.parse(data)
    root = tree.root_node

    return _walk_imports(root, file_path)


def _walk_imports(root: Node, file_path: str) -> list[RawImport]:
    """Iteratively walk the parse tree (explicit stack, no recursion) and
    emit a RawImport for every `import_statement` node, in source order.

    `import_from_statement` is intentionally not handled here (Task 2).
    """
    raw_imports: list[RawImport] = []
    stack: list[Node] = [root]

    while stack:
        node = stack.pop()

        if node.type == "import_statement":
            raw_imports.extend(_handle_import_statement(node, file_path))
            continue

        for child in reversed(node.children):
            stack.append(child)

    return raw_imports


def _handle_import_statement(node: Node, file_path: str) -> list[RawImport]:
    """`import os` / `import os, sys` / `import os.path as p` -- one RawImport
    per comma-separated name under the `name` field.
    """
    line = node.start_point.row + 1
    raw_imports: list[RawImport] = []

    for name_node in node.children_by_field_name("name"):
        module, names = _module_and_names(name_node)
        raw_imports.append(
            RawImport(
                kind="import",
                module=module,
                relative_level=0,
                names=names,
                is_star=False,
                line=line,
                file_path=file_path,
            )
        )

    return raw_imports


def _module_and_names(name_node: Node) -> tuple[str, list[tuple[str, str | None]]]:
    """Resolve a single child of an import `name` field (`dotted_name` or
    `aliased_import`) into its (module_text, [(name, alias_or_None)]) shape.
    """
    if name_node.type == "aliased_import":
        dotted = name_node.child_by_field_name("name")
        alias = name_node.child_by_field_name("alias")
        module = _node_text(dotted)
        alias_text = _node_text(alias) if alias is not None else None
        return module, [(module, alias_text)]

    # Plain dotted_name.
    module = _node_text(name_node)
    return module, [(module, None)]


def _node_text(node: Node | None) -> str:
    if node is None or node.text is None:
        return ""
    return node.text.decode("utf-8")
