# Devpost Submission: Kassandra

> Copy-paste into each Devpost field.

---

## Title

Kassandra: AI Performance Testing Agent for GitLab MRs

## Tagline

Performance prophecy for every merge request.

---

## Inspiration

I've been thinking about performance testing for a while. Last year I [ported Grafana k6 to IBM z/OS mainframes](https://medium.com/theropod/go-ing-native-porting-grafana-k6-to-z-os-with-go-f7f73267c1c), compiling it natively so it could run 24/7 as both the control and managed node on the same machine. That project convinced me k6 is the right engine for load testing: [23k+ GitHub stars](https://github.com/grafana/k6), cloud native, scriptable, compiled Go binary you can drop anywhere. The problem is what comes before k6 runs. Someone still has to write and maintain the scripts. Most teams don't. The result: latency regressions ship to production.

The business case for catching regressions early is well-established. Amazon found that every [100ms of latency costs 1% in sales](https://www.gigaspaces.com/blog/amazon-found-every-100ms-of-latency-cost-them-1-in-sales/). Google found that a [500ms delay reduces traffic by 20%](https://www.thinkwithgoogle.com/marketing-strategies/app-and-mobile/mobile-page-speed-new-industry-benchmarks/). Downtime costs the top 2,000 companies [$400 billion per year](https://www.cockroachlabs.com/blog/the-state-of-resilience-2025-reveals-the-true-cost-of-downtime/) collectively, and vulnerabilities caught in CI cost [6.8x less to remediate](https://blog.jetbrains.com/teamcity/2026/01/the-roi-of-dev-experience/) than those found in production. These numbers motivate the problem space.

k6 already supports [shift-left testing](https://grafana.com/docs/k6/latest/testing-guides/test-types/) in CI/CD pipelines. Kassandra takes that to its logical extreme: the test doesn't just run in CI, an AI agent writes it from the merge request diff. To my knowledge, no existing tool does this. [Schemathesis](https://schemathesis.io/) does schema-based fuzzing. [Dredd](https://dredd.org/) does contract validation. k6 Cloud handles execution. None of them read a diff, generate a targeted load test, run it, and post the results back to the MR.

This is where an LLM fits. Generating a correct k6 script from a code diff requires understanding endpoint semantics, choosing appropriate request bodies, writing validation logic for response schemas, and deciding what a reasonable SLO looks like for each endpoint type. That's a language understanding and code generation problem. Traditional tools can fuzz or validate, but they can't read a diff and produce a complete runnable load test. Kassandra is a proof of concept that closes this loop.

The name comes from Greek mythology. Kassandra had the gift of prophecy but was cursed so no one would believe her. This Kassandra sees your performance problems before production does, and posts the proof where you can't ignore it.

## What it does

Comment `@ai-kassandra-performance-test-gitlab-ai-hackathon` on any GitLab merge request. Kassandra:

1. **Reads the MR diff** to identify new or changed API endpoints
2. **Retrieves relevant schemas** via OpenAPI GraphRAG, reducing input tokens by ~95% ([verified via A/B test against the Anthropic API](scripts/graphrag-proof.py))
3. **Scans the diff for risks**: N+1 query loops, unbounded SELECTs, `fetchall()` loading all rows, missing pagination
4. **Generates a k6 load test** with [open-model executors](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/open-vs-closed/) and per-endpoint SLO thresholds, then validates responses against the OpenAPI spec: status codes, content types, body fields, schema structure
5. **Commits the test** to the MR branch (fully auditable in code review)
6. **Runs the test**: starts the app, executes k6, shuts everything down
7. **Posts the report** as an MR comment: [Mermaid](https://mermaid.js.org/) latency bar charts and pie charts, threshold pass/fail tables, per-endpoint breakdowns, timing phase analysis, regression detection

No CI YAML changes. No per-project agent code. One [`AGENTS.md`](AGENTS.md) config per project.

### It catches real bugs

The demo apps are sample applications built for this hackathon with intentional performance anti-patterns (N+1 queries, unbounded SELECTs, route ordering bugs). On [MR !39](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/39), Kassandra tested a new search suggestions endpoint on the Calliope Books app (Node.js/Express). 576 requests. 100% failure rate. The agent diagnosed the root cause in its report: Express.js [route ordering](https://expressjs.com/en/guide/routing.html). `/api/books/:id` was declared before `/api/books/suggestions`, so Express matched "suggestions" as an `:id` parameter and returned 404. Kassandra recommended the exact fix. The route ordering bug was intentional in the demo app, but Kassandra found it autonomously. No human prompted it to look for routing bugs or intervened at any point.

### Results across six runs

| MR | App | Requests | Thresholds | Outcome |
|----|-----|----------|------------|---------|
| [!36](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/36) | Midas Bank (Python/FastAPI) | 74 | 2/2 pass | Clean |
| [!37](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/37) | Midas Bank (Python/FastAPI) | 863 | 8/8 pass | Clean |
| [!39](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/39) | Calliope Books (Node/Express) | 576 | 1/3 pass | **Route ordering bug diagnosed autonomously** |
| [!41](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/41) | Hestia Eats (TypeScript/Hono) | 728 | 8/8 pass | Clean |
| [!74](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/74) | Midas Bank (Python/FastAPI) | 2,830 | 8/9 pass | Memory exhaustion risk flagged (`fetchall`) |
| [!75](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/75) | Calliope Books (Node/Express) | 306 | 9/11 pass | Clean, 4,000+ validation checks generated |

Five additional open MRs ([!76](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/76)–[!80](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/80)) across all three demo apps are available for judges to trigger Kassandra against live.

## How I built it

**Platform:** [GitLab Duo Workflow](https://docs.gitlab.com/ee/development/duo_workflow/) with `read_file`, `run_command`, `create_file_with_contents`, `create_commit`, and `create_merge_request_note`. The Duo Workflow sandbox runs [Anthropic models by default](https://docs.gitlab.com/ee/development/duo_workflow/).

### OpenAPI GraphRAG

The most interesting technical problem I solved. OpenAPI specs encode schema relationships through [`$ref` string pointers](https://swagger.io/docs/specification/v3_0/using-ref/). When you dump a full spec into an LLM prompt, the model has to do graph traversal at inference time: find each `$ref`, locate the schema elsewhere in the JSON, read its fields, notice nested `$ref`s, follow those too. All while simultaneously trying to write a k6 script. That's asking the model to do two different jobs at once.

GraphRAG pre-resolves the `$ref` chains before the LLM sees anything. It parses the spec into a directed graph where nodes represent endpoints, schemas, properties, and parameters, and edges encode typed relationships: `ACCEPTS`, `RETURNS`, `HAS_PROPERTY`, `REFERENCES`, `REQUIRES_AUTH`, `HAS_PARAM`. When an endpoint changes, [BFS](https://en.wikipedia.org/wiki/Breadth-first_search) traversal at depth 2 collects only the schemas reachable from that endpoint and presents them as a self-contained tree. Every field is already associated with its parent schema and endpoint. No pointer chasing required.

Kassandra's k6 scripts run unsupervised against a live server. In interactive tools (copilots, API explorers), a human catches hallucinated field names. Here, a wrong field name in a validation check means a misleading test failure. `$ref` resolution gives two things: ~95% fewer input tokens (faster, cheaper) and a guarantee that every field the model sees actually belongs to the endpoint being tested.

The implementation is a zero-dependency custom [`DiGraph`](graphrag/digraph.py) (114 lines, no external imports beyond the Python standard library). I initially tried using NetworkX on the Duo Workflow runner but hit dependency installation issues, so I wrote a minimal graph that does exactly what's needed. The token reduction is a side effect of the structural approach, but a significant one:

| Spec | Nodes | Edges | Full spec tokens | GraphRAG tokens | Reduction |
|------|-------|-------|-----------------|-----------------|-----------|
| Midas Bank | 104 | 107 | 6,403 | 347 | **94.6%** |
| Calliope Books | 107 | 106 | 6,407 | 303 | **95.3%** |
| Hestia Eats | 164 | 180 | 8,967 | 450 | **95.0%** |

Across all three A/B test scenarios, GraphRAG produced identical schema field coverage and zero hallucinated endpoints compared to full-spec prompting. Verified via [A/B test against the Anthropic API](scripts/graphrag-proof.py) using Claude Sonnet ([results](scripts/graphrag-proof-output.txt)). 57 unit tests, ~0.1s runtime.

I could not find prior work combining OpenAPI `$ref` graph structure with retrieval-augmented generation for LLM context injection. Embedding-based RAG ([Qdrant](https://qdrant.tech/), [Pinecone](https://www.pinecone.io/), FAISS) would lose the structural relationships between schemas entirely. The `$ref` graph topology is the information that matters, and embeddings flatten it. [Schemathesis](https://schemathesis.io/) resolves `$ref`s into flat structures. [Microsoft's GraphRAG](https://arxiv.org/abs/2404.16130) targets document summarization, not structured API schemas. No embeddings, no vector database, no LLM calls during retrieval.

### Why open-model executors

k6 supports [open-model and closed-model](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/open-vs-closed/) executor families. Closed-model executors like `ramping-vus` tie request rate to server response time. When the server slows down, they send fewer requests. That hides the regression you're trying to catch. Open-model executors (`constant-arrival-rate`, `ramping-arrival-rate`) maintain consistent throughput regardless of response time. Kassandra exclusively generates open-model executors.

### Deterministic reporting

Early experiments had the LLM producing inconsistent [Mermaid](https://mermaid.js.org/) syntax. One wrong indent breaks a chart. I moved report generation to [`generate-report.py`](scripts/generate-report.py): k6 JSON to Markdown with [`xychart-beta`](https://mermaid.js.org/syntax/xyChart.html) bar charts and pie charts with [color theming](https://mermaid.js.org/config/theming.html). The output is deterministic. The agent extracts it via delimiters (`=== KASSANDRA REPORT START/END ===`), then appends its own analysis: risk findings, performance interpretation, recommendations. The LLM does what it's good at (reasoning). The Python script does what it's good at (charting).

### Single-invocation execution

The Duo Workflow [`run_command`](https://docs.gitlab.com/ee/development/duo_workflow/duo_workflow_executor.html) blocks until the process exits. Starting the app in one call and k6 in another leaves the server running forever. [`run-k6-test.sh`](scripts/run-k6-test.sh) handles the full lifecycle in one process: branch checkout, app startup, health check, risk analysis, GraphRAG retrieval, k6 validation, test execution, report generation, cleanup.

### Demo applications

Three sample applications built for this hackathon, each with intentional performance anti-patterns for Kassandra to detect:

| App | Stack | Endpoints |
|-----|-------|-----------|
| Midas Bank | Python / [FastAPI](https://fastapi.tiangolo.com/) / SQLite | 11 |
| Calliope Books | JavaScript / [Express](https://expressjs.com/) / [sql.js](https://sql.js.org/) | 18 |
| Hestia Eats | TypeScript / [Hono](https://hono.dev/) / in-memory | 19 |

All use embedded databases or in-memory stores. Zero external dependencies. Each has an [`AGENTS.md`](AGENTS.md) config and an `openapi.json` spec. Same agent, three stacks, zero code changes. Only the per-project config differs. The polyglot setup is deliberate: it demonstrates that Kassandra generalizes across stacks without agent code changes, not just across endpoints within one app.

## Challenges I ran into

**Duo Workflow context limits.** Long prompts cause the agent to enter tool-routing loops. The fix: keep the [flow prompt](flows/flow.yml) under 25 lines, move k6 generation rules to [`agent.yml`](agents/agent.yml), and use GraphRAG to keep spec context minimal. Below ~25 lines the agent stays focused. Above ~60 lines it loops.

**Process lifecycle on the runner.** `run_command` blocks until exit. Two separate calls (one for the app, one for k6) leave the server hung. A single shell script with a [trap handler](https://www.gnu.org/software/bash/manual/html_node/Bourne-Shell-Builtins.html#index-trap) solved it. I lost two days to this before finding the pattern.

**Polyglot routing.** The agent tested the first demo app it found, regardless of which app the MR changed. Diff-path routing fixed this: the root [`AGENTS.md`](AGENTS.md) maps file paths in the MR diff to the correct demo config.

**Report consistency.** Mermaid syntax is fragile. The LLM produced broken charts 20% of the time. Delimiter-based extraction with a [deterministic Python generator](scripts/generate-report.py) solved it completely. The LLM never writes Mermaid.

**Optimizing Anthropic model usage.** The Duo Workflow sandbox runs Anthropic models by default. Without GraphRAG, every test generation call included 6,400+ tokens of OpenAPI spec. With GraphRAG, the same call uses ~350 tokens. Across the A/B test scenarios, this produced zero hallucinated endpoints and identical schema coverage. Lower cost and better output from the same model.

## Accomplishments I'm proud of

- **Caught a bug autonomously** ([MR !39](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/39)): 100% failure rate on a demo app's intentional route ordering bug, root cause diagnosed, exact fix recommended. No human intervention.
- **OpenAPI GraphRAG** that pre-resolves `$ref` pointer chains into explicit typed trees for autonomous LLM consumption (~95% token reduction, [verified against the Anthropic API](scripts/graphrag-proof.py), [results](scripts/graphrag-proof-output.txt)). 57 unit tests. Zero hallucinated endpoints across all A/B test scenarios.
- **Polyglot**: Python, JavaScript, TypeScript. Three stacks, zero agent code changes.
- **4,000+ validation checks** on a single MR ([!75](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/75)): status codes, content types, response body fields, schema structure. All generated from the OpenAPI spec via GraphRAG.
- **Zero-dependency GraphRAG**: custom [`DiGraph`](graphrag/digraph.py) (114 lines). No imports beyond the standard library.
- **Fully auditable**: every k6 script is committed to the MR branch, visible in code review.

## What I learned

- **Restructured context beats trimmed context.** With the full OpenAPI spec, the model generated tests for endpoints that weren't changed. Not because there was too much context, but because the flat JSON with `$ref` string pointers made it ambiguous which schemas belonged to which endpoints. GraphRAG changed two things at once: the volume (95% fewer tokens) and the representation (implicit `$ref` pointers resolved into an explicit tree where every field is pre-associated with its endpoint). The model stopped testing unrelated endpoints because the ambiguity was gone.
- **Don't let the LLM generate structured syntax.** Mermaid, YAML, k6 thresholds. I tried. 80% reliability means 20% broken charts. Deterministic generation from structured data works every time.
- **Open-model executors are non-negotiable.** [Closed-model executors](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/open-vs-closed/) reduce load when the server slows down, hiding the regressions you're testing for.
- **Lean on battle-tested tools.** k6 handles the hard parts. The agent's job is to generate the right script and interpret the results, not reinvent the engine.
- **Know where the LLM adds value and where it doesn't.** The LLM is good at reading a diff, understanding endpoint semantics, and generating a k6 script with the right request bodies and validation checks. It's bad at producing consistent Mermaid syntax and reliable threshold arithmetic. Kassandra splits the work: the LLM generates and reasons, deterministic Python handles charting and reporting, k6 handles load execution. Each tool does what it's good at.

## What's next for Kassandra

- **Multi-protocol support**: gRPC and GraphQL endpoint detection, schema traversal, and test generation
- **Baseline profiles on main**: auto-run on merge to build regression baselines
- **SLO alerting**: auto-create GitLab issues when performance degrades across runs
- **Community adoption**: publish the `AGENTS.md` convention so any project can onboard
