"""Extract raw route syntax without importing or executing analysed source.

Receivers and decorators are syntax candidates only. FastAPI identity and
registration are proved separately against the eligible import inventory.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

import tree_sitter_python
from tree_sitter import Language, Node, Parser

from app.analysis.imports import RawImport, extract_raw_imports
from app.analysis.python_symbols import extract_symbols
from app.analysis.route_models import RouteDeclaration, RouteDiagnostic

_LANGUAGE = Language(tree_sitter_python.language())
_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
_ROUTE_METHODS = _METHODS | {"api_route", "websocket", "websocket_route", "route"}


@dataclass
class RawReceiver:
    name: str
    constructor: str
    prefix: str | None
    line: int


@dataclass
class RawInclude:
    receiver: str
    child: str
    prefix: str | None
    line: int


@dataclass
class RouteSyntax:
    file_path: str
    declarations: list[RouteDeclaration] = field(default_factory=list)
    receivers: list[RawReceiver] = field(default_factory=list)
    includes: list[RawInclude] = field(default_factory=list)
    diagnostics: list[RouteDiagnostic] = field(default_factory=list)
    binding_counts: dict[str, int] = field(default_factory=dict)
    eligible_imports: list[RawImport] = field(default_factory=list)


def _text(node: Node | None) -> str:
    return node.text.decode("utf-8") if node is not None and node.text is not None else ""


def _literal(node: Node | None) -> str | None:
    if node is None or node.type != "string":
        return None
    # Reject interpolation before literal_eval (including an f-string with no fields).
    start = next((c for c in node.children if c.type == "string_start"), None)
    if start is None or "f" in _text(start).lower():
        return None
    try:
        value = ast.literal_eval(_text(node))
    except (ValueError, SyntaxError):
        return None
    return value if isinstance(value, str) else None


def _arguments(call: Node) -> tuple[list[Node], dict[str, Node], bool]:
    args = call.child_by_field_name("arguments")
    positional: list[Node] = []
    keywords: dict[str, Node] = {}
    unpacking = False
    if args is not None:
        for item in args.named_children:
            if item.type in {"list_splat", "dictionary_splat"}:
                unpacking = True
            elif item.type == "keyword_argument":
                value = item.child_by_field_name("value")
                if value is not None:
                    keywords[_text(item.child_by_field_name("name"))] = value
            elif item.type != "comment":
                positional.append(item)
    return positional, keywords, unpacking


def _targets(node: Node | None) -> list[str]:
    names: list[str] = []
    stack = [node] if node is not None else []
    while stack:
        current = stack.pop()
        if current.type == "identifier":
            names.append(_text(current))
        elif current.type in {
            "pattern_list",
            "tuple_pattern",
            "list_pattern",
            "list_splat_pattern",
            "as_pattern_target",
            "parenthesized_expression",
        }:
            stack.extend(reversed(current.named_children))
    return names


def extract_route_syntax(source: str | bytes, file_path: str, module_path: str) -> RouteSyntax:
    """Return source-ordered syntax candidates and explicit unsupported evidence."""
    result = RouteSyntax(file_path=file_path)

    def diagnostic(node: Node, reason: str) -> None:
        result.diagnostics.append(
            RouteDiagnostic(
                file_path=file_path,
                line=node.start_point.row + 1,
                expression=_text(node),
                reason=reason,
            )
        )

    data = source.encode("utf-8") if isinstance(source, str) else source
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        result.diagnostics.append(
            RouteDiagnostic(
                file_path=file_path, line=1, expression="<invalid UTF-8>", reason="decode_error"
            )
        )
        return result
    root = Parser(_LANGUAGE).parse(data).root_node
    symbols = {s.start_line: s for s in extract_symbols(data, file_path).symbols}

    def bind(names: list[str]) -> None:
        for name in names:
            result.binding_counts[name] = result.binding_counts.get(name, 0) + 1

    def prefix(call: Node, keywords: dict[str, Node]) -> str | None:
        if "prefix" not in keywords:
            return ""
        value = _literal(keywords["prefix"])
        if value is None:
            diagnostic(call, "dynamic_prefix_unsupported")
        return value

    # (node, inside function/class body). Root eligibility is checked structurally.
    stack: list[tuple[Node, bool]] = [(root, False)]
    while stack:
        node, scoped = stack.pop()
        if node.is_error or node.is_missing:
            diagnostic(node, "syntax_error")
            continue
        direct = node.parent is not None and node.parent.type == "module"

        if node.type in {"import_statement", "import_from_statement"}:
            # Parse only this root import's text, then restore its original location.
            imports = extract_raw_imports(node.text or b"", file_path)
            for item in imports:
                item.line = node.start_point.row + 1
            if direct:
                result.eligible_imports.extend(imports)
            if not scoped:
                for item in imports:
                    bind(
                        [
                            alias or (name.split(".")[0] if item.kind == "import" else name)
                            for name, alias in item.names
                            if name != "*"
                        ]
                    )
            continue

        if not scoped:
            if node.type in {"function_definition", "class_definition"}:
                bind([_text(node.child_by_field_name("name"))])
            elif node.type in {
                "assignment",
                "augmented_assignment",
                "for_statement",
                "named_expression",
            }:
                bind(_targets(node.child_by_field_name("left") or node.child_by_field_name("name")))
            elif node.type == "as_pattern":
                bind(_targets(node.child_by_field_name("alias")))

        if node.type == "assignment":
            value = node.child_by_field_name("right")
            target = node.child_by_field_name("left")
            if value is not None and value.type == "call":
                function = value.child_by_field_name("function")
                _, keywords, unpacking = _arguments(value)
                if value.has_error:
                    diagnostic(value, "syntax_error")
                elif unpacking:
                    diagnostic(value, "argument_unpacking_unsupported")
                elif (
                    not scoped
                    and node.parent is not None
                    and node.parent.type == "expression_statement"
                    and node.parent.parent is not None
                    and node.parent.parent.type == "module"
                    and target is not None
                    and target.type == "identifier"
                    and function is not None
                    and function.type in {"identifier", "attribute"}
                ):
                    result.receivers.append(
                        RawReceiver(
                            _text(target),
                            _text(function),
                            prefix(value, keywords),
                            node.start_point.row + 1,
                        )
                    )
                else:
                    diagnostic(node, "receiver_scope_or_assignment_unsupported")

        if node.type == "decorated_definition":
            definition = node.child_by_field_name("definition")
            symbol = symbols.get(definition.start_point.row + 1) if definition is not None else None
            for decorator in node.named_children:
                if decorator.type != "decorator":
                    continue
                call = next((c for c in decorator.named_children if c.type == "call"), None)
                if call is None:
                    attribute = next(
                        (c for c in decorator.named_children if c.type == "attribute"), None
                    )
                    if (
                        attribute is not None
                        and _text(attribute.child_by_field_name("attribute")) in _ROUTE_METHODS
                    ):
                        diagnostic(decorator, "route_arguments_unsupported")
                    continue
                function = call.child_by_field_name("function")
                if function is None or function.type != "attribute":
                    continue
                method = _text(function.child_by_field_name("attribute"))
                if method not in _ROUTE_METHODS:
                    continue
                positional, keywords, unpacking = _arguments(call)
                receiver = function.child_by_field_name("object")
                if call.has_error:
                    diagnostic(decorator, "syntax_error")
                elif unpacking:
                    diagnostic(decorator, "argument_unpacking_unsupported")
                elif (
                    not direct
                    or scoped
                    or definition is None
                    or definition.type != "function_definition"
                ):
                    diagnostic(decorator, "route_scope_unsupported")
                elif method not in _METHODS:
                    diagnostic(decorator, "route_method_unsupported")
                elif receiver is None or receiver.type != "identifier":
                    diagnostic(decorator, "route_receiver_unsupported")
                else:
                    path = _literal(keywords.get("path") or (positional[0] if positional else None))
                    if path is None or symbol is None or definition.has_error:
                        diagnostic(decorator, "route_path_or_definition_unsupported")
                    else:
                        result.declarations.append(
                            RouteDeclaration(
                                receiver_id=f"{module_path}:{_text(receiver)}",
                                handler_id=f"{module_path}:{symbol.qualified_name}",
                                method=method.upper(),
                                path=path,
                                file_path=file_path,
                                line=decorator.start_point.row + 1,
                                handler_line=symbol.start_line,
                                handler_end_line=symbol.end_line,
                            )
                        )

        if node.type == "call":
            function = node.child_by_field_name("function")
            if (
                function is not None
                and function.type == "attribute"
                and _text(function.child_by_field_name("attribute")) == "include_router"
            ):
                positional, keywords, unpacking = _arguments(node)
                receiver = function.child_by_field_name("object")
                child = keywords.get("router") or (positional[0] if positional else None)
                top_level = (
                    node.parent is not None
                    and node.parent.type == "expression_statement"
                    and node.parent.parent is not None
                    and node.parent.parent.type == "module"
                )
                if node.has_error:
                    diagnostic(node, "syntax_error")
                elif unpacking:
                    diagnostic(node, "argument_unpacking_unsupported")
                elif (
                    scoped
                    or not top_level
                    or receiver is None
                    or receiver.type != "identifier"
                    or child is None
                    or child.type not in {"identifier", "attribute"}
                ):
                    diagnostic(node, "include_scope_or_receiver_unsupported")
                else:
                    result.includes.append(
                        RawInclude(
                            _text(receiver),
                            _text(child),
                            prefix(node, keywords),
                            node.start_point.row + 1,
                        )
                    )

        child_scope = scoped or node.type in {"function_definition", "class_definition", "lambda"}
        stack.extend((child, child_scope) for child in reversed(node.named_children))
    return result
