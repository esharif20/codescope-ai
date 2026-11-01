---
phase: 02-imports-resolution-call-graph
plan: 03
subsystem: parsing
tags: [tree-sitter, python, imports, ast, pydantic]

# Dependency graph
requires:
  - phase: 02-imports-resolution-call-graph (plan 01)
    provides: module_path_for and the extended Symbol contract this plan's RawImport sits alongside
provides:
  - "backend/app/analysis/imports.py -- extract_raw_imports(source, file_path) -> list[RawImport], a second independent Tree-sitter traversal extracting every import shape (plain, multi-name, aliased, from-import, relative at any depth, star) with zero resolution attempted"
  - "RawImport.relative_level -- the dot-count Plan 05's import resolver climbs against the importing file's package location (D-06)"
affects: [02-05-import-resolver, 02-09-fixture-integration-tests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Second, independent iterative-stack traversal over the same parse tree shape as python_symbols.py's _walk_symbols/_collect_syntax_issues pair -- imports.py does not touch or import from python_symbols.py, it only mirrors its Language/Parser construction convention"
    - "wildcard_import detected by scanning node.children for an unnamed child (no child_by_field_name), matching the plan's confirmed grammar"

key-files:
  created:
    - backend/app/analysis/imports.py
    - backend/tests/test_imports.py
  modified: []

key-decisions:
  - "Verified exact tree-sitter-python node/field shapes empirically (Language/Parser dump of all 9 behavior-cited statements) before writing any extraction code, per the plan's explicit instruction not to re-derive grammar from memory -- all shapes matched the plan's <interfaces> block exactly, no surprises"

patterns-established:
  - "RawImport is extraction-only: no filesystem lookups, no concept of 'the repo', file_path used verbatim -- mirrors extract_symbols' contract so Plan 05 can compose cleanly on top"

requirements-completed: []

# Metrics
duration: 1min
completed: 2026-11-01
---

# Phase 02 Plan 03: Raw Import Extraction Summary

**`extract_raw_imports` extracts every Python import statement shape (plain, multi-name, aliased, from-import, relative at any depth, star) into `RawImport` Pydantic records via a second independent Tree-sitter traversal, with zero resolution attempted.**

## Performance

- **Duration:** ~1 min (2026-11-01T15:00:03Z to 2026-11-01T15:01:11Z, first to last task commit)
- **Started:** 2026-11-01T15:00:03Z
- **Completed:** 2026-11-01T15:01:11Z
- **Tasks:** 2/2 completed (each run as a full RED/GREEN TDD cycle)
- **Files modified:** 2 created (imports.py, test_imports.py)

## Accomplishments

- Empirically confirmed tree-sitter-python's exact node/field shapes for all 9 import statement variants named in the plan (via a throwaway `Language`/`Parser` dump), matching the plan's `<interfaces>` block exactly before writing any code
- `extract_raw_imports(source, file_path)` handles `import_statement` (plain `import os`, multi-name `import os, sys` -> one `RawImport` per name, aliased `import os.path as p`)
- Extended to `import_from_statement`: absolute (`from app.services import auth`), relative at level 1 with no trailing module (`from . import auth`), relative at level 2 with a trailing module (`from ..services.base import BaseService`), and star imports both absolute and relative -- including the exact `from ..services import *` statement used in `fixtures/sample_fastapi_repo/routes/__init__.py`
- `relative_level` computed by counting literal `.` characters in the `import_prefix` node's text, never by string-parsing the whole statement
- `wildcard_import` detected by scanning `node.children` (it carries no field name), not via `child_by_field_name`

## Task Commits

Each task followed the plan's `tdd="true"` RED/GREEN protocol with its own commits:

1. **Task 1: plain import extraction**
   - `2565108` (test) -- RED: 3 failing cases for `import os` / `import os, sys` / `import os.path as p`; confirmed `ModuleNotFoundError` before any implementation existed
   - `e920ced` (feat) -- GREEN: `imports.py` created, `import_statement` handling only; all 3 cases pass, ruff clean
2. **Task 2: from/relative/star import extraction**
   - `0ed6ed1` (test) -- RED: 6 new failing cases (from-plain, from-aliased, relative level 1, relative level 2, star absolute, star relative); confirmed all 6 fail against the Task-1-only implementation while the original 3 still pass
   - `8f20ae3` (feat) -- GREEN: extended `extract_raw_imports` with `import_from_statement` handling; all 9 cases pass, ruff clean, no regressions in the other 61 backend tests

**Plan metadata:** (this commit)

_Note: both TDD tasks produced exactly 2 commits each (test -> feat); no refactor commit was needed since no cleanup was required after either GREEN step._

## Files Created/Modified

- `backend/app/analysis/imports.py` - `RawImport` Pydantic model + `extract_raw_imports(source, file_path)`, a second independent Tree-sitter traversal mirroring `python_symbols.py`'s Language/Parser and iterative-stack conventions
- `backend/tests/test_imports.py` - 9 pytest cases covering every import shape named in the plan's `<behavior>` blocks, including the exact fixture statement `from ..services import *`

## Decisions Made

- Followed the plan's explicit instruction to confirm tree-sitter grammar shapes empirically (not from memory/documentation) before implementing -- a throwaway script dumped the parse tree for all 9 cited statements; every shape matched the plan's `<interfaces>` block exactly (no `Rule 4` architectural surprises, no grammar drift to flag)

## Deviations from Plan

None - plan executed exactly as written. One minor self-correction: the first draft of `RawImport`'s `module` field docstring comment exceeded ruff's 100-char line limit (E501); shortened the comment text before the Task 1 GREEN commit, no behavior change.

## Issues Encountered

- `backend/tests/test_calls.py` fails to collect (`ImportError: cannot import name 'RawClassBases' from app.analysis.calls`) when running the full backend suite. This is a different, parallel in-flight plan's (02-04) work-in-progress file, not something this plan's `files_modified` list touches or is responsible for. Confirmed out of scope per the executor's scope-boundary rule; verified no regression by re-running the full suite with `--ignore=tests/test_calls.py` (61/61 passed). Not added to `deferred-items.md` since it is actively being resolved by its own plan in the same execution window, not an abandoned pre-existing issue.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

`RawImport.relative_level` and `RawImport.module` are now available, with every shape (plain/aliased/from/relative/star) confirmed against the real fixture's `routes/__init__.py` star-import statement. Plan 05 (import resolver) can consume `extract_raw_imports`'s output directly without re-deriving any tree-sitter grammar details -- the dot-count-based `relative_level` is exactly what its dot-level climb algorithm needs per the plan's `key_links` contract.

No blockers.

---
*Phase: 02-imports-resolution-call-graph*
*Completed: 2026-11-01*

## Self-Check: PASSED

All created files confirmed present on disk (`backend/app/analysis/imports.py`, `backend/tests/test_imports.py`,
this SUMMARY.md); all 4 task commits (`2565108`, `e920ced`, `0ed6ed1`, `8f20ae3`) confirmed present in git history.
