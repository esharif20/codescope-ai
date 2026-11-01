"""Prove literal FastAPI registrations using only extracted syntax evidence."""

from dataclasses import dataclass

from app.analysis.import_resolver import _target_module
from app.analysis.imports import RawImport
from app.analysis.route_models import RouteDiagnostic, RouteInventory, RouteRegistration
from app.analysis.routes import RouteSyntax

_MAX_REGISTRATIONS = 1000
_MAX_MOUNT_STEPS = 10000


@dataclass
class _Receiver:
    kind: str
    prefix: str
    evidence: RouteDiagnostic


def _fact(syntax: RouteSyntax, line: int, expression: str, reason: str) -> RouteDiagnostic:
    return RouteDiagnostic(
        file_path=syntax.file_path, line=line, expression=expression, reason=reason
    )


def _valid_prefix(prefix: str | None) -> bool:
    return prefix == "" or (
        prefix is not None and prefix.startswith("/") and not prefix.endswith("/")
    )


def _imports(syntax: RouteSyntax) -> dict[str, list[tuple[RawImport, str]]]:
    result: dict[str, list[tuple[RawImport, str]]] = {}
    for raw in syntax.eligible_imports:
        if raw.is_star:
            continue
        for name, alias in raw.names:
            local = alias or (name.split(".")[0] if raw.kind == "import" else name)
            result.setdefault(local, []).append((raw, name))
    return result


def _constructor(expression: str, syntax: RouteSyntax) -> str | None:
    # A star import can replace any explicitly named binding; its exports are unknown.
    if any(raw.is_star for raw in syntax.eligible_imports):
        return None
    parts = expression.split(".")
    bindings = _imports(syntax).get(parts[0], [])
    if len(bindings) != 1 or syntax.binding_counts.get(parts[0]) != 1:
        return None
    raw, name = bindings[0]
    if raw.relative_level or raw.module != "fastapi":
        return None
    if len(parts) == 1 and raw.kind == "from_import":
        return name if name in {"FastAPI", "APIRouter"} else None
    if len(parts) == 2 and raw.kind == "import" and name == "fastapi":
        return parts[1] if parts[1] in {"FastAPI", "APIRouter"} else None
    return None


def _include_target(
    expression: str,
    module: str,
    syntax: RouteSyntax,
    init_modules: set[str],
) -> tuple[str | None, str]:
    if "." not in expression and syntax.binding_counts.get(expression) == 1:
        if any(raw.name == expression for raw in syntax.receivers):
            return f"{module}:{expression}", ""
    if any(raw.is_star for raw in syntax.eligible_imports):
        return None, "include_import_ambiguous"
    root = expression.split(".")[0]
    bindings = _imports(syntax).get(root, [])
    if syntax.binding_counts.get(root, 0) > 1 or len(bindings) > 1:
        return None, "include_alias_shadowed"
    if len(bindings) != 1 or syntax.binding_counts.get(root) != 1:
        return None, "include_import_unverified"
    raw, name = bindings[0]
    target_module = _target_module(raw, module, module in init_modules)
    if raw.kind == "from_import":
        if expression == root:
            return f"{target_module}:{name}", ""
        target_module = f"{target_module}.{name}" if target_module else name
        suffix = expression[len(root) + 1 :]
    else:
        # Without an alias, `import a.b` binds `a` and requires `a.b.router`.
        imported_prefix = root if raw.names[0][1] else name
        if not expression.startswith(imported_prefix + "."):
            return None, "include_attribute_unsupported"
        suffix = expression[len(imported_prefix) + 1 :]
    if not suffix or "." in suffix:
        return None, "include_attribute_unsupported"
    return f"{target_module}:{suffix}", ""


def resolve_route_inventory(
    syntax_by_module: dict[str, RouteSyntax],
    raw_imports_by_module: dict[str, list[RawImport]],
    init_modules: set[str],
) -> RouteInventory:
    """Resolve registrations without importing any analysed module.

    Only structurally eligible imports establish proof. The wider raw import
    inventory is deliberately never used to recover excluded bindings.
    """
    result = RouteInventory()
    receivers: dict[str, _Receiver] = {}
    for module, syntax in sorted(syntax_by_module.items()):
        result.diagnostics.extend(syntax.diagnostics)
        result.declarations.extend(syntax.declarations)
        for raw in syntax.receivers:
            kind = _constructor(raw.constructor, syntax)
            if kind is None or syntax.binding_counts.get(raw.name) != 1:
                result.diagnostics.append(
                    _fact(syntax, raw.line, raw.name, "receiver_unproven_or_shadowed")
                )
                continue
            if not _valid_prefix(raw.prefix):
                result.diagnostics.append(
                    _fact(syntax, raw.line, raw.name, "receiver_prefix_unsupported")
                )
                continue
            receivers[f"{module}:{raw.name}"] = _Receiver(
                kind,
                raw.prefix or "",
                _fact(syntax, raw.line, raw.constructor, "constructor_verified"),
            )
    declarations = {}
    for declaration in result.declarations:
        receiver = receivers.get(declaration.receiver_id)
        if receiver is None:
            result.diagnostics.append(
                RouteDiagnostic(
                    file_path=declaration.file_path,
                    line=declaration.line,
                    expression=declaration.receiver_id,
                    reason="route_receiver_unverified",
                )
            )
        elif declaration.path and not declaration.path.startswith("/"):
            result.diagnostics.append(
                RouteDiagnostic(
                    file_path=declaration.file_path,
                    line=declaration.line,
                    expression=declaration.path,
                    reason="route_path_unsupported",
                )
            )
        else:
            declarations.setdefault(declaration.receiver_id, []).append(declaration)

    mounts: dict[str, list[tuple[str, str, RouteDiagnostic]]] = {}
    for module, syntax in sorted(syntax_by_module.items()):
        for include in syntax.includes:
            child, reason = _include_target(include.child, module, syntax, init_modules)
            parent_id = f"{module}:{include.receiver}"
            # Check child alias safety even when the receiving variable is unverified.
            if not reason and parent_id not in receivers:
                reason = "include_receiver_unverified"
            if not reason and (child not in receivers or receivers[child].kind != "APIRouter"):
                reason = "include_target_unverified"
            if not reason and not _valid_prefix(include.prefix):
                reason = "include_prefix_unsupported"
            evidence = _fact(
                syntax,
                include.line,
                f"{include.receiver}.include_router({include.child})",
                reason or "include_verified",
            )
            if reason:
                result.diagnostics.append(evidence)
            else:
                mounts.setdefault(parent_id, []).append((child, include.prefix or "", evidence))

    seen_registrations: set[str] = set()
    steps = 0
    capped = False
    for app_id, app in sorted(receivers.items()):
        if app.kind != "FastAPI":
            continue
        stack = [(app_id, "", [app.evidence], frozenset({app_id}))]
        while stack:
            if steps >= _MAX_MOUNT_STEPS:
                capped = True
                break
            receiver_id, prefix, evidence, visited = stack.pop()
            steps += 1
            for declaration in declarations.get(receiver_id, []):
                registration = RouteRegistration(
                    app_id=app_id,
                    handler_id=declaration.handler_id,
                    method=declaration.method,
                    path=prefix + declaration.path,
                    declaration=declaration,
                    registration_evidence=evidence,
                )
                key = registration.model_dump_json()
                if key in seen_registrations:
                    continue
                if len(result.registrations) >= _MAX_REGISTRATIONS:
                    capped = True
                    break
                seen_registrations.add(key)
                result.registrations.append(registration)
            if capped:
                break
            for child, include_prefix, include_evidence in reversed(mounts.get(receiver_id, [])):
                if child in visited:
                    result.diagnostics.append(
                        include_evidence.model_copy(
                            update={
                                "reason": "include_cycle_unsupported",
                            }
                        )
                    )
                    continue
                receiver = receivers[child]
                stack.append(
                    (
                        child,
                        prefix + include_prefix + receiver.prefix,
                        evidence + [include_evidence, receiver.evidence],
                        visited | {child},
                    )
                )
        if capped:
            result.truncated = True
            result.diagnostics.append(
                app.evidence.model_copy(update={"reason": "registration_cap"})
            )
            break
    result.registrations.sort(
        key=lambda r: (
            r.app_id,
            r.path,
            r.method,
            r.handler_id,
            r.declaration.line,
            r.model_dump_json(),
        )
    )
    result.diagnostics = sorted(
        {d.model_dump_json(): d for d in result.diagnostics}.values(),
        key=lambda d: (d.file_path, d.line, d.expression, d.reason),
    )
    return result
