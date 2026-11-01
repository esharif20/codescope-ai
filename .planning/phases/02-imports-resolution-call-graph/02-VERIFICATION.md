---
phase: 02-imports-resolution-call-graph
verified: 2026-11-01T16:00:00Z
status: passed
score: 22/22 must-haves verified
---

# Phase 02: Imports, Resolution, Call Graph Verification Report

**Phase Goal:** Resolve imports and direct calls into a NetworkX call graph; unresolved edges are explicit, never invented.

**Verified:** 2026-11-01T16:00:00Z

**Status:** passed

**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Phase 2 contracts and deterministic module paths exist. | ✓ VERIFIED | `models.py` exports resolution/call records; `test_module_paths.py` covers package, root, and outside-root cases. |
| 2 | The fixture exercises resolved and dynamic/untyped call shapes together. | ✓ VERIFIED | 10-file fixture plus exact end-to-end inventory in `test_sample_fastapi_repo.py`. |
| 3 | Plain, from, relative, star, and aliased imports are extracted without resolution guesses. | ✓ VERIFIED | `extract_raw_imports` and 9 import-shape tests. |
| 4 | Calls and class bases retain lexical/source evidence before resolution. | ✓ VERIFIED | `calls.py` produces `RawCall`/`RawClassBases`; 15 focused extraction tests pass. |
| 5 | In-repo, relative/re-export, star, external, and unresolved imports are classified explicitly. | ✓ VERIFIED | Two-pass `import_resolver.py` and 9 resolver tests; fixture star/re-export path resolves end-to-end. |
| 6 | Supported direct calls resolve deterministically; dynamic, ambiguous, and untyped calls remain explicit evidence. | ✓ VERIFIED | `call_resolver.py` emits one resolved or unresolved/uncertain result per raw call; 14 resolver tests pass. |
| 7 | The graph is queryable, preserves call-site lines, and excludes unresolved/uncertain outcomes from traversal. | ✓ VERIFIED | `networkx.DiGraph`, sorted helper queries, and 8 graph tests. |
| 8 | A whole directory is analysed in project-wide dependency order with explicit partial-analysis statuses. | ✓ VERIFIED | `build_project_graph` sorts files, completes import passes before call resolution, and tests decode/OSError/cap handling. |
| 9 | The graph CLI is separately exposed without changing the existing parse CLI. | ✓ VERIFIED | `graph_main`, `codescope-graph` entry point, CLI tests, and direct JSON spot-check. |
| 10 | The real fixture has exactly its hand-written resolved and unresolved inventory. | ✓ VERIFIED | 10 verified edges and 7 explicit unresolved entries, asserted exactly by integration tests. |

**Score:** 22/22 must-haves verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `models.py`, `module_paths.py` | Contracts and module identities | ✓ VERIFIED | Artifact check 2/2; tests pass. |
| Fixture package | Real multi-file resolver input | ✓ VERIFIED | Artifact check 3/3; 10 files parse (`ok`/`empty`). |
| `imports.py`, `calls.py` | Raw syntax extraction | ✓ VERIFIED | Artifact check 2/2; source-location tests pass. |
| `import_resolver.py`, `call_resolver.py` | Evidence-preserving resolution | ✓ VERIFIED | Artifact check 2/2; internal/external/unresolved and uncertain paths tested. |
| `call_graph.py` | Queryable DiGraph | ✓ VERIFIED | Artifact check 1/1; edge-line and query tests pass. |
| `project_graph.py`, `cli.py` | Project pipeline and CLI | ✓ VERIFIED | Artifact check 2/2; pipeline and CLI behave as required. |
| `test_sample_fastapi_repo.py` | Hand-written integration inventory | ✓ VERIFIED | Artifact check 1/1; exact-set assertions pass. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- |
| Module paths | Symbol identities | Root-relative module paths | ✓ WIRED | Automated key-link check passed. |
| Fixture routes | Fixture services | Star import and one-hop re-export | ✓ WIRED | Manual source inspection confirms `from ..services import *` and `from .auth import ...`; integration test exercises both. |
| Raw extractors | Resolvers | `relative_level`, receiver kind, class bases | ✓ WIRED | Automated key-link checks passed. |
| Resolvers | Call graph | `ResolvedCall` / `UnresolvedCall` | ✓ WIRED | Automated key-link check passed; graph tests prove separation. |
| Project graph | Import/call stages | Project-wide ordered passes | ✓ WIRED | Automated key-link checks passed. |
| CLI | Project graph | `graph_main` invokes `build_project_graph` | ✓ WIRED | Automated key-link check and CLI spot-check passed. |
| Integration test | Fixture root | `build_project_graph(FIXTURE_ROOT)` | ✓ WIRED | Automated key-link check passed. |

Note: the key-link helper's two fixture regex checks reported false negatives because their escaped patterns did not match valid literal import syntax; direct source inspection and the end-to-end integration test verify those links.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Full analyzer regression suite | `cd backend && uv run pytest -q` | 124 passed | ✓ PASS |
| Static quality | `cd backend && uv run ruff check .` | All checks passed | ✓ PASS |
| Graph CLI emits evidence | `uv run codescope-graph ../fixtures/sample_fastapi_repo --compact` | 10 edges, 7 unresolved, required top-level fields | ✓ PASS |
| Invalid graph root is safe | `uv run codescope-graph /nonexistent/path` | Exit 1 with stderr | ✓ PASS |

The console-script checks used `uv sync --extra dev --no-editable`, because the environment's editable-install `.pth` behavior is documented separately; no analysed repository source was executed.

### Requirements Coverage

| Requirement | Source Plans | Status | Evidence |
| --- | --- | --- | --- |
| US-03 — trace supported caller relationships and flag unresolved edges | 02-01 through 02-09 | ✓ SATISFIED | Queryable NetworkX graph, exact fixture caller/callee inventory, and explicit unresolved/uncertain source records. |

No Phase 2 requirement is orphaned: every plan declares US-03 and the requirements list maps US-03 to Phase 2.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- |
| — | — | No TODO/FIXME/placeholder or empty-production-implementation patterns found in Phase 2 analyzer modules. | ℹ️ None | No blocker. |

### Human Verification Required

None. This phase is a deterministic, non-visual static-analysis layer; its observable behavior is covered by the runnable suite and CLI checks.

## Gaps Summary

None. Phase 2 achieves its US-03 goal without promoting uncertain or unresolved relationships into verified graph edges.

---

_Verified: 2026-11-01T16:00:00Z_
_Verifier: GSD phase verifier_
