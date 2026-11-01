---
phase: 02-imports-resolution-call-graph
plan: 04
subsystem: analysis
tags: [tree-sitter, python-ast, call-extraction, pydantic]

# Dependency graph
requires:
  - phase: 02-imports-resolution-call-graph (plan 01)
    provides: Symbol.module_path field, scope-stack conventions in python_symbols.py
provides:
  - "extract_raw_calls(source, file_path) -> list[RawCall]: every call expression inside a function/method/nested-function body, classified by receiver shape (bare/self/cls/attribute), with no resolution attempted"
  - "extract_raw_class_bases(source, file_path) -> list[RawClassBases]: every class's raw, as-written base-class expression list in source order"
affects: [02-05-imports-resolution, 02-06-call-and-hierarchy-resolution]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Second/third independent tree-walk per concern (mirrors python_symbols.py's _walk_symbols vs _collect_syntax_issues split) rather than one combined dispatcher"
    - "Reuse of python_symbols.py's private _Frame/_qualified_name/_node_name scope-stack helpers across modules instead of reimplementing qualified-name logic"

key-files:
  created: [backend/app/analysis/calls.py, backend/tests/test_calls.py]
  modified: []

key-decisions:
  - "Split into two independent stack-based traversals in one file (extract_raw_calls, extract_raw_class_bases) rather than one combined walk, per the plan's explicit instruction to avoid conflating call-site and class-base collection"
  - "enclosing_symbol computed as _qualified_name(scope[:-1], scope[-1][0]) at call-collection time, reproducing python_symbols.py's own qualified-name computation for the innermost enclosing function/method byte-for-byte"
  - "receiver_kind classified strictly by literal receiver text (self/cls) per D-04, never by decorator presence (@classmethod)"

patterns-established:
  - "New analysis-layer modules import private helpers (_Frame, _node_name, _qualified_name) directly from python_symbols.py rather than duplicating scope logic -- establishes the precedent for Plan 05/06's resolver modules"

requirements-completed: []  # US-03 is a phase-level requirement spanning all 9 plans; NOT marked complete here (see note below)

duration: 6min
completed: 2026-11-01
---

# Phase 02 Plan 04: Raw Call and Class-Base Extraction Summary

**New `backend/app/analysis/calls.py` module extracting raw call-expression receiver shapes (bare/self/cls/attribute) and raw class-base lists from Python source via two independent Tree-sitter stack traversals, with zero resolution performed.**

## Performance

- **Duration:** ~6 min
- **Completed:** 2026-11-01T15:01:27Z
- **Tasks:** 2 completed
- **Files modified:** 2 (both new)

## Accomplishments
- `extract_raw_calls` correctly classifies every call receiver shape (bare name, `self.x()`, `cls.x()`, chained attribute `a.b.c()`) found lexically inside a function/method/nested-function body, while explicitly excluding module-level calls and class-body-but-outside-method calls (the scope boundary the plan requires Phase 3 to own instead)
- `extract_raw_class_bases` captures every class's raw, as-written base-class expression list in source order, correctly treating a no-parens class definition (`class C:`) as zero bases rather than an error, and correctly computing qualified names for nested classes
- Both functions reuse `python_symbols.py`'s exact scope-stack convention (`_Frame`, `_qualified_name`, `_node_name`) rather than reimplementing qualified-name logic, so `RawCall.enclosing_symbol` and `RawClassBases.qualified_name` are byte-for-byte identical to Phase 1's `Symbol.qualified_name` for the same construct
- Verified against the real `fixtures/sample_fastapi_repo/services/auth.py` `AuthService(BaseService)` shape, not just synthetic cases

## Task Commits

Each task was committed atomically:

1. **Task 1: extract_raw_calls -- receiver classification inside function/method bodies** - `8d56dbb` (feat)
2. **Task 2: extract_raw_class_bases -- raw inheritance lists** - `ed66657` (feat)

**Plan metadata:** pending (this commit)

_Note: Both tasks were implemented together during drafting, then split into two atomic commits matching the plan's task boundaries (Task 1's file content committed first, Task 2's additions committed second) so each commit corresponds exactly to one plan task._

## Files Created/Modified
- `backend/app/analysis/calls.py` - New module: `RawCall`/`RawClassBases` Pydantic models, `extract_raw_calls`, `extract_raw_class_bases`, and their shared/private helpers (`_node_text`, `_classify_call`, `_extract_bases`)
- `backend/tests/test_calls.py` - 15 pytest cases covering all `<behavior>` shapes from both tasks, including the real `AuthService(BaseService)` fixture shape

## Decisions Made
- Kept the two extraction functions as fully independent traversals in the same file (not merged, not split into two files) — matches the plan's explicit instruction and the codebase's existing `_walk_symbols`/`_collect_syntax_issues` precedent for separate-pass-per-concern
- Did not add `calls.py`'s exports to `app/analysis/__init__.py`'s public surface — the plan's interface spec only requires the two functions to exist in `backend/app/analysis/calls.py`; downstream Plan 05/06 resolver modules are expected to import directly from `app.analysis.calls`, consistent with how `python_symbols.py`'s private helpers are themselves imported directly by this plan rather than re-exported

## Deviations from Plan

None - plan executed exactly as written. The only adjustment was splitting the already-correct, already-passing implementation into two commits along task boundaries (see Task Commits note above) to satisfy the per-task atomic-commit protocol; no code, test, or behavior was changed between the two commits.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 05 (import resolution) and Plan 06 (call + hierarchy resolution) can now consume `RawCall` and `RawClassBases` directly from `app.analysis.calls` — both carry `enclosing_symbol`/`qualified_name` values guaranteed consistent with Phase 1's `Symbol.qualified_name` scoping, so Plan 06's resolver can join against Phase 1 symbol data without any name-translation layer
- No blockers. `uv run pytest` (76/76) and `uv run ruff check` both clean across the full backend test suite after this plan's changes

---
*Phase: 02-imports-resolution-call-graph*
*Completed: 2026-11-01*

## Self-Check: PASSED

- FOUND: backend/app/analysis/calls.py
- FOUND: backend/tests/test_calls.py
- FOUND: 8d56dbb (Task 1 commit)
- FOUND: ed66657 (Task 2 commit)
