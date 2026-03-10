# Kassandra

Automated performance testing agent for GitLab merge requests. Kassandra analyzes code changes, generates [k6](https://k6.io) load test scripts, executes them against review environments, and posts performance reports back to the MR.

Built on the [GitLab Duo Agent Platform](https://docs.gitlab.com/ee/development/duo_workflow/).

## What it does

When triggered on a merge request, Kassandra:

1. **Reads the MR diff** and classifies changed API endpoints (REST CRUD, batch, auth, read-heavy, write-heavy)
2. **Generates k6 scripts** with appropriate executors, thresholds, and load profiles based on endpoint type
3. **Executes tests** — smoke test first, then full load test — against the review environment
4. **Posts a performance report** as an MR note with latency percentiles, error rates, throughput, and pass/fail status

## Project structure

```
agents/agent.yml              # Agent definition (GitLab Duo)
flows/flow.yml                # Flow definition (GitLab Duo)
prompts/kassandra-system.md   # Full system prompt
AGENTS.md                     # Project SLOs and conventions

simulator/                    # Local testing harness
  run.py                      # Agentic loop (OpenAI-compatible or Anthropic)
  evaluate.py                 # Script quality evaluator
  tools.py                    # Local tool implementations
  config.py                   # Configuration

samples/                      # Test fixtures
  diffs/                      # Sample MR diffs
  mr-contexts/                # Sample MR metadata
  expected/                   # Gold-standard k6 scripts

tests/k6/                     # k6 test scripts
  baseline-api.js             # Baseline performance test
  helpers/auth.js             # Auth helper
```

## Local simulator

The simulator replicates the GitLab Duo agentic loop locally for development and testing.

```bash
uv sync

# With a local OpenAI-compatible model server
uv run python -m simulator.run --sample 01-add-batch-endpoint

# With Anthropic API
export ANTHROPIC_API_KEY=sk-...
uv run python -m simulator.run --sample 01-add-batch-endpoint --anthropic

# Dry run (generates scripts without executing k6)
uv run python -m simulator.run --sample 01-add-batch-endpoint --dry-run
```

## Evaluator

Score generated k6 scripts against gold-standard expected outputs:

```bash
uv run python -m simulator.evaluate tests/k6/kassandra/mr-42-test.js samples/expected/01-batch-endpoint.js

# Check all expected scripts
uv run python -m simulator.evaluate --check-all
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `KASSANDRA_USE_ANTHROPIC` | `0` | Use Anthropic API (`1`) or local model (`0`) |
| `KASSANDRA_LOCAL_URL` | `http://localhost:8080/v1` | Local model server URL |
| `KASSANDRA_LOCAL_MODEL` | `default` | Local model name |
| `KASSANDRA_ANTHROPIC_MODEL` | `claude-sonnet-4-5-20250514` | Anthropic model |
| `KASSANDRA_REVIEW_URL` | `https://quickpizza.grafana.com` | Review environment URL |
