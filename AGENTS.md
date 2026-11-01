# CodeScope AI: Agent Instructions

## Context

CodeScope AI analyses GitHub pull requests using static dependency graphs and evidence-grounded RAG.

Read `ARCHITECTURE.md` before planning or editing. It defines the project's scope, user stories and design decisions. Do not change those decisions without approval.

## Stack

- Frontend: React, TypeScript, Vite, Tailwind CSS, React Flow
- Backend: Python, FastAPI, Pydantic
- Static analysis: Tree-sitter, NetworkX
- RAG: LangChain, ChromaDB, Gemini
- Data: Firestore and Cloud Storage when needed
- Hosting: Google Cloud Run; target less than £5/month
- Tests: pytest, Vitest; CI: GitHub Actions

## Rules

1. Work on one user story or bounded task at a time. Do not add unrelated features.
2. Prefer small, testable modules and existing project conventions.
3. Keep parsing, call resolution and graph traversal deterministic.
4. Mark unresolved dependencies. Never present LLM guesses as verified call paths.
5. Include source locations and evidence in analysis results.
6. Write tests for new functionality and regressions; run applicable checks.
7. Never execute untrusted repository code, install its dependencies or expose secrets.
8. Do not introduce paid infrastructure or new dependencies without justification and approval.
9. Keep the first deployment simple; defer multi-agent workflows and background workers.

## Workflow

1. Identify the relevant user story and read its architecture section.
2. Inspect existing implementation and tests.
3. Explain the proposed approach for substantial changes.
4. Implement the smallest complete solution and add tests.
5. Run checks, review the diff and report results.

## Completion report

Summarise changed files, tests run and outcomes, limitations and decisions needing approval. Never claim tests passed unless they ran successfully.
