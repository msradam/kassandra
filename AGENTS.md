# Project Configuration for AI Agents

## Kassandra

Kassandra is a project-agnostic performance testing agent. Each demo application
under `demos/` has its own `AGENTS.md` with project-specific SLOs, auth config,
critical paths, and test conventions.

### Demo Applications

| App | Stack | Directory | AGENTS.md |
|-----|-------|-----------|-----------|
| QuickPizza | Go / Chi / SQLite | `demos/quickpizza/` | `demos/quickpizza/AGENTS.md` |
| PageTurn | Python / FastAPI / in-memory | `demos/pageturn/` | `demos/pageturn/AGENTS.md` |

### How It Works

When triggered on a merge request, Kassandra:
1. Reads the project's `AGENTS.md` for SLOs and conventions
2. Reads the MR diff to classify changed endpoints
3. Reads reference k6 tests to match the project's style
4. Generates, executes, and reports k6 performance tests

The agent adapts to any project — different stacks, different SLOs,
different auth mechanisms — by reading the project config at runtime.
