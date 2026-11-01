"""Prove literal FastAPI registrations using only extracted syntax evidence."""

from dataclasses import dataclass

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
    return prefix == '' or (
        prefix is not None and prefix.startswith('/') and not prefix.endswith('/')
    )


def _imports(syntax: RouteSyntax) -> dict[str, list[tuple[RawImport, str]]]:
    result: dict[str, list[tuple[RawImport, str]]] = {}
    for raw in syntax.eligible_imports:
        if raw.is_star:
            continue
        for name, alias in raw.names:
            local = alias or (name.split('.')[0] if raw.kind == 'import' else name)
            result.setdefault(local, []).append((raw, name))
    return result


def _constructor(expression: str, syntax: RouteSyntax) -> str | None:
    parts = expression.split('.')
    bindings = _imports(syntax).get(parts[0], [])
    if len(bindings) != 1 or syntax.binding_counts.get(parts[0]) != 1:
        return None
    raw, name = bindings[0]
    if raw.relative_level or raw.module != 'fastapi':
        return None
    if len(parts) == 1 and raw.kind == 'from_import':
        return name if name in {'FastAPI', 'APIRouter'} else None
    if len(parts) == 2 and raw.kind == 'import' and name == 'fastapi':
        return parts[1] if parts[1] in {'FastAPI', 'APIRouter'} else None
    return None


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
                    _fact(syntax, raw.line, raw.name, 'receiver_unproven_or_shadowed')
                )
                continue
            if not _valid_prefix(raw.prefix):
                result.diagnostics.append(
                    _fact(syntax, raw.line, raw.name, 'receiver_prefix_unsupported')
                )
                continue
            receivers[f'{module}:{raw.name}'] = _Receiver(
                kind, raw.prefix or '', _fact(syntax, raw.line, raw.constructor, 'constructor_verified')
            )
    for declaration in result.declarations:
        receiver = receivers.get(declaration.receiver_id)
        if receiver is None:
            result.diagnostics.append(RouteDiagnostic(
                file_path=declaration.file_path, line=declaration.line,
                expression=declaration.receiver_id, reason='route_receiver_unverified',
            ))
        elif receiver.kind == 'FastAPI':
            result.registrations.append(RouteRegistration(
                app_id=declaration.receiver_id, handler_id=declaration.handler_id,
                method=declaration.method, path=declaration.path, declaration=declaration,
                registration_evidence=[receiver.evidence],
            ))
    return result
