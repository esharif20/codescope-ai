"""Tree-sitter based symbol extractor for Python source files.

This module is intentionally free of any web-framework dependency (see
``AGENTS.md``: parsing stays independent of FastAPI) so it can be reused by
CLI tools, batch jobs, or request handlers alike.

The public surface is two functions:

- ``extract_symbols(source, file_path)`` -- parse already-loaded source text.
- ``extract_symbols_from_file(path)`` -- read a file from disk and parse it.

Both return a ``ParseResult`` (see ``app.analysis.models``).
"""

from __future__ import annotations

import os

import tree_sitter_python
from tree_sitter import Language, Node, Parser

from app.analysis.models import (
    ParseResult,
    ParseStatus,
    Symbol,
    SymbolKind,
    SyntaxIssue,
    SyntaxIssueKind,
)

# Built once at import time. Per tree-sitter's docs, `Language` objects are
# safe to share; `Parser` instances are not documented as thread-safe, so a
# fresh `Parser` is created on every call to `extract_symbols` instead of
# reusing a module-level instance (this will be invoked from concurrent
# request handlers later).
_LANGUAGE = Language(tree_sitter_python.language())

# Cap on how many syntax issues we collect per file. Kept as a module-level
# constant so it is easy to find and tune later.
_MAX_SYNTAX_ISSUES = 50

# A scope frame: (symbol_name, is_class_frame).
_Frame = tuple[str, bool]

# Stack entry for the iterative symbol walk: (node, scope, decorator_start_line).
_StackEntry = tuple[Node, tuple[_Frame, ...], int | None]


def extract_symbols(source: str | bytes, file_path: str) -> ParseResult:
    """Extract function/class/method symbols from Python source text.

    ``file_path`` is used verbatim (never resolved or normalized) as the
    ``file_path`` recorded on the result and on every extracted symbol.
    """
    if isinstance(source, str):
        # str input is already valid text; decode_error can never happen here.
        if not source.strip():
            return _empty_result(file_path)
        data = source.encode("utf-8")
    else:
        # Empty check happens before any decode/parse attempt, and works at
        # the byte level so it never requires the bytes to be valid UTF-8.
        if not source.strip():
            return _empty_result(file_path)
        try:
            source.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return ParseResult(
                file_path=file_path,
                status=ParseStatus.DECODE_ERROR,
                symbols=[],
                errors=[
                    SyntaxIssue(
                        kind=SyntaxIssueKind.ERROR,
                        message="source is not valid UTF-8",
                        start_line=1,
                        end_line=1,
                    )
                ],
            )
        data = source

    parser = Parser(_LANGUAGE)
    tree = parser.parse(data)
    root = tree.root_node

    symbols = _walk_symbols(root, file_path)

    if root.has_error:
        status = ParseStatus.SYNTAX_ERRORS
        errors = _collect_syntax_issues(root)
    else:
        status = ParseStatus.OK
        errors = []

    return ParseResult(file_path=file_path, status=status, symbols=symbols, errors=errors)


def extract_symbols_from_file(path: str | os.PathLike[str]) -> ParseResult:
    """Read ``path`` as bytes and extract symbols from it.

    Any ``OSError`` raised while reading (file not found, permission denied,
    is a directory, ...) propagates to the caller.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    return extract_symbols(data, str(path))


def _empty_result(file_path: str) -> ParseResult:
    return ParseResult(file_path=file_path, status=ParseStatus.EMPTY, symbols=[], errors=[])


def _end_line(node: Node, start_line: int) -> int:
    end_point = node.end_point
    if end_point.column == 0:
        end_line = end_point.row
    else:
        end_line = end_point.row + 1
    return max(end_line, start_line)


def _qualified_name(scope: tuple[_Frame, ...], own_name: str) -> str:
    parts: list[str] = []
    for frame_name, is_class in scope:
        parts.append(frame_name)
        if not is_class:
            parts.append("<locals>")
    parts.append(own_name)
    return ".".join(parts)


def _parent_qualified_name(scope: tuple[_Frame, ...]) -> str | None:
    if not scope:
        return None
    parts: list[str] = []
    for frame_name, is_class in scope[:-1]:
        parts.append(frame_name)
        if not is_class:
            parts.append("<locals>")
    # The immediately enclosing symbol's own name, with no trailing
    # "<locals>" -- <locals> is a naming convention, not itself a symbol.
    parts.append(scope[-1][0])
    return ".".join(parts)


def _node_name(node: Node) -> str:
    name_node = node.child_by_field_name("name")
    if name_node is None or name_node.text is None:
        return "<unknown>"
    return name_node.text.decode("utf-8")


def _walk_symbols(root: Node, file_path: str) -> list[Symbol]:
    """Iteratively walk the parse tree (explicit stack, no recursion) and
    emit a Symbol for every class/function/method/nested-function definition,
    in source order.
    """
    symbols: list[Symbol] = []
    stack: list[_StackEntry] = [(root, (), None)]

    while stack:
        node, scope, decorator_start_line = stack.pop()

        # Definitions inside a syntax-error region are intentionally not
        # reported as symbols -- their line ranges surface in `errors`
        # instead (see _collect_syntax_issues).
        if node.is_error or node.is_missing:
            continue

        node_type = node.type

        if node_type == "decorated_definition":
            definition = node.child_by_field_name("definition")
            if definition is not None:
                stack.append((definition, scope, node.start_point.row + 1))
            continue

        if node_type == "class_definition":
            name = _node_name(node)
            start_line = node.start_point.row + 1
            end_line = _end_line(node, start_line)
            symbols.append(
                Symbol(
                    name=name,
                    qualified_name=_qualified_name(scope, name),
                    kind=SymbolKind.CLASS,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    parent_qualified_name=_parent_qualified_name(scope),
                    decorator_start_line=decorator_start_line,
                    is_async=False,
                )
            )
            body = node.child_by_field_name("body")
            if body is not None:
                stack.append((body, scope + ((name, True),), None))
            continue

        if node_type == "function_definition":
            name = _node_name(node)
            # `async` is an unnamed child token (not a named field) of
            # function_definition, so `.children` (not `.named_children`)
            # must be scanned, or it is silently skipped.
            is_async = any(child.type == "async" for child in node.children)

            if not scope:
                kind = SymbolKind.FUNCTION
            elif scope[-1][1]:
                kind = SymbolKind.METHOD
            else:
                kind = SymbolKind.NESTED_FUNCTION

            start_line = node.start_point.row + 1
            end_line = _end_line(node, start_line)
            symbols.append(
                Symbol(
                    name=name,
                    qualified_name=_qualified_name(scope, name),
                    kind=kind,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    parent_qualified_name=_parent_qualified_name(scope),
                    decorator_start_line=decorator_start_line,
                    is_async=is_async,
                )
            )
            body = node.child_by_field_name("body")
            if body is not None:
                # Applies even for methods, so a method's own nested
                # function is correctly "nested_function", not "method".
                stack.append((body, scope + ((name, False),), None))
            continue

        # Any other node type (module/block/if/try/with/for/...): keep
        # descending through it without changing scope, pushing children in
        # reverse order so popping yields left-to-right (source) order.
        for child in reversed(node.children):
            stack.append((child, scope, None))

    return symbols


def _collect_syntax_issues(root: Node) -> list[SyntaxIssue]:
    """Second, independent traversal: collect the top-most error/missing
    nodes (not descending further once one is found, to avoid nested noise),
    up to `_MAX_SYNTAX_ISSUES`.
    """
    issues: list[SyntaxIssue] = []
    stack: list[Node] = [root]

    while stack and len(issues) < _MAX_SYNTAX_ISSUES:
        node = stack.pop()

        if node.is_error or node.is_missing:
            start_line = node.start_point.row + 1
            end_line = _end_line(node, start_line)
            if node.is_missing:
                kind = SyntaxIssueKind.MISSING
                message = f"missing '{node.type}'"
            else:
                kind = SyntaxIssueKind.ERROR
                message = f"unexpected syntax near '{node.type}'"
            issues.append(
                SyntaxIssue(kind=kind, message=message, start_line=start_line, end_line=end_line)
            )
            continue

        for child in reversed(node.children):
            stack.append(child)

    return issues
