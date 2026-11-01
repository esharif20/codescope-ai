# CodeScope AI

## What This Is

A hosted GitHub pull request impact analyser for developers reviewing unfamiliar Python/FastAPI codebases. It
identifies changed symbols, traces supported call relationships to potentially affected functions and API routes,
and explains findings using retrieved source evidence from public, approved Python/FastAPI repositories.

## Core Value

Show what a PR might affect, why, and the exact code supporting each finding — never claim static analysis proves
runtime behaviour or finds every dependency.

## Requirements

### Validated

- ✓ US-02: Identify added, modified and removed functions with file and line references — Phase 1
  (`backend/app/analysis/`: Tree-sitter extractor, Pydantic contract, JSON CLI, 46 pytest cases)

### Active

- [ ] US-01: Submit a supported GitHub PR URL and see analysis status or a clear error
- [ ] US-03: Trace supported caller relationships and flag unresolved edges
- [ ] US-04: See potentially affected FastAPI routes and the paths connecting them
- [ ] US-05: Read a concise AI impact explanation grounded in source evidence
- [ ] US-08: Explore an interactive dependency graph and selected paths
- [ ] US-09: Open source locations pinned to the analysed GitHub revision
- [ ] US-11: View precomputed demo reports without signing in
- [ ] US-12: See meaningful progress, timeout and error states
- [ ] US-13: Keep live analyses restricted and bounded to prevent abuse and costs

### Out of Scope

- US-06 (follow-up Q&A against indexed code/graph evidence) — Later priority per ARCHITECTURE.md; deferred until
  the Must stories above ship and are evaluated
- US-07 (candidate relevant tests with supporting reasons) — Later priority; same reason
- US-10 (reopen cached analyses without repeating work) — Later priority; same reason
- Multiple languages, voice interaction, private repositories, executing project/repository code, automated fixes,
  unrestricted public scanning, multi-agent systems, comprehensive test-coverage claims — explicitly excluded by
  ARCHITECTURE.md MVP scope
- Call graphs, dependency resolution, GitHub PR integration, RAG, LangChain, ChromaDB, the frontend, cloud
  deployment — deferred to their own later phases below; not built in Phase 1

## Context

- Full technical specification already exists in `ARCHITECTURE.md` (purpose, users, MVP scope, technology
  decisions, system design, analysis flow, API outline, constraints/security/cost, evaluation plan) and
  `AGENTS.md` (stack, working rules, workflow). Both are treated as authoritative; this project was **not**
  discovered through conversational discovery — it was scoped end-to-end before GSD was introduced, so PROJECT.md
  and REQUIREMENTS.md are synthesised directly from those documents rather than from a fresh interview.
- A lightweight ticket system (`TASKS.md` + GitHub Issues on `esharif20/codescope-ai`) mirrors GSD's phase state for
  human-readable tracking. GSD owns in-flight phase state; `TASKS.md` ticket status changes only at phase
  boundaries — this is the agreed anti-drift rule, stated at the top of `TASKS.md`.
- Phase 1 (Python symbol extraction, US-02) already has an approved, detailed implementation design: Pydantic
  models (`Symbol`, `ParseResult`, etc.), a Tree-sitter-based extractor in `backend/app/analysis/`, a JSON CLI, and
  a pytest suite — kept structurally independent of FastAPI. That design is executed immediately after this GSD
  roadmap is approved, without re-running phase discussion/research for Phase 1 (research is disabled project-wide
  for the same reason: the stack and scope are already fixed in ARCHITECTURE.md).
- Work happens on `feat/stage-1-python-symbols`; GSD commits land locally on that branch; nothing is pushed without
  explicit approval.

## Constraints

- **Tech stack**: Frontend React/TypeScript/Vite/Tailwind/shadcn/React Flow; backend Python/FastAPI/Pydantic;
  parsing Tree-sitter; graph NetworkX; RAG LangChain/Gemini/ChromaDB; data Firestore/Cloud Storage; hosting Google
  Cloud Run — fixed by `ARCHITECTURE.md`. AGENTS.md rule 8 requires justification and approval to add dependencies
  or change these decisions; do not alter `ARCHITECTURE.md` without approval.
- **Budget**: Target £0, hard ceiling £5/month for the practice deployment. Cloud Run `min=0`/`max=1`; no Cloud
  SQL, Redis, Kubernetes or permanent workers.
- **Security**: Never execute untrusted repository code or install its dependencies; treat repository text as
  untrusted (including prompt-injection attempts); no secrets or private repositories; accept only parsed,
  allowlisted GitHub PR identifiers, not arbitrary URLs.
- **Determinism/evidence**: Parsing, call resolution and graph traversal must be deterministic; unresolved
  dependencies are marked explicitly, never presented as verified; every finding carries inspectable source
  evidence.
- **Scope discipline**: One user story or bounded task at a time; no unrelated features; small testable modules
  reusing existing conventions.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Adopt GSD for phase/stage tracking, mirrored by TASKS.md + GitHub Issues | User requested a durable one-step-at-a-time tracker; GSD's `gates.confirm_*` defaults give that for free | ✓ Good — in place |
| Disable `workflow.research` project-wide | ARCHITECTURE.md already fixes stack/scope; re-researching it would contradict AGENTS.md rule 8 (approval required to change fixed decisions) | ✓ Good |
| Approve local GSD commits on `feat/stage-1-python-symbols`; nothing pushed | Unblocks GSD's atomic per-task commit model while honouring "no pushes without approval" | ✓ Good |
| Phase 1 = Tree-sitter Python symbol extractor, `backend/app/analysis/`, tolerant syntax-error handling, CPython `__qualname__`-style qualified names | Already designed and approved in detail before GSD was introduced; US-02 blocks every downstream Must story | ✓ Good — shipped, 46/46 tests green |
| Built via 3 parallel subagents (backlog / extractor / tests) from one pinned contract, implementation and tests never seeing each other's code | Isolates bulky `gh`/test-matrix tool output from the main session's context; independent test authorship catches spec-vs-code gaps a single author could paper over | ✓ Good — one weak assertion tightened on reconciliation, zero real contract conflicts |
| `tree-sitter` pinned to `<0.26` (resolves to 0.25.2) | 0.26.0 has a reference-counting bug in its Node binding that segfaults on deeply nested trees (reproduced and isolated via bisection); 0.25.2 is clean through 150+ levels | ✓ Good — re-test before raising this ceiling |
| Dependencies added incrementally per phase (`uv add` on first need, not front-loaded); `requirements.txt`/`requirements-dev.txt` regenerated from `uv.lock`; backend README updated at each milestone | Explicit process rule from the user, applied from Phase 1 onward | ✓ Good — standing practice for Phase 2+ |
| Backend hosting stays Cloud Run, not Vercel | Settled architecture decision; cross-cloud credentials to Firestore/GCS would need long-lived keys Cloud Run avoids; hosting is Phase 8, not now | ✓ Good |
| Frontend static host left open per ARCHITECTURE.md; Vercel is a candidate to resolve that open question at Phase 7 | ARCHITECTURE.md explicitly leaves this undecided ("Firebase Hosting or another free static host") — Vercel fits that gap, with an approved doc amendment when reached | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-11-01 after Phase 1 completion*
