---
phase: 02-imports-resolution-call-graph
plan: 09
subsystem: static-analysis
tags: [python, integration-tests, fixture, evidence]

requires:
  - phase: 02-imports-resolution-call-graph
    provides: bounded whole-project call-graph pipeline
provides:
  - Hand-written end-to-end resolved-edge inventory
  - Hand-written end-to-end unresolved-call evidence inventory
affects: [route-impact-analysis, evaluation]

tech-stack:
  added: []
  patterns: [explicit fixture inventories, exact evidence assertions]

key-files:
  created: [backend/tests/test_sample_fastapi_repo.py]
  modified: []

key-decisions:
  - "The fixture's dynamic getattr call is explicit unresolved evidence, not silently omitted."
  - "Fixture file-status assertions accept the intentional empty __init__.py alongside parsed files."

requirements-completed: [US-03]
duration: 3min
completed: 2026-11-01
---

# Phase 02 Plan 09: Fixture Integration Tests Summary

**The complete Phase 2 pipeline is pinned to an inspectable, hand-written inventory of ten verified edges and seven unresolved call sites.**

## Accomplishments

- Added module-scoped end-to-end analysis of the real sample FastAPI fixture.
- Asserted every verified edge and call-site line, rejected any extra edge, and proved inherited-method resolution through the public query API.
- Asserted the exact unresolved evidence inventory and certainty status, preserving source evidence rather than hiding unsupported dynamic calls.

## Task Commits

1. **Task 1: resolved-edge and hierarchy assertions** — `cd4e681`
2. **Task 2: unresolved evidence and file-status assertions** — `920a534`

## Verification

- `cd backend && uv run pytest tests/test_sample_fastapi_repo.py -v` — 6 passed.
- `cd backend && uv run pytest -q` — 124 passed.
- `cd backend && uv run ruff check .` — passed.
- `cd backend && uv sync --extra dev --no-editable && uv run codescope-graph ../fixtures/sample_fastapi_repo --compact` — JSON reports 10 edges and 7 unresolved entries.
- Plan key-link verification — 1/1 verified.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected the expected unresolved evidence inventory**

- **Found during:** Task 2 preflight against the real fixture.
- **Issue:** The plan listed six unresolved calls but omitted the fixture's `getattr(router_handlers, handler_name)` at `callers.py:24`. The existing raw-call and resolver contracts correctly record this bare builtin-like call as unresolved.
- **Fix:** Added `("callers:dispatch", "getattr", 24)` to the hand-written expected inventory; no parser or resolver behavior was suppressed or changed.
- **Files modified:** `backend/tests/test_sample_fastapi_repo.py`.
- **Commit:** `920a534`.

**2. [Rule 1 - Bug] Corrected the fixture file-status expectation**

- **Found during:** Task 2 preflight against the real fixture.
- **Issue:** The plan referred to nine all-`ok` files, while the fixture contains ten Python files, including a deliberate empty `__init__.py` whose status is correctly `empty`.
- **Fix:** Asserted all ten fixture files are either `ok` or the intentional `empty` status.
- **Files modified:** `backend/tests/test_sample_fastapi_repo.py`.
- **Commit:** `920a534`.

**Total deviations:** 2 auto-fixed test-contract corrections. **Impact:** The final inventory now faithfully describes the implemented, evidence-preserving pipeline.

## Next Phase Readiness

- Phase 2's fixture-driven resolved and unresolved behavior is fully regression-tested.
- Phase 3 can safely build route detection and reverse-impact paths on this verified graph foundation.

## Self-Check: PASSED

- FOUND: `backend/tests/test_sample_fastapi_repo.py`
- FOUND: `cd4e681` and `920a534`

