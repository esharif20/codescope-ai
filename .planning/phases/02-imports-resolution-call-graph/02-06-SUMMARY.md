---
phase: 02-imports-resolution-call-graph
plan: 06
subsystem: static-analysis
tags: [python, call-resolution, inheritance, evidence]

requires:
  - phase: 02-imports-resolution-call-graph
    provides: RawCall, RawClassBases, resolved import bindings, and symbol identities
provides:
  - Deterministic repository-only class hierarchy index
  - Direct-call resolution with explicit unresolved and uncertain outcomes
affects: [call-graph-assembly, project-graph-orchestration, route-impact-analysis]

tech-stack:
  added: []
  patterns: [preorder hierarchy traversal, one-outcome-per-call-site resolution]

key-files:
  created: [backend/app/analysis/call_resolver.py, backend/tests/test_call_resolver.py]
  modified: []

key-decisions:
  - "Hierarchy traversal is iterative left-to-right preorder with cycle protection, not C3 MRO."
  - "Ambiguous bare calls become one uncertain record with sorted candidates; they never create graph edges."
  - "Only imports and lexical class hierarchy resolve calls; locals and parameters remain explicit gaps."

patterns-established:
  - "Every raw call produces exactly one resolved edge or unresolved/uncertain evidence record."
  - "Class bases and calls resolve only against repository symbols, never external packages."

requirements-completed: [US-03]
duration: 6min
completed: 2026-11-01
---

# Phase 02 Plan 06: Call and Hierarchy Resolution Summary

**Deterministic class-aware direct-call resolution that emits only defensible edges and preserves every ambiguous or unknowable call as source-located evidence.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-11-01T15:33:00Z
- **Completed:** 2026-11-01T15:39:03Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Built a repository-only class hierarchy index for same-module, imported, and module-alias base references.
- Resolved `self`/`cls`, bare, and whole-module-alias calls without type or variable tracking.
- Kept builtins, dynamic receivers, locals, parameters, external imports, and ambiguous bare calls out of the graph as explicit unresolved or uncertain entries.

## Task Commits

1. **Task 1: build_class_hierarchy (D-01 index)** - `5a3a919` (TDD tests), `7b26977` (implementation)
2. **Task 2: resolve_file_calls (D-01..D-04 call resolution)** - `5b327d5` (TDD tests), `5116137` (implementation)

**Plan metadata:** recorded in the final documentation commit.

## Files Created/Modified

- `backend/app/analysis/call_resolver.py` - Builds class-base links and resolves supported direct call shapes.
- `backend/tests/test_call_resolver.py` - Covers all hierarchy and call-resolution contracts, including a two-candidate uncertain call and no-variable-tracking cases.

## Decisions Made

- Used an explicit stack and visited set for class hierarchy traversal, preserving ordered base lookup while preventing cycles from hanging analysis.
- Kept uncertainty separate from resolved calls, with sorted candidate IDs and exactly one record per ambiguous call.
- Treated only whole-module import aliases as resolvable attribute receivers; any local or parameter receiver stays unresolved.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Repaired stale GSD progress prose**

- **Found during:** Final metadata update
- **Issue:** The GSD state commands advanced the numeric plan count but left the visible progress bar and next-plan reference at Plan 02-06.
- **Fix:** Aligned STATE.md and ROADMAP.md with the completed Plan 02-06 and next Plan 02-07.
- **Files modified:** `.planning/STATE.md`, `.planning/ROADMAP.md`
- **Verification:** Confirmed six Plan 02 summaries, the Plan 02-06 roadmap checkbox, and `6/9` roadmap progress agree.

**Total deviations:** 1 auto-fixed (1 bug).
**Impact on plan:** Metadata-only correction; resolver scope and implementation remain unchanged.

## Issues Encountered

- Ruff requested import normalization in the new resolver module; its mechanical fix was applied before the Task 2 implementation commit.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-07 can assemble `ResolvedCall` results into a NetworkX graph while retaining `UnresolvedCall` records outside graph traversal.
- No blockers. The resolver has no FastAPI dependency and the fixture repository was not executed.

## Self-Check: PASSED

- FOUND: `backend/app/analysis/call_resolver.py`
- FOUND: `backend/tests/test_call_resolver.py`
- FOUND: `5a3a919`, `7b26977`, `5b327d5`, and `5116137`

---
*Phase: 02-imports-resolution-call-graph*
*Completed: 2026-11-01*
