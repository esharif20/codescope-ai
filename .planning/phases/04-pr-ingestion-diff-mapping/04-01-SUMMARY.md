---
phase: 04-pr-ingestion-diff-mapping
plan: 01
subsystem: ingestion
tags: [pydantic, github, validation, provenance, security]
requires:
  - phase: 01-python-symbol-extraction
    provides: Framework-independent SymbolKind contract
provides:
  - Validated PR, revision, source, diff-mapping and analysis-status contracts
  - Strict allowlisted GitHub PR URL admission
  - Immutable fail-closed live settings and lower-only resource ceilings
affects: [04-02, 04-03, 04-04, 04-05]
tech-stack:
  added: []
  patterns: [Pydantic v2 boundary validation, private snapshot dataclass, SecretStr configuration]
key-files:
  created:
    - backend/app/ingestion/__init__.py
    - backend/app/ingestion/models.py
    - backend/app/ingestion/settings.py
    - backend/app/ingestion/urls.py
    - backend/tests/test_ingestion_models.py
    - backend/tests/test_pr_urls.py
  modified: []
key-decisions:
  - Preserve target-base, merge-base and head SHAs plus base/head repository provenance independently.
  - Canonicalize validated owner/repository identifiers to lowercase for exact allowlist membership.
  - Expose all numerical ceilings through immutable Limits; environment overrides may only lower them.
patterns-established:
  - Caller access and upstream GitHub credentials use separate SecretStr fields.
  - IngestionError exposes only explicit safe messages and stable error codes.
requirements-completed: [US-01, US-09, US-12]
duration: 7min
completed: 2026-11-01
---

# Phase 4 Plan 1: Ingestion Contracts and Admission Summary

**Pinned revision evidence and validated analysis statuses with strict GitHub PR admission and immutable fail-closed settings.**

## Performance

- **Duration:** Approximately 7 min
- **Completed:** 2026-11-01T16:40:33Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added all named shared contracts, including `base_repository`, `head_repository` and independently validated target-base, analysis-base and head SHAs.
- Validated source locations, changed-file/symbol sides and contradictory analysis terminal states; preserved JSON UUID and UTC timestamp round trips.
- Rejected malformed URL forms before transport, canonicalized exact allowlist membership and disabled live submissions without caller access plus an allowlist.
- Added independent mutable defaults, private snapshot roots and immutable bounded configuration without adding dependencies.

## Task Commits

1. **Task 1: Define pinned-ingestion and status contracts** — `8cc4622` (test), `83240c0` (feat), `327d99e` (test).
2. **Task 2: Validate PR URLs and fail-closed live settings** — `17c6d5d` (test), `f953ca0` (feat).

## Files Created/Modified

- `backend/app/ingestion/__init__.py` — Framework-independent ingestion package.
- `backend/app/ingestion/models.py` — PR identifiers, pinned repositories/revisions, changed files/symbols, source references, mapping, statuses, errors and private snapshot pair.
- `backend/app/ingestion/settings.py` — Frozen `Settings`/`Limits`, safe secrets and environment parsing.
- `backend/app/ingestion/urls.py` — Raw URL validation and exact allowlist admission.
- `backend/tests/test_ingestion_models.py` — Contract, provenance, JSON, defaults and framework-independence tests.
- `backend/tests/test_pr_urls.py` — Negative URL matrix, credentials, fail-closed configuration and numerical ceilings.

## Decisions Made

Followed the proposed plan defaults. `Settings.from_env(environment=None)` accepts an injected environment mapping. `Settings.live_enabled` and `require_live_enabled()` guard live admission; `github_token` never enables caller access. Invalid configured repository identifiers raise validation errors rather than admitting unrestricted requests.

The downstream configuration API is `Settings.allowed_repositories`, `Settings.live_access_token`, `Settings.github_token`, and `Settings.limits`. Secrets are `SecretStr | None` and omitted from repr. Limits are frozen and default to:

| Field | Ceiling |
| --- | ---: |
| analysis_timeout_seconds | 60 |
| http_timeout_seconds | 10 |
| max_http_requests | 200 |
| max_json_bytes | 2097152 |
| max_tree_entries | 2000 |
| max_changed_files | 100 |
| max_python_files_per_revision | 100 |
| max_source_file_bytes | 131072 |
| max_total_source_bytes | 8388608 |
| max_summary_bytes | 2097152 |
| max_terminal_records | 20 |
| terminal_ttl_seconds | 3600 |
| max_active_analyses | 1 |

Each limit accepts a `CODESCOPE_<UPPERCASE_FIELD>` environment override, validated against its ceiling. Transport and service consumers apply these ceilings to actual requests and retained state in subsequent plans.

## Verification

- Both TDD RED runs failed with the expected missing ingestion-module import before implementation.
- `cd backend && uv run --no-sync python -m pytest tests/test_pr_urls.py tests/test_ingestion_models.py -q` — **122 passed**.
- `cd backend && uv run --no-sync ruff check app/ingestion tests/test_ingestion_models.py tests/test_pr_urls.py` — **passed**.
- `git diff --check` — **passed**.
- Scanned owned implementation and tests for TODO/FIXME/placeholder patterns; no implementation stubs found.

## Deviations from Plan

None in implementation scope. The parent orchestrator owns shared STATE/ROADMAP/REQUIREMENTS updates and the phase-level completion report; this executor deliberately leaves those shared files untouched.

## Issues Encountered

None. No dependency installation, network request, fixture execution, infrastructure or push occurred.

## User Setup Required

No setup needed for offline validation. Live submissions later require `CODESCOPE_ALLOWED_REPOSITORIES` and `CODESCOPE_LIVE_ACCESS_TOKEN`; `GITHUB_TOKEN` is an optional separate upstream credential.

## Next Phase Readiness

Plans 04-02 and 04-03 can consume the committed contracts. Numerical budget enforcement belongs to the transport/service consumers; this plan supplies validated immutable ceilings and pre-transport admission. Root handles shared tracking updates.

## Self-Check: PASSED

Confirmed all six created implementation/test files and this summary exist. Confirmed commits `8cc4622`, `83240c0`, `327d99e`, `17c6d5d` and `f953ca0` exist in git history.
