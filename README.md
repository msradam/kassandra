# Kassandra

**Automated performance testing agent for GitLab merge requests.** Kassandra analyzes code changes, generates [k6](https://k6.io) load test scripts, executes them, and posts rich performance reports with Mermaid charts — catching regressions before they reach production.

Built on the [GitLab Duo Workflow Platform](https://docs.gitlab.com/ee/development/duo_workflow/) for the [GitLab AI Hackathon 2026](https://gitlab-ai-hackathon.devpost.com/).

> *In Greek mythology, Kassandra was gifted with prophecy but cursed so no one would believe her warnings. This Kassandra sees your performance problems before production does — and posts the proof directly in your MR.*

## What makes this different

| Feature | Traditional CI perf testing | Kassandra |
|---------|---------------------------|-----------|
| **Test creation** | Manual k6 script writing | AI generates tests from MR diff |
| **API awareness** | Developer reads docs | GraphRAG extracts relevant schemas |
| **Reporting** | Raw k6 stdout in CI logs | Mermaid charts + tables in MR comments |
| **Configuration** | Per-project CI YAML | Drop an `AGENTS.md` in any repo |
| **Trigger** | Every push (wasteful) | On-demand `@mention` on MR |

### Novel: OpenAPI GraphRAG

Kassandra includes a **deterministic knowledge graph** built from OpenAPI specs using NetworkX. When an MR changes an endpoint, instead of feeding the entire API spec to the LLM (wasteful, noisy), Kassandra:

1. Parses the OpenAPI `$ref` structure into a directed graph (endpoints → schemas → properties → refs)
2. Extracts changed endpoints from the diff
3. Traverses the graph (BFS, depth 2) to collect only relevant schemas
4. Outputs a visual traversal tree showing exactly which nodes were visited

**Result:** 96% context reduction (799 chars vs 18,777 for a full spec). No prior art combines OpenAPI graph structure with graph-based retrieval for LLM context injection.

```
$ echo '+@app.post("/api/transactions/transfer")' | python -m graphrag --spec openapi.json --diff-stdin

## GraphRAG Traversal

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

## How it works

When triggered by an `@mention` on a merge request, Kassandra:

1. **Analyzes the MR diff** to identify new or changed API endpoints
2. **Routes to the correct project** via diff file paths — each demo has its own `AGENTS.md` with SLOs, auth, and execution config
3. **Retrieves API context** via GraphRAG — only the schemas relevant to changed endpoints, not the entire spec
4. **Generates a k6 script** with open-model executors (constant/ramping-arrival-rate), per-endpoint thresholds, and deep response validation
5. **Commits the test** to the MR branch (it becomes part of the code review)
6. **Executes via `run_command`** — app startup, health check, k6 run, cleanup all in one process
7. **Posts a performance report** with Mermaid latency charts, threshold tables, regression detection, and per-endpoint breakdowns

### Example MR report output

The report renders natively in GitLab with Mermaid charts:

- Threshold pass/fail table with per-endpoint and per-scenario results
- Latency percentile table (avg, med, p95, p99, max)
- Mermaid xychart-beta bar chart for latency distribution
- Mermaid pie chart for check pass/fail ratio
- Regression detection against previous baselines
- Collapsible per-endpoint check details
- Pre-test risk analysis from code diff

See real examples: [MR !37](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/37) | [MR !38](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/38) | [MR !39](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/39)

## Demo applications

Three self-contained demo apps showcase Kassandra across different stacks and languages:

| App | Stack | Port | Endpoints | Performance patterns |
|-----|-------|------|-----------|---------------------|
| **Midas Bank** | Python / FastAPI / SQLite | 8000 | 8 | Aggregation queries, rate limiting, deposit caps |
| **Calliope Books** | Node.js / Express / sql.js | 3000 | 7 | N+1 queries, unoptimized LIKE scans, artificial delays |
| **Hestia Eats** | TypeScript / Hono / in-memory | 8080 | 20 | N+1 restaurant enrichment, iterative lookups, large response payloads |

All use embedded databases or in-memory stores (zero external dependencies) and include intentional performance patterns for Kassandra to detect. The polyglot setup — Python, JavaScript, TypeScript — demonstrates that Kassandra works across any stack with just an `AGENTS.md` config.

## Triggering Kassandra

On any MR in the project, comment:

```
@ai-kassandra-performance-test-gitlab-ai-hackathon
```

Kassandra picks up the project's `AGENTS.md` for configuration — no per-project agent code needed.

## Project structure

```
agents/agent.yml              # Agent definition (system prompt + tools)
flows/flow.yml                # Duo Workflow definition

graphrag/                     # OpenAPI GraphRAG module
  builder.py                  # OpenAPI spec -> NetworkX directed graph
  retriever.py                # Subgraph retrieval + diff parsing
  cli.py                      # CLI entry point for runner

scripts/
  run-k6-test.sh              # Test runner (app startup + k6 + cleanup)
  generate-report.py          # k6 JSON -> Markdown with Mermaid charts
  analyze-risk.py             # Pre-test code risk analysis from diff

demos/
  midas-bank/                 # Python banking API
    AGENTS.md                 # SLOs, auth, execution command
    app.py                    # FastAPI application
    openapi.json              # API spec
  calliope-books/             # Node.js bookshop API
    AGENTS.md                 # SLOs, auth, execution command
    app.js                    # Express application
    openapi.json              # API spec
  hestia-eats/                # TypeScript food delivery API
    AGENTS.md                 # SLOs, auth, execution command
    app.ts                    # Hono application
    openapi.json              # API spec

tests/                        # 57 unit tests for GraphRAG module
```

## Architecture decisions

- **Single `run_command` execution**: App startup + k6 + cleanup all run in one shell invocation via `run-k6-test.sh`. This prevents the Duo Workflow `run_command` tool from hanging on orphan child processes.
- **Deterministic report generation**: `generate-report.py` converts k6 JSON output to Markdown with Mermaid charts. The report format is guaranteed — the LLM only extracts and posts it.
- **Open-model executors only**: Kassandra uses `constant-arrival-rate` and `ramping-arrival-rate` (never `ramping-vus`), which provide accurate latency measurements even when the server is slow.
- **Diff-based routing**: The root `AGENTS.md` maps MR diff file paths to the correct demo-specific config. The agent reads the diff, identifies which app changed, and loads the right SLOs and execution command.
- **Slim prompt design**: The Duo Workflow agent has a context threshold — long prompts cause tool-routing loops. The flow prompt is kept to ~20 lines; detailed k6 rules live in `agent.yml` where the agent reads them naturally.

## Testing

```bash
# Run all tests (57 tests, ~0.1s)
uv run pytest tests/ -v

# Test GraphRAG CLI
echo '+@app.post("/api/transactions/transfer")' | uv run python -m graphrag --spec demos/midas-bank/openapi.json --diff-stdin

# Local podman test (mirrors CI runner environment)
podman run --rm -v $(pwd):/workspace:Z -w /workspace kassandra-runner-sim \
  bash scripts/run-k6-test.sh k6/kassandra/mr-41-hestia-promotions.js hestia '' ''
```

## Local development

```bash
# Run Midas Bank
cd demos/midas-bank && uv pip install -r requirements.txt && uv run uvicorn app:app --port 8000

# Run Calliope Books
cd demos/calliope-books && npm install && node app.js

# Run Hestia Eats
cd demos/hestia-eats && npm install && npx tsx app.ts
```

## Results

Across multiple MR runs on GitLab:

| MR | App | Feature | Requests | Duration | Thresholds | Outcome |
|----|-----|---------|----------|----------|------------|---------|
| !36 | Midas Bank (Python) | Transfer rate limiting | 1,650 | 60s | 10/10 pass | Clean |
| !37 | Midas Bank (Python) | Spending summary | 863 | 60s | 8/8 pass | Clean |
| !38 | Midas Bank (Python) | Deposit limits | 328 | 30s | 8/8 pass | Clean |
| !39 | Calliope Books (Node.js) | Search suggestions | 576 | 25s | 0/8 fail | **Caught real bug** |
| !41 | Hestia Eats (TypeScript) | Promotions system | — | — | — | Pending |

MR !39 demonstrates Kassandra's real value: the agent detected a 100% failure rate on a new endpoint, correctly diagnosed an Express.js route ordering bug (`/api/books/suggestions` shadowed by `/api/books/:id`), and recommended the exact fix — all autonomously.

## License

MIT
