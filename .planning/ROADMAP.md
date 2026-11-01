# Roadmap: CodeScope AI

## Overview

CodeScope AI goes from zero to a hosted GitHub PR impact analyser in eight phases, each lining up 1:1 with the
stage numbering already used in `TASKS.md` and GitHub Issues, and directly with steps 3-10 of ARCHITECTURE.md's
"Potential first steps". The build is strictly bottom-up: Tree-sitter symbol extraction first (independent of any
web framework), then import resolution and a NetworkX call graph, then FastAPI route detection and reverse-impact
tracing, then real GitHub PR ingestion wired to those analysis primitives, then a structured report format
evaluated against hand-labelled fixtures, then a cited Gemini explanation layered on top of that report, then the
React/Vite frontend that exposes all of it interactively, and finally a restricted, cost-bounded Cloud Run
deployment with caching. Every phase produces something independently verifiable before the next phase builds on
it; nothing downstream (API, RAG, UI, deployment) is built before its upstream analysis primitives exist and are
tested.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Python symbol extraction** - Tree-sitter extractor returns structured symbol data, independent of FastAPI
- [x] **Phase 2: Imports, resolution, call graph** - Resolve imports/direct calls into a NetworkX call graph with explicit unresolved edges (completed 2026-11-01)
- [ ] **Phase 3: FastAPI routes & impact paths** - Detect FastAPI routes and trace reverse-dependency paths from changes to routes
- [ ] **Phase 4: PR ingestion & diff mapping** - Fetch real PRs at pinned SHAs, map diffs to symbols, expose status/progress via the API
- [ ] **Phase 5: Report JSON & evaluation** - Build structured report JSON and evaluate it against hand-labelled fixtures, before Gemini
- [ ] **Phase 6: RAG & Gemini summary** - Bounded, cited Gemini impact explanation over untrusted repository evidence
- [ ] **Phase 7: Frontend** - React/Vite/Tailwind/shadcn app with an interactive React Flow dependency graph
- [ ] **Phase 8: Deployment, limits, caching** - Restricted Cloud Run deployment with abuse/cost limits and caching

## Phase Details

### Phase 1: Python symbol extraction
**Goal**: Tree-sitter-based extractor returns structured symbol data (functions/classes/methods/nested functions)
with qualified names and line ranges, independent of FastAPI
**Depends on**: Nothing (first phase)
**Requirements**: US-02
**Success Criteria** (what must be TRUE):
  1. Extractor returns structured symbol data (name, qualified name, kind, file path, start/end line) for
     functions, classes, methods and nested functions in a Python file
  2. Empty files and files with syntax errors are handled explicitly — surfaced as a clear result/error, never a
     crash or silent omission
  3. A CLI invocation outputs extracted symbols as JSON
  4. A pytest suite covers all supported symbol cases (functions, classes, methods, nested functions, empty
     files, syntax errors)
  5. The symbol-extraction module has zero import-time or runtime dependency on FastAPI
**Plans**: TBD

### Phase 2: Imports, resolution, call graph
**Goal**: Resolve imports and direct calls into a NetworkX call graph; unresolved edges are explicit, never
invented
**Depends on**: Phase 1
**Requirements**: US-03
**Success Criteria** (what must be TRUE):
  1. Import statements are resolved to their defining module/symbol where determinable
  2. Direct function/method calls are resolved into call-graph edges connecting caller to callee
  3. The call graph is a queryable NetworkX graph (callers/callees of a given symbol can be retrieved)
  4. Calls that cannot be resolved (dynamic, external or ambiguous targets) are explicitly flagged as unresolved
     rather than omitted or guessed at
  5. Fixtures deterministically verify both resolved and unresolved edge cases
**Plans**: 9 plans (7 waves)

Plans:
- [x] 02-01-PLAN.md — Wave 1: Symbol.module_path + new resolution contracts + module_path_for (D-08) + add networkx dependency
- [x] 02-02-PLAN.md — Wave 1: Build the real fixtures/sample_fastapi_repo/ sample package (CS-020)
- [x] 02-03-PLAN.md — Wave 2: Raw import statement extraction (CS-021, import half)
- [x] 02-04-PLAN.md — Wave 2: Raw call-site + class-base extraction (CS-021, call half)
- [x] 02-05-PLAN.md — Wave 3: Import resolver -- direct/relative/external + re-export hop + star expansion (CS-022, import half)
- [x] 02-06-PLAN.md — Wave 4: Class hierarchy index + call resolver (CS-022, call half)
- [x] 02-07-PLAN.md — Wave 5: NetworkX call graph builder + query API (CS-023)
- [x] 02-08-PLAN.md — Wave 6: Multi-file orchestrator (build_project_graph) + codescope-graph CLI
- [x] 02-09-PLAN.md — Wave 7: Fixture integration tests verifying exact resolved/unresolved edges

### Phase 3: FastAPI routes & impact paths
**Goal**: Detect FastAPI route declarations and trace reverse-dependency paths from changed symbols to routes;
a negative fixture proves no false positives
**Depends on**: Phase 2
**Requirements**: US-04
**Success Criteria** (what must be TRUE):
  1. FastAPI route declarations (e.g. `@app.get`, `@router.post`) are detected and recorded with their
     path/method and handler symbol
  2. Given a changed symbol, reverse-dependency traversal of the call graph identifies which routes are
     potentially affected
  3. A positive fixture (change reaches a route) produces the expected affected route
  4. A negative fixture (unrelated change) produces no affected routes, proving the analysis does not invent
     false positives
  5. Each reported route-impact result includes the full chain of symbols connecting the change to the route
**Plans**: TBD

### Phase 4: PR ingestion & diff mapping
**Goal**: GitHub REST client fetches PR metadata/diffs at pinned SHAs; diff lines map to symbols; `/api/analyses`
and `/health` expose status/progress/error states
**Depends on**: Phase 3
**Requirements**: US-01, US-09, US-12
**Success Criteria** (what must be TRUE):
  1. User can submit a supported GitHub PR URL and the system fetches PR metadata and diff at pinned base/head
     commit SHAs
  2. Submitting an unsupported or malformed PR URL returns a clear, specific error rather than a generic failure
  3. Changed diff lines are mapped to the enclosing symbol(s) across both revisions
  4. `GET /api/analyses/{id}` reports progress through meaningful states (e.g. pending, running, complete, error,
     timeout), and `GET /health` confirms basic service availability
  5. Every returned source reference is pinned to the exact analysed commit SHA, never a mutable branch
     reference
**Plans**: TBD

### Phase 5: Report JSON & evaluation
**Goal**: Structured report JSON (findings, uncertainties, source links) built before Gemini is added; evaluated
against hand-labelled fixtures
**Depends on**: Phase 4
**Requirements**: US-11
**Success Criteria** (what must be TRUE):
  1. `GET /api/analyses/{id}/report` returns structured JSON containing findings, uncertainties and source links,
     with no dependency on Gemini
  2. A visitor can open a precomputed demo report without any sign-in or authentication step
  3. Report output is evaluated against hand-labelled fixtures, with measured call-edge and endpoint-impact
     precision/recall
  4. Uncertain or unresolved relationships appear in the report as explicit uncertainties, never asserted as
     fact
**Plans**: TBD

### Phase 6: RAG & Gemini summary
**Goal**: Bounded LangChain evidence assembly plus ephemeral Chroma retrieval feed a cited Gemini impact
explanation; repository text is treated as untrusted (prompt-injection hardening)
**Depends on**: Phase 5
**Requirements**: US-05
**Success Criteria** (what must be TRUE):
  1. User can read a concise AI-generated impact explanation for an analysed PR
  2. Every claim in the explanation is grounded in cited source evidence (specific files/lines/graph paths), not
     free-form assertion
  3. The context sent to Gemini is bounded (size/token limits) and assembled via LangChain from graph paths plus
     Chroma semantic retrieval
  4. A fixture containing prompt-injection-style content embedded in repository text does not alter the
     explanation's instructions or leak system prompt content
**Plans**: TBD

### Phase 7: Frontend
**Goal**: Vite/React/TypeScript/Tailwind/shadcn app with a React Flow dependency graph, submission flow,
progress/error states and a demo report viewer
**Depends on**: Phase 6
**Requirements**: US-08
**Success Criteria** (what must be TRUE):
  1. User can submit a GitHub PR URL via the frontend form and see the analysis status update as it progresses
  2. User can explore the PR's dependency graph interactively (pan/zoom/select nodes), rendered with React Flow
  3. User can select a specific path in the graph and inspect the symbols and edges that make it up
  4. User can view a precomputed demo report in the UI without signing in
  5. User sees a clear error state in the UI if an analysis fails or times out
**Plans**: TBD
**UI hint**: yes

### Phase 8: Deployment, limits, caching
**Goal**: Cloud Run deployment (min 0 / max 1 instances), abuse and cost limits, billing alerts, caching by
repo + base SHA + head SHA + analyser version, optional Firestore/GCS persistence
**Depends on**: Phase 7
**Requirements**: US-13
**Success Criteria** (what must be TRUE):
  1. The deployed service runs on Cloud Run with min instances 0 and max instances 1, scaling to zero when idle
  2. Live analysis requests beyond a defined concurrency/rate limit are rejected or queued, preventing runaway
     cost
  3. Repeating an analysis for the same repository + base SHA + head SHA + analyser version returns the cached
     result instead of recomputing
  4. Billing alerts are configured and fire before the £5/month ceiling is exceeded
  5. Only PRs from an approved repository allowlist can be submitted for live analysis; all others are rejected
     with a clear error
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Python symbol extraction | 0/TBD | Not started | - |
| 2. Imports, resolution, call graph | 6/9 | In progress | - |
| 3. FastAPI routes & impact paths | 0/TBD | Not started | - |
| 4. PR ingestion & diff mapping | 0/TBD | Not started | - |
| 5. Report JSON & evaluation | 0/TBD | Not started | - |
| 6. RAG & Gemini summary | 0/TBD | Not started | - |
| 7. Frontend | 0/TBD | Not started | - |
| 8. Deployment, limits, caching | 0/TBD | Not started | - |

---
*Roadmap created: 2026-11-01*
*Last updated: 2026-11-01 — initial 8-phase structure, formalised from ARCHITECTURE.md steps 3-10 (pre-approved
before this roadmap step)*
