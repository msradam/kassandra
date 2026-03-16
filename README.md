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

1. Parses the OpenAPI `$ref` structure into a directed graph (endpoints -> schemas -> properties -> refs)
2. Extracts changed endpoints from the diff
3. Traverses the graph (BFS, depth 2) to collect only relevant schemas
4. Outputs a visual traversal tree showing exactly which nodes were visited

**Result:** 96% context reduction (799 chars vs 18,777 for a full spec). This is novel — [no prior art](https://scholar.google.com) combines OpenAPI graph structure + graph-based retrieval + LLM context injection.

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
2. **Reads `AGENTS.md`** for project-specific SLOs, auth config, and the execution command
3. **Reads `openapi.json`** for API schemas relevant to changed endpoints
4. **Generates a k6 script** with open-model executors (constant/ramping-arrival-rate), per-endpoint thresholds, deep response validation
5. **Commits the test** to the MR branch
6. **Executes via `run_command`** — app startup, health check, k6 run, cleanup all in one process
7. **Posts a performance report** with Mermaid latency charts, threshold tables, collapsible per-endpoint results, and AI analysis

### Example MR report output

The report renders natively in GitLab with Mermaid charts:

- Threshold pass/fail table with per-endpoint and per-scenario results
- Latency percentile table (avg, med, p95, p99, max)
- Mermaid xychart-beta bar chart for latency distribution
- Mermaid pie chart for check pass/fail ratio
- Collapsible per-endpoint check details
- AI-generated analysis with recommendations

See real examples: [MR !37](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/37) | [MR !38](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/38)

## Demo applications

Two self-contained demo apps showcase Kassandra across different stacks:

| App | Stack | Port | Endpoints | Performance patterns |
|-----|-------|------|-----------|---------------------|
| **Midas Bank** | Python / FastAPI / SQLite | 8000 | 8 | Aggregation queries, rate limiting, deposit caps |
| **Calliope Books** | Node.js / Express / sql.js | 3000 | 7 | N+1 queries, unoptimized LIKE scans, artificial delays |

Both use embedded SQLite (zero external dependencies) and include intentional performance patterns for Kassandra to detect.

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
scripts/
  run-k6-test.sh              # Test runner (app startup + k6 + cleanup)
  generate-report.py          # k6 JSON -> Markdown with Mermaid charts

graphrag/                     # OpenAPI GraphRAG module
  builder.py                  # OpenAPI spec -> NetworkX directed graph
  retriever.py                # Subgraph retrieval + diff parsing
  cli.py                      # CLI entry point for runner
  __main__.py                 # python -m graphrag support

demos/
  midas-bank/                 # Python banking API
    AGENTS.md                 # SLOs, auth, execution command
    app.py                    # FastAPI app
    openapi.json              # Auto-generated spec
  calliope-books/             # Node.js bookshop API
    AGENTS.md                 # SLOs, auth, execution command
    app.js                    # Express app
    openapi.json              # Hand-written spec

simulator/                    # Local testing harness (Anthropic API)
tests/                        # 57 tests for GraphRAG module
```

## Architecture decisions

- **Single `run_command` execution**: App startup + k6 + cleanup all run in one shell invocation via `run-k6-test.sh`. This prevents the Duo Workflow `run_command` tool from hanging on orphan child processes.
- **Deterministic report generation**: `generate-report.py` converts k6 JSON output to Markdown with Mermaid charts. The report format is guaranteed — the LLM only extracts and posts it.
- **Open-model executors only**: Kassandra uses `constant-arrival-rate` and `ramping-arrival-rate` (never `ramping-vus`), which provide accurate latency measurements even when the server is slow.
- **Slim prompt design**: The Duo Workflow agent has a context threshold — long prompts cause tool-routing loops. The flow prompt is kept to ~20 lines; detailed k6 rules live in `AGENTS.md` where the agent reads them naturally.

## Testing

```bash
# Run all tests (57 tests, ~0.1s)
uv run pytest tests/ -v

# Test GraphRAG CLI
echo '+@app.post("/api/transactions/transfer")' | uv run python -m graphrag --spec demos/midas-bank/openapi.json --diff-stdin
```

## Local development

```bash
# Run Midas Bank
cd demos/midas-bank && uv pip install -r requirements.txt && uv run uvicorn app:app --port 8000

# Run Calliope Books
cd demos/calliope-books && npm install && node app.js

# Run k6 test via helper script
bash scripts/run-k6-test.sh k6/kassandra/mr-38-deposit-limit.js midas

# Run the local simulator
KASSANDRA_PROJECT=midas-bank ANTHROPIC_API_KEY=... uv run python -m simulator
```

## Results

Across multiple MR runs on GitLab:

| MR | Feature | Requests | Duration | Thresholds | Self-corrections |
|----|---------|----------|----------|------------|-----------------|
| !36 | Transfer rate limiting | 1,650 | 60s | 10/10 pass | 0 |
| !37 | Spending summary | 863 | 60s | 8/8 pass | 0 |
| !38 | Deposit limits | 328 | 30s | 8/8 pass | 0 |

Zero self-correction commits (no "fix: remove external import" patches). The agent gets it right on the first try.

## License

MIT
