# Kassandra

Automated performance testing agent for GitLab merge requests. Kassandra analyzes code changes, generates [k6](https://k6.io) load test scripts, executes them, and posts performance reports — catching regressions before they reach production.

Built on the [GitLab Duo Workflow Platform](https://docs.gitlab.com/ee/development/duo_workflow/).

## How it works

When triggered by an `@mention` on a merge request, Kassandra:

1. **Analyzes the MR diff** — classifies changed endpoints (REST CRUD, batch, auth, read-heavy, write-heavy)
2. **Reads AGENTS.md** — picks up project-specific SLOs, auth config, and test conventions
3. **Generates k6 scripts** — per-endpoint scenarios with appropriate executors, thresholds, and load profiles
4. **Commits tests to the branch** — the k6 script and endpoint manifest become part of the MR
5. **Executes tests** — starts the app, runs k6, captures results (all in a single process)
6. **Posts a performance report** — latency percentiles, error rates, throughput, SLO compliance, and actionable recommendations

Kassandra is **project-agnostic**. Each project's `AGENTS.md` tells it what to test, what thresholds to use, and how to authenticate.

## Demo applications

Two self-contained demo apps showcase Kassandra across different stacks:

| App | Stack | Port | Description |
|-----|-------|------|-------------|
| **Calliope Books** | Node.js / Express / sql.js | 3000 | Bookshop API with search, reviews, trending |
| **Midas Bank** | Python / FastAPI / pysqlite3 | 8000 | Banking API with accounts, transfers, statements |

Both use embedded SQLite (no external dependencies) and include intentional performance patterns for Kassandra to catch:
- **Calliope Books**: N+1 queries, unoptimized LIKE scans, artificial delay on search
- **Midas Bank**: Aggregation queries, multi-table joins for statements

## Triggering Kassandra

On any MR in this project, comment:

```
@ai-kassandra-performance-test-gitlab-ai-hackathon Run performance tests on this MR.
```

## Project structure

```
agents/agent.yml                  # Agent definition (self-contained system prompt)
flows/flow.yml                    # Workflow definition (timeout, tool config)
prompts/kassandra-system.md       # Extended reference documentation
scripts/run-k6-test.sh            # Test execution helper (prevents run_command hanging)
.gitlab/duo/agent-config.yml      # Runner setup (k6, app dependencies)
.gitlab-ci.yml                    # CI pipeline (validation, test execution)

demos/
  calliope-books/                 # Node.js bookshop API
    AGENTS.md                     # SLOs, auth, endpoints
    app.js                        # Express app
  midas-bank/                     # Python banking API
    AGENTS.md                     # SLOs, auth, endpoints
    app.py                        # FastAPI app

k6/kassandra/                     # Generated test scripts (committed by agent)

simulator/                        # Local testing harness
  run.py                          # Agentic loop (Anthropic API)
  tools.py                        # Local tool implementations
```

## Architecture decisions

- **Single `run_command` execution**: App startup + k6 + cleanup all run in one shell invocation via `scripts/run-k6-test.sh`. This prevents the Duo Workflow `run_command` tool from hanging on orphan child processes.
- **Self-contained agent.yml**: All instructions are inline in the agent definition — no file reads needed at session start, saving ~30s of LLM processing time.
- **Per-endpoint scenarios**: Each changed endpoint gets its own k6 scenario with dedicated thresholds, giving granular pass/fail per endpoint rather than aggregate metrics.
- **Commit-then-execute**: Tests are committed to the branch before execution, so even if the session times out, the generated script is preserved as an artifact.

## Local development

```bash
# Run Calliope Books
cd demos/calliope-books && npm install && node app.js

# Run Midas Bank
cd demos/midas-bank && pip install -r requirements.txt && uvicorn app:app --port 8000

# Run k6 test via helper script
bash scripts/run-k6-test.sh k6/kassandra/mr-16-book-search.js calliope

# Run the local simulator
KASSANDRA_PROJECT=calliope-books ANTHROPIC_API_KEY=... uv run python -m simulator
```

## License

MIT
