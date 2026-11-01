---
phase: 05-report-json-evaluation
plan: "03"
subsystem: testing
tags: [evaluation, precision-recall, controlled-fixtures, deterministic-json]
requires:
  - phase: 05-report-json-evaluation
    provides: "05-01 shared report schema, evidence builder and canonical JSON"
provides:
  - Independently source-reviewed truth for five controlled cases
  - Offline report-based call-edge and endpoint exact-set evaluation
  - Deterministic JSON CLI with transparent false negatives and undefined metrics
affects: [05-04, 05-05, demo-reports]
tech-stack:
  added: []
  patterns: [source-reviewed labels before predictions, isolated byte-copy fixture roots]
key-files:
  created:
    - backend/app/reporting/evaluation.py
    - backend/tests/test_report_evaluation.py
    - fixtures/report_evaluation/labels.json
    - fixtures/report_evaluation/README.md
    - fixtures/report_evaluation/cycle_unresolved.py
  modified: []
key-decisions:
  - "Source-bound login calls remain gold positives despite resolver limitations; missing calls and the audit endpoint are false negatives."
  - "Each case uses only fixed-allowlisted source files copied as bytes, the shared snapshot digest and the shared report builder."
patterns-established:
  - "Truth labels are committed before predictions and never regenerated from analyser output."
  - "Evaluation extracts verified predictions from AnalysisReport revisions and reports exact identity sets with null undefined metrics."
requirements-completed: [US-11]
duration: approximately 5 min
completed: 2026-11-01
---

# Phase 5 Plan 3: Report Evaluation Summary

**Five independently labelled fixtures expose exact report edge/endpoint errors, including unsupported source-provable login paths, through an offline deterministic JSON CLI.**

## Performance

- **Duration:** Approximately 5 min
- **Started:** Exact start timestamp was not recorded; first task committed 2026-11-01T17:33:51Z
- **Completed:** 2026-11-01T17:36:26Z
- **Tasks:** 2
- **Files created:** 5

## Accomplishments

- Labelled all 12 local call relationships in the sample source, including its fixture test, before running predictions. Auth-positive, unsupported-audit and unrelated-callers share this explicitly declared source scope.
- Added inert cycle/callback source with an immediate execution guard, covering supported cyclic traversal and an unrelated unresolved change.
- Implemented strict label validation, fixed source allowlists, traversal/symlink rejection, isolated byte-copy roots, controlled provenance, exact-set scoring, uncertainty diagnostics, and pooled micro/macro aggregation with defined denominators.
- Added a CLI that writes the exact shared canonical JSON bytes to stdout and optional output file, with no additional newline or timestamps.

## Task Commits

1. **Task 1: Author independent labelled evaluation cases** — `0a48398` (test)
2. **Task 2 RED: Exact-set evaluation regressions** — `811b14d` (test)
3. **Task 2 GREEN: Executable controlled report evaluation** — `250f0fe` (feat)

## Files Created/Modified

- `fixtures/report_evaluation/labels.json` — Five hand-authored cases with seed ranges, exhaustive scoped edge truth, endpoint truth, unresolved expectations and source-located unknowns.
- `fixtures/report_evaluation/cycle_unresolved.py` — Inert guarded cycle, registered endpoint, unrelated helper and dynamic callback.
- `fixtures/report_evaluation/README.md` — Source rationale, support/exclusion conventions and measured results retaining every known miss.
- `backend/app/reporting/evaluation.py` — Shared report adapter, exact sets, diagnostics, metrics and canonical JSON CLI.
- `backend/tests/test_report_evaluation.py` — Scoring, aggregation, known misses, negatives, cycles, duplicate paths/seeds, invalid labels/paths, symlinks, nonexecution guard and CLI determinism.

## Verification and Measured Results

- Task 1 schema/case-count/unique-ID verification passed.
- RED ran and failed at collection because `app.reporting.evaluation` did not yet exist.
- `uv run --no-sync python -m pytest tests/test_report_evaluation.py -q`: **13 passed**.
- `uv run --no-sync ruff check app/reporting/evaluation.py tests/test_report_evaluation.py`: **All checks passed**; files formatted with Ruff.
- Two final CLI runs produced identical stdout and output-file bytes: **36,924 bytes**, SHA256 `4a00562b4e6f836e941c474a03e12fd88ab922bc3fe468d4b2438ab094ef77a7`.
- `git diff --check` passed. Stub-pattern scan found none.

Pooled over five cases and two separately scored revisions:

| Metric | TP | FP | FN | Micro precision | Micro recall |
| --- | --- | --- | --- | --- | --- |
| Call edges | 72 | 0 | 12 | 1.0 | 0.8571428571428571 |
| Endpoints | 6 | 0 | 2 | 1.0 | 0.75 |

Edge macro precision/recall are 1.0/0.9 (10 defined values each).
Endpoint macro precision is 1.0 (4 defined values); recall is 2/3 (6 defined).
Empty negative cases remain explicit with null undefined metrics. Source-bound
`auth.login` and `svc.login` are missing edge predictions; the audit case misses
GET `/users/me`. Unknown dynamic targets are source-located and excluded from
truth-target denominators. Source scope repeats across cases and base/head;
these are controlled measurements, not independent real-change samples.

## Decisions Made

Preserved precision-first analyser behaviour and upstream contracts. Kept provable
unsupported calls in truth rather than weakening labels to obtain perfect recall.
All source goes through byte copies and static parsing; no fixture imports,
source execution, network access, new dependencies or infrastructure were added.

## Deviations from Plan

None — plan executed as written. The parent orchestrator owns shared STATE,
ROADMAP and REQUIREMENTS updates to avoid concurrent metadata edits.

## Issues Encountered

None. Expected non-perfect measurements are documented evidence, not failures of
the evaluation harness. Routine formatting corrections passed final Ruff checks.

## Known Stubs

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

`build_case_report` is ready for shared controlled demo generation and golden
report tests. Known resolver misses and partial sample route diagnostics remain
visible. No report schema/runtime changes or architectural decisions are required.

## Self-Check: PASSED

All five created files exist. Task commits `0a48398`, `811b14d`, and `250f0fe`
exist in Git history. Targeted tests, Ruff and deterministic CLI checks passed.
