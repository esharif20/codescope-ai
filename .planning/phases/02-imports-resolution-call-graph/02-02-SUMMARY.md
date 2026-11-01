---
phase: 02-imports-resolution-call-graph
plan: 02
subsystem: testing
tags: [fixture, fastapi, python, tree-sitter, call-graph, test-data]

# Dependency graph
requires:
  - phase: 01-python-symbol-extraction
    provides: Tree-sitter-based single-file Python symbol extractor (backend/app/analysis/) that later plans in this phase build a cross-file layer on top of
provides:
  - "fixtures/sample_fastapi_repo/ -- a real, 10-file FastAPI-shaped Python package exercising every D-01..D-16 resolution rule from 02-CONTEXT.md in one coherent codebase"
  - "Exactly the 10 resolved call edges and 6 unresolved call sites enumerated in 02-02-PLAN.md's <interfaces> block, fixed and ready for later plans to assert against"
affects: [02-03-import-extraction, 02-04-call-site-extraction, 02-05-resolver, 02-06-call-graph, 02-09-fixture-integration-tests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fixture package is a parse target only -- never imported or executed by the real backend test suite (AGENTS.md rule 7, D-16)"
    - "Resolvable and unresolvable calls placed side by side in the same function body rather than quarantined (D-14)"

key-files:
  created:
    - fixtures/sample_fastapi_repo/__init__.py
    - fixtures/sample_fastapi_repo/main.py
    - fixtures/sample_fastapi_repo/services/__init__.py
    - fixtures/sample_fastapi_repo/services/base.py
    - fixtures/sample_fastapi_repo/services/auth.py
    - fixtures/sample_fastapi_repo/routes/__init__.py
    - fixtures/sample_fastapi_repo/routes/users.py
    - fixtures/sample_fastapi_repo/callers.py
    - fixtures/sample_fastapi_repo/tests/__init__.py
    - fixtures/sample_fastapi_repo/tests/test_services.py
  modified: []

key-decisions:
  - "Kept the task's explicit instruction to create fixtures/sample_fastapi_repo/tests/__init__.py (10th file), which is correct per D-13's 'roughly 8-10 files' fixture-size target; the plan's own verify/acceptance-criteria text hardcoding a count of 9 was a stale bug in the plan, not a reason to omit the file"

patterns-established:
  - "Fixture realism: every file mixes at least one resolvable pattern with at least one deliberately-unresolvable pattern in the same function body (D-14), never isolated into obviously-named toy modules"

requirements-completed: [US-03]

# Metrics
duration: 3min
completed: 2026-11-01
---

# Phase 02 Plan 02: Sample FastAPI Fixture Repo Summary

**Built the 10-file `fixtures/sample_fastapi_repo/` package (services, routes, callers, tests) that deterministically exercises every import/call-resolution rule (D-01 through D-16) from 02-CONTEXT.md, fixing the exact 10 resolved edges and 6 unresolved call sites later Phase 2 plans must resolve and assert against.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-11-01T14:53:00Z (approx, first task commit)
- **Completed:** 2026-11-01T14:55:06Z
- **Tasks:** 2/2 completed
- **Files modified:** 10 created

## Accomplishments

- Built `services/base.py` + `services/auth.py` exercising inherited self-calls (D-01), own-class self-calls, and a one-hop `__init__.py` re-export (D-06)
- Built `main.py` + `routes/users.py` exercising the external-import case (D-05, `fastapi`) and a star-import re-export expansion (D-07)
- Built `routes/users.py` + `callers.py` with two route handlers and five distinct caller functions, each pairing a resolved call with an unresolved one in the same function body (D-14), including the repeated-callee single-edge/two-call-site case (D-10) and a getattr-based dynamic dispatcher
- Added the fixture's own never-executed test file (`tests/test_services.py`, `tests/__init__.py`) per D-16, contributing one more resolved edge (construction call) and one more unresolved edge (untyped-local-variable method call)
- Confirmed, by direct inspection, that the fixture contains exactly the 10 resolved edges and 6 unresolved call sites enumerated in the plan's `<interfaces>` block (see Verification below)

## Task Commits

Each task was committed atomically:

1. **Task 1: Core package -- services layer with inheritance + external import** - `d2eae79` (feat)
2. **Task 2: Routes + callers -- star import, cross-package calls, and every unresolved pattern** - `2ff680f` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `fixtures/sample_fastapi_repo/__init__.py` - package docstring marking the fixture as a parse-only target
- `fixtures/sample_fastapi_repo/main.py` - FastAPI app wiring; external import (D-05) + relative import of `routes.users`
- `fixtures/sample_fastapi_repo/services/base.py` - `BaseService.audit()`, the inherited helper method for D-01
- `fixtures/sample_fastapi_repo/services/auth.py` - `AuthService(BaseService)` with inherited self-call + own-class self-call; module-level `get_current_user()`
- `fixtures/sample_fastapi_repo/services/__init__.py` - one-hop `__init__.py` re-export of the auth surface (D-06)
- `fixtures/sample_fastapi_repo/routes/__init__.py` - star-import of the services package surface (D-07)
- `fixtures/sample_fastapi_repo/routes/users.py` - `get_user`/`update_user` handlers, each mixing a resolved call with an unresolved untyped-object call (D-14)
- `fixtures/sample_fastapi_repo/callers.py` - five caller functions covering the D-10 dedup case plus the getattr-dispatch, callback-parameter, and untyped-parameter unresolved patterns (D-14)
- `fixtures/sample_fastapi_repo/tests/__init__.py` - empty, gives `tests/` the same subpackage shape as `services/`/`routes/`
- `fixtures/sample_fastapi_repo/tests/test_services.py` - fixture's own test file (D-16), parse-only, never collected by the real pytest suite

## Decisions Made

- Followed 02-CONTEXT.md's D-13 fixture-size target ("roughly 8-10 files") over the plan's own stale hardcoded file-count assertions (see Deviations below) -- the task's explicit instruction to add `tests/__init__.py` takes precedence since it is both directly stated in the task `<action>` and consistent with the design intent in 02-CONTEXT.md.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Plan bug] Stale hardcoded file-count of 9 in verify/acceptance-criteria text**
- **Found during:** Task 2 (Routes + callers)
- **Issue:** Task 2's `<action>` explicitly instructs creating `fixtures/sample_fastapi_repo/tests/__init__.py` as an empty file ("so the `tests/` subpackage has the same `__init__.py` shape as `services/`/`routes/`"). This makes the fixture 10 `.py` files total. However, Task 2's own `<verify>` command (`assert len(files) == 9`), its `<acceptance_criteria>` (`find ... | wc -l` expecting `9`), and the plan's top-level `<verification>` section (`reports 9`) all hardcode an expected count of exactly 9 -- one short of what the task's own action text produces. 02-CONTEXT.md's D-13 explicitly sizes the fixture at "roughly 8-10 files," so 10 is within the designed range and the action text (not the stale count) reflects intent.
- **Fix:** Created `tests/__init__.py` as instructed by the action text. Did not omit it to force the file count down to 9, since doing so would contradict both the explicit task instruction and D-13's stated size range, and would leave `tests/` structurally inconsistent with `services/`/`routes/` (each of which has an `__init__.py`).
- **Files modified:** `fixtures/sample_fastapi_repo/tests/__init__.py` (created, empty)
- **Verification:** Confirmed all 10 files parse via `ast.parse` with no `SyntaxError`; confirmed `fastapi` import appears only in `main.py` and `routes/users.py`; confirmed no `backend/tests/` file yet references `fixtures/sample_fastapi_repo` (grep returns no matches, as expected -- Plan 09 owns that reference).
- **Committed in:** `2ff680f` (part of Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 -- plan bug, not a code bug)
**Impact on plan:** No scope creep. The fixture's actual file set, resolved-edge inventory (10), and unresolved-call-site inventory (6) exactly match the plan's `<interfaces>` block, which is the authoritative content contract downstream plans (05, 06, 09) will assert against. Only the plan's own incidental file-count assertions in `<verify>`/`<acceptance_criteria>`/`<verification>` were stale; those are not part of `<interfaces>` and do not affect what later plans can rely on.

## Issues Encountered

None beyond the plan-text deviation documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

`fixtures/sample_fastapi_repo/` now exists with fixed, known content: 10 Python files, exactly 10 resolved call edges and 6 unresolved call sites as enumerated in 02-02-PLAN.md's `<interfaces>` block. Plans 03-06 (import extraction, call-site extraction, resolver, call graph) have a stable, realistic target to build and verify against. Plan 09 (fixture integration tests) can now write its hand-written expected-edge/unresolved lists (D-15) against this fixture's final, settled content -- confirmed no `backend/tests/` file references it yet, so Plan 09 remains the only plan that may add that reference.

No blockers. Note for the Phase 2 verifier: this plan intentionally deviates from its own `<verify>`/`<acceptance_criteria>` hardcoded "9" file-count text (see Deviations) in favor of the 10-file result mandated by the task's own `<action>` text and 02-CONTEXT.md's D-13 size range -- this is expected, not a regression.

---
*Phase: 02-imports-resolution-call-graph*
*Completed: 2026-11-01*

## Self-Check: PASSED

All 10 created files confirmed present on disk; both task commits (`d2eae79`, `2ff680f`) confirmed present in git history.
