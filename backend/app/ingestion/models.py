"""Framework-independent ingestion contracts; snapshot paths stay private."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app.analysis.models import SymbolKind

SHA40 = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
PositiveInt = Annotated[int, Field(gt=0, strict=True)]
NonnegativeInt = Annotated[int, Field(ge=0, strict=True)]


def validate_owner(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", value):
        raise ValueError("invalid GitHub owner")
    if "--" in value:
        raise ValueError("invalid GitHub owner")
    return value.lower()


def validate_repo(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", value) or value in (".", ".."):
        raise ValueError("invalid GitHub repository")
    return value.lower()


def validate_repository(value: str) -> str:
    parts = value.split("/")
    if len(parts) != 2:
        raise ValueError("repository must be owner/repo")
    return f"{validate_owner(parts[0])}/{validate_repo(parts[1])}"


def validate_path(value: str) -> str:
    if (
        not value
        or "\\" in value
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
        or any(part in ("", ".", "..") for part in value.split("/"))
    ):
        raise ValueError("file_path must be a relative POSIX path")
    return value


Repository = Annotated[str, AfterValidator(validate_repository)]
RelativePath = Annotated[str, AfterValidator(validate_path)]


class PullRequestRef(BaseModel):
    owner: Annotated[str, AfterValidator(validate_owner)]
    repo: Annotated[str, AfterValidator(validate_repo)]
    number: PositiveInt


class PinnedPullRequest(BaseModel):
    ref: PullRequestRef
    title: str
    base_repository: Repository
    head_repository: Repository
    target_base_sha: SHA40
    analysis_base_sha: SHA40
    head_sha: SHA40
    changed_files: NonnegativeInt


class ChangedFile(BaseModel):
    old_path: RelativePath | None = None
    new_path: RelativePath | None = None
    status: Literal["added", "modified", "removed", "renamed"]
    old_blob_sha: SHA40 | None = None
    new_blob_sha: SHA40 | None = None

    @model_validator(mode="after")
    def check_sides(self) -> ChangedFile:
        if self.status == "added":
            valid = (
                self.old_path is None and self.new_path is not None and self.old_blob_sha is None
            )
        elif self.status == "removed":
            valid = (
                self.old_path is not None and self.new_path is None and self.new_blob_sha is None
            )
        else:
            valid = self.old_path is not None and self.new_path is not None
        if not valid:
            raise ValueError("changed file sides contradict status")
        return self


class SourceReference(BaseModel):
    revision: Literal["base", "head"]
    repository: Repository
    commit_sha: SHA40
    file_path: RelativePath
    start_line: PositiveInt
    end_line: PositiveInt
    url: str

    @model_validator(mode="after")
    def check_range(self) -> SourceReference:
        if self.end_line < self.start_line:
            raise ValueError("end_line must be >= start_line")
        return self


class ChangedSymbol(BaseModel):
    status: Literal["added", "modified", "removed"]
    symbol_id: str
    kind: SymbolKind
    old: SourceReference | None = None
    new: SourceReference | None = None

    @model_validator(mode="after")
    def check_sides(self) -> ChangedSymbol:
        expected = {"added": (False, True), "modified": (True, True), "removed": (True, False)}
        if (self.old is not None, self.new is not None) != expected[self.status]:
            raise ValueError("changed symbol sides contradict status")
        if (self.old is not None and self.old.revision != "base") or (
            self.new is not None and self.new.revision != "head"
        ):
            raise ValueError("source revision contradicts change side")
        return self


class MappingResult(BaseModel):
    changes: list[ChangedSymbol] = Field(default_factory=list)
    unmapped_changes: list[SourceReference] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
    partial: bool = False


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analysis_id: UUID
    pr_url: str = Field(max_length=2048)


class AnalysisError(BaseModel):
    code: str
    message: str
    retry_after_seconds: NonnegativeInt | None = None


class AnalysisSummary(BaseModel):
    changed_symbols: list[ChangedSymbol] = Field(default_factory=list)
    affected_routes_base: NonnegativeInt = 0
    affected_routes_head: NonnegativeInt = 0
    partial: bool = False
    diagnostics: list[str] = Field(default_factory=list)


class AnalysisStatus(BaseModel):
    analysis_id: UUID
    state: Literal["pending", "running", "complete", "error", "timeout"]
    stage: Literal[
        "accepted", "metadata", "sources", "mapping", "impact_base", "impact_head", "finished"
    ]
    created_at: datetime
    updated_at: datetime
    revisions: PinnedPullRequest | None = None
    summary: AnalysisSummary | None = None
    error: AnalysisError | None = None

    @model_validator(mode="after")
    def check_terminal_state(self) -> AnalysisStatus:
        expected = {"complete": (True, False), "error": (False, True), "timeout": (False, True)}
        if (self.summary is not None, self.error is not None) != expected.get(
            self.state, (False, False)
        ):
            raise ValueError("summary/error contradict analysis state")
        return self


class IngestionError(Exception):
    """Only explicitly safe messages cross the public error boundary."""

    def __init__(
        self,
        code: str,
        public_message: str,
        http_status: int,
        retry_after_seconds: int | None = None,
    ):
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.http_status = http_status
        self.retry_after_seconds = retry_after_seconds


@dataclass
class SnapshotPair:
    metadata: PinnedPullRequest
    base_root: Path
    head_root: Path
    files: list[ChangedFile]
    diagnostics: list[str]
