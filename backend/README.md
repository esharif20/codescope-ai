# CodeScope AI -- backend

**Status (Phase 1 of 8 -- see `../TASKS.md` / `../.planning/ROADMAP.md`):** a Tree-sitter based Python symbol
extractor (`app/analysis/`) -- functions, classes, methods and nested functions, with qualified names, source
ranges, and explicit empty/syntax-error/decode-error handling. Independent of FastAPI; no web framework yet.

## Setup

```bash
uv sync --extra dev
```

Dependencies are added incrementally, one phase at a time, via `uv add <package>` only when that phase's code
first needs it -- e.g. `networkx` isn't added until Phase 2, `fastapi` not until Phase 4, `langchain`/`chromadb`
not until Phase 6. `pyproject.toml` + `uv.lock` are the source of truth; `requirements.txt` /
`requirements-dev.txt` are regenerated from them after every dependency change
(`uv export --format requirements.txt --no-dev --no-hashes --no-emit-project -o requirements.txt`, and the same
with `--extra dev -o requirements-dev.txt`) for tooling that expects plain pip-style files.

## Test

```bash
uv run pytest -q
```

## CLI usage

```bash
uv run python -m app.analysis.cli path/to/file.py
uv run python -m app.analysis.cli path/to/file.py --compact   # single-line JSON

# also installed as a console script, but see the caveat below:
uv run codescope-parse path/to/file.py
```

**Known local-environment caveat:** on this machine, `uv` 0.11.2 writes the editable-install `.pth` file with the
macOS `UF_HIDDEN` flag set; CPython 3.13's `site.py` silently skips any hidden `.pth` file (an intentional
security hardening change, not a project bug). That breaks `import app` for anything relying on the `.pth`
specifically -- the installed `codescope-parse` console script, in particular. `python -m app.analysis.cli` and
`uv run pytest` are unaffected (the former gets `sys.path[0]` from `-m`'s own cwd injection; the latter is pinned
via `pythonpath = ["."]` in `pyproject.toml`, deliberately added so test collection never depends on the `.pth`
mechanism at all). This is specific to uv 0.11.2 + CPython 3.13 on macOS -- it does not reproduce on Linux (no
`UF_HIDDEN` concept) and is reportedly fixed in newer `uv` releases. Prefer `python -m app.analysis.cli` until
confirmed otherwise.

## Pinned dependency note

`tree-sitter` is pinned to `<0.26` (currently resolves to `0.25.2`): version `0.26.0` has a reference-counting bug
in its `Node` binding that segfaults when `child_by_field_name()` + `.text` are called repeatedly while walking
deeply nested trees (reproduced consistently around 65+ nested function definitions; `0.25.2` is clean through
150+). Re-test deliberately before raising this ceiling.

## Design note

`app/analysis` has **zero dependency on FastAPI**, by design (see
`AGENTS.md`): symbol extraction must stay usable from CLIs, batch jobs, and
tests independently of any web framework that is layered on top later.
