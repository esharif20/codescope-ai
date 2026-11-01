# CodeScope AI -- backend

**Status (Phase 1 of 8 complete; Phase 2 (imports, resolution, call graph) in progress -- see `../TASKS.md` /
`../.planning/ROADMAP.md`):** a Tree-sitter based Python symbol extractor (`app/analysis/`) -- functions, classes,
methods and nested functions, with qualified names, source ranges, and explicit empty/syntax-error/decode-error
handling. Independent of FastAPI; no web framework yet.

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

## Pinned tooling note

`uv < 0.13` wrote the editable-install `.pth` file with macOS's `UF_HIDDEN` flag set; CPython 3.13's `site.py`
silently skips any hidden `.pth` file (intentional security hardening, not a project bug), which broke `import
app` for the installed `codescope-parse` console script specifically. Confirmed fixed in `uv` 0.13.0 (verified in
an isolated test venv) and enforced via the `required-version` pin above so this can't silently reproduce. Never
affected Linux (no `UF_HIDDEN` concept), so CI was never at risk.

## Pinned dependency note

`tree-sitter` is pinned to `<0.26` (currently resolves to `0.25.2`): version `0.26.0` has a reference-counting bug
in its `Node` binding that segfaults when `child_by_field_name()` + `.text` are called repeatedly while walking
deeply nested trees (reproduced consistently around 65+ nested function definitions; `0.25.2` is clean through
150+). Re-test deliberately before raising this ceiling.

## Design note

`app/analysis` has **zero dependency on FastAPI**, by design (see
`AGENTS.md`): symbol extraction must stay usable from CLIs, batch jobs, and
tests independently of any web framework that is layered on top later.
