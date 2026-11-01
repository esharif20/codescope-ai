---
phase: 04-pr-ingestion-diff-mapping
verified: 2026-11-01T17:08:00Z
status: passed
score: 18/18 must-haves verified
human_verification: []
human_verified: 2026-11-01T17:11:45Z
---

# Phase 4: PR ingestion & diff mapping Verification Report

**Phase Goal:** GitHub REST client fetches PR metadata/diffs at pinned SHAs; diff lines map to symbols; `/api/analyses` and `/health` expose status/progress/error states.
**Verified:** 2026-11-01T17:08:00Z
**Status:** passed
**Re-verification:** No — initial verification; no previous verification report existed.

## Goal Achievement

All 18 truths declared across the five plans have implementation and automated behavioral evidence. All five roadmap success criteria are covered by the actual API, ingestion and mapping code, including a successful live GitHub round trip through actual ASGI POST and concurrent GET. The user confirmed source navigation and highlighted lines: "yes those lines are higlted". No implementation or manual-verification gap remains.

Read `ARCHITECTURE.md`, `AGENTS.md`, `CLAUDE.md`, PROJECT, ROADMAP, REQUIREMENTS, and all five Phase 4 plans/summaries. No project `.claude/skills/` or `.agents/skills/` skill files were found. Summaries supplied scope and file lists; conclusions below come from code inspection and executed checks.

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Unsupported PR identifiers fail before any network request. | ✓ VERIFIED | `urls.parse_pr_url` validates raw ASCII URL, exact host/path and allowlist; URL matrix and ASGI invalid-input tests assert no client creation. |
| 2 | The comparison retains target-base, analysis-base and head commit identities separately. | ✓ VERIFIED | `PinnedPullRequest` stores three SHA40 fields; `pin_pull_request` derives merge base using immutable compares; divergent-base tests preserve all identities. |
| 3 | Missing live-access configuration disables live submissions. | ✓ VERIFIED | `Settings.live_enabled` requires caller token plus allowlist; API boundary returns 503 before body/network; settings and health tests cover disabled configuration. |
| 4 | PR ingestion reads only public allowlisted repositories and immutable source identities. | ✓ VERIFIED | Base admission uses the exact allowlist; metadata-identified fork head requires public visibility and matching repository identity. Commit/tree/blob paths use validated SHAs, never supplied remote URLs. |
| 5 | Truncated inventories, unsafe paths and resource limits fail explicitly rather than producing a complete analysis. | ✓ VERIFIED | Full recursive inventories and all-language old/new differences must match compare records. Path, tree, source, request, diff and output limits fail closed; snapshot and API regressions exercise these paths. |
| 6 | Temporary source files are removed after success, upstream error or timeout. | ✓ VERIFIED | `fetch_snapshots` owns both roots with `TemporaryDirectory`; tests check disappearance after collection/consumer failures and timeout. Pipeline publishes success only after context exit. |
| 7 | Added, modified and removed functions have revision-correct file and line references. | ✓ VERIFIED | Local byte diffs and two Tree-sitter inventories produce exact hand-labelled identities/statuses and old/new decorated spans. |
| 8 | Deleted definitions remain mapped in the base revision, including renamed paths and changed identities. | ✓ VERIFIED | Removed records keep old references; identity changes yield removed plus added. Pipeline tests assert removed helper affects base only and replacement identities seed head independently. |
| 9 | Every source URL uses its exact analyzed commit and correct public repository. | ✓ VERIFIED | `source_reference` chooses analysis-base/base repository or head SHA/head repository and encodes path segments; exact deletion/fork/path-encoding tests pass. |
| 10 | Unsupported or ambiguous mapping stays explicit rather than guessing a symbol. | ✓ VERIFIED | Syntax/decode failures and duplicate identities produce partial diagnostics/unmapped locations; module-only edits remain unmapped. Pipeline retains partial status and safe diagnostic codes. |
| 11 | Status progresses through metadata, sources, mapping and revision-specific impacts while work is active. | ✓ VERIFIED | Snapshot callbacks and pipeline registry updates correspond to actual work; Event-controlled pipeline and raw-ASGI tests observe `running/mapping` during active POST. |
| 12 | Only one analysis runs at a time, and timeout does not release its slot while work continues. | ✓ VERIFIED | RLock-protected reservation and explicit owner release; races reject duplicates/busy requests and cleanup tests prove admission remains held. No executor, detached task or queue is created. |
| 13 | Removed symbols trace base callers and added symbols trace head callers without mixing revisions. | ✓ VERIFIED | Two independent `analyze_route_impacts` calls receive their own roots and old/new seeds. Positive, removed, renamed and unrelated fixtures assert exact per-revision counts. |
| 14 | Failure and timeout clean source snapshots and preserve a safe terminal status. | ✓ VERIFIED | Typed errors become error/timeout records without summary; unknown exceptions become static safe errors. Deadline checks cover each stage and final publication; cleanup precedes release. |
| 15 | An authorized caller can submit a supported PR and poll meaningful status while the synchronous request runs. | ✓ VERIFIED | Real FastAPI sync POST calls `run_analysis`; same-process GET reads registry. Concurrent ASGI scenario confirms progress, public health, 409 competition, and eventual 201. |
| 16 | Health is available without GitHub access; malformed, unsupported, busy, upstream and timeout cases have specific safe errors. | ✓ VERIFIED | Actual ASGI routes exercise authentication, 8 KiB streaming cap, JSON/URL validation, safe upstream statuses, retry headers, 504 and redaction. Diff/mapping complexity limits now correctly return 413. |
| 17 | No dependency is installed before the user approves its concrete justification. | ✓ VERIFIED | Parent supplied explicit prior approval, “add fast api and finish pahse 4”. Approval record commit `b9a73f5` precedes dependency commit `156a076`; manifests add only core FastAPI and required transitives. |
| 18 | Polling and final summaries expose revision-correct changed-symbol source links. | ✓ VERIFIED | API success test asserts exact old/new URLs and equality of completed POST/polled GET payloads; no local root or upstream credential enters serialized results. |

**Score:** 18/18 plan truths verified through code and automated checks. **Roadmap criteria:** 5/5 have automated evidence, including live integration; the narrow browser check remains below.

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `backend/app/ingestion/models.py` | Revision/mapping/status contracts | ✓ VERIFIED | Substantive validated Pydantic models used throughout; private snapshot roots remain an internal dataclass. |
| `backend/app/ingestion/urls.py` | Strict PR admission | ✓ VERIFIED | `parse_pr_url` is defined, imports successfully and is used at HTTP and pipeline admission. |
| `backend/app/ingestion/settings.py` | Fail-closed settings and bounds | ✓ VERIFIED | Immutable limits, separate redacted secrets and lower-only environment overrides consumed by transport/runtime/API. |
| `backend/app/ingestion/github.py` | Immutable GitHub metadata reads | ✓ VERIFIED | Real stdlib transport, redirect rejection, bounded streaming and pinned compare/race checks consumed by snapshots. |
| `backend/app/ingestion/snapshots.py` | Safe complete source snapshots | ✓ VERIFIED | Public provenance, exhaustive inventories, actual Git blob hashes, safe private files and owning cleanup consumed by pipeline. |
| `backend/app/ingestion/diff_mapping.py` | Two-revision changed symbols | ✓ VERIFIED | Byte-preserving local diffs, narrowest symbol ownership, identity classification and explicit incompleteness consumed by pipeline. |
| `backend/app/ingestion/source_links.py` | SHA-pinned evidence | ✓ VERIFIED | Validated revision provenance and encoded GitHub permalink construction used for mapping references. |
| `backend/app/ingestion/runtime.py` | Registry and deadline | ✓ VERIFIED | Callable `AnalysisRegistry` and `Deadline`; atomic ownership, defensive copies, monotonic budget/TTL and bounded terminal output. |
| `backend/app/ingestion/pipeline.py` | Full synchronous orchestration | ✓ VERIFIED | Real snapshot → mapping → base/head graph analysis → sanitized summary flow; API calls it directly. |
| `backend/app/main.py` | ASGI entry point/factory | ✓ VERIFIED | Importable `app` and callable `create_app`; installs boundary, handlers and routes without upstream work. |
| `backend/app/api.py` | Authorized analyses/public health | ✓ VERIFIED | Routes execute the pipeline and registry; actual raw-ASGI requests exercise safe HTTP responses. |
| `backend/tests/test_analysis_api.py` | API and concurrent progress checks | ✓ VERIFIED | 36 parametrized cases, including actual Event-controlled polling and both complexity-limit regressions. |

The GSD artifact helper found all files but incorrectly reported Python `exports` as missing, including literal messages such as `Missing export: [GitHubClient]`. This is a checker limitation: direct source inspection, successful imports/callability checks and executed consumer tests verify the named Python definitions. These findings are not implementation stubs.

### Key Link Verification

All **11/11** declared links passed `gsd-tools verify key-links`; manual tracing additionally checked response use and ownership.

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `urls.py` | `models.py` | `PullRequestRef` | WIRED | Validated identifier returned and used downstream. |
| `snapshots.py` | `github.py` | `GitHubClient` | WIRED | Commit/tree/blob reads select actual snapshot bytes. |
| `snapshots.py` | `models.py` | `SnapshotPair` | WIRED | Owning context yields actual roots, metadata and verified files. |
| `diff_mapping.py` | `python_symbols.py` | `extract_symbols` | WIRED | Both revision inventories determine mapping. |
| `diff_mapping.py` | `source_links.py` | `source_reference` | WIRED | Old/new mapped and unmapped references use exact provenance. |
| `pipeline.py` | `snapshots.py` | `fetch_snapshots` | WIRED | Context encloses mapping and both impact passes. |
| `pipeline.py` | `project_routes.py` | `analyze_route_impacts` | WIRED | Independent base/head graphs and correct seeds feed route counts. |
| `pipeline.py` | `runtime.py` | Registry/deadline | WIRED | Real work updates progress, safe terminal state and exclusive release. |
| `main.py` | `api.py` | Factory/router/middleware | WIRED | Concrete dependencies are installed on the app. |
| `api.py` | `pipeline.py` | Sync POST `run_analysis` | WIRED | Returned status determines response body and terminal HTTP code. |
| `api.py` | `runtime.py` | Shared registry GET | WIRED | Polling returns defensive status snapshots updated by active POST. |

### Data-Flow Trace (Level 4)

No frontend is in this phase; the dynamic public artifact is the analysis JSON response.

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| Submission response | `result` | `run_analysis` → owning snapshots → local mapping → two graph analyses | Real GitHub transport and verified source bytes; live ASGI submission additionally returned 201/complete | ✓ FLOWING |
| Polling response | `registry.get(analysis_id)` | Same registry updated by snapshot callbacks and actual pipeline stages | Concurrent raw-ASGI test observes active work and later identical terminal result | ✓ FLOWING |
| Changed symbols | `mapping.changes` | Exact base/head bytes → Tree-sitter inventories and SequenceMatcher | Hand-labelled additions/modifications/removals; no static placeholder list | ✓ FLOWING |
| Route counts/partial diagnostics | `base`, `head`, `diagnostics` | Separate actual Phase 2/3 graph and route passes | Positive/deletion/replacement/unrelated fixtures produce distinct expected outcomes | ✓ FLOWING |
| Source links | `change.old`, `change.new` | Pinned public repository/SHA plus extracted line range | Exact expected URLs asserted at library and HTTP boundary | ✓ FLOWING |

### Behavioral Spot-Checks

All executed commands completed in under 10 seconds. No server was started, no live analysis was submitted by this verifier, and no untrusted repository code or dependencies were executed/installed.

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Ingestion, mapping, statuses and API work together under controlled inputs | `cd backend && uv run --no-sync python -m pytest tests/test_analysis_api.py tests/test_analysis_runtime.py tests/test_pr_pipeline.py tests/test_github_ingestion.py tests/test_snapshots.py tests/test_diff_mapping.py tests/test_source_links.py tests/test_pr_urls.py tests/test_ingestion_models.py -q` | 303 passed in 1.10s before two new limit regressions | ✓ PASS |
| Final implementation preserves all analysis phases, corrected HTTP behavior and trusted OS symlink ancestors | `cd backend && uv run --no-sync python -m pytest -q` | **554 passed in 1.98s**, after `d91f90f` and `a0030ce` | ✓ PASS |
| Code quality | `cd backend && uv run --no-sync ruff check app tests` | All checks passed | ✓ PASS |
| Lock consistency | `cd backend && uv lock --check` | Resolved 23 packages; exit 0 | ✓ PASS |
| Python exports and complexity error policy | Direct imports/callability assertions plus `http_status` assertions | All declared definitions callable; both diff/mapping limits return 413 | ✓ PASS |
| Whitespace integrity | `git diff --check` | Exit 0 | ✓ PASS |

**Additional live evidence from the orchestrator:** A bounded raw-ASGI run used the actual application, request thread pool and `GitHubClient`, with allowlisted public PR `https://github.com/fastapi/full-stack-fastapi-template/pull/1440`. After the macOS regression fix, POST returned **201 / complete**, `error=null`, one changed symbol and `partial=true` with explicit unsupported-analysis diagnostics. It made **53 GitHub requests in 18.2 seconds**. Concurrent GET observed `running` stages `metadata`, `sources`, `impact_base` and `impact_head`; health remained 200; final GET returned 200 and exactly the POST status. Target and analysis-base SHA were `2e95aea2bf61fc2436feb66ababc14a7c31991e8`; head SHA was `b8b68c109e50bea95e766943a8a2af3d08d4d255`. HTTPS HEAD to `https://github.com/fastapi/full-stack-fastapi-template/blob/2e95aea2bf61fc2436feb66ababc14a7c31991e8/backend/app/api/routes/login.py#L78-L98` returned **200**. No repository source execution or dependency installation occurred. This live probe exceeded the verifier's under-10-second spot-check limit and was run separately by the orchestrator, not as a verifier spot-check. It establishes live API/GitHub behavior in addition to mocked-upstream tests; browser line highlighting was not observed.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| US-01 | 04-01–04-05 | Submit a supported GitHub PR URL; see status or clear error | ✓ SATISFIED in automated checks | Actual authorized POST/GET plus strict admission, safe transport and terminal status tests. |
| US-02 | 04-03–04-05 | Identify added, modified and removed functions with file/line references | ✓ SATISFIED | Complete old/new inventories, deterministic ownership/classification, removed and renamed evidence, exact HTTP source links. |
| US-09 | 04-01–04-05 | Open source pinned to the exact analyzed revision | ✓ SATISFIED in automated checks | Distinct target/merge-base/head identities, fork provenance and exact immutable source URLs. Browser acceptance remains below. |
| US-12 | 04-01, 04-02, 04-04, 04-05 | Meaningful progress, timeout and errors | ✓ SATISFIED in automated checks | Concurrent polling, per-stage/final deadline tests, safe failure envelopes, no early release and corrected 413 limits. |

No requirement mapped to Phase 4 is orphaned: US-01, US-09 and US-12 all appear in plan frontmatter. US-02 is explicitly carried by plans 03–05. At inspection time, REQUIREMENTS mapped US-02 as Phase 1 Complete while its checkbox remained unchecked, and PROJECT overstated Phase 1 as completing classification. Phase 1 provided extraction foundations; actual added/modified/removed diff mapping is completed here. This is tracker drift for the orchestrator to reconcile, not missing implementation. Later US-13 deployment-wide controls remain Phase 8; current allowlist, bounds and exclusive admission do not claim deployment-wide rate/cost enforcement.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `backend/app/api.py` | 36–39 | Previously omitted `diff_limit_exceeded`/`mapping_limit_exceeded` from HTTP 413 policy | Resolved during verification | Commit `d91f90f` adds both codes and actual ASGI terminal-status/polling regressions; full suite passes afterward. |
| `backend/app/ingestion/diff_mapping.py` | 29 | Previous symlink rejection inspected every ancestor, including trusted macOS `/var` | Resolved during verification | Live ingestion reached mapping and exposed `snapshot_read_failed`. Commit `a0030ce` restricts symlink inspection to repository-controlled components below the trusted root; three regressions preserve internal/escaping symlink rejection. Live rerun succeeds. |

No blocking TODO/stub/placeholder or source-execution path found in Phase 4 implementation. Empty collections are initial buffers/registries or legitimate empty inputs populated by real work. Default no-op budget callbacks preserve existing library callers; the live pipeline injects a real monotonic deadline. Source acquisition uses validated REST reads, blob decoding/hashing and non-executable private regular files, never checkout/import/exec/subprocess or scanned-repository dependency installation. Public results exclude credentials, raw exceptions, source expressions and private snapshot roots.

### Human Verification Required

Completed on 2026-11-01: the user opened the supplied source link and confirmed "yes those lines are higlted". The original check below is retained for the audit trail; 04-HUMAN-UAT.md records its passing result.

### 1. US-09 source opening (nonblocking external-service acceptance)

**Test:** Open the returned old/new GitHub source links from the verified live analysis, including the base-side reference.

**Expected:** The page displays the intended function at its recorded commit, path and highlighted line range. The old reference uses `analysis_base_sha` and the new reference uses `head_sha`.

**Why human:** Actual live submission, progress, health, final polling and HTTP permalink availability already passed automated checks; exact line fragments are unit-tested. The verifier role explicitly requires human verification for external service integration. This is a nonblocking manual observation of US-09 source opening, not a new roadmap criterion or a missing capability. No new server/deployment or Phase 7 frontend acceptance is required here.

### Gaps Summary

No unresolved implementation gap remains. Both the complexity-limit HTTP mismatch and live-discovered macOS ancestor-symlink bug were fixed and independently retested. Final automated checks cover all 18 plan truths and all five roadmap outcomes. A real API/GitHub round trip, concurrent progress and immutable permalink availability also passed. The user confirmed browser navigation/highlighting, resolving the final human-verification item; status is `passed`.

Limitations are explicit and consistent with phase scope: synchronous POST with concurrent UUID polling; process-local ephemeral status; one active analysis per process; cooperative rather than hard parser preemption; approved small public Python repositories only; no graph/report endpoints, frontend, durable cache, RAG or deployment yet.

---

_Verified: 2026-11-01T17:08:00Z_
_Verifier: Codex (gsd-verifier)_
