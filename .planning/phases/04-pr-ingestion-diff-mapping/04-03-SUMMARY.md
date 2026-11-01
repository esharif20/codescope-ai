---
phase: 04-pr-ingestion-diff-mapping
plan: 03
subsystem: ingestion
tags: [diff, provenance, static-analysis, source-links]
requires:
  - phase: 04-01
    provides: Pinned metadata, snapshot, changed-symbol and source-reference contracts
provides:
  - Deterministic bounded local-byte diff mapping across both revisions
  - Immutable revision-specific GitHub source permalinks
affects: [04-04, 04-05]
tech-stack:
  added: []
  patterns: [narrowest-definition ownership, local-byte authority, explicit unmapped evidence]
key-files:
  created:
    - backend/app/ingestion/source_links.py
    - backend/app/ingestion/diff_mapping.py
    - backend/tests/test_source_links.py
    - backend/tests/test_diff_mapping.py
  modified: []
key-decisions:
  - Conservatively leave both sides of syntax/decode-error files unmapped because recovered inventories cannot prove additions or deletions.
  - Preserve raw line endings in diffs and decorated symbol spans; offset-only movement never marks a surviving definition modified.
  - Reject diff/output ceilings with explicit errors rather than silently truncating evidence.
requirements-completed: [US-01, US-02, US-09]
duration: 4min
completed: 2026-11-01
---

# Phase 4 Plan 3: Local Diff Mapping and Source References Summary

**Bounded exact-byte revision diffs identify added, modified and removed definitions with immutable fork-aware source evidence and explicit unmapped locations.**

## Performance

- **Duration:** Approximately 4 min
- **Tasks:** 2
- **Files created:** 4

## Accomplishments

- Independently validate pinned metadata, source paths and positive ranges before building encoded GitHub blob links. Base links use `analysis_base_sha` and the base repository; head links use the head SHA and repository.
- Compare exact snapshot bytes using bounded `SequenceMatcher(autojunk=False)` operations; preserve CRLF and final-newline differences without trusting upstream patch text.
- Use the narrowest enclosing decorated definition as changed-line owner. Compare actual spans to omit untouched shifted definitions and avoid marking every ancestor for nested edits.
- Preserve old-only removals, added-only definitions and both locations for modifications; path/function identity changes produce explicit removals and additions.
- Keep unsupported module lines, duplicate identities and malformed source visible as partial evidence. Enforce diff and output bounds and propagate budget callbacks throughout mapping.
- Reject missing/escaping/symlink snapshot source without exposing temporary roots in public references.

## Task Commits

1. **Task 1: Construct revision-correct source permalinks** — `e44554b` (test), `921db52` (feat).
2. **Task 2: Classify changes across complete local source revisions** — `646ab70` (test), `2b36e47` (feat; includes owned-file formatting).

## Files Created/Modified

- `backend/app/ingestion/source_links.py` — Validated pinned source-reference construction.
- `backend/app/ingestion/diff_mapping.py` — Pure local snapshot diff, ownership, identity classification and resource limits.
- `backend/tests/test_source_links.py` — 16 exact provenance, encoding and invalid-input cases.
- `backend/tests/test_diff_mapping.py` — 31 classification, ownership, malformed input, ordering, collision, byte-boundary and limit cases.

## Decisions Made

Whole-file conservative handling for syntax/decode failures prevents recovered or missing definitions from becoming confident change seeds. Valid files continue mapping independently. Diagnostics are stable codes, and temporary filesystem paths never enter source references.

No new dependencies or architecture changes were needed. Source bytes are parsed only, never executed or imported.

## Verification

- Task 1 TDD RED failed on the expected missing source-link module; Task 2 TDD RED failed on the expected missing diff-mapping module.
- `cd backend && uv run --no-sync python -m pytest tests/test_diff_mapping.py tests/test_source_links.py -q` — **47 passed**.
- `cd backend && uv run --no-sync ruff check app/ingestion/diff_mapping.py app/ingestion/source_links.py tests/test_diff_mapping.py tests/test_source_links.py` — **passed**.
- `git diff --check` — **passed**.
- Owned implementation/tests scanned for TODO/FIXME/placeholder patterns — none found.

## Deviations from Plan

None in implementation scope. The parent orchestrator owns shared STATE, ROADMAP and REQUIREMENTS updates; this executor leaves those files untouched to avoid parallel edits.

## Issues Encountered

Initial formatting checks identified long lines; formatting and the remaining test literal were corrected before the final checks. No authentication gates occurred.

## Known Stubs

None. Intentionally empty input sides represent missing or empty revisions and do not feed mock data into a user interface.

## Next Phase Readiness

Plan 04-04 can consume `map_snapshot_changes(pair, *, check_budget=...)` without network or web-framework dependencies. Fail-closed errors use `diff_limit_exceeded`, `mapping_limit_exceeded` and `snapshot_read_failed`.

## Self-Check: PASSED

Confirmed all four created implementation/test files and this summary exist. Confirmed commits `e44554b`, `921db52`, `646ab70` and `2b36e47` exist in git history. Shared tracking updates remain with the parent orchestrator.
