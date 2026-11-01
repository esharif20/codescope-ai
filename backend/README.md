# CodeScope AI -- backend

**Status (Phase 5 structured reports, evaluation and demos implemented -- see `../TASKS.md` / `../.planning/ROADMAP.md`):**
Tree-sitter Python symbols, deterministic import/call resolution, an evidence-preserving NetworkX graph,
and potentially affected FastAPI routes with supported call paths. The analysis library remains independent
of FastAPI. A restricted HTTP service retrieves immutable public GitHub PR snapshots,
maps changes to symbols and analyses base/head route impacts independently. Schema v1 reports retain
inspectable evidence; public frozen demos and offline hand-labelled evaluation need no credentials.

## Setup

Requires **uv >= 0.13** (enforced via `[tool.uv] required-version` in `pyproject.toml` -- `uv sync` fails fast
with a clear message on an older `uv` rather than silently misbehaving; see "Pinned tooling note" below for why).

```bash
uv sync --extra dev
```

Dependencies are added incrementally, one phase at a time, via `uv add <package>` only when that phase's code
first needs it -- e.g. `networkx` was added at the start of Phase 2, `fastapi` not until Phase 4,
`langchain`/`chromadb` not until Phase 6. `pyproject.toml` + `uv.lock` are the source of truth; `requirements.txt` /
`requirements-dev.txt` are regenerated from them after every dependency change
(`uv export --format requirements.txt --no-dev --no-hashes --no-emit-project -o requirements.txt`, and the same
with `--extra dev -o requirements-dev.txt`) for tooling that expects plain pip-style files.

## Test

```bash
uv run pytest -q
```

## CLI usage

```bash
uv run codescope-parse path/to/file.py
uv run codescope-parse path/to/file.py --compact   # single-line JSON

# equivalent, if you ever need it:
uv run python -m app.analysis.cli path/to/file.py
```

## Route impact library API

From `backend/`, analyse a local Python source tree using stable `module:qualified_name` change ids:

```python
from app.analysis import analyze_route_impacts

result = analyze_route_impacts(
    "../fixtures/sample_fastapi_repo",
    ["services.auth:get_current_user"],
)
for path in result.impact.impacts:
    print(path.route.method, path.route.path, path.symbols)
    print(path.route.declaration, path.route.registration_evidence, path.edges)
print(result.partial, result.routes.diagnostics, result.routes.file_statuses)
print(result.impact.unknown_symbols)
```

The fixture produces `GET /users/me` and `PUT /users/{user_id}` with direct helper calls at lines 13
and 21. Changes to `callers:call_twice` or `services.base:BaseService.audit` produce no routes.
The latter has a verified caller in `AuthService.login`, but the handler's `auth.login` receiver is
untyped and unresolved; static analysis cannot connect that missing edge by guessing its type.

Supported route methods are literal `.get`, `.post`, `.put`, `.patch`, `.delete`, `.options`, `.head`
and `.trace` decorators on module-level handlers. Constructors must be module-level `FastAPI` or
`APIRouter` calls verified through direct `fastapi` imports, including explicit aliases. Literal router
constructor and `include_router` prefixes compose across nested mounts and preserve trailing slashes.
Includes support local router variables and direct absolute/relative router imports or supported module
attributes. Package initializer relative imports work. Factories, re-exported router chains, wildcard or
shadowed bindings, conditional/local registrations, dynamic paths/prefixes, argument expansion,
`api_route`, websocket and legacy `route` decorators remain explicit diagnostics. Disconnected routers
remain declarations without registered endpoints. This API does not add a CLI command or HTTP endpoint.

Each registration carries its decorator/handler location, app/router constructors and every include
location. Each impact carries all call-site lines for every verified edge. One deterministic canonical
shortest handler-to-change path is returned per registration/change pair; sorted predecessor discovery
breaks ties. Direct handler changes return a one-symbol path with no call edges. Multiple mounts or
methods remain distinct registrations. These paths describe potential static impact, not runtime
execution, all possible paths, or proof that an absent route is unaffected.

Inspect `project_graph.call_graph.unresolved` for unresolved/uncertain calls: they never participate in
traversal, and their presence alone does not set `partial`. `partial` is true for file statuses outside
`ok`/`empty`, unsupported route diagnostics, `project_graph.unresolved_truncated`, `routes.truncated`
or `impact.truncated`. It is conservative: the fixture retains unrelated call-result assignment
diagnostics and therefore returns `partial=True` even while its two supported routes are verified.
`routes.file_statuses` also records late read/decode failures; original graph statuses remain inspectable
on `project_graph.file_statuses`. Unknown changed ids appear separately in `impact.unknown_symbols`.

Analysis retains at most 500 Python files and 1,000 unresolved call records. Router traversal permits
10,000 mount steps and 1,000 registrations; impact traversal permits 10,000 first node discoveries
across all changes and 1,000 complete paths. Omitted work sets the relevant truncation flag, and already
complete paths remain available. Only retained files are reparsed for routes; sources are read as text,
never imported or executed, and repository dependencies are never installed.

## PR analysis HTTP API

`app.main:app` is the ASGI entry point; `create_app(settings=None, registry=None,
client_factory=None)` supports explicit local/test dependencies. App construction does no GitHub work.
Core FastAPI is installed without server or test-client extras. Server setup and hosting are deferred
to Phase 8; this phase adds no server dependency or deployment.

`GET /health` is public and returns `{"status":"ok"}` without GitHub access. All analyses
endpoints require the same caller credential:

```http
POST /api/analyses
Authorization: Bearer <CODESCOPE_LIVE_ACCESS_TOKEN>
Content-Type: application/json

{"analysis_id":"50ca355d-3dc0-49bf-a670-7631fb990701","pr_url":"https://github.com/approved-owner/approved-repo/pull/123"}
```

The caller supplies a fresh UUID. POST runs synchronously and returns terminal `AnalysisStatus`:
201 for complete, or the appropriate failure HTTP status with a stored error/timeout status.
While POST is active, another request can poll the known UUID:

```http
GET /api/analyses/50ca355d-3dc0-49bf-a670-7631fb990701
Authorization: Bearer <CODESCOPE_LIVE_ACCESS_TOKEN>
```

An existing record returns 200, including terminal failures. Before POST reserves the ID there can
be a brief 404. States are `pending`, `running`, `complete`, `error`, `timeout`; stages are `accepted`,
`metadata`, `sources`, `mapping`, `impact_base`, `impact_head`, `finished`. These describe real work,
not percentage estimates. Only one analysis runs per process; a different active request gets 409,
and reusing a retained UUID also gets 409. Health and status remain available while POST works in
FastAPI's ordinary request thread pool. Disconnecting a caller does not stop analysis or free its
slot early; the pipeline releases admission after work and snapshot cleanup finish.

Configure live access through environment variables before creating the application:

- `CODESCOPE_ALLOWED_REPOSITORIES`: comma-separated base `owner/repo` allowlist. A fork head
  must be the public repository identified by that PR's metadata; it needs no separate allowlist
  entry. An empty allowlist disables live access.
- `CODESCOPE_LIVE_ACCESS_TOKEN`: caller bearer secret. Missing/blank disables live access.
- `GITHUB_TOKEN`: optional upstream GitHub credential, distinct from the caller secret. The API
  does not accept this token as caller authorization; never share it with API callers.
- `CODESCOPE_<LIMIT_NAME>`: optional lower overrides of the immutable ceilings in
  `app/ingestion/settings.py`, e.g. `CODESCOPE_ANALYSIS_TIMEOUT_SECONDS=30`.

Only strict HTTPS `github.com/{owner}/{repo}/pull/{positive-number}` URLs are accepted. Private
repositories and arbitrary destinations are rejected. Repository source is treated as data: it
is never imported/executed and its dependencies are never installed.

The body must be JSON encoded as UTF-8, at most 8 KiB including whitespace and streamed chunks.
Only `analysis_id` and `pr_url` are accepted. Pre-admission failures return
`{"error":{"code":"...","message":"...","retry_after_seconds":null}}` without recording an
analysis. Responses do not echo raw request data, credentials, upstream bodies or local temp roots.

| HTTP | Error conditions |
| --- | --- |
| 401 | `unauthorized`: missing or incorrect caller bearer credential |
| 403 | `repository_not_allowed`, `unsupported_repository` (including private repositories) |
| 404 | `analysis_not_found`, `github_not_found` |
| 409 | `analysis_busy`, `analysis_id_conflict`, `pr_changed` |
| 413 | `request_body_too_large`, `resource_limit`, `result_limit_exceeded` |
| 415 | `unsupported_media_type` |
| 422 | `validation_error`, `invalid_pr_url`, unsafe/unsupported repository paths or entries |
| 429 | `github_rate_limited`; safe numeric `Retry-After` when supplied by upstream |
| 502 | Upstream authentication, permission, network/protocol failures; unexpected analysis failure |
| 503 | `live_analysis_disabled` |
| 504 | `analysis_timeout` |

Successful statuses include `revisions` with target base SHA, merge-base `analysis_base_sha`, head
SHA and base/head repository identities. `summary.changed_symbols` preserves each old/new source
location and exact SHA-pinned GitHub link: removed symbols link to the merge-base snapshot and
added symbols to the head snapshot, including fork repository provenance. Base/head affected-route
counts come from separate graphs; missing edges stay unresolved. `partial` and diagnostics expose
unsupported/truncated work. A complete status means the bounded pipeline finished, not that every
runtime dependency was proven.

Default ceilings include 60 seconds overall, 10 seconds per HTTP request, 200 upstream requests,
100 changed files, 100 Python files per revision, 128 KiB per source file, 8 MiB source total,
2 MiB result JSON, 20 terminal records and a one-hour terminal TTL. Deadlines are cooperative:
a native parser call can overrun until the next budget check. Admission remains held until actual
work and cleanup exit. Status is bounded, in-memory and process-local: restart loses records and
requests routed to another process cannot poll them. This phase adds no cache, durable storage,
background worker, separate graph endpoint or AI summary. HTTP tests use a raw in-process ASGI
harness and fake upstream snapshots, with no HTTPX, socket connections or live GitHub claims.

## Structured reports and public demos

With an ASGI server already running locally, retrieve the protected report for a completed UUID:

```bash
curl -H "Authorization: Bearer $CODESCOPE_LIVE_ACCESS_TOKEN" \
  http://localhost:8000/api/analyses/50ca355d-3dc0-49bf-a670-7631fb990701/report

# Public, including when live analysis is disabled:
curl http://localhost:8000/api/demos
curl http://localhost:8000/api/demos/auth-positive/report
curl http://localhost:8000/api/demos/unrelated-negative/report
```

The catalog returns `{"schema_version":"1","demos":[...]}` with IDs, titles, descriptions
and `provenance_kind`. Public routes load only validated, checked-in, allowlisted JSON artifacts.
They do not retrieve source, scan repositories, reserve an analysis slot or regenerate reports.
There is no live UUID fallback; POST to these public endpoints returns 405. Restricted live
report retrieval uses the same authorization and disabled-live boundary as submission/status,
before UUID validation. Public demos remain available without that credential.

Schema v1 (`app/reporting/models.py`) contains:

| Field | Meaning |
| --- | --- |
| `schema_version`, `analyzer_version`, `report_id` | Contract/analyser versions and live UUID or fixed demo identity |
| `provenance` | Immutable GitHub PR/revision identity, or controlled fixture identity and SHA256 snapshot digests |
| `changes` | Added/modified/removed symbol IDs and available old/base and new/head evidence |
| `revisions` | Separate ordered base/head graphs: source-located `nodes`, verified caller/callee `edges`, and route `findings` |
| `findings` | Potentially affected route, registration evidence and canonical shortest handler-to-change path with call-site evidence |
| `unmapped_changes` | Source changes that could not be attributed to a supported symbol |
| `uncertainties` | Explicit unresolved/uncertain calls and candidates, route/file/mapping diagnostics, unknown symbols and truncation |
| `partial` | Conservative indication of unsupported, incomplete or truncated work; also available per revision |

Unresolved candidates never become verified traversal edges. A finding describes potential static
impact, not proven runtime behaviour; no finding does not prove a route is unaffected. The retained
nodes/edges are available to later Phase 6 explanations and Phase 7 graph UI without a separate graph
endpoint. This phase adds no Gemini/RAG, dependencies, cloud infrastructure or frontend.

GitHub evidence carries `kind: "github"` and a `source` reference with exact repository, SHA, file,
line range and URL. Base evidence uses the merge-base `analysis_base_sha` and base repository; head
evidence uses the head SHA and head repository, including forks. Controlled evidence instead carries
`kind: "controlled"`, fixture ID, revision, local relative path and line range. Its provenance uses
SHA256 snapshot manifests, never invented Git SHAs or remote source URLs. The two demos represent
hypothetical changed symbols against identical reviewed base/head fixture snapshots, not real PRs.

Live report success returns 200 with the exact retained report, after source cleanup. Safe error
responses use the existing `error` envelope and do not expose credentials or local paths:

| HTTP | Report/demo condition |
| --- | --- |
| 409 | `report_not_ready`: pending/running, including cleanup; `report_unavailable`: terminal failure/timeout |
| 404 | `analysis_not_found`: absent, expired or evicted UUID; `demo_not_found`: ID outside the fixed allowlist |
| 422 | `validation_error`: invalid live UUID after authorization |
| 503 | `live_analysis_disabled`: all live paths disabled; `demo_unavailable`: missing/corrupt frozen artifact |

Status and report are published atomically and share process-local retention: at most 20 terminal
records, one-hour TTL, lost on restart, unavailable across processes. Oldest terminal records are
evicted together with their reports. `CODESCOPE_MAX_REPORT_BYTES` can lower the default/hard ceiling
of 2 MiB canonical JSON, independently of the summary limit. Oversized reports fail with
`result_limit_exceeded` (413); no success or incomplete report is published.

## Offline evaluation and frozen artifact maintenance

From `backend/`, these commands read controlled source bytes without importing/executing them,
installing fixture dependencies, making network requests or invoking a model:

```bash
uv run --no-sync python -m app.reporting.evaluation \
  --labels ../fixtures/report_evaluation/labels.json --output /tmp/codescope-evaluation.json
uv run --no-sync python -m app.reporting.demos --check

# Explicit maintenance only; review resulting JSON/digest diffs before committing:
uv run --no-sync python -m app.reporting.demos --regenerate
```

`--check` recomputes offline and fails on artifact drift; HTTP serving never recomputes. Labels are
source-reviewed truth maintained independently of predictions. See
[`fixtures/report_evaluation/README.md`](../fixtures/report_evaluation/README.md) for scope,
adjudicated unknowns and individual cases. Edge identities are unique caller/callee pairs;
endpoint identities are `(app_id, handler_id, method, path)`, deduplicated across paths and seeds,
scored separately for each revision. TP is predicted and labelled, FP predicted only, FN labelled
only. Precision is `TP/(TP+FP)`, recall `TP/(TP+FN)`; zero denominators produce JSON `null`.
Micro metrics sum counts; macro means include defined values only and report their denominators.

Measured across five controlled cases and two revisions: edges have TP/FP/FN **72/0/12**,
micro precision **1.0**, recall **0.8571428571428571**; endpoints have **6/0/2**, precision
**1.0**, recall **0.75**. Edge macro precision/recall are **1.0/0.9** (10 defined each);
endpoint macro precision is **1.0** (4 defined), recall **2/3** (6 defined). Empty endpoint
negatives retain null precision/recall. The missed audit endpoint has null precision and zero recall.

The resolver misses two source-bound `login` receiver edges in the sample, including the route
edge needed to reach `BaseService.audit`; these remain false negatives and explicit uncertainties.
Adjudicated unknown target sites stay outside truth denominators. Sample diagnostics remain partial;
the fixtures show no truncation. Repeated identical source snapshots are not independent real PR
samples. These measurements establish neither general completeness, runtime impact, performance,
nor improvement over text/semantic retrieval. There is no model latency/cost measurement here.

## Pinned tooling note

`uv < 0.13` wrote the editable-install `.pth` file with macOS's `UF_HIDDEN` flag set; CPython 3.13's `site.py`
silently skips any hidden `.pth` file (intentional security hardening, not a project bug), which broke `import
app` for the installed `codescope-parse` console script specifically. Confirmed fixed in `uv` 0.13.0 (verified in
an isolated test venv) and enforced via the `required-version` pin above so this can't silently reproduce. Never
affected Linux (no `UF_HIDDEN` concept), so CI was never at risk.

For an existing macOS environment with a stale hidden editable-install `.pth`, rebuild the environment
with the supported uv version (`uv sync --extra dev --reinstall-package codescope-backend`). During local
checks, `uv run --no-sync python -m pytest -q` uses the existing environment without reinstalling it;
`uv run --no-sync python -m app.analysis.cli ...` is the module-entry workaround if a stale console script
cannot locate `app` from the backend directory.

## Pinned dependency note

`tree-sitter` is pinned to `<0.26` (currently resolves to `0.25.2`): version `0.26.0` has a reference-counting bug
in its `Node` binding that segfaults when `child_by_field_name()` + `.text` are called repeatedly while walking
deeply nested trees (reproduced consistently around 65+ nested function definitions; `0.25.2` is clean through
150+). Re-test deliberately before raising this ceiling.

## Design note

`app/analysis` has **zero dependency on FastAPI**, by design (see
`AGENTS.md`): symbol extraction must stay usable from CLIs, batch jobs, and
tests independently of any web framework that is layered on top later.
