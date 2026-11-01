# Phase 2: Imports, resolution, call graph - Context

**Gathered:** 2026-11-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Resolve imports and direct function/method calls across multiple Python files into a queryable
NetworkX call graph. Calls that cannot be resolved (dynamic, external, or ambiguous targets) are
explicitly flagged, never invented or silently omitted. Includes building the sample FastAPI fixture
repo (`fixtures/sample_fastapi_repo/`, currently empty) that makes this deterministically verifiable.
FastAPI route *detection* and reverse-impact *tracing* to routes are Phase 3, not this phase — Phase 2
only has to produce the graph and resolution data Phase 3 will traverse.

The through-line behind every decision below: **draw a call-graph edge only when we can point at the
reason; make every gap explicitly visible rather than silently absent.** This follows the project's core
value ("never claim static analysis proves runtime behaviour") and AGENTS.md rules 3-5. Consequence for
the planner: Phase 3's negative fixture must prove no false positives, so precision beats recall
everywhere the two trade off.

</domain>

<decisions>
## Implementation Decisions

### Call resolution precision
- **D-01:** `self.x()` / `cls.x()` resolve against the enclosing class's own methods first, then base
  classes **defined in the analysed repo** (left-to-right, MRO-ish). Requires a class-hierarchy index —
  Phase 3 will reuse it for route-handler lookup.
- **D-02:** A call on a receiver whose type isn't statically knowable produces **no edge**. Record an
  explicit unresolved entry carrying file, line, and the attribute name. Never omit silently (roadmap
  Phase 2 success criterion 4).
- **D-03:** Two or more plausible targets for one call → **one entry flagged uncertain, carrying the
  full candidate list** as evidence. Never emit multiple edges (would over-broaden reverse reachability
  and inflate Phase 3's affected-route results) and never a deterministic pick (a guess indistinguishable
  from a certain edge).
- **D-04:** **No type or variable tracking this phase.** Resolution is strictly syntactic: imports,
  lexical scope, class hierarchy only. `svc = UserService(); svc.login()` stays unresolved. Deferred, not
  rejected — see Deferred Ideas.

### Import resolution scope
- **D-05:** Imports pointing outside the repo (`fastapi`, `pydantic`, stdlib) are recorded as
  **resolved-external** — a third state distinct from unresolved. We know where the name comes from; we
  don't parse the external package. Keeps the unresolved list actionable and respects ARCHITECTURE.md's
  time/byte bounds.
- **D-06:** Resolve **relative imports** (`from .auth import x`) against the importing file's package
  location, **and follow one hop through `__init__.py` re-exports**. Both patterns are ubiquitous in real
  FastAPI layouts; skipping either would make the fixture unrealistically flat.
- **D-07:** `from auth import *` is **expanded using Phase 1's own symbol list** for in-repo modules
  (honouring `__all__` when it is a literal list of string constants). This is reading the already-known
  symbol table, not guessing. Star-imports from external (non-repo) modules leave the imported names
  unresolved.
- **D-08:** Module paths derive from an **explicitly-passed root directory**: path relative to root,
  `/` → `.`, `.py` suffix stripped, `__init__.py` maps to the package name itself. **No auto-detection**
  of the root (would silently misfire on `src/` layouts and namespace packages, and a wrong module name
  would corrupt every edge computed from it). This also has to work in Phase 4, where files arrive from
  the GitHub API with no real filesystem to walk.

### Graph shape & query API
- **D-09:** **One NetworkX node per symbol, classes included** (not just functions/methods). Node id
  shape: `module_path:qualified_name` (e.g. `app.service:UserService.login`). Classes need nodes both for
  D-01's inheritance lookup and for Phase 3's route→handler attachment.
- **D-10:** `networkx.DiGraph` (not `MultiDiGraph`) — **one edge per caller→callee pair**, carrying all of
  that pair's call-site line numbers as an edge attribute (a list, not a count). Nothing downstream needs
  N parallel edges; every traversal would otherwise have to de-duplicate. Line numbers are kept per
  AGENTS rule 5 (findings must carry source-location evidence).
- **D-11:** Unresolved and uncertain entries live in a **separate list/index keyed by enclosing symbol —
  never as nodes in the graph itself**. This guarantees the graph only ever contains defensible
  relationships, so reverse traversal can never silently route through a guess, while "what failed to
  resolve inside `login_route`?" stays answerable via the index.
- **D-12:** Query surface is **named helper functions** — `callers_of(symbol)`, `callees_of(symbol)`,
  `reverse_reachable_from(symbol)` — as the normal entry point, **with the underlying NetworkX graph
  object still accessible** for callers that need something the helpers don't anticipate. Phase 3's
  route-impact path-tracing is expected to need its own traversal.

### Fixture repo design
- **D-13:** `fixtures/sample_fastapi_repo/` (currently an empty directory) becomes a **real small Python
  package, roughly 8-10 files**, with at least one subpackage, deliberately exercising every rule above:
  a relative import, an `__init__.py` re-export, a star import, a base class with an inherited helper
  method, an external `fastapi` import, two route handlers, and multiple callers. A flat single-directory
  layout cannot exercise D-06/D-07/D-08 at all, so this structure is required, not decorative.
- **D-14:** Deliberately-unresolvable calls are placed **inline, in realistic locations** — e.g. a
  `getattr(handler, name)()` style dispatcher, a callback passed as a parameter, a method call on an
  untyped/unannotated object — rather than quarantined in one obviously-named module. This proves
  resolvable and unresolvable calls sitting side by side in the same function are both handled correctly.
- **D-15:** Expected results are captured as **hand-written expected edge/unresolved lists inside the
  test files themselves**, not a generated golden-snapshot file. A behaviour change then shows as a diff
  against explicitly stated intent that a reviewer can judge as right or wrong, rather than an opaque
  snapshot diff whose easiest "fix" is to regenerate and silently bless a regression.
- **D-16:** The fixture ships its own test files (per ARCHITECTURE.md's "Potential first steps" #3) but
  they are **parse targets only — never imported, never executed** by our test suite. `fastapi` therefore
  stays an uninstalled dependency until Phase 4, honouring the incremental-dependency rule, and we treat
  our own stand-in "untrusted repo" exactly as untrusted per AGENTS rule 7. The fixture's test files also
  serve as realistic additional callers feeding the call graph.

### Contract, failure handling, bounds, CLI
- **D-17:** Add an optional **`module_path: str | None = None`** field to the existing `Symbol` model in
  `backend/app/analysis/models.py`. This is exactly what the Phase 1 design recorded as its plan for this
  phase (Phase 1's L5 mitigation: "additive-only ... Stage 2 adds `module_path`"). Additive, so every
  existing Phase 1 test and JSON payload stays valid. A symbol's full identity is
  `module_path + "." + qualified_name`.
- **D-18:** A file that fails to parse **does not fail the whole run**: analyse every file that did
  parse, and record explicitly which file(s) failed and were therefore excluded from the graph. Matches
  Phase 1's existing tolerant-on-syntax-errors policy, and feeds the "partially analysed" progress state
  US-12 already requires. Never skip a failed file silently — that produces a graph that looks complete
  while actually missing data.
- **D-19:** Add **light caps now, as named module-level constants**, following the existing
  `_MAX_SYNTAX_ISSUES = 50` pattern in `python_symbols.py`: a ceiling on files analysed per run and on
  unresolved/uncertain entries recorded. Comprehensive byte/time/concurrency budgets remain owned by
  later phases (CS-040 ingestion limits / CS-081 abuse limits).
- **D-20:** Add a **new, separate CLI command `codescope-graph <root>`**, leaving the existing
  `codescope-parse` command and its tests completely untouched. One command takes a single file, the
  other a directory — folding them into one entry point would make the arguments and exit-code
  conventions contradict each other. Not required by any roadmap success criterion; included so the
  fixture's resulting graph can actually be inspected by hand during/after execution.

### Claude's Discretion
Nothing was deferred to discretion — every gray area raised was explicitly decided above. Ordinary
implementation choices left to `/gsd:plan-phase 2` / `/gsd:execute-phase 2`: internal module/file layout
within `backend/app/analysis/`, function decomposition, and the concrete data structure used for the
class-hierarchy index.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

`.planning/ROADMAP.md` lists no explicit `Canonical refs:` line for Phase 2, so this list was built from
REQUIREMENTS.md, PROJECT.md, AGENTS.md and the codebase scout performed during this discussion.

### Project specification
- `ARCHITECTURE.md` §"Potential first steps" items 3 & 5 — the fixture repo and import/call-graph work
  this phase delivers
- `ARCHITECTURE.md` §System design, §Analysis flow — where the NetworkX graph sits in the overall
  pipeline
- `ARCHITECTURE.md` §Constraints/security/cost — byte/time/concurrency bounding language D-19 follows
- `ARCHITECTURE.md` §Evaluation — call-edge precision/recall is the metric this phase's resolution rules
  will eventually be measured against (Phase 5)

### Working rules
- `AGENTS.md` rule 3 — parsing, call resolution and graph traversal must be deterministic
- `AGENTS.md` rule 4 — mark unresolved dependencies explicitly; never present guesses as verified call
  paths (drives D-02, D-03, D-11)
- `AGENTS.md` rule 5 — include source locations and evidence in analysis results (drives D-10's line
  numbers, D-02's unresolved-entry location)
- `AGENTS.md` rule 7 — never execute untrusted repository code or install its dependencies (drives D-16)
- `AGENTS.md` rule 8 — justification and approval required for new dependencies (covers `uv add
  networkx` during execution)

### GSD planning artifacts
- `.planning/ROADMAP.md` §Phase 2 — the five success criteria this phase is verified against
- `.planning/REQUIREMENTS.md` — US-03 (full requirement text and traceability)
- `.planning/PROJECT.md` §Constraints, §Key Decisions — standing process rules (incremental deps,
  README-per-milestone, no pushes without approval) that apply to this phase too
- `TASKS.md` — CS-020 (fixture repo), CS-021 (import/call-site extraction), CS-022 (resolver + explicit
  unresolved status), CS-023 (NetworkX graph + reverse reachability) acceptance criteria

### Existing implementation (the contract being extended)
- `backend/app/analysis/models.py` — the Pydantic contract D-17 extends
- `backend/app/analysis/python_symbols.py` — the single-file extractor this phase builds a cross-file
  layer on top of (see code_context below for specifics)
- `backend/README.md` — "Pinned tooling note" (`uv >= 0.13`) and "Pinned dependency note"
  (`tree-sitter < 0.26`) that remain in force during Phase 2 work

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_qualified_name` / `_parent_qualified_name` (`python_symbols.py`) — CPython `__qualname__`-style
  naming with the `<locals>` convention; reusable as-is for the within-file name portion of a resolved
  symbol.
- `_end_line`, `_node_name` (`python_symbols.py`) — generic Tree-sitter node helpers, reusable for any new
  node-type handling (import statements, call expressions).
- The iterative explicit-stack traversal pattern (both `_walk_symbols` and `_collect_syntax_issues`) — the
  established convention for any new walk; avoids Python recursion-limit issues on deep trees (ties to the
  tree-sitter<0.26 pin — see below).

### Established Patterns
- `extract_symbols(source, file_path)` is **single-file** and uses `file_path` **verbatim** — never
  resolved or normalized. Cross-file/cross-module work (imports, calls, the graph) therefore needs a new
  layer *above* this function, not changes inside it.
- **Drift worth flagging to the planner:** `_walk_symbols` (`python_symbols.py:154`) dispatches via an
  `if/elif` chain on `node.type`, not the dict-based dispatch the original Phase 1 design described as the
  intended extension point for adding new node kinds later. Extending for imports/calls means either (a)
  refactoring to dict dispatch first, or (b) adding a second independent traversal — option (b) matches
  how `_collect_syntax_issues` is already structured as a separate pass over the same tree.
- Bounded-output precedent: `_MAX_SYNTAX_ISSUES = 50` as a module-level constant, with
  `_collect_syntax_issues` stopping descent once a match is found (no nested noise). D-19's new caps
  should follow this exact pattern.
- `Symbol` has a `model_validator` enforcing `end_line >= start_line`; `SymbolKind` currently has no
  `module` or `import` member — any new symbol-like concept (e.g. "this is an import binding") needs its
  own type, not a shoehorned `SymbolKind` value.
- FastAPI isolation is **enforced, not aspirational**: a subprocess test asserts `"fastapi" not in
  sys.modules` after importing `app.analysis`. D-16 (never execute the fixture) keeps this guarantee true
  through Phase 2.

### Integration Points
- `fixtures/` sits at the **repo root**, outside `backend/`. Backend's pytest config is
  `testpaths = ["tests"]`, so the fixture is already immune to accidental test collection — but Phase 2's
  backend tests need to reach it via a path one level up from `backend/`.
- `networkx` is **not yet a dependency** — add it via `uv add networkx` at the point execution first needs
  it (not front-loaded), then regenerate `requirements.txt`/`requirements-dev.txt` from `uv.lock` and
  update `backend/README.md` at the Phase 2 milestone, per the standing incremental-dependency rule.
- `tree-sitter` is pinned `<0.26` in `pyproject.toml` (0.26.0's `Node` binding has a reference-counting
  segfault on deeply nested trees, reproduced and documented in Phase 1). Do not raise this ceiling
  opportunistically during Phase 2 work.

</code_context>

<specifics>
## Specific Ideas

No product-style "I want it like X" references came up — this is an internal analysis engine, not a
user-facing surface. The specific, concrete asks that did come up are captured as decisions D-01–D-20
above (e.g. the exact fixture structure in D-13, the exact edge/node shape in D-09–D-11).

</specifics>

<deferred>
## Deferred Ideas

- **Type/variable tracking** (`x = UserService()`, `x: UserService` annotations) — explicitly deferred by
  D-04, not rejected. Phase 5's evaluation harness can quantify how much recall is actually lost without
  it on real fixtures, turning this into an evidence-based decision later rather than a guess now.
- **Following imports into stdlib / installed site-packages** — rejected by D-05 on cost/budget grounds
  (ARCHITECTURE.md's time/byte bounds, £5/month ceiling), not capability.
- **Comprehensive ingestion budgets** (byte limits, wall-clock limits, concurrency limits) — remain owned
  by Phase 4 (CS-040, GitHub ingestion) and Phase 8 (CS-081, abuse/cost limits), per D-19. Phase 2 adds
  only light, named-constant caps.
- **Golden-snapshot graph testing** — rejected for this phase by D-15, but noted as a reasonable fit for
  Phase 5's evaluation harness, where the expected output is a measurement (precision/recall) rather than
  a fixed contract.
- **Larger or multi-package fixtures** — D-13 deliberately keeps the fixture tiny, per ARCHITECTURE.md's
  own wording ("tiny sample FastAPI fixture"); broader real-repo coverage arrives with Phase 5's 30-50
  controlled changes.
- **FastAPI route detection and reverse-impact tracing to routes** — Phase 3 (US-04). The fixture includes
  two route handlers (D-13) as call-graph material, but Phase 2 itself does not parse route decorators or
  trace paths to them.

</deferred>

---

*Phase: 02-imports-resolution-call-graph*
*Context gathered: 2026-11-01*
