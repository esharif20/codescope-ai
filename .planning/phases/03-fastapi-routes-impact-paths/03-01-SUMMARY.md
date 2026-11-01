---
phase: 03-fastapi-routes-impact-paths
plan: 01
subsystem: analysis
tags: [tree-sitter, pydantic, routes, evidence]
requires:
  - phase: 02
    provides: Python symbol identities and raw imports
provides:
  - Seven route and impact evidence models
  - Source-only route decorators, receiver constructors and router includes
  - Module binding counts and structurally eligible import inventory
affects: [03-02, 03-03, 03-04]
tech-stack:
  added: []
  patterns: [iterative syntax traversal, fresh parser per call, conservative syntax evidence]
key-files:
  created:
    - backend/app/analysis/route_models.py
    - backend/app/analysis/routes.py
    - backend/tests/test_routes.py
  modified: []
key-decisions:
  - "Raw receiver constructor text remains unverified until import and registration resolution."
patterns-established:
  - "Eligible imports are parsed from individual direct-root nodes and retain original source locations."
requirements-completed: [US-04]
duration: 6min
completed: 2026-11-01
---

# Phase 3 Plan 1: Route Syntax and Evidence Summary

**Tree-sitter route syntax extraction preserves decorator, handler, constructor and include evidence while rejecting unsupported scopes and argument expansion.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-11-01T16:06:00Z (approximate)
- **Completed:** 2026-11-01T16:12:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Seven Pydantic models preserve complete route, registration and call-path evidence; line fields reject zero, and mutable defaults remain independent.
- Extracts all eight supported HTTP methods, stacked sync/async handler decorators, literal positional/keyword paths, constructor prefixes and router includes without executing source.
- Counts module bindings across control flow and excludes function/class bodies. Only structurally direct-root imports enter the eligible inventory.
- Starred positional and keyword arguments invalidate the complete affected record. Dynamic strings/prefixes, unsupported scopes, bare route decorators and malformed source carry diagnostics.

## Task Commits

1. **Task 1: Define route and impact evidence models** — `8f4c205` (test), `c5457cd` (feat).
2. **Task 2: Extract decorators, constructors and include calls** — `2c20886` (test), `e4dde1e` (feat).

## Files Created/Modified

- `backend/app/analysis/route_models.py` — Internal route and impact contracts, independent of FastAPI runtime.
- `backend/app/analysis/routes.py` — Raw syntax dataclasses and deterministic source-only extraction.
- `backend/tests/test_routes.py` — 30 model, syntax, scope, expansion and static fixture cases.

## Decisions Made

Raw receiver constructor text remains unverified until Plan 02 resolves constructor imports and registrations. Individual root import nodes are parsed separately, preserving structural eligibility even when source lines overlap other scopes.

## Deviations from Plan

None — plan executed as written. Used `uv run --no-sync` with the existing environment as instructed by the orchestrator; no dependencies were changed.

## Verification

- TDD model phase: missing module failed collection; after implementation, 3 model tests passed.
- TDD syntax phase: 25 new cases failed against the absent extractor; implementation made them pass.
- Final `uv run --no-sync python -m pytest -q`: **154 passed**, including **30 route/model tests**.
- Final `uv run --no-sync ruff check .`: **passed**.
- Fixture files were read as bytes only; no fixture module was imported or executed.
- Stub scan found only intentional empty accumulators/defaults and test assertions; no unfinished functionality.

## Issues Encountered

None. No authentication gates or external services were needed.

## User Setup Required

None.

## Next Phase Readiness

Plan 02 can consume `RouteSyntax` for registration verification; Plan 03 can consume the evidence models for impact traversal. US-04 requires those later plans and the integrated CLI before the user story is fully delivered.

## Self-Check: PASSED

All three created files exist. All four task commits were verified in Git history. The complete backend suite and Ruff checks passed.
