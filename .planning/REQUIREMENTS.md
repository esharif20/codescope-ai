# Requirements: CodeScope AI

**Defined:** 2026-11-01
**Core Value:** Show what a PR might affect, why, and the exact code supporting each finding — never claim static
analysis proves runtime behaviour or finds every dependency.

**Source:** Synthesised directly from `ARCHITECTURE.md`'s user-story table (US-01…US-13) and MVP scope — not
gathered through fresh discovery, since that specification already exists and is approved. Requirement IDs are
kept as the existing `US-NN` identifiers rather than re-numbered, so `TASKS.md`, `ARCHITECTURE.md` and this file
stay in sync under one scheme.

## v1 Requirements

Must-priority stories from ARCHITECTURE.md. Each maps to exactly one roadmap phase below.

### Ingestion & Status

- [ ] **US-01**: User can submit a supported GitHub PR URL and see analysis status or a clear error
- [ ] **US-12**: User sees meaningful progress, timeout and error states during analysis
- [ ] **US-13**: Live analyses are restricted and bounded to prevent abuse and runaway cost

### Symbol & Dependency Analysis

- [ ] **US-02**: User can identify added, modified and removed functions with file and line references
- [ ] **US-03**: User can trace supported caller relationships and see unresolved edges flagged explicitly

### Route Impact

- [ ] **US-04**: User can see potentially affected FastAPI routes and the paths connecting them to a change

### Evidence & Navigation

- [ ] **US-05**: User can read a concise AI impact explanation grounded in cited source evidence
- [ ] **US-09**: User can open source locations pinned to the exact analysed GitHub revision

### Exploration UI

- [ ] **US-08**: User can explore an interactive dependency graph and inspect selected paths

### Demo Access

- [ ] **US-11**: User can view precomputed demo reports without signing in

## v2 Requirements

Later-priority per ARCHITECTURE.md. Acknowledged, not in the current roadmap.

### Follow-up Interaction

- **US-06**: User can ask follow-up questions against indexed code and graph evidence
- **US-07**: User can receive candidate relevant tests with supporting reasons, not coverage guarantees

### Caching

- **US-10**: User can reopen cached analyses without repeating work

## Out of Scope

Explicitly excluded by ARCHITECTURE.md's MVP scope.

| Feature | Reason |
|---------|--------|
| Multiple languages (non-Python) | MVP targets Python/FastAPI only |
| Voice interaction | Not an MVP goal |
| Private repositories | Public, allowlisted repos only — security and scope |
| Executing project/repository code or installing its dependencies | Untrusted code; security constraint in AGENTS.md |
| Automated fixes | Analysis and explanation only, not remediation |
| Unrestricted public scanning | Would break the £5/month budget and abuse controls |
| Multi-agent systems | Deferred; single bounded request flow for the MVP |
| Comprehensive test-coverage claims | Evaluation measures precision/recall, not guarantees |
| General repository chat | Explicitly deferred past "New team members exploring architecture" in ARCHITECTURE.md |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| US-02 | Phase 1 | Complete |
| US-03 | Phase 2 | Pending |
| US-04 | Phase 3 | Pending |
| US-01 | Phase 4 | Pending |
| US-09 | Phase 4 | Pending |
| US-12 | Phase 4 | Pending |
| US-11 | Phase 5 | Pending |
| US-05 | Phase 6 | Pending |
| US-08 | Phase 7 | Pending |
| US-13 | Phase 8 | Pending |

**Coverage:**
- v1 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0 ✓

---
*Requirements defined: 2026-11-01*
*Last updated: 2026-11-01 after Phase 1 completion*
