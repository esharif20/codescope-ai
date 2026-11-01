---
phase: 05-report-json-evaluation
verified: 2026-11-01T17:45:07Z
status: passed
score: 15/15 must-haves verified
---

# Phase 5: Report JSON & evaluation Verification Report

**Phase Goal:** Structured report JSON (findings, uncertainties, source links) built before Gemini is added; evaluated against hand-labelled fixtures.
**Verified:** 2026-11-01T17:45:07Z
**Status:** passed
**Re-verification:** No — initial verification; no previous Phase 05 VERIFICATION.md existed.

## Goal Achievement

Read ARCHITECTURE.md, AGENTS.md, CLAUDE.md, ROADMAP.md, REQUIREMENTS.md, all five plans and summaries. No project skill directories exist under `.claude/skills` or `.agents/skills`. Verification used implementation, fixture source and executed checks rather than treating summaries as proof. Scope is the deterministic backend JSON contract; the frontend belongs to Phase 7.

### Roadmap Success Criteria

| # | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| 1 | GET `/api/analyses/{id}/report` returns findings, uncertainties and source links without Gemini | VERIFIED | `backend/app/api.py:156` retrieves `registry.get_report`; `pipeline.py:114` builds actual base/head analysis outputs into schema-v1 reports. Raw-ASGI tests verify returned retained JSON, paths and pinned source URLs after local source deletion. No model service participates. |
| 2 | Visitor opens a precomputed demo without authentication | VERIFIED | Public GET routes at `api.py:160` and `api.py:164` use only fixed loaders. Tests retrieve actual frozen reports with no credentials, with live analysis both disabled and enabled; attempted computation/admission fails the tests. |
| 3 | Hand-labelled fixtures measure edge and endpoint precision/recall | VERIFIED | `reporting/evaluation.py:242` compares report predictions with committed labels, retaining exact TP/FP/FN sets. Source review confirms unsupported login calls remain gold positives. Independently rerun metrics: edges 72/0/12, precision 1.0, recall 6/7; endpoints 6/0/2, precision 1.0, recall 0.75. |
| 4 | Unresolved/uncertain relationships are explicit, never verified facts | VERIFIED | Builder iterates verified graph edges separately from `call_graph.unresolved`; candidates enter `ReportUncertainty` only. Regression tests inject candidates, verify they do not enter graph/path output, and check redaction. Every expected unresolved fixture location remains present. |

### Observable Truths

All PLAN frontmatter must-haves are retained below, including implementation details supporting the four roadmap criteria.

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Structured reports retain separate base/head verified graphs, potential route paths and inspectable source evidence | VERIFIED | `models.py` enforces ordered revisions, graph referential integrity and evidence revisions; builder converts actual graph nodes/edges and impact paths with call-site, handler, decorator and registration evidence. Builder/API tests cover both revisions, multiple call sites, zero-edge handler paths, fork links and removals. |
| 2 | Unresolved/uncertain relationships remain explicit outside verified paths | VERIFIED | Builder's separate uncertainty collection; `test_unverified_candidates_and_bad_diagnostic_stay_outside_graph` verifies injected uncertain candidates cannot become edges. |
| 3 | Controlled fixture locations are never represented as browsable GitHub commits | VERIFIED | Discriminated controlled references have relative source ranges without URL/SHA fields; provenance validation rejects mixed reference kinds. Frozen artifacts and evaluation use SHA256 snapshot digests and explicit hypothetical scenarios. |
| 4 | Completed live analyses retain full reports after source cleanup | VERIFIED | Report constructed inside `fetch_snapshots` context, then retained after context exit. Pipeline tests assert roots are removed; API tests delete remaining fake source and retrieve exact retained reports. |
| 5 | Status/report become visible atomically and expire/evict together | VERIFIED | Registry uses one RLock for publication/read/pruning; both stores pruned together. Concurrent-reader, fake-clock TTL, eviction and active-owner tests passed. |
| 6 | Pending, failed, timed-out or oversized analyses never expose a report | VERIFIED | `get_report` gates state; assembly/publication errors fail safely. Runtime, pipeline and ASGI tests cover not-ready/unavailable, timeout, cleanup failure and serialized limits. |
| 7 | Edge/endpoint precision and recall use independent hand-labelled truth | VERIFIED | Labels contain exhaustive scoped true edges including both unsupported source-bound login calls. Evaluation reads labels, computes real reports and set differences; scoring test explicitly exercises missing and extra predictions. |
| 8 | Positive, unrelated, cyclic and unresolved cases expose exact errors without general completeness claims | VERIFIED | Five cases include auth-positive, unsupported-audit, unrelated-callers, cycle-positive and unresolved-negative. Both negatives have no endpoint predictions or truth; audit has explicit endpoint FN. README explains controlled sample limitations. |
| 9 | Evaluation is deterministic, offline and never imports/executes fixture code | VERIFIED | Fixed source allowlists, symlink checks and byte copies feed static analysis; guarded fixture would raise if imported. Two evaluations produced identical canonical bytes. CLI determinism and marker nonexecution regressions passed. |
| 10 | Visitors retrieve precomputed positive/negative artifacts without scanning | VERIFIED | `demos.list_demos`/`get_demo_report` validate frozen files. Tests disable scanner, builder, regeneration and socket entry points while retrieval succeeds. |
| 11 | Frozen demos identify controlled provenance without invented GitHub links | VERIFIED | Both artifacts use controlled references and SHA256 manifests; generation description states identical source snapshots with hypothetical seeds, not real PRs. Positive has two routes; unrelated negative has none. |
| 12 | Only fixed allowlisted checked-in reports load; runtime never regenerates | VERIFIED | Exact ID lookup precedes file access; user IDs never form paths. Catalog identity/order, metadata, canonical bytes, digest, schema, provenance and report ID are checked. Regeneration imports/calls occur only in explicit offline CLI functions. |
| 13 | Authorized live GET returns retained findings, uncertainties and pinned evidence without Gemini | VERIFIED | Existing namespace boundary runs before UUID validation; route retrieves defensive registry copy. Real local pipeline/ASGI checks verify exact base/head source links after cleanup. |
| 14 | Public catalog/reports return only frozen reports even when live analysis is disabled | VERIFIED | Separate public namespace bypasses live boundary intentionally; no-auth GET tests pass in enabled and disabled configurations. |
| 15 | Public demos cannot reveal live analyses, scan source or bypass cost/authentication controls | VERIFIED | Fixed ID map has no live fallback; live UUID through demo route returns 404. No-auth live route returns 401/503 before validation; public POST returns 405. Tests forbid reserve, client, scanner and regeneration calls. |

**Score:** 15/15 plan truths verified; 4/4 roadmap criteria verified.

### Required Artifacts

`gsd-tools verify artifacts` passed for all five plans: **13/13 declared artifacts** exist and pass substantive checks. Manual inspection additionally verified usage/data flow, not just existence.

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `backend/app/reporting/models.py` | Schema-v1 contracts | VERIFIED | Strict extra-field rejection, provenance/side/range validation, graph/path consistency, handler evidence agreement; consumed by builder, registry, evaluation and loader. |
| `backend/app/reporting/builder.py` | Deterministic report assembly | VERIFIED | Actual ProjectImpactAnalysis conversion, source-byte checks, pinned references, digest checks, canonical serialization and byte/deadline limits; invoked by live/evaluation flows. |
| `backend/app/ingestion/runtime.py` | Atomic bounded retention | VERIFIED | Owned validated reports, locked complete/read/prune, defensive copies and consistent expiration/eviction. |
| `backend/app/ingestion/pipeline.py` | Assembly/cleanup/publication sequence | VERIFIED | Analysis → report before cleanup → successful cleanup → registry.complete, with terminal failure handling and eventual slot release. |
| `backend/app/reporting/evaluation.py` | Exact-set evaluation/CLI | VERIFIED | Actual report predictions, independent labels, errors and micro/macro metrics with null undefined denominators. |
| `fixtures/report_evaluation/labels.json` | Independent ground truth | VERIFIED | Five source-located cases with scoped edges, endpoints, seeds, expected uncertainty and adjudicated unknowns; unsupported true relationships preserved. |
| `fixtures/report_evaluation/README.md` | Label/metric rationale | VERIFIED | Explains source review, exclusion conventions, known misses, repeated-source limitation and actual measured results. |
| `backend/app/reporting/demos.py` | Fixed loader/offline maintenance | VERIFIED | Loader only reads bounded fixed artifacts; explicit offline regeneration/check use shared evaluation/report contracts. |
| `backend/app/reporting/demo_reports/auth-positive.json` | Frozen positive | VERIFIED | Canonical validated controlled report, both revisions, two potential affected endpoints each and explicit uncertainties. |
| `backend/app/reporting/demo_reports/unrelated-negative.json` | Frozen negative | VERIFIED | Actual unrelated caller seed, verified graph retained, no affected endpoints; uncertainties preserved. |
| `backend/app/api.py` | Protected live/public demo routes | VERIFIED | All three GET endpoints connected to intended stores; unchanged live namespace authentication. |
| `backend/tests/test_report_api.py` | Hermetic HTTP regressions | VERIFIED | Collected/executed raw-ASGI tests cover real local pipeline outputs and public/private lifecycle boundaries. |
| `backend/README.md` | Usage/limits/evaluation | VERIFIED | Accurate commands, JSON fields, provenance distinction, retention, safe errors and conservative measurement claims. |

Supporting catalog, package exports, cycle fixture, model/builder/evaluation/demo tests, runtime/pipeline tests and report byte settings also inspected. Catalog hashes match exact canonical report bytes.

### Key Link Verification

The helper's key-link parser retains literal single quotes from PLAN `pattern: 'foo'`, so all ten automated pattern lookups falsely report failure. Actual imports, invocations, upstream results and executed integration tests establish every link below; no implementation gap was inferred from the parser defect.

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| reporting/builder.py | analysis/project_routes.py | ProjectImpactAnalysis | WIRED | Import/type boundary; graph, routes and impact outputs consumed in revision construction. |
| reporting/builder.py | ingestion/source_links.py | source_reference | WIRED | Evidence function creates exact base/head pinned references; fork/deletion tests passed. |
| ingestion/pipeline.py | reporting/builder.py | build_report | WIRED | Calls builder with mapping, actual analyses, roots, budget and size limit before cleanup. |
| ingestion/pipeline.py | ingestion/runtime.py | registry.complete | WIRED | Invokes after snapshot context exit and deadline check with validated summary/report. |
| reporting/evaluation.py | fixtures/report_evaluation/labels.json | label loading | WIRED | CLI supplies label path; strict Labels parse drives independent expected sets, never writes labels. |
| reporting/evaluation.py | analysis/project_routes.py | analyze_route_impacts | WIRED | Real static analyses on isolated allowlisted source copies; report predictions subsequently scored. |
| reporting/demos.py | demo_reports/catalog.json | catalog/digest validation | WIRED | Fixed catalog read and strict validation precede bounded allowlisted artifact loads. |
| reporting/demos.py | reporting/evaluation.py | offline build_case_report | WIRED | Lazy import inside explicit regeneration function only; HTTP loaders never call it. |
| api.py | ingestion/runtime.py | get_report | WIRED | Protected UUID route retrieves retained report, no source reads or recomputation. |
| api.py | reporting/demos.py | get_demo_report | WIRED | Public fixed-ID route uses validated loader; no registry fallback. |

### Data-Flow Trace (Level 4)

No dynamic frontend rendering is in scope. Equivalent output data flows were traced to avoid accepting wired but hollow JSON endpoints.

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| live report API | registry report | pinned snapshot source → mapping/actual ProjectImpactAnalysis → build_report → atomic retention | Yes; ASGI test verifies nonempty graph/findings and pinned links after cleanup | FLOWING |
| report builder | nodes/edges/findings | graph node/edge attributes and actual impact paths with retained source byte checks | Yes; not hardcoded empty or synthetic relationships | FLOWING |
| demo catalog/report API | catalog/report models | checked-in canonical files, exact digest and provenance checks | Yes; intentionally precomputed real controlled analysis artifacts | FLOWING |
| evaluation JSON | expected/predicted identities | independent labels versus verified edges/findings extracted from shared reports | Yes; actual false negatives retained, negatives explicitly empty | FLOWING |

### Behavioral Spot-Checks

Each direct check below completed in under 10 seconds; no server/service was started, fixture source was not executed, and no application data or checked-in artifact was mutated. Tests use isolated temporary fixtures and controlled upstream fakes.

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Models, evidence, evaluation, demos, API and lifecycle | From backend: `uv run --no-sync python -m pytest tests/test_report_models.py tests/test_report_builder.py tests/test_report_evaluation.py tests/test_demo_reports.py tests/test_report_api.py tests/test_analysis_runtime.py tests/test_pr_pipeline.py -q` | **130 passed in 3.09s**, command wall time 4.06s | PASS |
| Repeatable metrics and uncertainty retention | Read-only `uv run --no-sync python -c` invoking evaluate_suite twice, asserting identical canonical bytes and no missing_expected_unresolved | Edges TP/FP/FN 72/0/12; endpoints 6/0/2; every expected unresolved location retained | PASS |
| Frozen artifacts match actual analysis | From backend: `uv run --no-sync python -m app.reporting.demos --check` | Exit 0; no drift/writes | PASS |

The execution orchestrator separately reported full pytest **665 passed**, full Ruff, uv lock check and git diff whitespace checks passed. Those are supporting execution evidence, not independently rerun claims; this verifier independently ran the focused checks above. No broader rerun was needed after their successful results and source review.

Measured edge micro precision/recall: **1.0 / 0.8571428571428571**; endpoint micro precision/recall: **1.0 / 0.75**. Edge macro precision/recall: **1.0 / 0.9**, 10 defined values each. Endpoint macro precision: **1.0**, 4 defined; recall: **0.6666666666666666**, 6 defined. Undefined negative denominators remain null.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| US-11 | 05-01 through 05-05 | View precomputed demo reports without signing in | SATISFIED | Unauthenticated raw-ASGI requests return the two validated frozen reports and catalog, including when live analysis is disabled; private UUIDs/scanning are inaccessible through demo routes. |

Every plan declares US-11. REQUIREMENTS.md maps only US-11 to Phase 5, so no orphaned requirement exists. Its pending checkbox/traceability state is workflow bookkeeping for the orchestrator to update, not missing implementation. Interactive frontend presentation is separately assigned to Phase 7.

### Anti-Patterns Found

Scanned reporting source/artifacts, modified ingestion/API modules, evaluation fixtures and README for TODO/FIXME/placeholder, coming-soon and empty implementation patterns; none block the goal. Inspected empty negative findings in context: they follow actual reverse traversal of unrelated seeds and are intentional, not stubs.

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `backend/app/reporting/evaluation.py` | 242 | Known unsupported source-bound login edges remain FN | Info | Evaluation honestly exposes conservative resolver limitations; does not prevent measured evaluation goal. |
| `backend/app/reporting/demos.py` | 126 | Base/head fixture snapshots identical, hypothetical seeds | Info | Explicit controlled provenance; does not claim actual PRs or independent real-world samples. |
| `backend/app/ingestion/runtime.py` | 38 | Ephemeral in-process report retention | Info | Documented TTL/eviction/restart limitation within the approved phase scope. |

Verified regressions for trusted ancestor filesystem aliases and contradictory handler identity/range/file evidence: builder/model checks reject unsupported evidence and preserve canonical bytes through a trusted root alias. Source-payload marker tests establish static parsing without executing analysed source. No new dependencies, paid infrastructure, model service or worker is introduced by these report flows.

### Human Verification Required

None required for this phase's deterministic backend/JSON contract. HTTP behavior was checked with raw ASGI and controlled local source; no external service call was necessary. Browser layout, interactive frontend flow, live external integration and deployment performance are outside Phase 5 and are not claimed verified here.

### Gaps Summary

No blocking gap found. Structured live reports preserve real revision-correct evidence after cleanup; public demos are genuinely precomputed and unauthenticated within a fixed namespace; independent source-reviewed labels produce measured exact-set errors; uncertain relationships remain outside verified paths. The two source-bound receiver misses and audit endpoint miss remain visible false negatives. These limited repeated-source measurements do not establish general completeness, runtime effects or improvement over another method.

---

_Verified: 2026-11-01T17:45:07Z_
_Verifier: Codex (gsd-verifier)_
