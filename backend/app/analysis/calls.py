"""Raw call-expression extraction for Python source files.

This module performs **no resolution** -- it only extracts, verbatim, the raw
shapes Tree-sitter already exposes:

- ``extract_raw_calls`` -- every call expression found lexically inside a
  function/method/nested-function body, tagged with its receiver shape
  (``bare``, ``self``, ``cls``, or ``attribute``).

Resolving these raw shapes into actual call-graph edges is Plan 05 (imports)
and Plan 06 (call resolution)'s job, not this module's. See
``python_symbols.py`` for the sibling symbol extractor whose scope-stack
convention (``_Frame``, ``_qualified_name``) this module reuses rather than
reimplements.
"""

from __future__ import annotations

from typing import Literal

import tree_sitter_python
from pydantic import BaseModel
from tree_sitter import Language, Node, Parser

from app.analysis.python_symbols import _Frame, _node_name, _qualified_name

# Built once at import time, same rationale as python_symbols.py: `Language`
# is safe to share, `Parser` is not documented as thread-safe so a fresh
# instance is created per call.
_LANGUAGE = Language(tree_sitter_python.language())


class RawCall(BaseModel):
    """One call expression found inside a function/method body.

    ``enclosing_symbol`` is the qualified_name of the containing
    function/method -- NOT yet prefixed with ``module_path`` (that happens
    downstream, once a resolver knows the file's module path).
    """

    enclosing_symbol: str
    receiver_kind: Literal["bare", "self", "cls", "attribute"]
    expression: str
    line: int
    file_path: str


def _node_text(node: Node) -> str:
    if node.text is None:
        return ""
    return node.text.decode("utf-8")


def extract_raw_calls(source: str | bytes, file_path: str) -> list[RawCall]:
    """Extract every call expression lexically inside a function/method body.

    Calls at module level, inside a class body but outside any method,
    inside decorator expressions, or inside parameter default-value
    expressions are out of scope and are not extracted (Phase 3 owns
    route-decorator parsing; this phase does not record them as unresolved
    either -- they are simply never visited as call sites).
    """
    data = source.encode("utf-8") if isinstance(source, str) else source
    parser = Parser(_LANGUAGE)
    tree = parser.parse(data)
    root = tree.root_node

    calls: list[RawCall] = []
    # Stack entries mirror _walk_symbols: (node, scope).
    stack: list[tuple[Node, tuple[_Frame, ...]]] = [(root, ())]

    while stack:
        node, scope = stack.pop()

        if node.is_error or node.is_missing:
            continue

        node_type = node.type

        if node_type == "class_definition":
            name = _node_name(node)
            body = node.child_by_field_name("body")
            if body is not None:
                stack.append((body, scope + ((name, True),)))
            continue

        if node_type == "function_definition":
            name = _node_name(node)
            body = node.child_by_field_name("body")
            if body is not None:
                stack.append((body, scope + ((name, False),)))
            continue

        # Only look for `call` nodes while the innermost scope frame is a
        # function (not a class, not module level) -- the explicit scope
        # boundary from <interfaces>.
        in_function_scope = bool(scope) and scope[-1][1] is False

        if in_function_scope and node_type == "call":
            function_field = node.child_by_field_name("function")
            if function_field is not None:
                receiver_kind, expression = _classify_call(function_field)
                if receiver_kind is not None:
                    enclosing_symbol = _qualified_name(scope[:-1], scope[-1][0])
                    calls.append(
                        RawCall(
                            enclosing_symbol=enclosing_symbol,
                            receiver_kind=receiver_kind,
                            expression=expression,
                            line=node.start_point.row + 1,
                            file_path=file_path,
                        )
                    )

        # Keep descending through everything else (if/for/try/with/call
        # arguments/...) so nested structures and nested function
        # definitions are still reached.
        for child in reversed(node.children):
            stack.append((child, scope))

    return calls


def _classify_call(
    function_field: Node,
) -> tuple[Literal["bare", "self", "cls", "attribute"] | None, str]:
    """Classify a `call` node's `function` field into a receiver kind.

    Returns ``(None, "")`` for any callee shape this phase does not record
    (only bare identifiers and attribute expressions are in scope).
    """
    if function_field.type == "identifier":
        return "bare", _node_text(function_field)

    if function_field.type == "attribute":
        object_field = function_field.child_by_field_name("object")
        full_text = _node_text(function_field)
        if object_field is not None:
            object_text = _node_text(object_field)
            if object_text == "self":
                return "self", full_text
            if object_text == "cls":
                return "cls", full_text
        return "attribute", full_text

    return None, ""
