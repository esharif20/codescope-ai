---
phase: 02-imports-resolution-call-graph
plan: 08
subsystem: static-analysis
tags: [python, orchestration, networkx, cli, evidence]

requires:
  - phase: 02-imports-resolution-call-graph
    provides: symbol extraction, import/call resolution, and queryable CallGraph
provides:
  - Bounded deterministic build_project_graph directory pipeline
  - Explicit per-file failure/cap statuses and unresolved-result truncation signal
  - codescope-graph JSON inspection CLI
affects: [fixture-integration-tests, route-impact-analysis, pr-ingestion]

tech-stack:
  added: []
  patterns: [project-wide two-pass resolution, explicit partial-analysis evidence]

key-files:
  created: [backend/app/analysis/project_graph.py, backend/tests/test_project_graph.py, backend/tests/test_cli_graph.py]
  modified: [backend/app/analysis/__init__.py, backend/app/analysis/cli.py, backend/pyproject.toml]

key-decisions:
  - "Project extraction resolves every module's direct imports before package re-exports and stars, then resolves all calls after collecting every source file."
  - "Decode failures, unreadable files, and file-cap skips remain explicit file statuses rather than silently shrinking the graph."
  - "The graph CLI emits NetworkX node-link data plus unresolved source evidence; it does not execute analysed source."

requirements-completed: [US-03]
duration: 6min
completed: 2026-11-01
---

# Phase 02 Plan 08: Multi-file Orchestrator and Graph CLI Summary

**A bounded, deterministic filesystem-to-call-graph pipeline with explicit partial-analysis evidence and a separate inspectable JSON CLI.**

## Accomplishments

- Added `build_project_graph(root)`, which gathers a sorted, capped Python file set; resolves imports across the complete project before resolving calls; and produces a `CallGraph` with explicit unresolved evidence.
- Preserved decode errors, unreadable paths, and over-cap paths in `file_statuses`; the unresolved evidence cap exposes `unresolved_truncated` instead of silently dropping its effect.
- Re-exported the new graph API without removing the Phase 1 names and added `codescope-graph <root>` with readable or compact JSON output.

## Task Commits

1. **Task 1: walk, extraction, and import resolution** — `5cdf91b` (RED tests), `44fe0dc` (implementation)
2. **Task 2: call resolution, graph assembly, and public API** — `ba9eb46` (RED tests), `378f5d5` (implementation)
3. **Task 3: graph CLI** — `22e99da` (RED tests), `305eaf4` (implementation)

## Verification

- `cd backend && uv run pytest -q` — 118 passed.
- `cd backend && uv run ruff check .` — passed.
- `cd backend && uv run codescope-graph ../fixtures/sample_fastapi_repo` — produced readable JSON with graph, unresolved evidence, file statuses, and truncation state.
- Invalid graph root exits 1 and writes a non-empty stderr message.
- Plan key-link verification — 2/2 verified.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Used a non-editable local install for console-script verification**

- **Found during:** Task 3 verification.
- **Issue:** In this macOS environment, default editable `uv sync --extra dev` recreated a Finder-hidden `.pth` file, so generated console scripts could not import `app`, despite direct `uv run python` imports working.
- **Fix:** Verified both console scripts after `uv sync --extra dev --no-editable`, which installs the local package without the hidden editable `.pth` indirection.
- **Files modified:** None; virtual-environment-only remediation.
- **Verification:** `codescope-parse` and `codescope-graph` both imported and ran successfully under the non-editable local install.

**Total deviations:** 1 auto-fixed blocking environment issue. **Impact:** No source or dependency change; normal editable-sync console-script behavior remains an environment limitation to revisit.

## Issues Encountered

- The existing uv editable-install hidden-`.pth` issue recurred with `uv 0.13.6` in this environment. Repository tests remain runnable; console-script checks need `uv sync --no-editable` until the external behavior is resolved.

## Next Phase Readiness

- Plan 02-09 can assert exact fixture edges and unresolved records through the public project graph pipeline.
- No implementation blockers.

## Self-Check: PASSED

- FOUND: `backend/app/analysis/project_graph.py`
- FOUND: `backend/tests/test_project_graph.py`
- FOUND: `backend/tests/test_cli_graph.py`
- FOUND: `5cdf91b`, `44fe0dc`, `ba9eb46`, `378f5d5`, `22e99da`, and `305eaf4`
