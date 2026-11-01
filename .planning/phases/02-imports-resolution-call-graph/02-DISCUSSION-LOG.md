# Phase 2: Imports, resolution, call graph - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `02-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-11-01
**Phase:** 2-imports-resolution-call-graph
**Areas discussed:** Call resolution precision, Import resolution scope, Graph shape & query API,
Fixture repo design, plus a closing round on contract/failure-handling/bounds/CLI loose ends

---

## Gray area selection

All four identified gray areas were selected by the user in one multi-select question:
Call resolution precision, Import resolution scope, Graph shape & query API, Fixture repo design.

---

## Call resolution precision

### self/cls calls

| Option | Description | Selected |
|--------|-------------|----------|
| Enclosing class + same-repo bases | Resolve to the enclosing class's own methods first, then walk in-repo base classes (left-to-right, MRO-ish) | ✓ |
| Enclosing class only | Resolve only to methods defined directly on the enclosing class; inherited calls unresolved | |
| Always unresolved | Treat every attribute call, including self, as unresolved | |

**User's choice:** Enclosing class + same-repo bases.

### Unknown-receiver attribute calls

| Option | Description | Selected |
|--------|-------------|----------|
| No arrow, but log where we got stuck | Record file/line/attribute name as an explicit unresolved entry; no edge drawn | ✓ |
| Draw arrows to every method with that name | Link to all same-named methods in the repo, flagged low-confidence | |
| Ignore it completely | Record nothing | |

**User's choice:** No arrow, but log where we got stuck.

### Ambiguous (2+ candidate) calls

| Option | Description | Selected |
|--------|-------------|----------|
| One 'uncertain' entry listing both/all | Single entry flagged ambiguous, carrying the full candidate list | ✓ |
| Multiple candidate edges | One edge per candidate, each flagged | |
| Deterministic first + flag | Pick first candidate by fixed ordering, flag it | |

**User's choice:** One 'uncertain' entry listing both.

### Type/variable tracking

| Option | Description | Selected |
|--------|-------------|----------|
| No — not in this phase | Strictly syntactic: imports, lexical scope, class hierarchy only | ✓ |
| Yes — handle the obvious cases | Track `x = UserService()` / `x: UserService` annotations | |
| Decide once the fixture exists | Defer the decision until after building the fixture | |

**User's choice:** No — not in this phase.

**Notes:** This whole area was first asked using technical/abstract framing (MRO, dataflow pass,
reverse reachability) and the user asked for a plain-language re-explanation before answering. The
re-ask used a worked code example (`auth.py` → `service.py` → `main.py`, following arrows backward to a
route) and framed every question as "do we draw the arrow, or log 'don't know'?" All four answers above
are from that plain-language re-ask.

---

## Import resolution scope

### Imports outside the repo

| Option | Description | Selected |
|--------|-------------|----------|
| Mark as external, don't go in | Record "this name comes from package X" and stop; a distinct third state from unknown | ✓ |
| Follow into the installed packages | Actually parse fastapi, pydantic, etc. from the virtualenv | |
| Treat them as unknown | Lump external imports in with genuinely unresolved calls | |

**User's choice:** Mark as external, don't go in.

### Relative imports / `__init__.py` re-exports

| Option | Description | Selected |
|--------|-------------|----------|
| Handle both | Resolve relative imports against the file's package location, and follow one hop through `__init__.py` re-exports | ✓ |
| Relative imports only | Resolve relative imports; re-exported names logged as unknown | |
| Neither — direct module imports only | Only resolve `from auth import x` where `auth.py` is directly findable | |

**User's choice:** Handle both.

### `from x import *`

| Option | Description | Selected |
|--------|-------------|----------|
| Expand using Phase 1's symbol list | Bind exactly the names Phase 1 already found in that module (honouring `__all__`); external star-imports stay unknown | ✓ |
| Treat affected names as uncertain | Flag any otherwise-unplaced name in that file as possibly from the star import | |
| Ignore star imports | Pretend the line isn't there | |

**User's choice:** Expand using Phase 1's symbol list.

### Module path / repo root

| Option | Description | Selected |
|--------|-------------|----------|
| Caller passes the root explicitly | `analyse` function takes a root directory; module path computed relative to it | ✓ |
| Auto-detect the root | Walk upward looking for `__init__.py` / `pyproject.toml` | |
| Both — explicit, auto as fallback | Take an optional root, auto-detect when absent | |

**User's choice:** Caller passes the root explicitly.

---

## Graph shape & query API

### Node granularity

| Option | Description | Selected |
|--------|-------------|----------|
| One per symbol, classes included | Function, method and class nodes, named like `module_path:qualified_name` | ✓ |
| One per symbol, functions only | Skip class nodes; keep inheritance data in a separate structure | |
| One per file | Coarse file-level dependency graph | |

**User's choice:** One per symbol, classes included.

### Repeated calls between the same pair

| Option | Description | Selected |
|--------|-------------|----------|
| One arrow carrying all call-site lines | Single DiGraph edge, line numbers stored as an edge attribute | ✓ |
| Three separate arrows | `MultiDiGraph`, one edge per call site | |
| One arrow with just a count | Store a call count, drop line numbers | |

**User's choice:** One arrow carrying all three line numbers.

### Where unresolved notes live

| Option | Description | Selected |
|--------|-------------|----------|
| A separate list, indexed by enclosing symbol | Kept alongside, not inside, the graph | ✓ |
| Placeholder nodes inside the graph | An "unknown" node per unresolved call, flagged | |
| Both — list plus flagged nodes | Maintain both representations | |

**User's choice:** A separate list, indexed by enclosing symbol.

### Query API shape

| Option | Description | Selected |
|--------|-------------|----------|
| Named helpers, graph still reachable | `callers_of`/`callees_of`/`reverse_reachable_from`, plus raw NetworkX graph access | ✓ |
| Raw NetworkX graph only | No wrapper helpers | |
| Fully wrapped, graph hidden | Only the anticipated query helpers are exposed | |

**User's choice:** Named helpers, graph still reachable.

---

## Fixture repo design

### Overall shape

| Option | Description | Selected |
|--------|-------------|----------|
| A real small package (~8-10 files) | One subpackage, deliberately exercising every resolution rule decided above | ✓ |
| Flat files, one directory | Four or five modules side by side | |
| Larger, multi-package | Two or three top-level packages with cross-package imports | |

**User's choice:** A real small package (~8–10 files).

### Placement of unresolvable calls

| Option | Description | Selected |
|--------|-------------|----------|
| Inline, in realistic places | Scattered where they'd really appear — dispatcher, callback param, untyped object | ✓ |
| One clearly-named module | All quarantined in `dynamic_cases.py` | |
| A second separate fixture | A dedicated `tricky_cases/` fixture alongside the clean one | |

**User's choice:** Inline, in realistic places.

### Expected-output verification style

| Option | Description | Selected |
|--------|-------------|----------|
| Hand-written expected lists in the tests | Expected edges/unresolved entries spelled out explicitly in test code | ✓ |
| A committed golden JSON snapshot | Generate once, commit, compare every run | |
| Spot-check the key arrows only | Assert a handful of important edges | |

**User's choice:** Hand-written expected lists in the tests.

### Fixture's own tests

| Option | Description | Selected |
|--------|-------------|----------|
| No — parse it, never import or run it | Fixture test files exist as parse targets / extra callers only | ✓ |
| Yes — install fastapi now and run them | Pull fastapi in early and execute the fixture's tests | |
| No test files in the fixture at all | Skip shipping test files in the fixture entirely | |

**User's choice:** No — parse it, never import or run it.

---

## Closing round: contract, failure handling, bounds, CLI

### `module_path` on the Symbol contract

| Option | Description | Selected |
|--------|-------------|----------|
| Add `module_path` to the existing Symbol | New optional field, default `None`, additive per Phase 1's own plan | ✓ |
| A new model that wraps Symbol | Separate `ResolvedSymbol` holding a Symbol plus module path | |
| Don't store it — compute when needed | Derive module path from file path at each call site | |

**User's choice:** Add `module_path` to the existing Symbol.

### One file fails to parse — effect on the rest

| Option | Description | Selected |
|--------|-------------|----------|
| Analyse the rest, label the gap | Build the graph from everything that parsed; explicitly record which files failed | ✓ |
| Fail the whole analysis | Refuse to produce any graph if one file is unparseable | |
| Skip it quietly | Leave the failed file out and say nothing | |

**User's choice:** Analyse the rest, label the gap.

### New bounds/limits this phase

| Option | Description | Selected |
|--------|-------------|----------|
| Light caps now, as named constants | Ceiling on files analysed and unresolved entries recorded, following `_MAX_SYNTAX_ISSUES` pattern | ✓ |
| Defer all limits to Phase 4 | Leave all bounding to ingestion phases | |
| Comprehensive limits now | Caps on files, bytes, symbols, edges, time | |

**User's choice:** Light caps now, as named constants.

### CLI for inspecting the graph

| Option | Description | Selected |
|--------|-------------|----------|
| A new separate command | `codescope-graph <root>`, alongside the untouched `codescope-parse` | ✓ |
| Add a flag to the existing CLI | `codescope-parse --graph` | |
| No CLI — tests only | Rely entirely on the pytest suite | |

**User's choice:** A new separate command.

---

## Claude's Discretion

Nothing was deferred to discretion — every gray area raised across all five rounds was explicitly
decided by the user. Ordinary implementation choices (internal module layout, function decomposition,
the concrete data structure backing the class-hierarchy index) are left to planning/execution as normal.

## Deferred Ideas

- Type/variable tracking (`x = UserService()`, annotations) — deferred pending Phase 5 evaluation data
- Following imports into stdlib/site-packages — rejected on cost grounds
- Comprehensive ingestion budgets (bytes/time/concurrency) — remain Phase 4 (CS-040) / Phase 8 (CS-081)
- Golden-snapshot graph testing — reasonable fit for Phase 5's evaluation harness instead
- Larger/multi-package fixtures — real-repo breadth arrives via Phase 5's 30-50 controlled changes
- FastAPI route detection / reverse-impact tracing to routes — Phase 3 (US-04)
