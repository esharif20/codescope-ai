---
phase: 05-report-json-evaluation
plan: "02"
subsystem: ingestion
tags: [reports, retention, concurrency, provenance, pytest]
requires:
  - phase: 05-report-json-evaluation
    provides: Schema v1 report contracts and deterministic report builder from plan 01
provides:
  - Atomic bounded retention of complete statuses and validated reports
  - Pre-cleanup report assembly and post-cleanup successful publication
affects: [05-04-report-api, live-analysis]
tech-stack:
  added: []
  patterns: [lock-protected report publication, canonical serialized report byte limits]
key-files:
  created: []
  modified:
    - backend/app/ingestion/runtime.py
    - backend/app/ingestion/pipeline.py
    - backend/app/ingestion/settings.py
    - backend/tests/test_analysis_runtime.py
    - backend/tests/test_pr_pipeline.py
key-decisions:
  - "Require a report on every successful internal completion and validate it before any terminal mutation."
  - "Derive summary route counts from unique report registrations and preserve existing summary serialization."
patterns-established:
  - "Build source evidence inside the snapshot context; publish only after cleanup and final deadline validation."
requirements-completed: [US-11]
duration: 3min
completed: 2026-11-01
---

# Phase 5 Plan 2: Live Report Retention Summary

**Live analyses retain complete pinned evidence reports atomically with status after temporary source cleanup, with shared expiry and strict serialized byte limits.**

## Performance

- **Duration:** Approximately 3 minutes
- **Completed:** 2026-11-01
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added mandatory report publication, identity/provenance/change/count consistency checks, defensive copies, safe report readiness errors, and shared terminal TTL/eviction under the registry lock.
- Added a strict positive, lower-only 2 MiB report ceiling, including the shared canonical JSON final newline; preserved the existing independent summary limit.
- Integrated full report assembly while base/head sources exist, with successful publication after cleanup and final deadline validation.
- Covered polling races, cleanup ownership, removed/renamed paths, unrelated changes, partial diagnostics, both output limits, and assembly/cleanup/publication failure paths.

## Task Commits

1. **Task 1: Retain reports atomically with terminal statuses** — `4902292` (test, RED), `e5526c0` (feat, GREEN).
2. **Task 2: Build reports before cleanup and publish only after it** — `5c5c08c` (test, RED), `1923795` (feat, GREEN).

## Files Created/Modified

- `backend/app/ingestion/runtime.py` — Report validation, atomic publication, defensive retrieval, shared pruning and safe report errors.
- `backend/app/ingestion/settings.py` — Lower-only `max_report_bytes` setting and existing-loop environment parsing.
- `backend/app/ingestion/pipeline.py` — Pinned report input conversion, source-time assembly, report-derived registration counts and post-cleanup publication.
- `backend/tests/test_analysis_runtime.py` — Retention, copies, exact byte boundaries, invalid inputs, concurrent readers and settings checks.
- `backend/tests/test_pr_pipeline.py` — Local-source reports, pinned evidence, races, cleanup faults, timeouts and result limits.

## Verification

- RED runtime run: 12 failed, 7 passed because report retention and the new setting were not implemented.
- RED pipeline run: 11 failed, 12 passed because report assembly/publication was not implemented.
- `cd backend && uv run --no-sync python -m pytest tests/test_analysis_runtime.py tests/test_pr_urls.py -q` — 70 passed after Task 1.
- `cd backend && uv run --no-sync python -m pytest tests/test_pr_pipeline.py tests/test_analysis_runtime.py tests/test_analysis_api.py tests/test_pr_urls.py -q` — 131 passed after Task 2.
- `uv run --no-sync ruff check` on all five changed Python files — passed; Ruff formatting applied.
- Reviewed every internal `complete` call site; all pass the mandatory report argument.
- Stub scan found no TODO, FIXME or placeholder implementations. Empty dictionaries initialize real registry stores; empty report revisions appear only in intentional minimal runtime test inputs.

## Decisions Made

Followed the planned shared-lock storage, canonical byte budget and cleanup-before-publication design. Report changes use canonical ordering, while existing summary ordering remains unchanged; consistency checks compare change content independently of ordering.

## Deviations from Plan

None — plan executed as written. Shared STATE, ROADMAP and REQUIREMENTS updates are reserved for the parent orchestrator to avoid concurrent tracker edits.

## Issues Encountered

One initial pipeline assertion assumed report and summary change ordering matched. The report builder intentionally canonicalizes findings, so the test now compares sorted identities while runtime validation checks complete canonical change content.

## User Setup Required

None — no dependencies, infrastructure, network calls or external service configuration added.

## Next Phase Readiness

Report retrieval is ready for the report API plan. Retention remains ephemeral and bounded by existing terminal count and TTL limits. No new blockers or approval decisions.

## Self-Check: PASSED

Confirmed the summary and all five modified Python files exist, all four task commits resolve, and the owned-file diff has no whitespace errors.

---
*Phase: 05-report-json-evaluation*
*Completed: 2026-11-01*
