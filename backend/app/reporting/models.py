"""Framework-independent, evidence-preserving schema v1 report contracts.

``builder.snapshot_digest(root, relative_paths)`` hashes the sorted unique POSIX
path inventory with 8-byte big-endian path/content lengths and exact source bytes.
Controlled digests describe source snapshots, never Git commit identities.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.analysis.models import SymbolKind
from app.ingestion.models import PinnedPullRequest, PositiveInt, RelativePath, SourceReference
from app.ingestion.source_links import source_reference

ANALYZER_VERSION = "codescope-static-1"
Revision = Literal["base", "head"]
Text = Annotated[str, Field(min_length=1)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GitHubProvenance(Contract):
    kind: Literal["github"] = "github"
    pull_request: PinnedPullRequest


class ControlledProvenance(Contract):
    kind: Literal["controlled"] = "controlled"
    fixture_id: Text
    base_digest: Digest
    head_digest: Digest
    description: Text


Provenance = Annotated[GitHubProvenance | ControlledProvenance, Field(discriminator="kind")]


class GitHubReference(Contract):
    kind: Literal["github"] = "github"
    source: SourceReference


class ControlledReference(Contract):
    kind: Literal["controlled"] = "controlled"
    fixture_id: Text
    revision: Revision
    file_path: RelativePath
    start_line: PositiveInt
    end_line: PositiveInt

    @model_validator(mode="after")
    def check_range(self):
        if self.end_line < self.start_line:
            raise ValueError("invalid source range")
        return self


EvidenceRef = Annotated[GitHubReference | ControlledReference, Field(discriminator="kind")]


def evidence_revision(ref: EvidenceRef) -> Revision:
    return ref.source.revision if isinstance(ref, GitHubReference) else ref.revision


class ReportChange(Contract):
    status: Literal["added", "modified", "removed"]
    symbol_id: Text
    kind: SymbolKind
    old: EvidenceRef | None = None
    new: EvidenceRef | None = None

    @model_validator(mode="after")
    def check_sides(self):
        expected = {"added": (False, True), "modified": (True, True), "removed": (True, False)}
        if (self.old is not None, self.new is not None) != expected[self.status]:
            raise ValueError("change sides contradict status")
        if (self.old and evidence_revision(self.old) != "base") or (
            self.new and evidence_revision(self.new) != "head"
        ):
            raise ValueError("source revision contradicts change side")
        return self


class ReportNode(Contract):
    symbol_id: Text
    kind: SymbolKind
    source: EvidenceRef


class ReportEdge(Contract):
    caller: Text
    callee: Text
    evidence: list[EvidenceRef] = Field(min_length=1)


class ReportRoute(Contract):
    app_id: Text
    handler_id: Text
    method: Text
    path: Text
    declaration: EvidenceRef
    handler: EvidenceRef
    registration_evidence: list[EvidenceRef] = Field(default_factory=list)


class ReportFinding(Contract):
    """One potential impact path, ordered from handler to changed symbol."""

    changed_symbol: Text
    route: ReportRoute
    symbols: list[str] = Field(min_length=1)
    edges: list[ReportEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_path(self):
        if self.symbols[0] != self.route.handler_id or self.symbols[-1] != self.changed_symbol:
            raise ValueError("invalid path endpoints")
        if [(e.caller, e.callee) for e in self.edges] != list(zip(self.symbols, self.symbols[1:])):
            raise ValueError("path edges contradict symbols")
        return self


def _references(value):
    if isinstance(value, (GitHubReference, ControlledReference)):
        yield value
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            yield from _references(getattr(value, name))
    elif isinstance(value, list):
        for item in value:
            yield from _references(item)


class RevisionReport(Contract):
    revision: Revision
    nodes: list[ReportNode] = Field(default_factory=list)
    edges: list[ReportEdge] = Field(default_factory=list)
    findings: list[ReportFinding] = Field(default_factory=list)
    partial: bool = False

    @model_validator(mode="after")
    def check_graph(self):
        nodes = {node.symbol_id for node in self.nodes}
        node_index = {node.symbol_id: node for node in self.nodes}
        edges = {(edge.caller, edge.callee): edge for edge in self.edges}
        if len(nodes) != len(self.nodes) or len(edges) != len(self.edges):
            raise ValueError("duplicate graph identities")
        if any(e.caller not in nodes or e.callee not in nodes for e in self.edges):
            raise ValueError("dangling graph edge")
        for finding in self.findings:
            if not set(finding.symbols) <= nodes or any(
                edges.get((e.caller, e.callee)) != e for e in finding.edges
            ):
                raise ValueError("finding lacks verified graph evidence")
            if finding.route.handler != node_index[finding.route.handler_id].source:
                raise ValueError("route handler contradicts verified node evidence")
        if any(evidence_revision(ref) != self.revision for ref in _references(self)):
            raise ValueError("evidence revision contradicts graph")
        return self


class ReportUncertainty(Contract):
    revision: Revision | None = None
    category: Literal[
        "unresolved_call",
        "uncertain_call",
        "route_diagnostic",
        "file_status",
        "mapping",
        "unmapped_change",
        "unknown_symbol",
        "truncation",
        "invalid_evidence",
    ]
    reason: Text
    source: EvidenceRef | None = None
    symbol_id: str | None = None
    candidates: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_revision(self):
        if self.source and self.revision != evidence_revision(self.source):
            raise ValueError("uncertainty revision contradicts evidence")
        return self


class ReportInput(Contract):
    report_id: Text
    provenance: Provenance
    changes: list[ReportChange] = Field(default_factory=list)
    unmapped_changes: list[EvidenceRef] = Field(default_factory=list)
    mapping_diagnostics: list[str] = Field(default_factory=list)
    mapping_partial: bool = False

    @model_validator(mode="after")
    def check_provenance(self):
        _check_provenance(self, self.provenance)
        return self


def _check_provenance(value, provenance):
    for ref in _references(value):
        if isinstance(provenance, ControlledProvenance):
            if not isinstance(ref, ControlledReference) or ref.fixture_id != provenance.fixture_id:
                raise ValueError("evidence contradicts controlled provenance")
        else:
            if not isinstance(ref, GitHubReference):
                raise ValueError("evidence contradicts GitHub provenance")
            source = ref.source
            expected = source_reference(
                provenance.pull_request,
                source.revision,
                source.file_path,
                source.start_line,
                source.end_line,
            )
            if source != expected:
                raise ValueError("evidence contradicts pinned GitHub provenance")


class AnalysisReport(Contract):
    schema_version: Literal["1"] = "1"
    report_id: Text
    analyzer_version: Text = ANALYZER_VERSION
    provenance: Provenance
    changes: list[ReportChange] = Field(default_factory=list)
    revisions: list[RevisionReport]
    unmapped_changes: list[EvidenceRef] = Field(default_factory=list)
    uncertainties: list[ReportUncertainty] = Field(default_factory=list)
    partial: bool = False

    @model_validator(mode="after")
    def check_report(self):
        if [r.revision for r in self.revisions] != ["base", "head"]:
            raise ValueError("expected base/head revisions in order")
        _check_provenance(self, self.provenance)
        return self
