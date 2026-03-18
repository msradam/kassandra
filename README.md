# Kassandra

Performance testing agent for GitLab merge requests. Reads the MR diff, generates a [k6](https://k6.io) load test, executes it, and posts a Mermaid-charted report as an MR comment. Zero manual test writing, zero CI configuration.

Built on the [GitLab Duo Workflow Platform](https://docs.gitlab.com/ee/development/duo_workflow/) for the [GitLab AI Hackathon 2026](https://gitlab-ai-hackathon.devpost.com/).

> *In Greek mythology, Kassandra had the gift of prophecy but was cursed so no one would believe her. This Kassandra sees your performance regressions before production does — and posts the proof in your MR.*

## The problem

Performance testing gets skipped. A 2023 Sauce Labs survey found 56% of teams don't performance test before release. The reasons are predictable: writing k6 scripts is tedious, maintaining them alongside API changes is worse, and interpreting raw stdout in CI logs requires expertise most teams don't have.

The result: latency regressions ship to production. An N+1 query that adds 200ms per request under load goes unnoticed until customers complain.

## What Kassandra does

Comment `@ai-kassandra-performance-test-gitlab-ai-hackathon` on any MR. The agent:

1. Reads the MR diff to identify new/changed API endpoints
2. Routes to the correct project config via diff file paths
3. Retrieves relevant API schemas via OpenAPI GraphRAG (96% context reduction)
4. Generates a k6 script with open-model executors, per-endpoint SLO thresholds, deep response validation
5. Commits the test to the MR branch
6. Starts the app, runs k6, shuts everything down
7. Posts a performance report with Mermaid charts, threshold tables, regression detection

No CI YAML changes. No per-project agent code. One `AGENTS.md` config file per project.

## OpenAPI GraphRAG

Feeding a full OpenAPI spec to the LLM wastes context and produces worse tests — the model hallucinates endpoints that exist in the spec but weren't changed. Kassandra solves this with a deterministic knowledge graph built from the spec's `$ref` structure using NetworkX.

When an MR changes an endpoint, BFS traversal (depth 2) collects only the schemas reachable from that endpoint. On the Midas Bank spec (76 nodes, 79 edges), this reduces context from 18,777 characters to 799 — a 96% reduction. The LLM sees exactly the schemas it needs to generate accurate tests.

```
$ echo '+@app.post("/api/transactions/transfer")' | python -m graphrag --spec openapi.json --diff-stdin

Graph: 76 nodes, 79 edges
Matched endpoints: 1

  * POST /api/transactions/transfer
    |-- ACCEPTS -> TransferRequest (schema)
    |   |-- .from_account_id: integer
    |   |-- .to_account_id: integer
    |   |-- .amount: number
    |-- RETURNS -> TransactionOut (schema)
    |   |-- .id: integer
    |   |-- .amount: number
    |   |-- .type: string
    |-- HAS_PARAM -> authorization (header)

Retrieved: 4 schemas, 1 params
```

57 unit tests, ~0.1s runtime.

## Results

| MR | App | Feature | Requests | Duration | Thresholds | Outcome |
|----|-----|---------|----------|----------|------------|---------|
| !36 | Midas Bank | Transfer rate limiting | 1,650 | 60s | 10/10 pass | Clean |
| !37 | Midas Bank | Spending summary | 863 | 60s | 8/8 pass | Clean |
| !38 | Midas Bank | Deposit limits | 328 | 30s | 8/8 pass | Clean |
| !39 | Calliope Books | Search suggestions | 576 | 25s | 0/8 fail | **Caught real bug** |
| !41 | Hestia Eats | Promotions system | — | — | — | Pending |

MR !39 is the interesting one. Kassandra ran the test, saw a 100% failure rate on a new `/api/books/suggestions` endpoint, and diagnosed the root cause: Express.js route ordering. The route `/api/books/:id` was declared before `/api/books/suggestions`, so Express matched "suggestions" as an `:id` parameter and returned 404. The agent identified the exact fix in its report. No human intervention.

Total across MRs !36–!39: 3,417 requests, 3 clean runs, 1 real bug caught.

## Demo applications

Three self-contained apps covering different stacks:

| App | Stack | Port | Endpoints | Intentional patterns |
|-----|-------|------|-----------|---------------------|
| Midas Bank | Python / FastAPI / SQLite | 8000 | 8 | Aggregation queries, rate limiting, deposit caps |
| Calliope Books | JavaScript / Express / sql.js | 3000 | 7 | N+1 queries, unoptimized LIKE, route ordering bugs |
| Hestia Eats | TypeScript / Hono / in-memory | 8080 | 20 | N+1 restaurant enrichment, iterative lookups |

All use embedded databases or in-memory stores. Zero external dependencies. Each includes an `AGENTS.md` with project-specific SLOs and auth config, and an `openapi.json` spec.

The polyglot setup exists to demonstrate that Kassandra works across stacks without code changes — only the `AGENTS.md` differs.

## Architecture

### Key decisions

**Single `run_command` execution.** The Duo Workflow `run_command` tool blocks until the process exits. Starting the app server in one call and k6 in another leaves the server running forever — the runtime treats it as a hung command. `run-k6-test.sh` handles the full lifecycle: branch checkout, app startup, health check, k6 run, report generation, cleanup. One process, clean exit.

**Deterministic report generation.** Early runs produced inconsistent Mermaid syntax. One wrong indent breaks a chart. `generate-report.py` converts k6 JSON to Markdown with `xychart-beta` bar charts and pie charts — the format is guaranteed. The agent extracts and posts the report verbatim via delimiters (`=== KASSANDRA REPORT START/END ===`).

**Open-model executors only.** `constant-arrival-rate` and `ramping-arrival-rate` maintain consistent request throughput regardless of server response time. `ramping-vus` (closed model) reduces load when the server slows down, hiding the exact regressions you're trying to catch.

**Diff-based routing.** The root `AGENTS.md` maps MR diff file paths to demo-specific configs. Changes under `demos/midas-bank/` → load Midas Bank SLOs and execution command. The agent doesn't scan the repo or guess which app to test.

**Slim prompt design.** The Duo Workflow agent enters tool-routing loops when the prompt exceeds a context threshold. The flow prompt is ~20 lines. Detailed k6 generation rules live in `agent.yml`. GraphRAG keeps spec context minimal. The agent stays focused.

### Project structure

```
agents/agent.yml              # Agent definition (system prompt + tools)
flows/flow.yml                # Duo Workflow orchestration

graphrag/                     # OpenAPI GraphRAG module
  builder.py                  # OpenAPI spec -> NetworkX directed graph
  retriever.py                # Subgraph retrieval + diff parsing
  cli.py                      # CLI entry point

scripts/
  run-k6-test.sh              # Full test lifecycle (app + k6 + cleanup)
  generate-report.py          # k6 JSON -> Mermaid Markdown report
  analyze-risk.py             # Pre-test code risk analysis from diff

demos/
  midas-bank/                 # Python / FastAPI / SQLite
  calliope-books/             # JavaScript / Express / sql.js
  hestia-eats/                # TypeScript / Hono / in-memory

tests/                        # 57 unit tests for GraphRAG
```

## Running locally

```bash
# Unit tests
uv run pytest tests/ -v

# GraphRAG CLI
echo '+@app.post("/api/transactions/transfer")' | uv run python -m graphrag --spec demos/midas-bank/openapi.json --diff-stdin

# Demo apps
cd demos/midas-bank && uv pip install -r requirements.txt && uv run uvicorn app:app --port 8000
cd demos/calliope-books && npm install && node app.js
cd demos/hestia-eats && npm install && npx tsx app.ts

# Full test in podman (mirrors CI runner: Python 3.12, Node.js 18, k6 v0.56.0)
podman run --rm -v $(pwd):/workspace:Z -w /workspace kassandra-runner-sim \
  bash scripts/run-k6-test.sh k6/kassandra/mr-41-hestia-promotions.js hestia '' ''
```

## License

MIT
