---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: ready_to_plan
stopped_at: Phase 5 complete and independently verified; ready to plan Phase 6
last_updated: "2026-11-01T17:46:47.573Z"
last_activity: 2026-11-01
progress:
  total_phases: 8
  completed_phases: 5
  total_plans: 23
  completed_plans: 23
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-01)

**Core value:** Show what a PR might affect, why, and the exact code supporting each finding — never claim static
analysis proves runtime behaviour or finds every dependency.
**Current focus:** Phase 6 — RAG & Gemini summary (not planned)

## Current Position

Phase: 6
Plan: Not started
Status: Phase 5 complete — ready to plan Phase 6
Last activity: 2026-11-01

Phase 5 delivered schema-v1 evidence reports, atomic bounded retention, independently labelled evaluation,
two frozen controlled demos, protected live report retrieval and public demo APIs. All five plans completed
across four waves; retention/evaluation ran in parallel. Independent verification passed 15/15 must-haves
and all four roadmap criteria; no human checks remain. Full backend verification: 665 tests, Ruff,
uv lock --check, frozen demo drift and diff checks passed. No dependencies were added.

Five controlled cases, each scored separately at base/head, measured micro call-edge TP/FP/FN=72/0/12
(precision 1, recall 6/7) and endpoint TP/FP/FN=6/0/2 (precision 1, recall .75). Source-known receiver
relationships and the missed audit endpoint remain false negatives. The unrelated-callers demo has zero
verified affected routes. These are controlled hypothetical seeds, not real PR diffs or general guarantees.
Reports preserve uncertainties separately from verified paths and controlled SHA256 manifests without
invented GitHub links. Reports/status expire together (default 1 hour, 20 terminal records, 2 MiB/report).

Progress: 5/8 phases complete; 23/23 currently planned GSD plans complete (Phase 1 predates GSD plans).
Phase 6 has not been planned or started; automatic advance is disabled.

Phase 4 is fully accepted: 18/18 must-haves, live GitHub/API check and user-confirmed source highlighting.
Its FastAPI dependency approval remains recorded. Phase 4/5 implementation and completion are pushed
through eb9ff16 on feat/stage-1-python-symbols. Backend CI passed on that exact commit: 665 tests and Ruff.
https://github.com/esharif20/codescope-ai/actions/runs/41333556516
GitHub issues #10/#11 are complete and closed; #12 remains open and unstarted with updated readiness.

## Performance Metrics

**Velocity:**

- Total plans completed: 23
- Average duration: - min
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 02 P01 | 2min | 2 tasks | 8 files |
| Phase 02 P02 | 3min | 2 tasks | 10 files |
| Phase 02 P03 | 1min | 2 tasks | 2 files |
| Phase 02 P04 | 6min | 2 tasks | 2 files |
| Phase 02 P05 | 14 min | 2 tasks | 2 files |
| Phase 02 P06 | 6 min | 2 tasks | 2 files |
| Phase 02 P07 | 8 min | 2 tasks | 2 files |
| Phase 02 P08 | 6 min | 3 tasks | 6 files |
| Phase 02 P09 | 3 min | 2 tasks | 1 files |
| Phase 03 P01 | 6min | 2 tasks | 3 files |
| Phase 03 P02 | 4min | 2 tasks | 2 files |
| Phase 03 P03 | 3min | 2 tasks | 2 files |
| Phase 03 P04 | 3min | 2 tasks | 5 files |
| Phase 04 P01 | 7min | 2 tasks | 6 files |
| Phase 04 P02 | 6min | 2 tasks | 4 files |
| Phase 04 P03 | 4min | 2 tasks | 4 files |
| Phase 04 P04 | 4min | 2 tasks | 6 files |
| Phase 04 P05 | 5min | 3 tasks | 8 files |
| Phase 05 | Four waves | 10 tasks | 5 plans |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Phase 1 = Tree-sitter Python symbol extractor in `backend/app/analysis/` (Pydantic models, JSON CLI, pytest
  suite) — implemented directly, bypassing `/gsd:plan-phase`/`/gsd:execute-phase`, since the design was already
  approved before GSD was introduced. **This was a one-time exception for Phase 1 only** — Phase 2 onward uses the
  full discuss → plan → execute → verify cycle.

- `workflow.research` disabled project-wide: ARCHITECTURE.md already fixes stack/scope for all 8 phases.
- GSD commits land locally on `feat/stage-1-python-symbols`; nothing pushed without explicit approval.
- Dependencies are added incrementally per phase (`uv add <pkg>` only when that phase's code first needs it), not
  front-loaded; `requirements.txt`/`requirements-dev.txt` are regenerated from `uv.lock` after every change; the
  backend README is updated at every phase/milestone boundary.

- `tree-sitter` pinned to `<0.26` (resolves to 0.25.2) after reproducing a reference-counting segfault in 0.26.0's
  Node binding on deeply nested trees — re-test deliberately before raising this ceiling.

- [Phase 02]: Symbol.module_path inserted directly after file_path per D-17, additive-only
- [Phase 02]: module_path_for uses pathlib.Path.relative_to for native ValueError-on-outside-root behavior
- [Phase 02]: networkx added via uv add with no version ceiling (no known compatibility issue)
- [Phase 02]: Kept task's explicit tests/__init__.py instruction (10th fixture file) over plan's stale hardcoded 9-file verify count; D-13 sizes the fixture at roughly 8-10 files, so 10 is within design intent
- [Phase 02]: Confirmed tree-sitter-python import-statement grammar shapes empirically before implementation (no re-derivation from memory) -- all 9 cited statement shapes matched the plan's interfaces block exactly
- [Phase 02]: 02-04: calls.py reuses python_symbols.py's private _Frame/_qualified_name/_node_name helpers directly rather than reimplementing scope-stack logic, establishing the cross-module reuse pattern for Plan 05/06 resolvers
- [Phase 02]: 02-04: extract_raw_calls/extract_raw_class_bases implemented as two fully independent tree traversals in one file (not merged), matching the existing _walk_symbols/_collect_syntax_issues separate-pass precedent
- [Phase 02]: 02-05: import resolution is a pure two-pass operation; direct/relative/external classification runs per file, while verified package re-exports and star expansion run over the full project binding map
- [Phase 02]: 02-05: symbol-table membership is the sole source of truth for external modules; unresolvable external star imports remain explicit unresolved bindings
- [Phase 02]: 02-06: Call resolution uses a deterministic iterative hierarchy walk and produces one resolved edge or explicit unresolved/uncertain record per call site.
- [Phase 02]: 02-07: Call graph uses serializable node attributes and keeps unresolved/uncertain calls outside traversal; helpers sort and safely return empty results.
- [Phase 02]: 02-08: Project-wide import passes finish before any call resolution; partial analysis is recorded explicitly.
- [Phase 02]: 02-09: Exact fixture inventory retains the dynamic getattr call as explicit unresolved evidence; intentional empty package files are recorded as empty.
- [Phase 03]: Raw receiver constructor text remains unverified until import and registration resolution.
- [Phase 03]: Only eligible unshadowed imports prove receivers/router mounts; unsupported forms remain diagnostics.
- [Phase 03]: Reverse BFS returns one canonical shortest verified chain per route/change; limits report actual omissions.
- [Phase 03]: The public library API exposes graph, routes, impacts and conservative partial/truncation indicators together.
- [Phase 04]: Immutable merge-base/head snapshots retain target-base identity separately; changed symbols and links preserve revision provenance.
- [Phase 04]: Synchronous POST uses a caller UUID for concurrent polling, one active analysis per process, and cooperative deadlines through cleanup.
- [Phase 04]: User approved core FastAPI and required transitives; dependency lock and exports are synchronized.
- [Phase 04]: User confirmed pinned-source highlighting; 18/18 must-haves, 554 tests and live API verification passed.

- [Phase 05]: Canonical UTF-8 JSON includes one final newline in byte limits and artifact hashes.
- [Phase 05]: Publish status/report atomically after source cleanup; controlled demos never invoke live analysis.
- [Phase 05]: Independent gold retains source-known unsupported relationships as false negatives.

### Pending Todos

None.

### Blockers/Concerns

The fixture returns partial=True because ordinary constructor assignments also trigger conservative route diagnostics; verified paths remain usable. Editable installs can still fail in this macOS environment; use the documented --no-editable workaround for console scripts.

## Session Continuity

Last session: 2026-11-01T17:47:15Z
Stopped at: Phase 5 complete; 15/15 must-haves and four roadmap criteria verified.
Next: $gsd-plan-phase 6. No pending approval or human verification for Phase 5.
Resume file: None
