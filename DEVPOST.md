# Devpost Submission — Kassandra

> Copy-paste into each Devpost field.

---

## Title

Kassandra — AI Performance Testing Agent for GitLab MRs

## Tagline

Performance prophecy for every merge request.

---

## Inspiration

AI writes code faster than ever. But who tests whether it performs under load?

Performance testing gets skipped — on every team, in every sprint. Writing k6 scripts takes time, maintaining them alongside evolving APIs is worse, and interpreting raw k6 stdout in CI logs requires expertise most teams don't have. The result: latency regressions ship to production. Amazon found that every [100ms of latency costs 1% in sales](https://www.gigaspaces.com/blog/amazon-found-every-100ms-of-latency-cost-them-1-in-sales/).

This is the AI Paradox in action: AI accelerates code production, which means more endpoints, more features, more performance risk — but the testing that catches regressions stays manual and gets cut first. Kassandra closes this gap end-to-end: from reading a code diff to posting a visual performance report in the MR. No test authoring, no CI pipeline configuration, no log parsing.

The name comes from Greek mythology. Kassandra had the gift of prophecy but was cursed so no one would believe her. This Kassandra sees your performance problems before production does, and posts the proof where you can't ignore it.

## What it does

Comment `@ai-kassandra-performance-test-gitlab-ai-hackathon` on any GitLab merge request. Kassandra:

1. Reads the MR diff to identify new or changed API endpoints
2. Retrieves relevant API schemas via OpenAPI GraphRAG — ~97% context reduction (618 chars vs 24,421 for the full spec)
3. Generates a [k6](https://k6.io/) load test with arrival-rate executors ([constant](https://grafana.com/docs/k6/latest/using-k6/scenarios/executors/constant-arrival-rate/) and [ramping](https://grafana.com/docs/k6/latest/using-k6/scenarios/executors/ramping-arrival-rate/)), per-endpoint SLO thresholds, deep response validation
4. Commits the test script to the MR branch (visible in code review)
5. Starts the application, runs k6, shuts everything down
6. Posts a performance report as an MR comment — [Mermaid](https://mermaid.js.org/) latency charts, threshold pass/fail tables, regression detection, per-endpoint breakdowns

No CI YAML changes. No per-project agent code. One `AGENTS.md` config file defines the SLOs, auth, and execution command.

### It catches real bugs

On [MR !39](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/39), Kassandra tested a new search suggestions endpoint on a Node.js/Express bookshop API. Every request returned 404. The agent identified the root cause in its report: Express.js [route ordering](https://expressjs.com/en/guide/routing.html) — `/api/books/:id` was declared before `/api/books/suggestions`, so Express matched "suggestions" as an `:id` parameter. Kassandra recommended the exact fix. No human intervention.

### Results across runs

| MR | App | Feature | Requests | Thresholds | Outcome |
|----|-----|---------|----------|------------|---------|
| [!36](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/36) | Midas Bank (Python/FastAPI) | Transfer rate limiting | 74 | 2/2 pass | Clean |
| [!37](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/37) | Midas Bank (Python/FastAPI) | Spending summary | 863 | 8/8 pass | Clean |
| [!39](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/39) | Calliope Books (Node/Express) | Search suggestions | 576 | 1/3 pass | Bug caught |
| [!41](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/41) | Hestia Eats (TypeScript/Hono) | Promotions | 728 | 8/8 pass | Clean + GraphRAG visible |

## How I built it

**Platform:** [GitLab Duo Workflow](https://docs.gitlab.com/ee/development/duo_workflow/) with `read_file`, `run_command`, `create_file_with_contents`, `create_commit`, and `create_merge_request_note` tools.

### OpenAPI GraphRAG

Feeding the full OpenAPI spec to the LLM wastes context and produces worse tests — the model references endpoints that exist in the spec but weren't changed. I built a deterministic knowledge graph using [NetworkX](https://networkx.org/) that parses the spec's [`$ref` structure](https://swagger.io/docs/specification/v3_0/using-ref/) into a directed graph (endpoints → schemas → properties → refs). When an endpoint changes, BFS traversal (depth 2) collects only the reachable schemas.

On the Midas Bank spec (104 nodes, 107 edges), this reduces context from 24,421 characters to 618. The LLM sees exactly the schemas it needs. 57 unit tests, ~0.1s runtime.

I couldn't find prior work combining OpenAPI graph structure with retrieval-augmented generation for LLM context injection. Existing RAG approaches for API specs tend to use embedding-based retrieval ([Qdrant](https://qdrant.tech/), [Pinecone](https://www.pinecone.io/)), which loses the structural relationships between schemas. Graph traversal preserves `$ref` chains — if `TransferRequest` references `AccountId`, the traversal follows that edge automatically.

### Deterministic report generation

Early experiments had the LLM producing inconsistent [Mermaid](https://mermaid.js.org/) syntax — one wrong indent breaks a chart. I moved report generation entirely to `generate-report.py`: k6 JSON → Markdown with [`xychart-beta`](https://mermaid.js.org/syntax/xyChart.html) bar charts and pie charts. The format is guaranteed. The agent extracts and posts the report via delimiters (`=== KASSANDRA REPORT START/END ===`), then optionally appends its own analysis.

### Single-invocation execution

The Duo Workflow [`run_command`](https://docs.gitlab.com/ee/development/duo_workflow/duo_workflow_executor.html) tool blocks until the process exits. Starting the app in one call and k6 in another leaves the server running — the runtime treats it as hung. `run-k6-test.sh` handles the full lifecycle in one process: branch checkout, app startup, health check, k6 validation, test execution, report generation, cleanup.

### Demo applications

Three self-contained apps across three stacks:

| App | Stack | Endpoints | Intentional patterns |
|-----|-------|-----------|---------------------|
| Midas Bank | Python / [FastAPI](https://fastapi.tiangolo.com/) / SQLite | 11 | Aggregation queries, rate limiting, deposit caps |
| Calliope Books | JavaScript / [Express](https://expressjs.com/) / [sql.js](https://sql.js.org/) | 17 | N+1 queries, unoptimized LIKE, route ordering |
| Hestia Eats | TypeScript / [Hono](https://hono.dev/) / in-memory | 17 | N+1 enrichment, iterative lookups |

All use embedded databases or in-memory stores. Zero external dependencies. Each has an `AGENTS.md` (SLOs, auth, execution command) and an `openapi.json` spec. The polyglot setup demonstrates that Kassandra works across stacks without agent code changes — only the per-project config differs.

## Challenges I ran into

**Duo Workflow context limits.** Long prompts cause the agent to enter tool-routing loops — it calls the same tool repeatedly without making progress. I learned to keep the flow prompt under 25 lines and move detailed k6 rules to `agent.yml`. GraphRAG keeps spec context minimal. The agent stays focused.

**Process lifecycle on the runner.** `run_command` semantics required everything — app startup, health check, k6, report generation, cleanup — to happen in a single process with a trap handler. Two separate `run_command` calls don't work.

**Polyglot routing.** The agent would test the first demo app it found, regardless of which app the MR actually changed. Diff-path routing fixed this: the root `AGENTS.md` maps file paths to the correct demo-specific config.

**Report consistency.** Mermaid syntax is fragile. Delimiter-based extraction (`=== KASSANDRA REPORT START/END ===`) with a Python report generator solved it completely. The LLM never generates Mermaid — it only posts the output.

## Accomplishments I'm proud of

- Caught a real bug autonomously ([MR !39](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/39)) — 100% failure rate, root cause diagnosed, exact fix recommended
- ~97% context reduction via OpenAPI GraphRAG with 57 unit tests
- Works across Python, JavaScript, and TypeScript with zero agent code changes
- Full workflow from @mention to posted report with zero human intervention

## What I learned

- Smaller context beats bigger context. When I fed the full 24K OpenAPI spec, the model would generate tests for endpoints that weren't even changed. Trimming to 618 chars of relevant schemas fixed that.
- Duo Workflow agents break when prompts get long. I hit a wall around ~60 lines of flow prompt — the agent started looping on the same tool call. Cutting to 20 lines and moving the rules to `agent.yml` fixed it immediately.
- Don't let the LLM generate Mermaid. I tried. It works 80% of the time, which means 20% of reports have broken charts. Deterministic generation from k6 JSON is boring but it works every time.
- C++ matters even in an LLM pipeline. [NetworKit](https://networkit.github.io/) runs graph algorithms significantly faster than pure-Python NetworkX ([Staudt et al., 2016](https://doi.org/10.1017/nws.2016.20)). I used NetworkX here because the specs are small enough, but for production-scale OpenAPI specs this would matter.
- The AI Paradox is real. AI generates more code faster, which means more performance risk. The tooling for catching that risk hasn't kept up. Kassandra is a step toward closing that loop.

## What's next for Kassandra

- **Multi-protocol support**: gRPC and GraphQL endpoint detection and test generation
- **Baseline profiles on main**: Auto-run performance tests on merge to build regression baselines
- **Custom SLO alerting**: Auto-create GitLab issues when performance degrades across runs
- **Community adoption**: Publish the `AGENTS.md` convention so any project can onboard without forking

## Built with

- GitLab Duo Workflow
- Python
- NetworkX
- k6
- FastAPI
- Express
- Hono
- Mermaid

---

> **Tracks:** Grand Prize, Most Technically Impressive, Most Impactful, GitLab & Anthropic
