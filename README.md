# Kassandra

Automated performance testing agent for GitLab merge requests. Kassandra analyzes code changes, generates [k6](https://k6.io) load test scripts, executes them, and posts performance reports back to the MR.

Built on the [GitLab Duo Workflow Platform](https://docs.gitlab.com/ee/development/duo_workflow/).

## How it works

Kassandra is **project-agnostic**. It reads each project's `AGENTS.md` for SLOs, auth config, critical paths, and test conventions — then adapts accordingly. When a merge request introduces or modifies API endpoints, the agent:

1. **Reads the MR diff** and classifies changed endpoints (REST CRUD, batch, auth, read-heavy, write-heavy)
2. **Reads AGENTS.md** for project-specific SLOs, auth credentials, and test conventions
3. **Generates k6 scripts** with appropriate executors, thresholds, and load profiles
4. **Executes tests** against the running application
5. **Posts a performance report** as an MR note with latency percentiles, error rates, throughput, and pass/fail status

## Demo applications

Two self-contained demo apps (named after Greek mythology figures) prove Kassandra works across stacks:

| App | Stack | Port | Directory |
|-----|-------|------|-----------|
| **Calliope Books** | Node.js / Express / sql.js | 3000 | `demos/calliope-books/` |
| **Midas Bank** | Python / FastAPI / pysqlite3 | 8000 | `demos/midas-bank/` |

Both apps use embedded SQLite (no external database) and run on the GitLab Duo runner image without native compilation. Each has its own `AGENTS.md` with SLOs, auth config, and endpoint documentation.

## Project structure

```
agents/agent.yml                  # Agent definition (GitLab Duo)
flows/flow.yml                    # Flow definition (GitLab Duo)
prompts/kassandra-system.md       # Full system prompt
.gitlab/duo/agent-config.yml      # Runner setup (k6, apps)

demos/
  calliope-books/                 # Node.js bookshop API
    AGENTS.md                     # SLOs, auth, endpoints
    app.js                        # Express app (sql.js)
    k6/                           # Reference k6 tests
  midas-bank/                     # Python banking API
    AGENTS.md                     # SLOs, auth, endpoints
    app.py                        # FastAPI app (pysqlite3)
    k6/                           # Reference k6 tests

simulator/                        # Local testing harness
  run.py                          # Agentic loop (Anthropic API)
  evaluate.py                     # Script quality evaluator
  tools.py                        # Local tool implementations
  config.py                       # Configuration
```

## Runner environment

The `setup_script` in `.gitlab/duo/agent-config.yml` handles everything before Kassandra runs:
- Installs k6
- Starts Calliope Books on port 3000
- Starts Midas Bank on port 8000
- Verifies both apps are healthy

Kassandra does **not** start or manage applications — it only generates and runs k6 tests against them.

## Local simulator

The simulator replicates the GitLab Duo agentic loop locally.

```bash
# Run against Calliope Books
KASSANDRA_PROJECT=calliope-books ANTHROPIC_API_KEY=... uv run python -m simulator.run --anthropic

# Run against Midas Bank
KASSANDRA_PROJECT=midas-bank ANTHROPIC_API_KEY=... uv run python -m simulator.run --anthropic
```

## License

MIT
