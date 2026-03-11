# Kassandra

Automated performance testing agent for GitLab merge requests. Kassandra analyzes code changes, generates [k6](https://k6.io) load test scripts, executes them against review environments, and posts performance reports back to the MR.

Built on the [GitLab Duo Agent Platform](https://docs.gitlab.com/ee/development/duo_workflow/).

## How it works

Kassandra is **project-agnostic**. It reads each project's `AGENTS.md` for SLOs, auth config, critical paths, and test conventions — then adapts accordingly. When a merge request introduces or modifies API endpoints, the agent:

1. **Reads the MR diff** and classifies changed endpoints (REST CRUD, batch, auth, read-heavy, write-heavy)
2. **Reads AGENTS.md** for project-specific SLOs, auth credentials, and test conventions
3. **Generates k6 scripts** with appropriate executors, thresholds, and load profiles based on endpoint type
4. **Executes tests** against the review environment
5. **Posts a performance report** as an MR note with latency percentiles, error rates, throughput, and pass/fail status

## Demo applications

Two demo apps prove Kassandra works across different stacks:

| App | Stack | Port | Directory |
|-----|-------|------|-----------|
| **QuickPizza** | Go / Chi / SQLite | 3333 | `demos/quickpizza/` |
| **PageTurn** | Python / FastAPI / in-memory | 8000 | `demos/pageturn/` |

Each has its own `AGENTS.md`, reference k6 tests, and OpenAPI spec. Kassandra generates different test strategies for each based on their unique SLOs and auth mechanisms.

## Project structure

```
agents/agent.yml                  # Agent definition (GitLab Duo)
flows/flow.yml                    # Flow definition (GitLab Duo)
prompts/kassandra-system.md       # Full system prompt
.gitlab/duo/agent-config.yml      # Platform environment setup

simulator/                        # Local testing harness
  run.py                          # Agentic loop (Anthropic API)
  evaluate.py                     # Script quality + runtime evaluator
  tools.py                        # Local tool implementations
  config.py                       # Configuration

demos/
  quickpizza/                     # Go demo app
    AGENTS.md                     # QuickPizza-specific SLOs and config
    app/                          # Go source
    k6/                           # Reference tests + generated output
  pageturn/                       # Python demo app
    AGENTS.md                     # PageTurn-specific SLOs and config
    pageturn/                     # FastAPI source
    k6/                           # Reference tests + generated output

samples/
  quickpizza/                     # Sample MR diffs and contexts
  pageturn/
```

## Local simulator

The simulator replicates the GitLab Duo agentic loop locally with the same tool interface.

```bash
# Run against QuickPizza (default)
ANTHROPIC_API_KEY=... python -m simulator.run --sample 01-batch-endpoint --anthropic

# Run against PageTurn
KASSANDRA_PROJECT=pageturn ANTHROPIC_API_KEY=... python -m simulator.run --sample 04-book-search-filters --anthropic

# Dry run (generate scripts without executing k6)
python -m simulator.run --sample 01-batch-endpoint --anthropic --dry-run

# From a real git branch
python -m simulator.run --branch feature/add-favorites --anthropic
```

## Evaluator

Score generated k6 scripts and runtime results:

```bash
# Full session evaluation (static analysis + runtime SLO checks)
python -m simulator.evaluate --session

# Evaluate a single script
python -m simulator.evaluate generated-test.js

# Check all reference scripts
python -m simulator.evaluate --check-all
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `KASSANDRA_PROJECT` | `quickpizza` | Target demo app (`quickpizza` or `pageturn`) |
| `KASSANDRA_ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Anthropic model |
| `KASSANDRA_REVIEW_URL` | per-project | Review environment URL |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |

## License

Kassandra is MIT licensed. QuickPizza (in `demos/quickpizza/`) is Apache 2.0 licensed by Grafana Labs — see [demos/quickpizza/LICENSE](demos/quickpizza/LICENSE).
