# Project Configuration for AI Agents

## Kassandra

Kassandra is a project-agnostic performance testing agent. Each demo application
under `demos/` has its own `AGENTS.md` with project-specific SLOs, auth config,
critical paths, and test conventions.

### Demo Applications

| App | Stack | Directory | AGENTS.md | URL |
|-----|-------|-----------|-----------|-----|
| Calliope Books | Node.js / Express / sql.js | `demos/calliope-books/` | `demos/calliope-books/AGENTS.md` | http://localhost:3000 |
| Midas Bank | Python / FastAPI / pysqlite3 | `demos/midas-bank/` | `demos/midas-bank/AGENTS.md` | http://localhost:8000 |
| Hestia Eats | Go / net/http / in-memory | `demos/hestia-eats/` | `demos/hestia-eats/AGENTS.md` | http://localhost:8080 |

### Routing — Which AGENTS.md to Read

Check the MR diff file paths to determine which demo app is being changed:
- Files under `demos/calliope-books/` → read `demos/calliope-books/AGENTS.md` and `demos/calliope-books/openapi.json`
- Files under `demos/midas-bank/` → read `demos/midas-bank/AGENTS.md` and `demos/midas-bank/openapi.json`
- Files under `demos/hestia-eats/` → read `demos/hestia-eats/AGENTS.md` and `demos/hestia-eats/openapi.json`

**Always use the demo-specific AGENTS.md** — it contains the correct SLOs, auth config, and execution command for that app.
