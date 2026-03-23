# Kassandra

Performance testing agent for GitLab merge requests. Mention it on an MR. It reads the diff, generates a [Grafana k6](https://k6.io) load test, executes it, and posts a Mermaid-charted performance report as an MR comment. No test authoring. No CI configuration. One config file per project.

Built on the [GitLab Duo Workflow Platform](https://docs.gitlab.com/ee/development/duo_workflow/) for the [GitLab AI Hackathon 2026](https://gitlab-ai-hackathon.devpost.com/).

> *Kassandra had the gift of prophecy but was cursed so no one would believe her. This Kassandra sees your performance regressions before production does, and posts the proof in your MR.*

## The problem

Performance testing doesn't scale with development velocity. [Grafana k6](https://k6.io/) is best-in-class for load testing ([23k+ GitHub stars](https://github.com/grafana/k6), cloud native, scriptable), but writing and maintaining test scripts compounds the gap. Teams ship endpoints faster than they can test them. Kassandra is a proof of concept for closing this loop with an AI agent.

The result: latency regressions ship to production. An N+1 query that adds 200ms per request under load goes unnoticed until customers complain. Amazon found that every [100ms of latency costs 1% in sales](https://www.gigaspaces.com/blog/amazon-found-every-100ms-of-latency-cost-them-1-in-sales/). Downtime costs Global 2000 companies [$400 billion annually](https://www.splunk.com/en_us/form/the-hidden-costs-of-downtime.html).

To my knowledge, no existing tool auto-generates k6 performance tests from merge request diffs. [Schemathesis](https://schemathesis.io/) does schema fuzzing. [Dredd](https://dredd.org/) does contract validation. k6 Cloud handles execution. None of them close the loop from code change to performance verdict.

## What Kassandra does

Comment `@ai-kassandra-performance-test-gitlab-ai-hackathon` on any MR. The agent:

1. Reads the MR diff to identify new/changed API endpoints
2. Routes to the correct project config via diff file paths
3. Retrieves relevant API schemas via OpenAPI GraphRAG (~95% input token reduction)
4. Scans the diff for performance anti-patterns (N+1 queries, unbounded SELECTs, missing pagination)
5. Generates a k6 script with [open-model executors](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/open-vs-closed/), per-endpoint SLO thresholds, deep response validation
6. Commits the test to the MR branch
7. Starts the app, runs k6, shuts everything down
8. Posts a performance report with Mermaid charts, threshold tables, regression detection

No CI YAML changes. No per-project agent code. One `AGENTS.md` config file per project.

## OpenAPI GraphRAG

Feeding a full OpenAPI spec to the LLM wastes context and produces worse tests. The model hallucinates endpoints that exist in the spec but weren't changed. Kassandra solves this with a deterministic knowledge graph built from the spec's [`$ref` structure](https://swagger.io/docs/specification/v3_0/using-ref/) using a zero-dependency custom `DiGraph` implementation (114 lines).

When an MR changes an endpoint, [BFS traversal](https://en.wikipedia.org/wiki/Breadth-first_search) at depth 2 collects only the schemas reachable from that endpoint.

| Spec | Nodes | Edges | Token reduction |
|------|-------|-------|-----------------|
| Midas Bank | 104 | 107 | **94.6%** (6,403 → 347) |
| Calliope Books | 107 | 106 | **95.3%** (6,407 → 303) |
| Hestia Eats | 164 | 180 | **95.0%** (8,967 → 450) |

Identical schema field coverage. Zero hallucinated endpoints across all A/B test scenarios. [Verified via A/B test against the Anthropic API](scripts/graphrag-proof.py) ([results](scripts/graphrag-proof-output.txt)). 57 unit tests, ~0.1s runtime.

```
$ echo '+@app.post("/api/transactions/transfer")' | uv run python -m graphrag --spec demos/midas-bank/openapi.json --diff-stdin

Graph: 104 nodes, 107 edges
Matched endpoints: 1

  ● POST /api/transactions/transfer
    ├─ ACCEPTS → TransferRequest (schema)
    │  ├─ .from_account_id: integer
    │  ├─ .to_account_id: integer
    │  ├─ .amount: number
    │  ├─ .description: string
    ├─ RETURNS → TransactionOut (schema)
    │  ├─ .id: integer
    │  ├─ .amount: number
    │  ├─ .type: string
    │  ├─ .description: string|null
    │  ├─ .created_at: string|null
    ├─ HAS_PARAM → authorization (header)

Retrieved: 4 schemas, 1 params, auth=yes
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full technical deep dive.

## Results

| MR | App | Requests | Thresholds | Outcome |
|----|-----|----------|------------|---------|
| !36 | Midas Bank | 74 | 2/2 pass | Clean |
| !37 | Midas Bank | 863 | 8/8 pass | Clean |
| !39 | Calliope Books | 576 | 1/3 pass | **Route ordering bug caught** |
| !41 | Hestia Eats | 728 | 8/8 pass | Clean |
| !69 | Midas Bank | 2,828 | 3/5 pass | **SQLite thread-safety bug caught** |
| !74 | Midas Bank | 2,830 | 8/9 pass | Risk: `fetchall()` flagged |
| !75 | Calliope Books | 306 | 9/11 pass | 4,000+ validation checks |

MR !69 caught a SQLite thread-safety bug that passes every unit test but fails under concurrent load. FastAPI runs requests in a thread pool, but the SQLite connection wasn't thread-safe. The endpoint failed 60.6% of requests under load. Kassandra diagnosed the exact error and recommended the fix.

MR !39 caught an Express.js [route ordering](https://expressjs.com/en/guide/routing.html) bug. `/api/books/:id` was declared before `/api/books/suggestions`, so Express matched "suggestions" as an `:id` parameter and returned 404. 100% failure rate. Both bugs were found autonomously.

## Demo applications

Three sample applications built for this hackathon, each with intentional performance anti-patterns:

| App | Stack | Port | Endpoints | Intentional patterns |
|-----|-------|------|-----------|---------------------|
| Midas Bank | Python / FastAPI / SQLite | 8000 | 11 | Aggregation queries, rate limiting, deposit caps |
| Calliope Books | JavaScript / Express / sql.js | 3000 | 18 | N+1 queries, unoptimized LIKE, route ordering bugs |
| Hestia Eats | TypeScript / Hono / in-memory | 8080 | 19 | N+1 restaurant enrichment, iterative lookups |

All use embedded databases or in-memory stores. Zero external dependencies. Each includes an `AGENTS.md` with project-specific SLOs and auth config, and an `openapi.json` spec.

## Architecture

```
@mention on MR
  │
  ▼
Duo Workflow Agent (agent.yml + flow.yml)
  │
  ├── read_file ─── MR diff + AGENTS.md routing
  │
  ├── run_command ── GraphRAG: openapi.json → DiGraph → BFS → relevant schemas
  │
  ├── create_file ── k6 script (open-model executors, SLO thresholds, validation)
  │
  ├── create_commit ── test committed to MR branch
  │
  ├── run_command ── run-k6-test.sh (app startup → k6 → report → cleanup)
  │
  └── create_merge_request_note ── Mermaid report + agent analysis
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for design decisions and technical details.

### Project structure

```
agents/agent.yml              # Agent definition (system prompt + tools)
flows/flow.yml                # Duo Workflow orchestration

graphrag/                     # OpenAPI GraphRAG module (zero external deps)
  digraph.py                  # Custom directed graph (114 lines)
  builder.py                  # OpenAPI spec → directed graph
  retriever.py                # BFS subgraph retrieval + diff parsing
  cli.py                      # CLI entry point

scripts/
  run-k6-test.sh              # Full test lifecycle (app + k6 + cleanup)
  generate-report.py          # k6 JSON → Mermaid Markdown report
  analyze-risk.py             # Pre-test code risk analysis from diff

demos/
  midas-bank/                 # Python / FastAPI / SQLite
  calliope-books/             # JavaScript / Express / sql.js
  hestia-eats/                # TypeScript / Hono / in-memory

tests/                        # 57 unit tests for GraphRAG
```

## Adding Kassandra to your project

One file: `AGENTS.md`. No CI YAML. No SDK. No pipeline changes.

```markdown
# MyApp: Performance Testing Config

## Application
Node.js REST API (Express, PostgreSQL, port 3000)

## Auth
Bearer token: `test-token` (header: `Authorization: Bearer test-token`)

## SLOs
- Default: p95 < 500ms
- Search: p95 < 800ms

## k6 Script Rules
- Include handleSummary() for JSON output to k6/kassandra/results/
- Use constant-arrival-rate or ramping-arrival-rate executors only
- Total wall-clock under 30 seconds

## Execution Command
bash scripts/run-k6-test.sh k6/kassandra/mr-{MR_IID}-{slug}.js myapp "" {source_branch}
```

Add an `openapi.json` spec and Kassandra handles the rest.

## Running locally

```bash
# Unit tests
uv run pytest tests/ -v

# GraphRAG CLI
echo '+@app.post("/api/transactions/transfer")' | uv run python -m graphrag --spec demos/midas-bank/openapi.json --diff-stdin

# Demo apps
cd demos/midas-bank && uv pip install -r requirements.txt && uv run uvicorn app:app --port 8000
cd demos/calliope-books && npm install && node app.js
cd demos/hestia-eats && npm install && node app.js
```

## License

MIT
