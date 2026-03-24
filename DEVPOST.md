# Kassandra: AI Performance Testing Agent

> Performance prophecy for every merge request. Kassandra turns code diffs into load tests, executes them, and catches regressions before production does.

## Summary
**Kassandra is a Duo Workflow agent that auto-generates [Grafana k6](https://k6.io/) load tests from GitLab merge request diffs, executes them against the live application, and reports real runtime results.** [k6](https://k6.io/) is Grafana's open-source load testing engine ([30k+ GitHub stars](https://github.com/grafana/k6)), a compiled Go binary that runs JavaScript test scripts at high concurrency. Mention Kassandra on an MR and it handles the rest: reads the diff, retrieves relevant API schemas via OpenAPI GraphRAG, generates a load test, starts the app, runs k6, and posts a performance report with actual latency numbers, Mermaid charts, and regression detection. No tests to write. No pipelines to configure. One config file per project.

## Why performance testing matters

Some bugs only appear under load. A SQLite endpoint that passes every unit test can fail 60% of requests when concurrent users hit it, because thread-safety constraints only surface under real concurrency. **Unit tests verify logic. Load tests verify behavior under production conditions.** They catch different classes of bugs.

The cost of skipping load testing is well-documented. Amazon found that every [100ms of latency costs 1% in sales](https://www.gigaspaces.com/blog/amazon-found-every-100ms-of-latency-cost-them-1-in-sales/). Unplanned downtime now averages [$14,056 per minute](https://www.erwoodgroup.com/blog/the-true-costs-of-downtime-in-2025-a-deep-dive-by-business-size-and-industry/), rising to $23,750 for large enterprises. Siemens found that unscheduled downtime [saps 11% of annual revenues](https://www.ismworld.org/supply-management-news-and-reports/news-publications/inside-supply-management-magazine/blog/2024/2024-08/the-monthly-metric-unscheduled-downtime/) from the world's 500 biggest companies, totaling <u>$1.4 trillion per year</u>.

Companies that do load test see the difference. [fuboTV uses Grafana k6](https://grafana.com/success/k6-fubotv/) to catch performance regressions before production during high-traffic sporting events. [Olo processes millions of restaurant orders per day](https://grafana.com/success/k6-olo/) and integrated k6 into their CI/CD pipeline so every release is verified under load before deployment. The pattern is the same: **teams that test under load find bugs before users do. Teams that don't, don't.**

But performance testing doesn't scale with development velocity. Teams ship endpoints faster than they can test them. Someone still has to write and maintain the load test scripts. Most teams don't. [Grafana k6](https://k6.io/) supports [shift-left testing](https://grafana.com/docs/k6/latest/testing-guides/test-types/) in CI/CD pipelines. [Schemathesis](https://schemathesis.io/) does schema-based fuzzing. [Dredd](https://dredd.org/) does contract validation. k6 Cloud handles execution. None of them read a diff, generate a targeted load test, run it, and post the results back to the MR. **To my knowledge, no existing tool closes this loop.**

This is where an LLM fits. Generating a correct k6 script from a code diff requires understanding endpoint semantics, choosing appropriate request bodies, writing validation logic for response schemas, and deciding what a reasonable SLO looks like for each endpoint type. That's a language understanding and code generation problem. Traditional tools can fuzz or validate, but they can't read a diff and produce a complete runnable load test.

## Inspiration

Last year I [ported Grafana k6 to IBM z/OS mainframes](https://medium.com/theropod/go-ing-native-porting-grafana-k6-to-z-os-with-go-f7f73267c1c), compiling it natively so it could run 24/7 as both the control and managed node on the same machine. That project convinced me k6 is the right engine for load testing: cloud native, scriptable, runs anywhere. Kassandra takes k6 to its logical extreme: an AI agent writes the test from the merge request diff.

The name comes from Greek mythology. Kassandra had the gift of prophecy but was cursed so no one would believe her. This Kassandra sees your performance problems before production does, and posts the proof where you can't ignore it.

## What it does

**Kassandra is the full loop: diff to test to execution to verdict.** It generates a k6 load test, deploys the application, runs concurrent virtual users against it, and reports what actually happened under load. Real latency numbers. Real pass/fail thresholds. Real bugs caught. <u>Kassandra includes static risk analysis, but it doesn't stop there — it generates and executes real k6 load tests against a running server under concurrent load, then reports what actually happened.</u>

On [MR !69](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/69), every API call returned the correct response. The endpoint worked perfectly in serial. Under load, **the endpoint failed 60.6% of requests**. Kassandra diagnosed the root cause autonomously: SQLite thread-safety under FastAPI's thread pool. On [MR !39](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/39), it caught an Express.js route ordering bug. **100% failure rate**, root cause diagnosed, fix recommended. <u>No human prompted it to look for either issue.</u>

Comment `@ai-kassandra-performance-test-gitlab-ai-hackathon` on any GitLab merge request. Kassandra:

1. **Reads the MR diff** to identify new or changed API endpoints
2. **Retrieves relevant schemas** via OpenAPI GraphRAG, pre-resolving `$ref` chains so the model sees fields and types directly, not pointers to chase (~95% token reduction, [A/B verified](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/blob/main/scripts/graphrag-proof.py))
3. **Scans the diff for risks**: N+1 query loops, unbounded SELECTs, `fetchall()` loading all rows, missing pagination
4. **Generates a k6 load test** with [open-model executors](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/open-vs-closed/) and per-endpoint SLO thresholds, then validates responses against the OpenAPI spec: status codes, content types, body fields, schema structure
5. **Commits the test** to the MR branch (fully auditable in code review)
6. **Runs the test**: starts the app, executes k6, shuts everything down
7. **Posts the report** as an MR comment: [Mermaid](https://mermaid.js.org/) latency bar charts and pie charts, threshold pass/fail tables, per-endpoint breakdowns, timing phase analysis, regression detection. The report is self-contained — a developer reading the MR comment immediately sees what's broken, why, and how to fix it, without needing to know anything about Kassandra.

No CI YAML changes. No per-project agent code. One [`AGENTS.md`](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/blob/main/AGENTS.md) config per project.

### Results: 24+ autonomous k6 runs across three apps

Kassandra ran **24+ end-to-end test cycles** across 50+ merge requests during iterative development, consistently generating valid k6 scripts, executing them, and posting reports. The table below highlights five runs that showcase cross-stack coverage, autonomous bug detection, and deep validation.

| MR | App | Requests | VUs | req/s | p95 | Thresholds | Outcome |
|----|-----|----------|-----|-------|-----|------------|---------|
| [!39](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/39) | Calliope Books (Node/Express) | 576 | 55 | 22.9 | 1.5ms | 1/3 pass | **Route ordering bug: 100% failure** |
| [!41](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/41) | Hestia Eats (TypeScript/Hono) | 728 | 75 | 29.1 | 1.1ms | 8/8 pass | Clean |
| [!69](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/69) | Midas Bank (Python/FastAPI) | 2,828 | 60 | 113.1 | 47.0ms | 3/5 pass | **SQLite thread-safety: 60.6% failure** |
| [!74](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/74) | Midas Bank (Python/FastAPI) | 2,830 | 60 | 112.9 | 3.6ms | 8/9 pass | Memory exhaustion risk (`fetchall`) |
| [!75](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/75) | Calliope Books (Node/Express) | 306 | 60 | 25.5 | 5.4ms | 9/11 pass | Clean, 4,000+ validation checks |

**Aggregate across all runs: ~25,000 requests, up to 75 concurrent virtual users within a single run, peak 113 req/s.** Every run is a real k6 execution: the agent deployed the application, spawned concurrent virtual users that sent live HTTP requests, measured latency percentiles under real concurrency, validated response schemas, and posted results back to the MR. These are not static analysis results or mocked responses. k6 hit a running server with parallel load.

![Kassandra Performance Report: threshold pass/fail table and pre-test risk analysis](https://d112y698adiu2z.cloudfront.net/photos/production/software_photos/004/489/853/datas/original.png)

![Mermaid.js latency bar charts and timing breakdown generated from k6 JSON output](https://d112y698adiu2z.cloudfront.net/photos/production/software_photos/004/489/854/datas/original.png)

The Duo Workflow runner is a lightweight container, so these runs are scoped as pre-merge validation, not production-scale load simulations. That's by design. The value at the MR stage is catching threshold violations, validating response schemas, and surfacing anti-patterns early, targeted at the code that just changed. The architecture is runner-agnostic: the agent logic (diff → GraphRAG → k6 script → execute → report) doesn't depend on the container. A runner with Docker Compose or a staging environment would handle full-stack applications with external databases. The `AGENTS.md` config already abstracts the startup command. Fully automated.

Five additional open MRs ([!76](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/76)–[!80](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/80)) across all three demo apps are available for judges to trigger Kassandra on live.

## How I built it

**Platform:** [GitLab Duo Workflow](https://docs.gitlab.com/ee/development/duo_workflow/) with `get_merge_request`, `list_merge_request_diffs`, `read_file`, `run_command`, `create_file_with_contents`, `create_commit`, and `create_merge_request_note`. The Duo Workflow sandbox runs Anthropic models by default.

### OpenAPI GraphRAG

Kassandra's k6 scripts run unsupervised against a live server. A wrong field name in a validation check means a misleading test failure. Dumping a full OpenAPI spec into the prompt forces the model to chase [`$ref` pointers](https://swagger.io/docs/specification/v3_0/using-ref/) at inference time while simultaneously writing a k6 script. GraphRAG pre-resolves those `$ref` chains into an explicit typed tree: every field pre-associated with its parent schema and endpoint. The model gets only the schemas reachable from the changed endpoints, with no pointer chasing required.

The result: <u>zero hallucinated endpoints and ~95% fewer input tokens</u> across all [A/B test scenarios](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/blob/main/scripts/graphrag-proof.py) ([results](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/blob/main/scripts/graphrag-proof-output.txt)). Implemented as a zero-dependency custom [`DiGraph`](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/blob/main/graphrag/digraph.py) (114 lines, standard library only). 57 unit tests. For the full graph construction pipeline (node/edge types, BFS depth rationale, diff parsing, novelty analysis), see [ARCHITECTURE.md § OpenAPI GraphRAG](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/blob/main/ARCHITECTURE.md#openapi-graphrag).

Kassandra currently requires an [OpenAPI](https://www.openapis.org/) spec. OpenAPI is the [industry standard](https://www.openapis.org/membership/members) for REST API description, backed by the Linux Foundation and adopted by AWS, Google, Microsoft, Stripe, and thousands of others. Most modern frameworks ([FastAPI](https://fastapi.tiangolo.com/), [NestJS](https://docs.nestjs.com/openapi/introduction), [Spring Boot](https://springdoc.org/)) auto-generate specs from code. Projects that don't maintain a discoverable, machine-readable API contract are missing out on the entire ecosystem of tooling built around it, such as contract testing, client generation, and documentation. GraphQL and gRPC introspection support are planned as future extensions, since both protocols expose schema structure that maps naturally to the same graph-based retrieval approach.

Sample output for a single endpoint:

```
$ echo '+@app.post("/api/transactions/transfer")' | uv run python -m graphrag --spec demos/midas-bank/openapi.json --diff-stdin

## GraphRAG Traversal

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
    │  ├─ .from_account_id: integer|null
    │  ├─ .to_account_id: integer|null
    │  ├─ .amount: number
    │  ├─ .type: string
    │  ├─ .description: string|null
    │  ├─ .created_at: string|null
    ├─ RETURNS → HTTPValidationError (schema)
    │  ├─ .detail: array<ValidationError>
    │  └─ REFERENCES → ValidationError
    │     ├─ .loc: array
    │     ├─ .msg: string
    │     ├─ .type: string
    ├─ HAS_PARAM → authorization (header)

Retrieved: 4 schemas, 1 params, auth=yes
```

### Key design decisions

**Open-model executors only.** [Closed-model executors](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/open-vs-closed/) reduce load when the server slows down, hiding the regressions you're testing for. Kassandra exclusively generates open-model executors that maintain consistent throughput.

**Deterministic reporting.** The LLM produced broken [Mermaid](https://mermaid.js.org/) charts 20% of the time. Report generation is now a [deterministic Python script](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/blob/main/scripts/generate-report.py): k6 JSON to Markdown with color-themed bar and pie charts. The shell script outputs the report, and the agent posts it as the MR note. The LLM reasons. Python charts. k6 executes.

**Single-invocation execution.** Duo Workflow's `run_command` blocks until exit. [`run-k6-test.sh`](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/blob/main/scripts/run-k6-test.sh) handles the full lifecycle in one process: app startup, health check, risk analysis, GraphRAG, k6, report generation, cleanup. See [ARCHITECTURE.md](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/blob/main/ARCHITECTURE.md) for the full design rationale on executor selection, report pipeline, baseline regression detection, and prompt design.

### Demo applications

Three sample applications spanning latency-sensitive industries (banking, retail, food delivery), each with injected performance faults for Kassandra to detect:

| App | Stack | Endpoints |
|-----|-------|-----------|
| Midas Bank | Python / [FastAPI](https://fastapi.tiangolo.com/) / SQLite | 11 |
| Calliope Books | JavaScript / [Express](https://expressjs.com/) / [sql.js](https://sql.js.org/) | 17 |
| Hestia Eats | TypeScript / [Hono](https://hono.dev/) / in-memory | 19 |

Each app uses production frameworks and real database layers (SQLite, sql.js, in-memory stores), with authentication, pagination, and 11–19 endpoints per app. All have an [`AGENTS.md`](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/blob/main/AGENTS.md) config and an `openapi.json` spec. **Same agent, three stacks, zero code changes.** Only the per-project config differs. The polyglot setup is deliberate: it demonstrates that Kassandra generalizes across entirely different stacks, not endpoints within a single app.

## Challenges I ran into

**Duo Workflow context limits.** Long prompts cause the agent to enter tool-routing loops. Early iterations with verbose prompts looped indefinitely. The fix was structuring the prompt as a strict numbered checklist with inline k6 generation rules, and keeping dynamic context (the OpenAPI spec) minimal via GraphRAG.

**Process lifecycle on the runner.** `run_command` blocks until exit, so starting the app and k6 in separate calls leaves the server hung. A single shell script with a [trap handler](https://www.gnu.org/software/bash/manual/html_node/Bourne-Shell-Builtins.html#index-trap) solved it.

**Polyglot routing.** The agent initially tested whichever demo app it found first. Diff-path routing fixed this: the root [`AGENTS.md`](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/blob/main/AGENTS.md) maps file paths in the MR diff to the correct project config.

## Accomplishments I'm proud of

- **Two autonomous bug catches**: SQLite thread-safety under load ([MR !69](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/69)) and Express route ordering ([MR !39](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/39)). Root causes diagnosed, fixes recommended, no human intervention.
- **OpenAPI GraphRAG**: a novel approach to structured API context for LLMs. ~95% token reduction, zero hallucinated endpoints, [A/B verified](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/blob/main/scripts/graphrag-proof.py). 114 lines, zero dependencies, 57 tests.
- **Polyglot**: Python, JavaScript, TypeScript. Three stacks, same agent, zero code changes.
- **4,000+ validation checks** on a single MR ([!75](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/75)), all generated from the OpenAPI spec.
- **Fully auditable**: every k6 script is committed to the MR branch, visible in code review.

## What I learned

- **Restructured context beats trimmed context.** I expected that reducing token count would be enough. It wasn't. The model hallucinated endpoints from the full spec even when the prompt said "only test changed endpoints." The fix wasn't fewer tokens; it was changing the representation so the ambiguity was gone before the model saw it.
- **Don't let the LLM generate structured syntax.** Mermaid, YAML, k6 thresholds. 80% reliability means 20% broken charts. I wasted time prompt-engineering around this before accepting that deterministic generation from structured data is the only reliable path.
- **Lean on battle-tested tools.** The agent's job is to generate the right script and interpret the results, not reinvent the load testing engine. k6 handles the hard parts.
- **Split LLM and deterministic work explicitly.** The LLM reads diffs and generates k6 scripts. Python charts. k6 executes. Every time I let the LLM cross into deterministic territory (Mermaid syntax, threshold arithmetic), reliability dropped.

For the full technical deep dive: [README.md](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/blob/main/README.md) covers setup, GraphRAG CLI usage, and per-spec token reduction numbers. [ARCHITECTURE.md](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/blob/main/ARCHITECTURE.md) covers graph construction, BFS depth rationale, executor selection, report pipeline, baseline regression detection, prompt design, and the novelty analysis.

## What's next for Kassandra

- **Reliable test commits**: the agent occasionally skips the `create_commit` step for the generated k6 script. The script is always visible in the Duo Workflow agent session log, but committing it to the MR branch makes it reviewable in the diff. Actively working on prompt and flow changes to make this consistent.
- **Multi-protocol support**: gRPC and GraphQL endpoint detection, schema traversal, and test generation. GraphQL's [introspection schema](https://graphql.org/learn/introspection/) is natively graph-structured (types reference types, fields have arguments with types), making it a natural fit for the same BFS retrieval approach without needing `$ref` resolution
- **Baseline profiles on main**: auto-run on merge to build regression baselines
- **SLO alerting**: auto-create GitLab issues when performance degrades across runs
- **Community adoption**: publish the `AGENTS.md` convention so any project can onboard

---

Icon: "fortune teller" by Eucalyp from [the Noun Project](https://thenounproject.com/icon/fortune-teller-4395882/) (CC BY 3.0)
