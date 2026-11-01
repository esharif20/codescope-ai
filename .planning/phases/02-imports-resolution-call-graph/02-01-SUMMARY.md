---
phase: 02-imports-resolution-call-graph
plan: 01
subsystem: analysis
tags: [pydantic, networkx, tree-sitter, module-paths, contracts]

# Dependency graph
requires:
  - phase: 01-python-symbol-extraction
    provides: "Symbol/ParseResult Pydantic contract and app/analysis package layout this plan extends"
provides:
  - "Symbol.module_path field (D-17)"
  - "ResolutionStatus, ImportBinding, UnresolvedCall, ResolvedCall Pydantic contracts (D-09/D-11) for Plans 03-08"
  - "module_path_for(file_path, root) -- deterministic root-relative module path derivation (D-08)"
  - "networkx added as a locked backend dependency"
affects: [03-import-resolution, 04-call-site-extraction, 05-call-resolution, 06-class-hierarchy, 07-graph-assembly, 08-cli-fixture]

# Tech tracking
tech-stack:
  added: ["networkx>=3.6.1"]
  patterns:
    - "Pure, I/O-free path-derivation functions (module_paths.py) kept separate from any Tree-sitter/parsing logic"
    - "Interface-first contract extension: new Pydantic models added once, verbatim, for all downstream plans to consume unchanged"

key-files:
  created:
    - backend/app/analysis/module_paths.py
    - backend/tests/test_module_paths.py
  modified:
    - backend/app/analysis/models.py
    - backend/pyproject.toml
    - backend/requirements.txt
    - backend/requirements-dev.txt
    - backend/uv.lock
    - backend/README.md

key-decisions:
  - "Symbol.module_path inserted directly after file_path per D-17, additive-only, no existing field/validator changed"
  - "module_path_for implemented with pathlib.Path.relative_to (not os.path.relpath) for its native, already-correct ValueError-on-outside-root behavior"
  - "networkx added via uv add with no version ceiling (no known compatibility issue, unlike the existing tree-sitter<0.26 pin)"

patterns-established:
  - "D-08 module-path rule: __init__.py maps to its containing directory's dotted path; repo-root __init__.py maps to \"\""

requirements-completed: [US-03]

# Metrics
duration: 2min
completed: 2026-11-01
---

# Phase 2 Plan 01: Contracts and module-path foundation Summary

**Extended the Symbol contract with module_path, added the four Phase 2 Pydantic contracts (ResolutionStatus/ImportBinding/UnresolvedCall/ResolvedCall) verbatim per the interface spec, added networkx as a locked dependency, and implemented the pure `module_path_for` D-08 path-derivation function with full TDD coverage.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-11-01T14:51:40Z
- **Completed:** 2026-11-01T14:53:45Z
- **Tasks:** 2 completed
- **Files modified:** 8 (2 created, 6 modified)

## Accomplishments
- `Symbol.module_path: str | None = None` added (D-17), additive-only, zero existing-field changes
- `ResolutionStatus`, `ImportBinding`, `UnresolvedCall`, `ResolvedCall` added to `app/analysis/models.py` exactly per the pinned interface spec, ready for Plans 03-08 to implement against verbatim
- `networkx` added as a backend dependency (`uv add networkx`), `requirements.txt`/`requirements-dev.txt` regenerated, `backend/README.md` updated to reflect Phase 2 in progress and the dependency addition
- `module_path_for(file_path, root)` implemented in a new `backend/app/analysis/module_paths.py`: pure, I/O-free, handles one-level and nested files, `__init__.py` package-name mapping, repo-root `__init__.py` -> `""`, raises `ValueError` for paths outside root, and normalizes trailing-slash roots
- 6 new tests in `backend/tests/test_module_paths.py` cover every D-08 behavior case; full backend suite now 52/52 green, ruff clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend models.py contract + add networkx dependency** - `6525cfc` (feat)
2. **Task 2: Implement module_path_for (D-08)** - TDD: `9e09d4c` (test, RED) -> `c2b64c7` (feat, GREEN; no refactor commit needed, implementation was already clean)

**Plan metadata:** (final commit recorded after this summary is committed)

## Files Created/Modified
- `backend/app/analysis/models.py` - Added `Symbol.module_path`; appended `ResolutionStatus`, `ImportBinding`, `UnresolvedCall`, `ResolvedCall`
- `backend/app/analysis/module_paths.py` - New: `module_path_for(file_path, root) -> str` (D-08)
- `backend/tests/test_module_paths.py` - New: 6 tests covering every D-08 rule
- `backend/pyproject.toml` - `networkx>=3.6.1` dependency added
- `backend/requirements.txt`, `backend/requirements-dev.txt`, `backend/uv.lock` - Regenerated after `uv add networkx`
- `backend/README.md` - Status line updated to "Phase 1 of 8 complete; Phase 2 ... in progress"; dependency-incrementality note updated to reflect networkx now added

## Decisions Made
- Used `pathlib.Path.relative_to` (catching its native `ValueError`) rather than `os.path.relpath`, since `relative_to` already raises exactly the "not inside root" signal D-08 requires, avoiding a hand-rolled outside-root check
- Reformatted the `ResolvedCall` docstring onto two lines to satisfy the project's `line-length = 100` ruff rule while preserving the exact wording from the pinned interface spec (no semantic change)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff E501 (line too long) on ResolvedCall docstring**
- **Found during:** Task 1 verification (`uv run ruff check .`)
- **Issue:** The exact docstring text from `<interfaces>` ("One resolved caller -> callee call site, before graph assembly (Plan 07 groups these into edges).") is 107 characters, exceeding the project's 100-char ruff line-length limit
- **Fix:** Wrapped the docstring onto two lines (summary line + continuation sentence), preserving identical wording and meaning
- **Files modified:** backend/app/analysis/models.py
- **Verification:** `uv run ruff check .` passes with no warnings; `uv run pytest -q` still 46/46 (then 52/52 after Task 2) green
- **Committed in:** 6525cfc (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug/lint)
**Impact on plan:** Cosmetic formatting fix only; no change to the class name, field names, or any contract shape specified in `<interfaces>`. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `app.analysis.models` now exposes the full Phase 2 contract surface (`ResolutionStatus`, `ImportBinding`, `UnresolvedCall`, `ResolvedCall`, `Symbol.module_path`) for Plans 03-08 to implement against verbatim
- `module_path_for` is ready for every cross-file plan in this phase to turn a file path into a module path
- `networkx` is installed and locked, ready for Plan 07's graph assembly
- No blockers or concerns for the next plan (02-02)

---
*Phase: 02-imports-resolution-call-graph*
*Completed: 2026-11-01*

## Self-Check: PASSED

All claimed files found on disk (module_paths.py, test_module_paths.py, models.py, README.md,
pyproject.toml, requirements.txt, requirements-dev.txt, this SUMMARY.md). All claimed commit hashes
(6525cfc, 9e09d4c, c2b64c7) found in git history.
