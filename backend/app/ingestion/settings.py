"""Immutable, fail-closed configuration with ceilings that can only be lowered."""

from __future__ import annotations

import os
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.ingestion.models import IngestionError, validate_repository


class Limits(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis_timeout_seconds: float = Field(default=60, gt=0, le=60, allow_inf_nan=False)
    http_timeout_seconds: float = Field(default=10, gt=0, le=10, allow_inf_nan=False)
    max_http_requests: int = Field(default=200, gt=0, le=200, strict=True)
    max_json_bytes: int = Field(default=2 * 1024**2, gt=0, le=2 * 1024**2, strict=True)
    max_tree_entries: int = Field(default=2000, gt=0, le=2000, strict=True)
    max_changed_files: int = Field(default=100, gt=0, le=100, strict=True)
    max_python_files_per_revision: int = Field(default=100, gt=0, le=100, strict=True)
    max_source_file_bytes: int = Field(default=128 * 1024, gt=0, le=128 * 1024, strict=True)
    max_total_source_bytes: int = Field(default=8 * 1024**2, gt=0, le=8 * 1024**2, strict=True)
    max_summary_bytes: int = Field(default=2 * 1024**2, gt=0, le=2 * 1024**2, strict=True)
    max_terminal_records: int = Field(default=20, gt=0, le=20, strict=True)
    terminal_ttl_seconds: float = Field(default=3600, gt=0, le=3600, allow_inf_nan=False)
    max_active_analyses: int = Field(default=1, gt=0, le=1, strict=True)


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed_repositories: frozenset[str] = Field(default_factory=frozenset)
    live_access_token: SecretStr | None = Field(default=None, repr=False)
    github_token: SecretStr | None = Field(default=None, repr=False)
    limits: Limits = Field(default_factory=Limits)

    @field_validator("allowed_repositories")
    @classmethod
    def canonical_repositories(cls, value: frozenset[str]) -> frozenset[str]:
        return frozenset(validate_repository(repository) for repository in value)

    @field_validator("live_access_token", "github_token")
    @classmethod
    def nonblank_secret(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None or not value.get_secret_value().strip():
            return None
        return value

    @property
    def live_enabled(self) -> bool:
        return bool(self.allowed_repositories and self.live_access_token)

    def require_live_enabled(self) -> None:
        if not self.live_enabled:
            raise IngestionError(
                "live_analysis_disabled", "Live analysis is currently disabled.", 503
            )

    @classmethod
    def from_env(cls, environment: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if environment is None else environment
        raw_repositories = env.get("CODESCOPE_ALLOWED_REPOSITORIES", "").strip()
        repositories = (
            frozenset(part.strip() for part in raw_repositories.split(","))
            if raw_repositories
            else frozenset()
        )
        # Explicit parsing permits strict integer fields while rejecting decimal/bool strings.
        limit_values: dict[str, int | float] = {}
        for name, field in Limits.model_fields.items():
            raw = env.get("CODESCOPE_" + name.upper())
            if raw is not None:
                limit_values[name] = int(raw) if field.annotation is int else float(raw)
        return cls(
            allowed_repositories=repositories,
            live_access_token=env.get("CODESCOPE_LIVE_ACCESS_TOKEN"),
            github_token=env.get("GITHUB_TOKEN"),
            limits=Limits(**limit_values),
        )
