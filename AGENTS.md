# Project Configuration for AI Agents

## Kassandra

Kassandra is a project-agnostic performance testing agent. Each demo application
under `demos/` has its own `AGENTS.md` with project-specific SLOs, auth config,
critical paths, and test conventions.

### Active Demo Applications

**RealWorld** (Node.js) — Express-Sequelize RealWorld Conduit app at **http://localhost:3000**
**FastAPI Shop** (Python) — FastAPI e-commerce app at **http://localhost:8000**

Read the project-specific `AGENTS.md` for whichever app the MR targets.

### All Demo Applications

| App | Stack | Directory | AGENTS.md | URL |
|-----|-------|-----------|-----------|-----|
| RealWorld | Node.js / Express / Sequelize / SQLite | `demos/realworld/` | `demos/realworld/AGENTS.md` | http://localhost:3000 |
| FastAPI Shop | Python / FastAPI / SQLAlchemy / SQLite | `demos/fastapi-shop/` | `demos/fastapi-shop/AGENTS.md` | http://localhost:8000 |
| PageTurn | Python / FastAPI / in-memory | `demos/pageturn/` | `demos/pageturn/AGENTS.md` | http://localhost:8000 |

### How It Works

When triggered on a merge request, Kassandra:
1. Reads the relevant `AGENTS.md` for SLOs and conventions
2. Reads the MR diff to classify changed endpoints
3. Reads reference k6 tests to match the project's style
4. Generates, executes, and reports k6 performance tests

The agent adapts to any project — different stacks, different SLOs,
different auth mechanisms — by reading the project config at runtime.
