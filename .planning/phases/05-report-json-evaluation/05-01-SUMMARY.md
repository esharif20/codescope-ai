---
phase: 05-report-json-evaluation
plan: "01"
subsystem: analysis
tags: [pydantic, reports, provenance, deterministic-json, sha256]
requires:
  - phase: 04-pr-ingestion-diff-mapping
    provides: Immutable snapshots, pinned source references and two-revision change mapping
  - phase: 03-route-impact
    provides: Verified route registrations and evidence-backed impact paths
provides:
  - Validated schema-v1 reports with separate base/head graphs and explicit uncertainties
  - Source-validated deterministic report assembly with pinned or controlled evidence
  - Shared canonical UTF-8 JSON bytes and source-manifest SHA256 helper
affects: [report-retention, evaluation, demo-reports, report-api]
tech-stack:
  added: []
  patterns: [Discriminated provenance unions, fail-closed verified evidence, canonical JSON bytes]
key-files:
  created:
    - backend/app/reporting/__init__.py
    - backend/app/reporting/models.py
    - backend/app/reporting/builder.py
    - backend/tests/test_report_models.py
    - backend/tests/test_report_builder.py
  modified: []
key-decisions:
  - "Canonical report bytes use sorted compact JSON, literal UTF-8, no non-finite numbers and exactly one final newline."
  - "Controlled source inventory includes retained empty and skipped files from the analysis file-status maps; SHA256 manifests are never represented as Git commits."
patterns-established:
  - "Verified evidence failures raise safe report_evidence_invalid errors; invalid uncertainty locations remain generic uncertainties."
  - "Unresolved calls and candidates remain outside verified graph traversal."
requirements-completed: [US-11]
duration: 4min
completed: 2026-11-01
---

# Phase 5 Plan 1: Report Contracts and Assembly Summary

**Schema-v1 base/head reports preserve source-backed graph paths, explicit uncertainties and revision-correct GitHub or controlled provenance.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-11-01T17:28:20Z
- **Completed:** 2026-11-01T17:32:20Z
- **Tasks:** 2
- **Files created:** 5 implementation/test files and this summary

## Accomplishments

- Added strict discriminated report contracts with independent defaults, source-range validation, revision/provenance compatibility and verified graph/path referential checks.
- Added deterministic source-only assembly preserving call-site lines, registrations, handler/decorator evidence, fork-head links and zero-edge paths.
- Added shared canonical serialization and length-prefixed SHA256 manifests, plus budget checks and an exact byte limit including the final newline.
- Preserved safe diagnostics and all analysis omission flags without converting candidates into verified edges.

## Task Commits

1. **Task 1 RED: Report contract tests** — `c6fac96`
2. **Task 1 GREEN: Report/provenance contracts** — `79a05c4`
3. **Task 2 RED: Builder regression tests** — `535c39c`
4. **Task 2 GREEN: Deterministic source-backed assembly** — `7b6443f`

## Files Created/Modified

- `backend/app/reporting/__init__.py` — public contract exports.
- `backend/app/reporting/models.py` — schema v1 and provenance/reference consistency validation.
- `backend/app/reporting/builder.py` — canonical bytes, source manifests and evidence-checked report construction.
- `backend/tests/test_report_models.py` — seven boundary-validation tests.
- `backend/tests/test_report_builder.py` — sixteen source/evidence, determinism, limit, safety and omission tests.

## Verification

- Both RED test runs failed at collection for their then-missing implementation module, as expected.
- `uv run --no-sync python -m pytest tests/test_report_models.py tests/test_report_builder.py -q` — **23 passed**, including five review regressions added after initial completion.
- `uv run --no-sync ruff check app/reporting tests/test_report_models.py tests/test_report_builder.py` — **passed**.
- `git diff --check` — **passed** before the final source-only nonexecution regression was added; Ruff and focused tests passed after that addition.
- Source containing a marker-writing payload and top-level raise was parsed only; the marker was never created.
- No dependencies, network calls, infrastructure or source execution were introduced.

## Decisions Made

Followed the plan's exact shared JSON and provenance contracts. Controlled snapshot inventory uses the union of both existing file-status inventories for that revision, retaining empty/skipped source files while excluding unrelated fixture siblings.

## Deviations from Plan

The two tasks followed the planned RED/GREEN flow. Shared tracker and requirement updates are delegated to the parent orchestrator, as explicitly assigned.

### Review Corrections

**1. [Rule 1 - Bug] Preserve trusted root aliases during relative-path conversion**
- **Found during:** Independent review after Task 2.
- **Issue:** Resolving the trusted root before converting analyzer paths rejected lexical ancestor aliases such as macOS `/var` versus `/private/var`.
- **Fix:** Retain the original absolute trusted root alongside its resolved root; accept either spelling while validating every source suffix for traversal and symlinks.
- **Files:** `backend/app/reporting/builder.py`, `backend/tests/test_report_builder.py`.
- **Verification:** Alias and original snapshots produce identical canonical report bytes.

**2. [Rule 1 - Bug] Require route handler evidence to match its verified graph node**
- **Found during:** Independent review after Task 2.
- **Issue:** An otherwise valid source range could contradict the handler node's actual file/range, and declaration identity could contradict registration identity.
- **Fix:** Validate declaration handler identity during assembly and compare report handler evidence exactly with the referenced node source during model validation.
- **Files:** Reporting models/builder and both focused test files.
- **Verification:** Range, file and declaration-identity tampering fail with `report_evidence_invalid`; direct schema validation rejects contradictory handler evidence.
- **Commit:** Recorded by the follow-up `fix(05-01)` commit containing these corrections and this summary update.

## Issues Encountered

None. Ruff formatting resolved initial line-length findings before the successful final lint/test run.

## Known Stubs

None. Empty list defaults are intentional schema defaults; report graph data is assembled from the actual retained analyses.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

Report retention and offline evaluation can now consume `build_report`, `canonical_json_bytes`, `snapshot_digest` and the exported report contracts. US-11 remains a phase-wide delivery; this plan supplies its report foundation.

## Self-Check: PASSED

All five implementation/test files and this summary exist. All four task commit hashes were verified in Git history. Focused tests and Ruff passed successfully.
