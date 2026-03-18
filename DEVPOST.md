# Devpost Submission — Kassandra

> Copy-paste into each Devpost field.

---

## Title

Kassandra — AI Performance Testing Agent for GitLab MRs

## Tagline

Reads MR diffs, generates k6 load tests, posts Mermaid-charted performance reports. One @mention, zero CI config.

---

## Inspiration

Performance testing gets skipped. A 2023 Sauce Labs survey found 56% of teams don't performance test before release. Writing k6 scripts is tedious, maintaining them alongside evolving APIs is worse, and interpreting raw k6 stdout in CI logs requires expertise most teams don't have.

The result is predictable: latency regressions ship to production. An N+1 query that adds 200ms per request under load goes unnoticed until customers complain.

I wanted an agent that closes this gap end-to-end — from reading a code diff to posting a visual performance report in the MR. No test authoring, no CI pipeline configuration, no log parsing.

The name comes from Greek mythology. Kassandra had the gift of prophecy but was cursed so no one would believe her warnings. This Kassandra sees your performance problems before production does, and posts the proof where you can't ignore it.

## What it does

Comment `@ai-kassandra-performance-test-gitlab-ai-hackathon` on any GitLab merge request. Kassandra:

1. Reads the MR diff to identify new/changed API endpoints
2. Retrieves relevant API schemas via OpenAPI GraphRAG — 96% context reduction (799 chars vs 18,777 for full spec)
3. Generates a k6 load test with open-model executors, per-endpoint SLO thresholds, deep response validation
4. Commits the test script to the MR branch (visible in code review)
5. Starts the application, runs k6, shuts everything down
6. Posts a performance report as an MR comment — Mermaid latency charts, threshold pass/fail tables, regression detection, per-endpoint breakdowns

No CI YAML changes. No per-project agent code. One `AGENTS.md` config file defines the SLOs, auth, and execution command.

### It catches real bugs

On MR !39, Kassandra tested a new search suggestions endpoint on a Node.js/Express bookshop API. Every request returned 404. The agent identified the root cause in its report: Express.js route ordering — `/api/books/:id` was declared before `/api/books/suggestions`, so Express matched "suggestions" as an `:id` parameter. Kassandra recommended the exact fix. No human intervention.

### Results across runs

| MR | App | Feature | Requests | Thresholds | Outcome |
|----|-----|---------|----------|------------|---------|
| !36 | Midas Bank (Python/FastAPI) | Transfer rate limiting | 1,650 | 10/10 pass | Clean |
| !37 | Midas Bank (Python/FastAPI) | Spending summary | 863 | 8/8 pass | Clean |
| !38 | Midas Bank (Python/FastAPI) | Deposit limits | 328 | 8/8 pass | Clean |
| !39 | Calliope Books (Node/Express) | Search suggestions | 576 | 0/8 fail | Bug caught |
| !41 | Hestia Eats (TypeScript/Hono) | Promotions | — | — | Pending |

Total: 3,417 requests across 4 MRs. 3 clean runs, 1 real bug caught.

## How we built it

**Platform:** GitLab Duo Workflow with `read_file`, `run_command`, `create_file_with_contents`, `create_commit`, and `create_merge_request_note` tools.

### OpenAPI GraphRAG

Feeding the full OpenAPI spec to the LLM wastes context and produces worse tests — the model hallucinates endpoints that exist in the spec but weren't changed. I built a deterministic knowledge graph using NetworkX that parses the spec's `$ref` structure into a directed graph (endpoints → schemas → properties → refs). When an endpoint changes, BFS traversal (depth 2) collects only the reachable schemas.

On the Midas Bank spec (76 nodes, 79 edges), this reduces context from 18,777 characters to 799. The LLM sees exactly the schemas it needs. 57 unit tests, ~0.1s runtime.

### Deterministic report generation

Early experiments had the LLM producing inconsistent Mermaid syntax — one wrong indent breaks a chart. I moved report generation entirely to `generate-report.py`: k6 JSON → Markdown with `xychart-beta` bar charts and pie charts. The format is guaranteed. The agent extracts and posts the report via delimiters (`=== KASSANDRA REPORT START/END ===`), then optionally appends its own analysis.

### Single-invocation execution

The Duo Workflow `run_command` tool blocks until the process exits. Starting the app in one call and k6 in another leaves the server running — the runtime treats it as hung. `run-k6-test.sh` handles the full lifecycle in one process: branch checkout, app startup, health check, k6 validation, test execution, report generation, cleanup.

### Demo applications

Three self-contained apps across three stacks:

| App | Stack | Endpoints | Intentional patterns |
|-----|-------|-----------|---------------------|
| Midas Bank | Python / FastAPI / SQLite | 8 | Aggregation queries, rate limiting, deposit caps |
| Calliope Books | JavaScript / Express / sql.js | 7 | N+1 queries, unoptimized LIKE, route ordering |
| Hestia Eats | TypeScript / Hono / in-memory | 20 | N+1 enrichment, iterative lookups |

All use embedded databases or in-memory stores. Zero external dependencies. Each has an `AGENTS.md` (SLOs, auth, execution command) and an `openapi.json` spec.

## Challenges we ran into

**Duo Workflow context limits.** Long prompts cause the agent to enter tool-routing loops — it calls the same tool repeatedly without making progress. I learned to keep the flow prompt under 20 lines and move detailed k6 rules to `agent.yml`. GraphRAG keeps spec context minimal. The agent stays focused.

**Process lifecycle on the runner.** `run_command` semantics required everything — app startup, health check, k6, report generation, cleanup — to happen in a single process with a trap handler. Two separate `run_command` calls don't work.

**Polyglot routing.** The agent would test the first demo app it found, regardless of which app the MR actually changed. Diff-path routing fixed this: the root `AGENTS.md` maps file paths to the correct demo-specific config.

**Report consistency.** Mermaid syntax is fragile. Delimiter-based extraction (`=== KASSANDRA REPORT START/END ===`) with a Python report generator solved it completely. The LLM never generates Mermaid — it only posts the output.

## Accomplishments we're proud of

- Caught a real bug autonomously (MR !39) — 100% failure rate, root cause diagnosed, exact fix recommended
- 3,417 total requests across 4 MR runs — 3 clean, 1 bug caught
- 96% context reduction via OpenAPI GraphRAG with 57 unit tests
- Works across Python, JavaScript, and TypeScript with zero agent code changes
- Full workflow from @mention to posted report with zero human intervention

## What we learned

- Context quality matters more than context quantity. GraphRAG's 96% reduction isn't about saving tokens — it's about giving the model exactly the right information so it generates accurate tests instead of hallucinating from a 19K spec.
- Specialized small models for structured tasks beat general large models. But within Duo Workflow, you work with what the platform provides — so you design constraints around the model instead. GBNF grammars aren't available; prompt engineering and deterministic pipelines are.
- Short prompts outperform detailed ones in workflow agents. The model routes tools better with less instruction. Every line in the flow prompt that isn't load-bearing is a liability.
- Let the LLM do what LLMs are good at (understanding diffs, generating test logic) and keep everything else deterministic (report formatting, app lifecycle, schema retrieval).

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
