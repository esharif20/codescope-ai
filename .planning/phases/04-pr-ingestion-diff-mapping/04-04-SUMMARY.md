---
phase: 04-pr-ingestion-diff-mapping
plan: 04
subsystem: ingestion
tags: [runtime, concurrency, deadlines, static-analysis, provenance, tdd]
requires:
  - phase: 04-02
    provides: Bounded GitHub client and cleanup-owning immutable snapshots
  - phase: 04-03
    provides: Local diff mapping and revision-specific changed-symbol evidence
provides:
  - Thread-safe bounded ephemeral analysis registry and cooperative monotonic deadline
  - Synchronous snapshot-to-impact pipeline with independent base/head seeds and counts
  - Cooperative budget callbacks throughout project graph and route orchestration
affects: [04-05, 05-evidence-grounded-reports]
tech-stack:
  added: []
  patterns: [exclusive same-process admission, cleanup-before-publication, revision-separated analysis]
key-files:
  created:
    - backend/app/ingestion/runtime.py
    - backend/app/ingestion/pipeline.py
    - backend/tests/test_analysis_runtime.py
    - backend/tests/test_pr_pipeline.py
  modified:
    - backend/app/analysis/project_graph.py
    - backend/app/analysis/project_routes.py
key-decisions:
  - Keep exclusive admission until actual work and snapshot cleanup exit, including timeout and error paths.
  - Publish success only after snapshot cleanup succeeds and a final deadline check passes.
  - Count unique affected registrations independently per revision; never combine base and head graph paths.
patterns-established:
  - Add keyword-only check_budget callbacks without changing existing positional graph/route APIs.
  - Public diagnostics retain validated relative locations and safe reason codes, excluding expressions and private roots.
requirements-completed: [US-01, US-02, US-09, US-12]
duration: 4min
completed: 2026-11-01
---

# Phase 4 Plan 4: Bounded Analysis Runtime and Revision Impacts Summary

**Exclusive observable analysis connects immutable source snapshots to independent base/head route impacts with cooperative deadlines and cleanup before success.**

## Performance

- **Duration:** Approximately 4 min
- **Completed:** 2026-11-01T16:51:45Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added an RLock-protected registry with atomic duplicate/busy rejection, defensive status copies, monotonic terminal TTL, bounded terminal retention and encoded-summary limits.
- Kept admission owned through timeout/error and explicit cleanup; active records cannot expire or evict while work remains active.
- Published metadata/source/mapping/base-impact/head-impact stages during synchronous work. Terminal records never regress.
- Seeded base with old identities and head with new identities; preserved old/new pinned source references and conservative partial/truncation diagnostics.
- Propagated budget checks through bounded file, import, call, route and impact phases while retaining deterministic algorithms and existing public call forms.
- Sanitized diagnostic locations/reasons and withheld raw exceptions and source expressions. Repository source is parsed as data only.

## Task Commits

1. **Task 1: Exclusive status registry and deadline** — `6e468a1` (test), `44911c8` (feat).
2. **Task 2: Two-revision impacts and cooperative budgets** — `10188f7` (test), `af872ef` (feat).

## Files Created/Modified

- `backend/app/ingestion/runtime.py` — Monotonic deadline and thread-safe bounded status/admission registry.
- `backend/app/ingestion/pipeline.py` — Live admission, snapshot lifetime, revision mapping/impact analysis, sanitized summaries and safe terminal handling.
- `backend/app/analysis/project_graph.py` — Optional per-file and per-phase cooperative budget checks.
- `backend/app/analysis/project_routes.py` — Optional budget propagation through graph, route inventory and reverse impacts.
- `backend/tests/test_analysis_runtime.py` — Exact deadlines, duplicate races, defensive copies, monotonic states, TTL, retention and output bounds.
- `backend/tests/test_pr_pipeline.py` — Actual local mapping and graph analysis, removed/renamed identities, unrelated changes, source non-execution, progress polling, stage deadlines, physical cleanup and redaction.

## Decisions Made

Followed the proposed synchronous same-process design. `run_analysis(request, registry, settings, *, client_factory=GitHubClient)` reserves before its error handler, so duplicate/busy conflicts remain request-level errors and cannot overwrite an existing analysis. It returns terminal `AnalysisStatus` for admitted work. `AnalysisRegistry` exposes `reserve`, `update`, `complete`, `fail`, `get`, and `release`; IDs use the existing UUID contract. Settings remain immutable and limits are read through `settings.limits`.

Success is published after the owning snapshot context exits. Deadline checks do not forcibly interrupt Tree-sitter or native code: bounded work may overrun until its next cooperative check, retaining admission throughout. The HTTP integration must let synchronous request work finish when a caller disconnects; no detached thread, executor, queue or worker was added.

The original no-budget route call invokes `build_project_graph(root)` without extra keywords, preserving existing wrappers and unchanged Phase 3 tests. Explicit budget callbacks propagate through the new keyword-only argument.

## Verification

- Both TDD RED collections failed as expected on missing runtime/pipeline modules before implementation.
- Focused runtime/pipeline/graph/routes/fixture run before the final two added regressions: **45 passed**.
- `cd backend && uv run --no-sync python -m pytest -q` — **515 passed**.
- `cd backend && uv run --no-sync ruff check app tests` — **passed**.
- `git diff --check` — **passed**.
- Stub scan of all six owned implementation/test files found no TODO/FIXME/placeholder text or unwired functionality. The no-budget callback deliberately does nothing for backward-compatible callers.

## Deviations from Plan

None in implementation scope. The parent orchestrator owns STATE, ROADMAP, REQUIREMENTS and TASKS updates and their metadata commit; this executor leaves those shared trackers untouched as assigned.

## Issues Encountered

Initial focused verification exposed a new keyword reaching an existing one-argument test wrapper. Preserved the existing no-budget call form and reran the unchanged tests successfully. Initial formatting/import checks were corrected before final verification. No authentication gates occurred.

## Known Stubs

None.

## User Setup Required

None for offline verification. Live settings and access controls retain the prior plan contracts.

## Next Phase Readiness

Plan 04-05 can call the synchronous pipeline and poll UUID-addressed defensive status snapshots in the same process. API dependency approval remains its explicit checkpoint; no dependencies, network calls, infrastructure, source execution or pushes occurred here. Status is ephemeral and has no process-restart recovery promise.

## Self-Check: PASSED

Confirmed all six implementation/test files and this summary exist. Confirmed commits `6e468a1`, `44911c8`, `10188f7` and `af872ef` exist in git history. The orchestrator owns shared tracking updates.
