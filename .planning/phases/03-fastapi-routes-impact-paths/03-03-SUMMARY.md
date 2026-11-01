---
phase: 03-fastapi-routes-impact-paths
plan: 03
subsystem: analysis
tags: [networkx, bfs, routes, impact, evidence]
requires:
  - phase: 02
    provides: Verified caller-to-callee graph and call-site locations
  - phase: 03-01
    provides: RouteRegistration, ImpactPath and ImpactResult contracts
provides:
  - Deterministic canonical shortest supported route-impact paths
  - Invocation-wide node and output caps with explicit omission reporting
  - Source-located call-site evidence and preserved registration evidence
affects: [03-04, report-generation]
tech-stack:
  added: []
  patterns: [iterative reverse BFS, sorted first discovery, complete bounded evidence chains]
key-files:
  created:
    - backend/app/analysis/impact.py
    - backend/tests/test_impact.py
  modified: []
key-decisions:
  - "Visited-node budget counts first discoveries per change, including roots, across the entire invocation."
  - "Reaching either cap is not truncation until a node search or complete route result is actually omitted."
patterns-established:
  - "Impact paths follow handler-to-change direction and retain every unique call-site line for each verified edge."
requirements-completed: []
duration: 3min
completed: 2026-11-01
---

# Phase 3 Plan 3: Bounded Route Impact Paths Summary

**Reverse BFS returns canonical shortest handler-to-change chains with complete call-site and registration evidence, deterministic ordering and explicit traversal/output limits.**

## Performance

- **Duration:** 3 min (approximate)
- **Started:** 2026-11-01T16:12:00Z (approximate)
- **Completed:** 2026-11-01T16:15:00Z (approximate)
- **Tasks:** 2
- **Files modified:** 2 implementation/test files

## Accomplishments

- Pure `find_affected_routes` consumes the existing graph and registration contracts without altering graph data, unresolved records or routes.
- Sorted unique changes, sorted predecessor discovery and sorted registration matching select one reproducible shortest supported chain per registration/change pair.
- Every edge retains the caller file and all unique call-site lines. Direct handler changes produce a zero-edge chain; disconnected changes and unresolved candidates produce no impacts.
- Invocation-wide limits of 10,000 node discoveries and 1,000 complete paths retain already complete results and mark actual omissions explicitly.
- Twenty-five tests cover cycles, self-loops, diamonds, repeated changes, unknown ids, distinct methods/mounts/apps, insertion order, immutability, exact limits including zero/one, and an iterative 1,100-symbol chain.

## Task Commits

1. **Task 1: Trace canonical paths with complete call-site evidence** — `d64d6b4` (test), `37fc4f5` (feat).
2. **Task 2: Bound cycles, search work and output** — `01766c1` (test), `67e8beb` (feat).

## Files Created/Modified

- `backend/app/analysis/impact.py` — Pure bounded reverse traversal and evidence-path assembly.
- `backend/tests/test_impact.py` — Evidence, determinism, cap and regression checks using synthetic graphs; no repository fixture execution.

## Decisions Made

Count roots and rediscoveries for separate changes against the same invocation-wide budget. Preserve complete paths from the discovered parent map when subsequent node work is omitted. Exact cap equality alone does not imply truncation; a blocked discovery or additional matching registration does.

## Deviations from Plan

No implementation deviations. Used the coordinator-required `uv run --no-sync` and `git commit --no-verify`; no dependencies changed. Shared STATE.md, ROADMAP.md and REQUIREMENTS.md updates remain with the coordinator during parallel execution. US-04 remains incomplete until the registration and integration plans finish.

## Verification

- Task 1 RED: collection failed because `app.analysis.impact` did not exist. GREEN: **6 passed**.
- Task 2 RED: **15 failed, 8 passed**, with failures identifying missing cap constants. GREEN and additional boundary/deep-chain cases: **25 passed**.
- `cd backend && uv run --no-sync python -m pytest tests/test_impact.py -q`: **25 passed**.
- `cd backend && uv run --no-sync python -m pytest -q`: **219 passed**.
- `cd backend && uv run --no-sync ruff check app/analysis/impact.py tests/test_impact.py`: **passed**.
- `git diff --check`: **passed**.
- Whole-backend Ruff found one concurrent, out-of-ownership E501 at `backend/tests/test_route_resolver.py:65`; reported to the coordinator and left to the resolver agent. No claim of global Ruff success.
- Stub scan found only the populated edge accumulator and assertions for intentionally empty results; no unfinished implementation stubs.

## Issues Encountered

No interface gaps, authentication gates or dependency changes. A test line-length issue in the owned file was corrected before the final commit. Concurrent resolver edits were preserved.

## User Setup Required

None.

## Next Phase Readiness

Plan 04 can invoke `find_affected_routes(call_graph, registrations, changed_symbols)` and expose `ImpactResult`. Results describe static potential impact through verified edges, not runtime execution or all possible paths. Revision diffs and removed-symbol mapping remain Phase 4 scope.

## Self-Check: PASSED

Both created implementation/test files exist. All four task commit hashes were verified in Git history. The impact suite and full backend suite ran successfully; owned-file Ruff passed. Shared planning updates are intentionally delegated to the coordinator.
