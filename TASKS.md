# CodeScope AI — Project Backlog

This file mirrors the phase state tracked by GSD under `.planning/`. It exists to give a
flat, human-readable view of every ticket, its linked GitHub Issue, and its acceptance
criteria, stage by stage.

> **Anti-drift rule:** GSD owns in-flight phase state; TASKS.md ticket status changes only
> at phase boundaries. Mid-phase progress should be read from `/gsd:progress`, never
> hand-edited here.

Ticket IDs use the `CS-0NN` scheme. Stage 1 tickets (`CS-010`–`CS-016`) each have an
individual GitHub Issue. Stage 2–8 tickets are tracked as checklist items inside a single
epic Issue per stage (`Stage N: <name>`), not as individual Issues.

---

## User story coverage

Every user story US-01…US-13 must map to an owning ticket so nothing silently drops.

| Story | Owning ticket(s) | Stage |
| --- | --- | --- |
| US-01 | CS-040 (GitHub REST client) | Stage 4 |
| US-02 | CS-010–CS-016 (Python symbol extraction) | Stage 1 |
| US-03 | CS-023 (NetworkX graph + reverse reachability) | Stage 2 |
| US-04 | CS-031 (changed-symbol → route tracing) | Stage 3 |
| US-05 | CS-062 (cited Gemini explanation) | Stage 6 |
| US-06 | CS-090 (follow-up Q&A) | Deferred (Later) |
| US-07 | CS-091 (candidate test selection) | Deferred (Later) |
| US-08 | CS-071 (React Flow graph + path selection) | Stage 7 |
| US-09 | CS-043 (`/api/analyses` + `/health` progress states) | Stage 4 |
| US-10 | CS-081 (abuse & cost limits + billing alerts) | Stage 8 |
| US-11 | CS-051 (evaluation harness on labelled fixtures) | Stage 5 |
| US-12 | CS-043 (`/api/analyses` + `/health` error states) | Stage 4 |
| US-13 | CS-080 (Dockerfile + Cloud Run deploy) | Stage 8 |

---

## Stage 0 — Project bootstrap (pre-GSD)

| ID | Title | Story | GSD Phase | Status | Acceptance criteria | Issue |
| --- | --- | --- | --- | --- | --- | --- |
| CS-001 | Repo + folder scaffold | — | — | **DONE** | Repository and backend/frontend/fixtures/infra/docs folders created | (none, already done pre-GSD) |
| CS-002 | Core docs + .gitignore | — | — | **DONE** | ARCHITECTURE.md, AGENTS.md, README.md, .gitignore committed | (none, already done pre-GSD) |
| CS-003 | GitHub Actions CI | — | — | **IN PROGRESS** | CI runs backend pytest and frontend Vitest on push | (none — workflow authored at `.github/workflows/backend-ci.yml`, YAML-validated locally; backend half only — frontend Vitest doesn't exist until Stage 7; cannot confirm an actual green run until this branch is pushed, which is outside the current "no pushes without approval" agreement) |

---

## Stage 1 — Python symbol extraction

Epic story: US-02 · GSD Phase 1

| ID | Title | Story | GSD Phase | Status | Acceptance criteria | Issue |
| --- | --- | --- | --- | --- | --- | --- |
| CS-010 | Backend Python project scaffold | US-02 | 1 | **DONE** | `uv sync --extra dev` succeeds; `app` importable; pytest configured | https://github.com/esharif20/codescope-ai/issues/1 |
| CS-011 | Pydantic symbol models | US-02 | 1 | **DONE** | `Symbol`, `SymbolKind`, `SyntaxIssue`, `ParseResult`, `ParseStatus` validate and round-trip to JSON | https://github.com/esharif20/codescope-ai/issues/2 |
| CS-012 | Tree-sitter Python parser setup | US-02 | 1 | **DONE** | Language built once at import; smoke test parses a trivial module | https://github.com/esharif20/codescope-ai/issues/3 |
| CS-013 | Symbol extraction with qualified names + ranges | US-02 | 1 | **DONE** | Top-level functions, classes, methods, nested functions in source order with exact 1-based line ranges | https://github.com/esharif20/codescope-ai/issues/4 |
| CS-014 | Explicit empty / syntax-error / decode handling | US-02 | 1 | **DONE** | Empty → `empty`; broken → `syntax_errors` with recovered symbols and error ranges; non-UTF-8 → `decode_error`; never raises | https://github.com/esharif20/codescope-ai/issues/5 |
| CS-015 | JSON CLI | US-02 | 1 | **DONE** | `codescope-parse FILE` prints valid JSON, exit 0; missing file → stderr, exit 1. Verified via the literal installed console script directly (root-caused and fixed a global `uv<0.13` bug that was breaking it — see note below), plus `python -m app.analysis.cli` and exit codes 0/0/0/1 across ok/empty/syntax_errors/missing-file | https://github.com/esharif20/codescope-ai/issues/6 |
| CS-016 | pytest suite | US-02 | 1 | **DONE** | All supported cases green (46/46); guard test asserts `fastapi` is never imported by `app.analysis` | https://github.com/esharif20/codescope-ai/issues/7 |

**Stage 1 complete, no open caveats.** Two genuine issues were found and fixed during verification
(not contract ambiguities):
- `tree-sitter==0.26.0` reference-counting bug that segfaults on deeply nested trees — reproduced,
  isolated by bisection, fixed by pinning `<0.26`.
- `uv<0.13` wrote editable-install `.pth` files with macOS's `UF_HIDDEN` flag set, which CPython
  3.13's `site.py` silently skips, breaking the installed `codescope-parse` console script.
  Confirmed the fix in an isolated test venv, upgraded the global `uv` (0.11.2 → 0.13.6, approved),
  rebuilt the backend `.venv`, and pinned `[tool.uv] required-version = ">=0.13"` in
  `backend/pyproject.toml` so this can't silently reproduce for any contributor or in CI.

CI workflow (`.github/workflows/backend-ci.yml`) pins `setup-uv` to the same confirmed-fixed
version. All commands it runs (`uv sync --extra dev --locked`, `ruff check`, `pytest -q`) verified
locally against the exact same invocations. Full detail in the `feat:`/fix-up commit messages and
`backend/README.md`.

---

## Stage 2 — Imports, resolution, call graph

Epic story: US-03 · GSD Phase 2 · Epic issue: https://github.com/esharif20/codescope-ai/issues/8

| ID | Title | Story | GSD Phase | Status | Acceptance criteria | Issue |
| --- | --- | --- | --- | --- | --- | --- |
| CS-020 | Sample FastAPI fixture repo | US-03 | 2 | **TODO** | See epic for full context | tracked in epic #8 |
| CS-021 | Import/call-site extraction | US-03 | 2 | **TODO** | See epic for full context | tracked in epic #8 |
| CS-022 | Resolver + explicit unresolved status | US-03 | 2 | **TODO** | See epic for full context | tracked in epic #8 |
| CS-023 | NetworkX graph + reverse reachability | US-03 | 2 | **TODO** | See epic for full context | tracked in epic #8 |

---

## Stage 3 — FastAPI routes & impact paths

Epic story: US-04 · GSD Phase 3 · Epic issue: https://github.com/esharif20/codescope-ai/issues/9

| ID | Title | Story | GSD Phase | Status | Acceptance criteria | Issue |
| --- | --- | --- | --- | --- | --- | --- |
| CS-030 | Route declaration detection | US-04 | 3 | **TODO** | See epic for full context | tracked in epic #9 |
| CS-031 | Changed-symbol → route tracing | US-04 | 3 | **TODO** | See epic for full context | tracked in epic #9 |
| CS-032 | Negative fixture (no false routes) | US-04 | 3 | **TODO** | See epic for full context | tracked in epic #9 |

---

## Stage 4 — PR ingestion & diff mapping

Epic story: US-01 / US-02 / US-09 / US-12 · GSD Phase 4 · Epic issue: https://github.com/esharif20/codescope-ai/issues/10

| ID | Title | Story | GSD Phase | Status | Acceptance criteria | Issue |
| --- | --- | --- | --- | --- | --- | --- |
| CS-040 | GitHub REST client (allowlist+limits) | US-01 | 4 | **TODO** | See epic for full context | tracked in epic #10 |
| CS-041 | Diff → symbol mapping | US-02 | 4 | **TODO** | See epic for full context | tracked in epic #10 |
| CS-042 | SHA-pinned permalinks | US-01 | 4 | **TODO** | See epic for full context | tracked in epic #10 |
| CS-043 | `/api/analyses` + `/health` with status/error states | US-09 / US-12 | 4 | **TODO** | See epic for full context | tracked in epic #10 |

---

## Stage 5 — Report JSON & evaluation

Epic story: US-11 · GSD Phase 5 · Epic issue: https://github.com/esharif20/codescope-ai/issues/11

| ID | Title | Story | GSD Phase | Status | Acceptance criteria | Issue |
| --- | --- | --- | --- | --- | --- | --- |
| CS-050 | Report schema | US-11 | 5 | **TODO** | See epic for full context | tracked in epic #11 |
| CS-051 | Evaluation harness on labelled fixtures | US-11 | 5 | **TODO** | See epic for full context | tracked in epic #11 |
| CS-052 | Precomputed demo reports | US-11 | 5 | **TODO** | See epic for full context | tracked in epic #11 |

---

## Stage 6 — RAG & Gemini summary

Epic story: US-05 · GSD Phase 6 · Epic issue: https://github.com/esharif20/codescope-ai/issues/12

| ID | Title | Story | GSD Phase | Status | Acceptance criteria | Issue |
| --- | --- | --- | --- | --- | --- | --- |
| CS-060 | Bounded evidence assembly | US-05 | 6 | **TODO** | See epic for full context | tracked in epic #12 |
| CS-061 | Ephemeral Chroma retrieval | US-05 | 6 | **TODO** | See epic for full context | tracked in epic #12 |
| CS-062 | Cited Gemini explanation + injection hardening | US-05 | 6 | **TODO** | See epic for full context | tracked in epic #12 |

---

## Stage 7 — Frontend

Epic story: US-08 · GSD Phase 7 · Epic issue: https://github.com/esharif20/codescope-ai/issues/13

| ID | Title | Story | GSD Phase | Status | Acceptance criteria | Issue |
| --- | --- | --- | --- | --- | --- | --- |
| CS-070 | Vite+React+TS+Tailwind scaffold | US-08 | 7 | **TODO** | See epic for full context | tracked in epic #13 |
| CS-071 | React Flow graph + path selection | US-08 | 7 | **TODO** | See epic for full context | tracked in epic #13 |
| CS-072 | Submission + progress/timeout/error states | US-08 | 7 | **TODO** | See epic for full context | tracked in epic #13 |
| CS-073 | Demo report viewer | US-08 | 7 | **TODO** | See epic for full context | tracked in epic #13 |

---

## Stage 8 — Deployment, limits, caching

Epic story: US-13 / US-10 · GSD Phase 8 · Epic issue: https://github.com/esharif20/codescope-ai/issues/14

| ID | Title | Story | GSD Phase | Status | Acceptance criteria | Issue |
| --- | --- | --- | --- | --- | --- | --- |
| CS-080 | Dockerfile + Cloud Run (min 0 / max 1) | US-13 | 8 | **TODO** | See epic for full context | tracked in epic #14 |
| CS-081 | Abuse & cost limits + billing alerts | US-10 | 8 | **TODO** | See epic for full context | tracked in epic #14 |
| CS-082 | Cache by repo+base SHA+head SHA+analyser version | — | 8 | **TODO** | See epic for full context | tracked in epic #14 |
| CS-083 | Optional Firestore/GCS persistence | — | 8 | **TODO** | See epic for full context | tracked in epic #14 |

---

## Deferred (Later stories)

Out of the current roadmap per PROJECT.md/REQUIREMENTS.md — no GSD phase assigned.

| ID | Title | Story | GSD Phase | Status | Acceptance criteria | Issue |
| --- | --- | --- | --- | --- | --- | --- |
| CS-090 | US-06 follow-up Q&A | US-06 | — | **TODO (Later)** | — | (none — deferred, TASKS.md-only) |
| CS-091 | US-07 candidate test selection | US-07 | — | **TODO (Later)** | — | (none — deferred, TASKS.md-only) |
