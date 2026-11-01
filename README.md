# CodeScope AI

An AI-powered GitHub pull request impact analyser.

CodeScope combines static code analysis, dependency graphs
and retrieval-augmented generation (RAG) to identify
potentially affected functions and API endpoints.

## Tech Stack

- Python, FastAPI
- Tree-sitter, NetworkX
- LangChain, ChromaDB, Gemini
- React, TypeScript, React Flow
- Google Cloud Run, Firestore, Cloud Storage

## Status

**Phase 1 of 8 complete** (see [TASKS.md](TASKS.md) and [.planning/ROADMAP.md](.planning/ROADMAP.md)): a
Tree-sitter based Python symbol extractor (`backend/app/analysis/`) — functions, classes, methods and nested
functions, with qualified names, source ranges, and a JSON CLI. See [backend/README.md](backend/README.md) for
setup and usage. Everything else below is still planned, not built.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the system
design, user stories and planned features.