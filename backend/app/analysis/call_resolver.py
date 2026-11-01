"""Deterministic D-01 through D-04 call and class-hierarchy resolution."""

from __future__ import annotations

from app.analysis.calls import RawCall, RawClassBases
from app.analysis.models import (
    ImportBinding,
    ResolutionStatus,
    ResolvedCall,
    Symbol,
    UnresolvedCall,
)


def build_class_hierarchy(
    raw_bases_by_module: dict[str, list[RawClassBases]],
    bindings_by_module: dict[str, list[ImportBinding]],
) -> dict[str, list[str]]:
    """Index ordered, directly inherited in-repository base classes (D-01)."""
    hierarchy: dict[str, list[str]] = {}

    for module_path, raw_classes in raw_bases_by_module.items():
        same_module_classes = {raw_class.qualified_name for raw_class in raw_classes}
        bindings = bindings_by_module.get(module_path, [])

        for raw_class in raw_classes:
            resolved_bases: list[str] = []
            for base in raw_class.bases:
                base_id = _resolve_base_id(base, module_path, same_module_classes, bindings)
                if base_id is not None:
                    resolved_bases.append(base_id)

            if resolved_bases:
                hierarchy[f"{module_path}:{raw_class.qualified_name}"] = resolved_bases

    return hierarchy


def _resolve_base_id(
    base: str,
    module_path: str,
    same_module_classes: set[str],
    bindings: list[ImportBinding],
) -> str | None:
    if "." not in base:
        if base in same_module_classes:
            return f"{module_path}:{base}"

        binding = next((item for item in bindings if item.imported_name == base), None)
        if (
            binding is not None
            and binding.status == ResolutionStatus.RESOLVED
            and binding.source_module is not None
            and binding.source_name is not None
        ):
            return f"{binding.source_module}:{binding.source_name}"
        return None

    module_alias, rest = base.split(".", 1)
    binding = next((item for item in bindings if item.imported_name == module_alias), None)
    if (
        binding is not None
        and binding.status == ResolutionStatus.RESOLVED
        and binding.source_module is not None
        and binding.source_name is None
    ):
        return f"{binding.source_module}:{rest}"
    return None


def resolve_file_calls(
    raw_calls: list[RawCall],
    importing_module: str,
    bindings: list[ImportBinding],
    symbol_table: dict[str, list[Symbol]],
    class_hierarchy: dict[str, list[str]],
) -> tuple[list[ResolvedCall], list[UnresolvedCall]]:
    """Resolve each supported raw call to one edge or explicit gap (D-01--D-04)."""
    resolved_calls: list[ResolvedCall] = []
    unresolved_calls: list[UnresolvedCall] = []

    for raw_call in raw_calls:
        caller = f"{importing_module}:{raw_call.enclosing_symbol}"
        callee: str | None = None
        uncertain_candidates: list[str] | None = None

        if raw_call.receiver_kind in {"self", "cls"}:
            callee = _resolve_self_or_cls_call(
                raw_call, importing_module, symbol_table, class_hierarchy
            )
        elif raw_call.receiver_kind == "bare":
            callee, uncertain_candidates = _resolve_bare_call(
                raw_call.expression, importing_module, bindings, symbol_table
            )
        else:
            callee = _resolve_attribute_call(raw_call.expression, bindings, symbol_table)

        if callee is not None:
            resolved_calls.append(ResolvedCall(caller=caller, callee=callee, line=raw_call.line))
        elif uncertain_candidates is not None:
            unresolved_calls.append(
                _unresolved_call(raw_call, caller, ResolutionStatus.UNCERTAIN, uncertain_candidates)
            )
        else:
            unresolved_calls.append(_unresolved_call(raw_call, caller, ResolutionStatus.UNRESOLVED))

    return resolved_calls, unresolved_calls


def _resolve_self_or_cls_call(
    raw_call: RawCall,
    importing_module: str,
    symbol_table: dict[str, list[Symbol]],
    class_hierarchy: dict[str, list[str]],
) -> str | None:
    enclosing = next(
        (
            symbol
            for symbol in symbol_table.get(importing_module, [])
            if symbol.qualified_name == raw_call.enclosing_symbol
        ),
        None,
    )
    if enclosing is None or enclosing.parent_qualified_name is None:
        return None

    method_name = raw_call.expression.split(".", 1)[1]
    class_id = f"{importing_module}:{enclosing.parent_qualified_name}"
    for candidate_class_id in _hierarchy_preorder(class_id, class_hierarchy):
        module_path, class_name = candidate_class_id.split(":", 1)
        target = _top_level_or_member(
            symbol_table.get(module_path, []), f"{class_name}.{method_name}", class_name
        )
        if target is not None:
            return f"{module_path}:{target.qualified_name}"
    return None


def _hierarchy_preorder(
    root: str,
    class_hierarchy: dict[str, list[str]],
) -> list[str]:
    ordered: list[str] = []
    visited: set[str] = set()
    stack = [root]

    while stack:
        class_id = stack.pop()
        if class_id in visited:
            continue
        visited.add(class_id)
        ordered.append(class_id)
        stack.extend(reversed(class_hierarchy.get(class_id, [])))

    return ordered


def _resolve_bare_call(
    name: str,
    importing_module: str,
    bindings: list[ImportBinding],
    symbol_table: dict[str, list[Symbol]],
) -> tuple[str | None, list[str] | None]:
    local_target = _top_level_or_member(symbol_table.get(importing_module, []), name, None)
    if local_target is not None:
        return f"{importing_module}:{local_target.qualified_name}", None

    candidates: set[str] = set()
    for binding in bindings:
        if (
            binding.imported_name != name
            or binding.status != ResolutionStatus.RESOLVED
            or binding.source_module is None
            or binding.source_name is None
        ):
            continue
        target = _top_level_or_member(
            symbol_table.get(binding.source_module, []), binding.source_name, None
        )
        if target is not None:
            candidates.add(f"{binding.source_module}:{target.qualified_name}")

    if len(candidates) == 1:
        return next(iter(candidates)), None
    if candidates:
        return None, sorted(candidates)
    return None, None


def _resolve_attribute_call(
    expression: str,
    bindings: list[ImportBinding],
    symbol_table: dict[str, list[Symbol]],
) -> str | None:
    object_name, attr_name = expression.split(".", 1)
    binding = next((item for item in bindings if item.imported_name == object_name), None)
    if (
        binding is None
        or binding.status != ResolutionStatus.RESOLVED
        or binding.source_module is None
        or binding.source_name is not None
    ):
        return None

    target = _top_level_or_member(symbol_table.get(binding.source_module, []), attr_name, None)
    if target is None:
        return None
    return f"{binding.source_module}:{target.qualified_name}"


def _top_level_or_member(
    symbols: list[Symbol],
    qualified_name: str,
    parent_qualified_name: str | None,
) -> Symbol | None:
    return next(
        (
            symbol
            for symbol in symbols
            if symbol.qualified_name == qualified_name
            and symbol.parent_qualified_name == parent_qualified_name
        ),
        None,
    )


def _unresolved_call(
    raw_call: RawCall,
    caller: str,
    status: ResolutionStatus,
    candidates: list[str] | None = None,
) -> UnresolvedCall:
    return UnresolvedCall(
        enclosing_symbol=caller,
        file_path=raw_call.file_path,
        line=raw_call.line,
        expression=raw_call.expression,
        status=status,
        candidates=candidates or [],
    )
