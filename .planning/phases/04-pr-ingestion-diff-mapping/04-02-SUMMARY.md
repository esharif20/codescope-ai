---
phase: 04-pr-ingestion-diff-mapping
plan: 02
subsystem: ingestion
tags: [github, urllib, snapshots, provenance, security, tdd]
requires:
  - phase: 04-01
    provides: Validated PR/revision/change contracts and bounded immutable settings
provides:
  - Bounded redirect-disabled GitHub REST client with public repository provenance
  - Target-base, merge-base and head revision pinning with repeated metadata race checks
  - Complete Python snapshots verified against immutable all-language tree differences
  - Private cleanup-owning source roots and verified Git blob bytes
affects: [04-04, 04-05]
tech-stack:
  added: []
  patterns: [injected stdlib transport, owning snapshot context manager, immutable blob verification]
key-files:
  created:
    - backend/app/ingestion/github.py
    - backend/app/ingestion/snapshots.py
    - backend/tests/test_github_ingestion.py
    - backend/tests/test_snapshots.py
  modified: []
key-decisions:
  - Only immutable compare records establish renames; mutable PR records corroborate paths/status/count.
  - Compare complete file identities and modes across both recursive trees before downloading Python sources.
  - Reuse verified identical blob bytes within one bounded analysis while counting both snapshot sizes.
patterns-established:
  - Transport receives a locally built urllib Request plus bounded keyword timeout and returns a closable stream.
  - SnapshotPair roots are valid only within fetch_snapshots consumer context.
requirements-completed: [US-01, US-09, US-12]
duration: 6min
completed: 2026-11-01
---

# Phase 4 Plan 2: GitHub Ingestion and Immutable Snapshots Summary

**Public PR revision pinning and complete blob-verified Python snapshots, with bounded REST reads and automatic source cleanup.**

## Performance

- **Duration:** Approximately 6 min
- **Started:** 2026-11-01T16:41:30Z
- **Completed:** 2026-11-01T16:47:21Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added a mockable stdlib client that restricts requests to validated API paths, refuses redirects, keeps caller and upstream credentials separate, closes response streams, and enforces request/body/deadline limits.
- Rechecked allowlisted base and metadata-identified public head repository identities, pinned target-base/merge-base/head SHAs, corroborated complete changed-file counts and repeated metadata checks before snapshot delivery.
- Validated full recursive tree inventories across all languages, proved comparison coverage including mode changes and renames, and downloaded all permitted Python files including unchanged callers and base-only deleted source.
- Verified Base64 encoding, reported sizes, object SHAs and actual Git blob SHA1 before writing ordinary private files; rejected unsafe paths, portable Unicode/case collisions, symlinks, submodules, incomplete inventories and exceeded limits.
- Confirmed both temporary roots disappear after ordinary completion, consumer exceptions, upstream failures, deadline exceptions and metadata races.

## Task Commits

1. **Task 1: Build allowlisted, bounded GitHub REST reads** — `463fc5b` (test), `42ed99f` (feat).
2. **Task 2: Materialize complete safe Python snapshots at immutable SHAs** — `c968ce9` (test), `cb6fedf` (feat, including additional malformed-response transport regressions).

## Files Created/Modified

- `backend/app/ingestion/github.py` — bounded GET transport, safe upstream errors, public provenance, immutable comparison and PR race checks.
- `backend/app/ingestion/snapshots.py` — complete tree verification, safe paths, blob validation, private regular source files and lifetime cleanup.
- `backend/tests/test_github_ingestion.py` — 39 mocked cases for transport, public/fork admission, immutable pinning, count limits, races and safe errors.
- `backend/tests/test_snapshots.py` — 42 cases for source completeness, rename/deletion, all-language inventories, file modes, paths, blob verification, ceilings and cleanup.

## Decisions Made

Followed the plan without adding dependencies. `GitHubClient.pin_pull_request(ref)` returns `(PinnedPullRequest, list[ChangedFile])`; `verify_pull_request(metadata)` rechecks the original identities. The injected transport is callable as `transport(request, timeout=bounded_seconds)` and exposes response `status`, `headers`, `read(size)` and `close()`.

`fetch_snapshots(ref, client, settings, *, check_budget=..., on_stage=...)` yields the existing `SnapshotPair` contract and owns both roots through the consumer lifetime. It emits `metadata` and `sources`. Immutable tree-derived old/new blob SHAs enrich the returned changed-file records. Per-analysis identical blob reuse saves requests without weakening SHA/size checks or cumulative snapshot-byte limits.

The configured changed-file ceiling is at most 100, so one locally constructed PR-files page suffices for every supported PR. Response Link URLs never control destinations; exact metadata count plus exhaustive immutable tree comparison detects missing changes.

## Verification

- Both TDD RED collections failed as expected with the missing implementation module before their corresponding implementation commits.
- `cd backend && uv run --no-sync python -m pytest tests/test_github_ingestion.py tests/test_snapshots.py -q` — **81 passed**.
- `cd backend && uv run --no-sync ruff check app/ingestion/github.py app/ingestion/snapshots.py tests/test_github_ingestion.py tests/test_snapshots.py` — **passed**.
- `git diff --check` — **passed**.
- Official GitHub REST documentation was checked for compare/tree/blob response semantics and the current `2026-03-10` version header. Every ingestion test uses in-memory HTTP fixtures; no live GitHub API call or repository source execution occurred.
- Stub scan across all four owned implementation/test files found no TODO/FIXME/placeholder content or unwired implementation stubs.

## Deviations from Plan

None in implementation scope. The parent orchestrator owns shared STATE/ROADMAP/REQUIREMENTS updates and the phase-level report, so this executor leaves those trackers untouched as assigned.

## Issues Encountered

None. No dependencies, infrastructure, pushes, repository imports or repository commands were introduced.

## User Setup Required

None for offline validation. Live admission uses the settings established in Plan 04-01; GitHub's optional upstream token stays independent from the caller access token.

## Next Phase Readiness

Plan 04-04 can combine snapshot lifetime ownership with the mapper and runtime budget callbacks. No shared-contract changes are required. The orchestrator runs the complete backend checks after parallel work is reconciled.

## Self-Check: PASSED

Confirmed all four created implementation/test files and this summary exist. Confirmed commits `463fc5b`, `42ed99f`, `c968ce9` and `cb6fedf` exist in git history.
