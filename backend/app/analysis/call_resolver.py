"""Deterministic D-01 through D-04 call and class-hierarchy resolution."""

from __future__ import annotations

from app.analysis.calls import RawClassBases
from app.analysis.models import ImportBinding, ResolutionStatus


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
