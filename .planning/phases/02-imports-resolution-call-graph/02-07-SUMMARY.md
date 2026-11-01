---
phase: 02-imports-resolution-call-graph
plan: 07
subsystem: static-analysis
tags: [python, networkx, call-graph, evidence]

requires:
  - phase: 02-imports-resolution-call-graph
    provides: ResolvedCall, UnresolvedCall, and module-scoped symbols
provides:
  - Queryable NetworkX DiGraph with serializable symbol-node evidence
  - Explicit unresolved-call index outside graph traversal
  - Deterministic caller, callee, and reverse-reachability helpers
affects: [project-graph-orchestration, route-impact-analysis]

tech-stack:
  added: []
  patterns: [deduplicated call-site edge evidence, sorted graph-query results]

key-files:
  created: [backend/app/analysis/call_graph.py, backend/tests/test_call_graph.py]
  modified: []

key-decisions:
  - "Call-graph nodes retain only plain serializable source attributes, not Pydantic Symbol objects."
  - "Unresolved and uncertain calls are grouped by caller outside the DiGraph, so reverse traversal only sees verified edges."
  - "All named query helpers sort output and return an empty list for unknown symbols."

requirements-completed: [US-03]
duration: 8min
completed: 2026-11-01
---

# Phase 02 Plan 07: Call Graph Assembly Summary

**A deterministic, evidence-preserving NetworkX call graph: verified symbol relationships form a queryable DiGraph while unresolved and uncertain calls remain explicit, non-traversable evidence.**

## Performance

- **Duration:** 8 min
- **Tasks:** 2
- **Files created:** 2

## Accomplishments

- Added one serializable `DiGraph` node for each symbol, including classes, and only one edge per caller/callee pair with sorted, unique source lines.
- Prevented unknown endpoints from inventing partial nodes or edges; grouped every unresolved call by its enclosing symbol outside the graph.
- Added deterministic direct caller/callee and reverse-reachability helpers with safe empty results for isolated or unknown ids.

## Task Commits

1. **Task 1: build_call_graph** - `95e0864` (RED tests), `f917913` (implementation)
2. **Task 2: named query helpers** - `f40adbb` (RED tests), `6f25c22` (implementation), `f4a756a` (formatting)

## Files Created/Modified

- `backend/app/analysis/call_graph.py` - NetworkX graph assembly, unresolved evidence index, and deterministic query API.
- `backend/tests/test_call_graph.py` - Eight behavior tests for graph evidence and safe deterministic queries.

## Decisions Made

- Stored primitive node attributes rather than model instances so callers can serialize graph data without custom conversion.
- Left unresolved and uncertain entries deliberately outside the graph, preventing them from participating in impact traversal.
- Sorted every query result independently of insertion order to satisfy deterministic traversal requirements.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Kept Task 1 test collection independent of Task 2 exports**

- **Found during:** Task 1 GREEN verification
- **Issue:** The Task 1 test module imported Task 2's not-yet-created helpers, preventing Task 1 tests from collecting.
- **Fix:** Deferred those imports until Task 2's RED test change, preserving the intended TDD boundary.
- **Files modified:** `backend/tests/test_call_graph.py`
- **Commit:** `f917913`

**2. [Rule 1 - Bug] Corrected query-test line formatting**

- **Found during:** Task 2 acceptance verification
- **Issue:** One new test line exceeded the repository's 100-character Ruff limit.
- **Fix:** Wrapped the list comprehension, then re-ran all tests and Ruff.
- **Files modified:** `backend/tests/test_call_graph.py`
- **Commit:** `f4a756a`

**Total deviations:** 2 auto-fixed bugs. **Impact:** No scope expansion; both corrections preserve the planned graph contract and required verification gates.

## Verification

- `cd backend && uv run pytest tests/test_call_graph.py -v` — 8 passed
- `cd backend && uv run ruff check app/analysis/call_graph.py tests/test_call_graph.py` — passed
- `cd backend && uv run python -c "import networkx"` — passed
- Confirmed plain `DiGraph` use, required API definitions, and no FastAPI imports.

## Next Phase Readiness

- Plan 02-08 can now assemble parsed files, bindings, resolution results, and this call graph through a single project-level entry point.
- No blockers.

## Self-Check: PASSED

- FOUND: `backend/app/analysis/call_graph.py`
- FOUND: `backend/tests/test_call_graph.py`
- FOUND: `95e0864`, `f917913`, `f40adbb`, `6f25c22`, and `f4a756a`

---
*Phase: 02-imports-resolution-call-graph*
*Completed: 2026-11-01*
