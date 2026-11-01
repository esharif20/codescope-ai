---
phase: 04-pr-ingestion-diff-mapping
plan: 05
subsystem: api
tags: [fastapi, asgi, authorization, polling, ingestion, tdd]
requires:
  - phase: 04-04
    provides: Exclusive observable synchronous pipeline and revision-correct analysis statuses
provides:
  - Approved locked core FastAPI runtime without optional server/test-client dependencies
  - Public health and authorized bounded synchronous submission with concurrent UUID polling
  - Safe HTTP errors and hermetic raw-ASGI contract tests
affects: [05-evidence-grounded-reports, 07-interactive-graph-ui, 08-cloud-run-demo]
tech-stack:
  added: [fastapi, starlette, anyio, annotated-doc, idna, opentelemetry-api]
  patterns: [pure-ASGI admission boundary, standard request thread pool, raw-ASGI test harness]
key-files:
  created:
    - backend/app/api.py
    - backend/app/main.py
    - backend/tests/test_analysis_api.py
  modified:
    - backend/pyproject.toml
    - backend/uv.lock
    - backend/requirements.txt
    - backend/requirements-dev.txt
    - backend/README.md
key-decisions:
  - Add only approved core FastAPI and resolver-required transitives without optional extras.
  - Authenticate both analyses routes before body parsing and cap actual streamed bytes at 8 KiB.
  - Keep HTTP status policy in the API boundary without changing framework-independent ingestion codes.
  - Use ordinary synchronous FastAPI handlers for analysis while the same-process registry supports polling.
patterns-established:
  - Test actual ASGI messages using asyncio and threading Events without HTTPX or sockets.
  - Suppress raw framework validation details and return only safe AnalysisError envelopes.
requirements-completed: [US-01, US-02, US-09, US-12]
duration: 5min
completed: 2026-11-01
---

# Phase 4 Plan 5: Bounded REST API Summary

**Authorized synchronous PR analysis exposes concurrent UUID polling, revision-pinned source links and bounded safe errors through core FastAPI.**

## Performance

- **Duration:** Approximately 5 min
- **Completed:** 2026-11-01
- **Tasks:** 3, including the resolved dependency checkpoint
- **Implementation/documentation files:** 8

## Dependency Approval

Before dependency changes, the user explicitly approved: “add fast api and finish pahse 4”. This resolves Task 1 and approves core FastAPI plus required resolver-selected transitives, without standard/server/test-client extras, HTTPX, Uvicorn or a GitHub SDK. Installation is justified by the architecture's selected FastAPI REST boundary. The parent executor relayed this approval on 2026-11-01.

Resolved FastAPI **0.162.0**, Starlette **1.10.0**, AnyIO **4.16.0**, annotated-doc **0.0.5**, idna **3.20**, and opentelemetry-api **1.45.2**. Existing direct dependencies and Tree-sitter/Python/Pydantic constraints remain preserved. Both requirement exports match the lockfile. `uv sync --extra dev --locked` succeeded directly; no editable workaround was needed.

## Accomplishments

- Added public `/health`, authorized synchronous `POST /api/analyses`, and authorized `GET /api/analyses/{analysis_id}` with no import-time upstream work.
- Verified actual concurrent GET responses observe the `running`/`mapping` stage while POST blocks, health responds, and competing submissions get 409 without another upstream client.
- Enforced authorization with constant-time bytes comparison, strict JSON media types and an 8 KiB streamed body cap before parsing.
- Preserved the existing AnalysisRequest/Status contracts, safe pre-admission errors, terminal status envelopes, exact pinned links and separate base/head route counts.
- Mapped request/upstream/limit/timeout errors at the HTTP boundary, including safe numeric Retry-After for 429 responses, without changing ingestion's framework-independent statuses.
- Documented examples, UUID pre-reservation 404, meaningful stages, caller/upstream credential separation, allowlist/fork/merge-base provenance, ceilings and process-local lifetime.

## Task Commits

1. **Task 1: Record explicit dependency approval** — `b9a73f5` (docs).
2. **Task 2: Install minimal FastAPI and refresh lock/exports** — `156a076` (chore).
3. **Task 3: Expose and test bounded REST API** — `33602cc` (test RED), `300351e` (feat GREEN).

## Files Created/Modified

- `backend/app/api.py` — Admission/body boundary, health/submission/polling routes, HTTP status policy and sanitized exception handlers.
- `backend/app/main.py` — Injectable app factory and default ASGI entry point.
- `backend/tests/test_analysis_api.py` — 34 hermetic API cases with real local graph/mapping work, blocked concurrent polling, invalid inputs, authorization, cleanup, failures and redaction.
- `backend/pyproject.toml`, `backend/uv.lock`, `backend/requirements.txt`, `backend/requirements-dev.txt` — Approved core runtime and reproducible exports.
- `backend/README.md` — Complete Phase 4 usage and operational limitations.

## Verification

- TDD RED: API test collection failed on missing `app.main` before implementation, as expected.
- Focused API/runtime/pipeline/project routes suite — **67 passed**.
- `cd backend && uv run --no-sync python -m pytest -q` — **549 passed**.
- `cd backend && uv run --no-sync ruff check app tests` — **passed**.
- `cd backend && uv lock --check` — **passed**.
- Fresh runtime/dev exports compared against committed exports, ignoring generated command headers — **identical**.
- `git diff --check` — **passed**.
- Stub scan found no TODO/FIXME/placeholder or unwired implementation. Empty buffers and fake client objects are intentional middleware/test infrastructure.

## Decisions Made

Followed the planned synchronous same-process boundary. FastAPI uses its ordinary request thread pool; no custom executor, detached task, queue or worker was added. The HTTP mapping intentionally translates ingestion limit errors from 422 to 413 and rate limits from 503 to 429 without changing CLI/library behavior. Authorization is enforced before body reading and validation. Duplicate authorization/content-type headers fail closed.

## Deviations from Plan

None in scope. The parent orchestrator owns shared STATE, ROADMAP, REQUIREMENTS and TASKS updates and their metadata commit; this executor leaves those shared trackers untouched as assigned. Local commits use the explicitly requested `--no-verify`; all stated checks ran separately.

## Issues Encountered

A targeted invalid-UTF-8 regression exposed FastAPI's default HTTP 400 parsing response. Added a sanitized HTTP exception handler so malformed body encoding meets the planned 422 error contract. The regression and all other tests pass. Ruff formatting and two test lint findings were corrected before verification. No authentication gates occurred.

## Known Stubs

None.

## User Setup Required

None for offline tests. Live analysis requires the documented allowlist and caller credential; an optional GitHub token remains distinct. Server/deployment setup is deferred to Phase 8 as planned.

## Next Phase Readiness

The REST boundary exposes revision-correct changed-symbol summaries for later report/UI work. Status remains ephemeral and process-local, with cooperative deadlines and bounded retention. Tests use fake upstream sources and prove no live GitHub compatibility. No server, graph/report endpoint, RAG, storage, infrastructure, fixture execution, push or deployment was added.

## Self-Check: PASSED

Confirmed all eight implementation/documentation files and this summary exist. Confirmed task commits `b9a73f5`, `156a076`, `33602cc` and `300351e` exist in git. Shared tracking updates belong to the parent orchestrator.
