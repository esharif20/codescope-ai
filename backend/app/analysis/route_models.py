"""Internal route syntax, registration and impact evidence contracts."""

from typing import Annotated

from pydantic import BaseModel, Field

Line = Annotated[int, Field(ge=1)]


class RouteDeclaration(BaseModel):
    receiver_id: str
    handler_id: str
    method: str
    path: str
    file_path: str
    line: Line
    handler_line: Line
    handler_end_line: Line


class RouteDiagnostic(BaseModel):
    file_path: str
    line: Line
    expression: str
    reason: str


class RouteRegistration(BaseModel):
    app_id: str
    handler_id: str
    method: str
    path: str
    declaration: RouteDeclaration
    registration_evidence: list[RouteDiagnostic]


class RouteInventory(BaseModel):
    declarations: list[RouteDeclaration] = Field(default_factory=list)
    registrations: list[RouteRegistration] = Field(default_factory=list)
    diagnostics: list[RouteDiagnostic] = Field(default_factory=list)
    file_statuses: dict[str, str] = Field(default_factory=dict)
    truncated: bool = False


class CallSiteEvidence(BaseModel):
    caller: str
    callee: str
    file_path: str
    lines: list[Line]


class ImpactPath(BaseModel):
    changed_symbol: str
    route: RouteRegistration
    symbols: list[str]
    edges: list[CallSiteEvidence]


class ImpactResult(BaseModel):
    impacts: list[ImpactPath] = Field(default_factory=list)
    unknown_symbols: list[str] = Field(default_factory=list)
    truncated: bool = False
