---
phase: 05-report-json-evaluation
plan: "05"
subsystem: api
tags: [fastapi, reports, demos, evaluation, asgi]
requires:
  - phase: 05-02
    provides: Atomically retained, bounded live report evidence
  - phase: 05-04
    provides: Fixed allowlisted frozen demo artifacts and loader
provides:
  - Protected UUID-addressed live report retrieval
  - Public frozen demo catalog and report retrieval independent of live enablement
  - Hermetic report API boundary regressions and reproducible usage documentation
affects: [06-rag-explanations, 07-frontend, 08-deployment]
tech-stack:
  added: []
  patterns: [raw-ASGI HTTP tests, fixed artifact lookup outside protected live namespace]
key-files:
  created: [backend/tests/test_report_api.py]
  modified: [backend/app/api.py, backend/README.md]
key-decisions:
  - "Retain the entire existing analyses authentication boundary; public demos use only the fixed artifact loader."
  - "Return validated retained report models without recomputation or source access."
patterns-established:
  - "Public demo routes never reserve admission, scan source, regenerate reports or fall back to live UUIDs."
requirements-completed: [US-11]
duration: 4 min
completed: 2026-11-01
---

# Phase 5 Plan 5: Report API and Complete Evaluation Summary

**Protected retained report JSON and public frozen demo endpoints preserve evidence and admission boundaries, verified by 665 backend tests.**

## Performance

- **Duration:** Approximately 4 min
- **Started:** 2026-11-01T17:40:58Z
- **Completed:** 2026-11-01T17:44:00Z
- **Tasks:** 2
- **Files modified:** 3 implementation/documentation files

## Accomplishments

- Added synchronous `GET /api/analyses/{analysis_id}/report` using `registry.get_report`, preserving authorization before UUID validation and disabled-live behavior.
- Added public `GET /api/demos` and `GET /api/demos/{demo_id}/report` using only the fixed validated artifact loader; added safe report/demo HTTP status mappings.
- Added 24 raw-ASGI cases covering exact retained report output after local source deletion, SHA-pinned base/head call-site links, pending/running/failure/timeout, TTL/eviction, concurrent cleanup, no public analysis/admission, unsupported POST, traversal IDs and safe artifact errors.
- Documented schema v1, static-impact caveats, controlled versus GitHub evidence, retention/limits, curl usage, maintenance commands and measured evaluation limitations.

## Task Commits

1. **Task 1 RED: Report API contracts** — `fe93bbe` (test)
2. **Task 1 GREEN: Protected reports and public frozen demos** — `84446a9` (feat)
3. **Task 2: Documentation and final failure regressions** — `0458013` (docs)

## Files Created/Modified

- `backend/app/api.py` — Three GET routes and report/demo HTTP error mappings; existing submission/status behavior and live namespace boundary preserved.
- `backend/tests/test_report_api.py` — Hermetic API tests reusing controlled upstream fixture inputs and raw-ASGI helpers.
- `backend/README.md` — Report contracts, retrieval examples, reproducible offline evaluation and explicit known limits.

## Verification

- TDD RED: 12 failed / 10 passed before endpoint implementation; missing report/demo routes caused the expected failures.
- Focused report plus existing analysis API suite: **58 passed** before the final two failure regressions.
- Final `uv run --no-sync python -m pytest -q`: **665 passed in 5.53s**.
- `uv run --no-sync ruff check app tests`: **passed**.
- `uv run --no-sync python -m app.reporting.evaluation --labels ../fixtures/report_evaluation/labels.json --output /tmp/codescope-05-05-evaluation.json`: **passed**; reviewed aggregate counts from the generated artifact.
- `uv run --no-sync python -m app.reporting.demos --check`: **passed**, frozen bytes match offline regeneration.
- `git diff --check`: **passed**.
- Stub-pattern scan of all three changed implementation/documentation files: no TODO/FIXME/placeholder stubs.
- No network requests, repository source execution, fixture dependency installation or new project dependencies.

Measured across five cases and two separately scored revisions:

| Metric | TP / FP / FN | Micro precision | Micro recall | Macro precision / recall |
| --- | --- | --- | --- | --- |
| Edges | 72 / 0 / 12 | 1.0 | 0.8571428571428571 | 1.0 / 0.9 (10 defined each) |
| Endpoints | 6 / 0 / 2 | 1.0 | 0.75 | 1.0 (4 defined) / 0.6666666666666666 (6 defined) |

## Decisions Made

Followed the planned fixed-loader/public versus protected-live boundary. Reused existing registry, error redaction and raw-ASGI patterns; no new service or infrastructure.

## Deviations from Plan

None — plan implemented within assigned files. Shared STATE/ROADMAP/REQUIREMENTS updates remain owned by the parent execution orchestrator to avoid conflicting edits.

## Issues Encountered

Corrected two test-authoring assertions during verification: single-line source URLs use `#L5`, and redaction checks serialize the response body rather than raw ASGI byte-keyed headers. Final verification passed after these corrections. Evaluation CLI writes its output file and also prints JSON to stdout; redirect stdout when running it for compact logs.

## Known Limitations

- Reports/statuses remain bounded process-local memory, sharing TTL/eviction and lost on restart; no durable storage or cross-process retrieval.
- Two source-bound local `login` receiver edges remain unsupported, including the missing edge needed for the audit endpoint. Evaluation retains these false negatives.
- Controlled demos use hypothetical changes over identical source snapshots with local evidence and SHA256 manifests. They do not represent real PRs or independent real-world samples.
- Partial diagnostics persist; these measurements establish neither runtime effects, general completeness nor improvement over another approach. No Gemini/RAG, UI, cloud deployment or model-cost measurements are included.

## User Setup Required

None for public demos or offline evaluation. Protected live access uses existing Phase 4 configuration.

## Next Phase Readiness

All Phase 5 plans now have summaries; retained report nodes, edges, findings and uncertainties are available for later explanation/UI consumers. Ready for independent Phase 5 verification. No approval decision remains for this deterministic backend work.

## Self-Check: PASSED

- Confirmed all three changed implementation/documentation files and this summary exist.
- Confirmed commits `fe93bbe`, `84446a9` and `0458013` exist in local history.

---
*Phase: 05-report-json-evaluation*
*Completed: 2026-11-01*
