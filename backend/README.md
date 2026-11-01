# CodeScope AI -- backend

**Status (Phase 3 analysis library implemented -- see `../TASKS.md` / `../.planning/ROADMAP.md`):**
Tree-sitter Python symbols, deterministic import/call resolution, an evidence-preserving NetworkX graph,
and potentially affected FastAPI routes with supported call paths. The analysis library remains independent
of FastAPI; an HTTP service and PR retrieval come in later phases.

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
