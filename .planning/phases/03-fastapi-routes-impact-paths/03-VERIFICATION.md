---
phase: 03-fastapi-routes-impact-paths
verified: 2026-11-01T16:21:09Z
status: passed
score: 12/12 must-haves verified
---

# Phase 3: FastAPI Routes & Impact Paths Verification Report

**Phase Goal:** Detect FastAPI route declarations and trace reverse-dependency paths from changed symbols to routes; a negative fixture proves no false positives.
**Verified:** 2026-11-01T16:21:09Z
**Status:** passed
**Re-verification:** No — initial verification; no previous Phase 03 VERIFICATION.md existed.

## Goal Achievement

Verification used the 12 truths declared across all four plans, cross-checked against all five ROADMAP success criteria. Actual implementation and test assertions were inspected independently of SUMMARY claims. ARCHITECTURE.md, AGENTS.md, CLAUDE.md, ROADMAP.md, REQUIREMENTS.md, and all Phase 03 plans/summaries supplied context. Neither `.claude/skills/` nor `.agents/skills/` exists in this repository.

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Route declarations retain method, literal path, handler identity and source location. | ✓ VERIFIED | `routes.py:106` extracts eight HTTP methods, sync/async and stacked top-level decorators using existing symbol identities; `test_routes.py` asserts methods, literal paths and exact source lines. |
| 2 | Raw syntax is distinguished from verified FastAPI registration. | ✓ VERIFIED | `RouteSyntax` candidates and `RouteDeclaration` remain separate from `RouteRegistration`; only the resolver creates registrations after constructor and include proof. Disconnected routers remain declarations. |
| 3 | Only receivers proven to originate from FastAPI constructors produce verified registrations. | ✓ VERIFIED | `route_resolver.py:44` accepts explicit absolute FastAPI constructor/module imports with one eligible unshadowed binding. Fake constructors, stars, conditional/local imports and reassignment are covered by negative tests. |
| 4 | Effective paths include literal router and include prefixes across supported repository imports. | ✓ VERIFIED | `_include_target` and iterative mount traversal resolve local/direct absolute/relative imports and supported module attributes, compose nested prefixes and retain trailing slashes and multiple mounts. Resolver and project integration assertions exercise these forms. |
| 5 | Unsupported or ambiguous registration remains explicit evidence and never becomes a verified endpoint. | ✓ VERIFIED | Scope, path, prefix, receiver/import and argument expansion failures create source-located diagnostics; affected syntax records are excluded. Resolver tests assert zero guessed registrations and retained diagnostics. |
| 6 | A changed symbol returns potentially affected registered routes with verified symbol chains and call-site evidence. | ✓ VERIFIED | `impact.py:16` traverses graph predecessors and reconstructs handler-to-change chains; `CallSiteEvidence` uses caller source paths and every unique sorted edge line. Unresolved calls are stored separately by `call_graph.py` and never consulted. |
| 7 | Unknown or disconnected symbols produce no affected routes. | ✓ VERIFIED | Unit tests distinguish unknown ids from known disconnected nodes and unresolved-only links. Read-only API invocation returned no impacts for both negative fixture changes and reported only `missing:symbol` as unknown. |
| 8 | Cyclic and branching graphs terminate with deterministic bounded results. | ✓ VERIFIED | Iterative sorted BFS, visited/parent maps, invocation-wide 10,000-discovery and 1,000-path limits; tests cover cycles, diamonds, insertion order, exact boundaries, caps 0/1, unchanged inputs and a 1,100-symbol chain. |
| 9 | A directory can be analysed for registered routes and changed-symbol impact through a public package API. | ✓ VERIFIED | `__init__.py:23` exports `ProjectImpactAnalysis`/`analyze_route_impacts`; `project_routes.py:25` builds the graph once, reparses only retained source paths, resolves inventory and invokes impact traversal. Direct package API spot-checks succeeded. |
| 10 | Authentication helper changes reach exactly the expected two fixture routes. | ✓ VERIFIED | `test_route_impact_fixture.py` and direct API output agree: `GET /users/me` and `PUT /users/{user_id}`, with exact handler→`services.auth:get_current_user` chains and call lines 13/21. |
| 11 | Unrelated or unsupported-only changes reach zero fixture routes. | ✓ VERIFIED | Exact negative assertions and direct API check return zero routes for `callers:call_twice` and `services.base:BaseService.audit`. The existing `auth.login` unresolved record remains visible; no inferred receiver type bridges it. |
| 12 | Partial parse/file analysis and traversal truncation remain visible to callers. | ✓ VERIFIED | `project_routes.py:61` combines non-ok/empty file statuses, route diagnostics and all three truncation flags; 14 project tests cover syntax/decode/unreadable files, late read failures, file caps, route/impact/unresolved caps and import isolation. |

**Score:** 12/12 truths verified. All five ROADMAP criteria are represented by truths 1, 6, 10, 11 and 6/10 respectively.

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `backend/app/analysis/route_models.py` | Source-located route, inventory and impact contracts | ✓ VERIFIED | Eight substantive Pydantic classes, validated positive lines and independent mutable defaults; consumed by extraction, resolution, traversal and public results. The plan's prose count of seven does not change its eight explicitly named contracts. |
| `backend/app/analysis/routes.py` | `extract_route_syntax` | ✓ VERIFIED | Tree-sitter extraction, literal-only parsing, structural import eligibility, binding inventory and diagnostics; invoked by project orchestration. |
| `backend/app/analysis/route_resolver.py` | `resolve_route_inventory` | ✓ VERIFIED | Constructor/import proof and bounded project-wide registration traversal; its returned inventory feeds impact analysis. |
| `backend/app/analysis/impact.py` | `find_affected_routes` | ✓ VERIFIED | Deterministic bounded reverse traversal and complete evidence reconstruction; public project API invokes it with verified registrations. |
| `backend/app/analysis/project_routes.py` | `ProjectImpactAnalysis`, `analyze_route_impacts` | ✓ VERIFIED | Publicly exported and exercised by integrations and direct read-only source-tree analysis. |
| `backend/tests/test_route_impact_fixture.py` | Hand-written positive/negative inventories | ✓ VERIFIED | Exact registrations, positive paths, call/declaration/mount evidence, negatives, self-impact, unknown ids and original graph counts. Collected and run successfully. |

`gsd-tools verify artifacts` passed **6/6** artifacts across all four plans. Manual verification additionally checked substantive implementation and actual use; helper pattern matches were not treated as sufficient proof.

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `routes.py` | `python_symbols.py` | `extract_symbols` | ✓ WIRED | Extracted definition start lines map decorators to existing qualified names and handler ranges. |
| `route_resolver.py` | `routes.py` | `RouteSyntax` | ✓ WIRED | Consumes declarations, receivers, includes, structural eligible imports, binding counts and diagnostics. Broader raw imports cannot restore excluded import proof. |
| `impact.py` | `call_graph.py` | Verified predecessors and edge evidence | ✓ WIRED | Reads only `CallGraph.graph`, sorted predecessors, caller node paths and edge lines; unresolved inventory remains separate. |
| `project_routes.py` | `route_resolver.py` | Source extraction and project resolution | ✓ WIRED | Builds module syntax/import inventories from retained paths and calls resolver once; returned registrations are used. |
| `project_routes.py` | `impact.py` | Graph plus verified registrations | ✓ WIRED | Passes existing graph, resolved registrations and supplied changed ids; returns actual `ImpactResult` together with diagnostics. |

`gsd-tools verify key-links` passed **5/5** links, confirmed by manual call/return tracing. Package exports provide the additional public entry-point link.

### Data-Flow Trace (Level 4)

This phase delivers an analysis library, with no dynamic UI artifacts. The equivalent upstream result trace was nevertheless checked end to end:

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `project_routes.py` | `syntax_by_module`, statuses | Retained `ProjectGraph.file_statuses` → source `read_bytes` → Tree-sitter extraction | Yes; actual fixture files, no imports/execution of analysed source | ✓ FLOWING |
| `route_resolver.py` | `registrations` | Eligible imports, constructor/binding proof, declarations and include graph | Yes; exact two fixture registrations and nested-prefix integration results | ✓ FLOWING |
| `impact.py` | `impacts`, symbols, edges | Verified registrations + resolved NetworkX graph predecessors/edge source lines | Yes; exact two helper paths and zero negative paths | ✓ FLOWING |
| `project_routes.py` | `ProjectImpactAnalysis` | Actual graph, inventory, impacts, statuses and flags | Yes; package API exposes all computed outputs and original unresolved evidence | ✓ FLOWING |

No static response, hollow input or disconnected result was found. Empty defaults/accumulators are populated from source; empty negative results are intentional tested outcomes.

### Behavioral Spot-Checks

Each direct invocation below completed in under one second, used the existing environment and read repository source only. No server, repository module execution, dependency installation, persistent mutation or external service was used.

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Exact positive paths and evidence | `uv run --no-sync python -c '…analyze_route_impacts("../fixtures/sample_fastapi_repo", ["services.auth:get_current_user"])…'` | Exact GET/PUT paths, handler→helper chains, call lines 13/21; partial flag and both diagnostic reasons visible | ✓ PASS |
| Negative precision and unknown id | Same API invocation with audit, call_twice and missing symbol ids | `impacts=[]`, `unknown_symbols=['missing:symbol']` | ✓ PASS |
| Self-impact and import isolation | Same API invocation for `routes.users:get_user`, plus `sys.modules` assertion | One-symbol chain, no call edges, FastAPI absent from imported modules | ✓ PASS |
| Syntax/resolution/traversal/fixture regressions | `uv run --no-sync python -m pytest tests/test_routes.py tests/test_route_resolver.py tests/test_impact.py tests/test_route_impact_fixture.py -q` | **108 passed in 0.30s** | ✓ PASS |
| Public API, errors, partial flags and isolation | `uv run --no-sync python -m pytest tests/test_project_routes.py -q` | **14 passed in 0.40s**; tests use isolated temporary source trees | ✓ PASS |
| Phase implementation/test lint | `uv run --no-sync ruff check` on all five phase modules and five phase test files | All checks passed | ✓ PASS |

The verifier independently ran **122 phase tests**. The coordinator separately reports the complete backend suite **246 passed** and whole-backend Ruff passing; these are coordinator results, not additional verifier runs. The fixture regression independently preserves **10 verified edges**, **7 unresolved calls** and **10 retained file statuses**.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| US-04 | 03-01 | User can see potentially affected FastAPI routes and paths connecting them to a change | ✓ SATISFIED contribution | Source-located route/impact contracts and literal syntax extraction establish inspectable declarations. |
| US-04 | 03-02 | Same requirement | ✓ SATISFIED contribution | Proven FastAPI registrations, effective paths and constructor/include evidence. |
| US-04 | 03-03 | Same requirement | ✓ SATISFIED contribution | Verified canonical handler-to-change chains with all edge evidence and explicit limits. |
| US-04 | 03-04 | Same requirement | ✓ SATISFIED | Public library exposes integrated results; exact positive/negative fixture assertions and direct calls demonstrate the supported local-analysis outcome. |

All four plans declare US-04. REQUIREMENTS.md maps only US-04 to Phase 3, so there are **no orphaned requirements**. Completion here concerns the Phase 3 analysis-library contract; frontend presentation, PR ingestion/diff mapping and pinned revision links remain their separately assigned later phases.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `backend/app/analysis/routes.py` | 184 | Broad call-result assignment candidate extraction | ℹ️ Info | Non-router call assignments can produce conservative unsupported/unproven diagnostics. This is documented, tested and visible as `partial=True`, while the two supported fixture registrations remain verified. |
| `backend/app/analysis/__init__.py` | 3 | Original docstring says all logic lives in only two older modules | ℹ️ Info | Minor stale package description; current imports/exports and library behavior are correct. No goal impact. |

Scan of all phase implementation/test files and README found no TODO/FIXME/placeholder implementations. Initial empty collections are populated by source extraction/traversal. `ast.literal_eval` is restricted to Tree-sitter string literals; f-strings, bytes and dynamic expressions are excluded. No production code evaluates/imports analysed source or installs its dependencies. No new dependencies or infrastructure are required for this phase.

### Human Verification Required

None for this bounded source-analysis library phase. No visual UI, live service integration or real-time interaction is part of its contract. Passing static fixtures does not establish exhaustive route recall, runtime execution or universal absence of false positives in arbitrary repositories.

### Gaps Summary

No blocking implementation or wiring gaps were found. The exact hand-labelled fixture demonstrates both positive route reachability and negative precision without inventing links through unresolved `auth.login`.

The fixture deliberately remains **`partial=True`**: unrelated call-result assignments produce `receiver_scope_or_assignment_unsupported` and `receiver_unproven_or_shadowed` diagnostics. Those diagnostics are preserved rather than suppressed. The supported registrations and their evidence remain usable, while consumers can inspect incompleteness explicitly. Factories, re-export chains, dynamic paths/prefixes, wildcard/shadowed bindings, conditional/local registrations and argument expansion remain outside the verified supported scope. Paths are one deterministic shortest supported chain per registration/change pair, not all runtime paths. Changed symbol ids are supplied by the caller; revision diff/removed-symbol mapping is deferred to Phase 4.

---

_Verified: 2026-11-01T16:21:09Z_
_Verifier: Codex (gsd-verifier)_
