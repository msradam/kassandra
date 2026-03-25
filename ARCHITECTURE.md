# Architecture

Technical deep dive into Kassandra's design, a proof of concept for AI-driven performance testing on GitLab merge requests. For usage and results, see [README.md](README.md).

## System overview

```
GitLab MR
  │
  @mention trigger
  │
  ▼
Duo Workflow Agent (Anthropic model)
  │
  1. get_merge_request ──── MR metadata (branch, IID)
  │
  2. list_merge_request_diffs ──── code diff
  │
  3. read_file ──── AGENTS.md routing table
  │                 └── demos/{app}/AGENTS.md (SLOs, auth, exec command)
  │
  4. run_command ──── GraphRAG: openapi.json → DiGraph → BFS → relevant schemas
  │
  5. create_file_with_contents ──── k6 script + GraphRAG output
  │
  6. create_commit ──── test committed to MR branch
  │
  7. run_command ──── run-k6-test.sh (app startup → k6 → report → cleanup)
  │
  8. create_merge_request_note ──── Mermaid report posted to MR
```

The agent runs on the [GitLab Duo Workflow Platform](https://docs.gitlab.com/ee/development/duo_workflow/), which provides these tools: `get_merge_request`, `list_merge_request_diffs`, `read_file`, `run_command`, `create_file_with_contents`, `create_commit`, and `create_merge_request_note`. The sandbox runs Anthropic models by default. Everything below works within these constraints.

## OpenAPI GraphRAG

### The problem with full-spec prompting

When the full OpenAPI spec is included in the LLM context, the model can generate tests for endpoints that exist in the spec but weren't changed in the MR. GraphRAG pre-resolves `$ref` chains into an explicit typed tree, eliminating hallucinated endpoints and cutting ~95% of input tokens while keeping identical schema field coverage (see [A/B test results](scripts/graphrag-proof-output.txt)). Fewer tokens means faster iteration, lower cost, and less room for the model to pick up unrelated endpoints.

### Graph construction

[`builder.py`](graphrag/builder.py) parses an OpenAPI 3.x spec into a directed graph. The spec's `$ref` structure is a natural graph: endpoints reference schemas, schemas reference other schemas via `$ref`, schemas have properties with types.

**Node types:**
- `endpoint`: one per HTTP method + path combination (e.g., `POST /api/transactions/transfer`)
- `schema`: one per named schema in `components/schemas`
- `property`: one per field on a schema (stores name, type, format, required flag)
- `parameter`: one per query/path/header parameter
- `security`: one per security scheme

**Edge types:**
- `RETURNS`: endpoint → schema (response body)
- `ACCEPTS`: endpoint → schema (request body)
- `HAS_PROPERTY`: schema → property
- `REFERENCES`: property → schema (via `$ref`)
- `HAS_PARAM`: endpoint → parameter
- `REQUIRES_AUTH`: endpoint → security scheme

### The DiGraph implementation

[`digraph.py`](graphrag/digraph.py) is a 114-line directed graph with no external dependencies. It supports `add_node`, `add_edge`, `successors`, `edges`, `subgraph`, and `number_of_nodes/edges`. No imports beyond the standard library.

I initially tried using NetworkX on the Duo Workflow runner but hit dependency installation issues. The runner environment doesn't guarantee third-party package availability. A minimal custom graph that does exactly what's needed (BFS traversal and subgraph extraction) turned out to be more reliable and imports in milliseconds.

### BFS retrieval

[`retriever.py`](graphrag/retriever.py) takes a list of changed endpoints (parsed from the MR diff) and runs breadth-first search at depth 2 from each endpoint node. Depth 2 captures the endpoint's direct schemas and one level of `$ref` references.

```
POST /api/transactions/transfer          (depth 0: endpoint)
  ├── ACCEPTS → TransferRequest          (depth 1: schema)
  │     ├── .from_account_id: integer    (depth 2: property)
  │     ├── .to_account_id: integer      (depth 2: property)
  │     └── .amount: number              (depth 2: property)
  ├── RETURNS → TransactionOut           (depth 1: schema)
  │     ├── .id: integer                 (depth 2: property)
  │     ├── .amount: number              (depth 2: property)
  │     └── .type: string               (depth 2: property)
  └── HAS_PARAM → authorization          (depth 1: parameter)
```
(Simplified; full output includes all schema properties and validation error types. See README for complete CLI output.)

Depth 2 was chosen empirically. Depth 1 misses property-level detail (the LLM can't validate response fields without knowing their types). Depth 3 pulls in too many transitive schemas and re-introduces the noise problem.

### Diff parsing

The retriever extracts endpoint paths from the **actual code diff** (the output of `list_merge_request_diffs`), not from OpenAPI spec changes. It matches added lines (starting with `+`) that contain route declaration patterns (`@app.get`, `@app.post`, `router.get`, `app.get`, etc.) across Python, JavaScript, and TypeScript conventions.

The matched paths are fuzzy-matched against the graph's endpoint nodes. Kassandra detects what the developer actually changed in their source code, then looks up the corresponding schemas from the OpenAPI spec via GraphRAG.

### Measured results

| Spec | Nodes | Edges | Full spec (tokens) | GraphRAG (tokens) | Reduction |
|------|-------|-------|-------------------|-------------------|-----------|
| Midas Bank | 104 | 107 | 6,403 | 347 | 94.6% |
| Calliope Books | 88 | 88 | 5,585 | 228 | 95.9% |
| Hestia Eats | 164 | 180 | 8,967 | 450 | 95.0% |

Verified via [A/B test against the Anthropic API](scripts/graphrag-proof.py) using Claude Sonnet ([results](scripts/graphrag-proof-output.txt)). Both conditions (full spec vs. GraphRAG) were tested on the same endpoints with the same system prompt. Across all three test scenarios, GraphRAG produced identical schema field coverage and zero hallucinated endpoints. [Cross-validated with Qwen 2.5 Coder 7B](scripts/graphrag-proof-qwen.py) (local, via Ollama, [results](scripts/graphrag-proof-qwen-output.txt)): the 7B model achieved zero hallucinations and GraphRAG outperformed full-spec prompting on the largest spec (15/17 vs 10/17 on Hestia Eats), with 33-68% faster inference.

### Novelty

I could not find prior work combining OpenAPI `$ref` graph structure with retrieval-augmented generation for LLM context injection. The [GraphRAG literature](https://arxiv.org/abs/2501.13958) focuses on document summarization and knowledge base construction ([Microsoft, 2024](https://arxiv.org/abs/2404.16130)). Existing OpenAPI testing tools ([Schemathesis](https://schemathesis.io/), [Dredd](https://dredd.org/), [Prism](https://stoplight.io/open-source/prism)) resolve `$ref`s into flat structures or do linear traversal. Embedding-based RAG ([Qdrant](https://qdrant.tech/), [Pinecone](https://www.pinecone.io/)) loses the structural relationships between schemas.

This approach preserves `$ref` chains. No embeddings. No vector database. No LLM calls during retrieval. Deterministic output.

## Executor selection

k6 supports [open-model and closed-model](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/open-vs-closed/) executor families.

**Closed-model** (`ramping-vus`): each virtual user waits for the response before sending the next request. When the server slows down, request rate drops. This masks latency regressions under load.

**Open-model** (`constant-arrival-rate`, `ramping-arrival-rate`): request rate is maintained regardless of server response time. If the server can't keep up, requests queue. Latency regressions become visible.

Kassandra exclusively generates open-model executors. The agent prompt in [`agent.yml`](agents/agent.yml) enforces this rule.

## Report generation

### Report pipeline

The agent generates k6 scripts that include a `handleSummary()` function writing JSON output to `k6/kassandra/results/`. After k6 completes, [`generate-report.py`](scripts/generate-report.py) converts this JSON into Markdown with Mermaid charts and writes it to a report file. The shell script pipes this file to stdout (via fd redirection), which is the only output the agent sees. The agent posts it verbatim via `create_merge_request_note`. The LLM never generates Mermaid syntax.

### Chart generation

[`generate-report.py`](scripts/generate-report.py) produces:
- **Latency percentile chart** (`xychart-beta`): min, avg, med, p90, p95, max as bar chart
- **p95 by endpoint** (`xychart-beta`): one bar per endpoint
- **Timing breakdown** (`pie`): blocked, connecting, sending, TTFB, receiving
- **Check results** (`pie`): passed vs. failed validation checks

All charts use [Mermaid color theming](https://mermaid.js.org/config/theming.html) for consistent styling across GitLab's renderer.

### Deep validation

The generated k6 scripts validate:
- HTTP status codes (200, 201, 404 as appropriate)
- Content-Type headers
- Response body field presence (from GraphRAG schema properties)
- Field types (string, number, array, object)
- Schema structure (nested objects match OpenAPI `$ref` structure)

On [MR !75](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/75), a single run produced 4,000+ individual validation checks across 5 endpoints.

## Pre-test risk analysis

[`analyze-risk.py`](scripts/analyze-risk.py) scans the MR diff before k6 runs. Pattern matching detects:

| Pattern | Severity | Example |
|---------|----------|---------|
| N+1 query loops | High | `for item in items: db.query(...)` |
| Unbounded SELECT | Medium | `SELECT * FROM ... ` with no LIMIT |
| `fetchall()` in memory | Medium | Loading all rows before processing |
| Synchronous sleep | Low | `time.sleep()` in request handler |
| Missing pagination | Medium | List endpoint with no LIMIT/OFFSET |

Findings are included in the report with severity labels. On [MR !74](https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/74), the risk analysis flagged a `fetchall()` call in the spending trends endpoint that loads all matching transactions into memory.

## Single-invocation execution

### The constraint

Duo Workflow's `run_command` [blocks until exit](https://docs.gitlab.com/ee/development/duo_workflow/duo_workflow_executor.html). If you start the app server in one `run_command` call, the agent hangs forever waiting for it to exit. You can't start the app in one call and k6 in another.

### The solution

[`run-k6-test.sh`](scripts/run-k6-test.sh) runs the full lifecycle in one process:

```
1. Checkout MR branch
2. Install dependencies (pip/npm based on app type)
3. Start app server (background, with PID tracking)
4. Health check loop (retry until /api/health returns 200)
5. Run risk analysis (analyze-risk.py on the diff)
6. Run GraphRAG (python -m graphrag on the OpenAPI spec)
7. Validate k6 script syntax
8. Execute k6 test
9. Generate report (generate-report.py on k6 JSON output)
10. Cleanup (kill app server via trapped PID)
```

A bash `trap` handler ensures cleanup runs even if any step fails. One process, clean exit.

## Diff-based routing

The root [`AGENTS.md`](AGENTS.md) maps MR diff file paths to demo-specific configs:

```
demos/midas-bank/*     → demos/midas-bank/AGENTS.md
demos/calliope-books/* → demos/calliope-books/AGENTS.md
demos/hestia-eats/*    → demos/hestia-eats/AGENTS.md
```

The agent reads the diff, identifies which files changed, and loads the matching config. No repo scanning. No guessing.

## Prompt design

The Duo Workflow agent enters tool-routing loops when prompts are too long or unfocused. The system prompt in [`flow.yml`](flows/flow.yml) is structured in strict numbered steps: read inputs, generate k6 script, commit, execute, report. k6 generation rules (executor types, threshold syntax, validation patterns, `handleSummary` format) are inline in the same prompt, organized by section. GraphRAG keeps spec context under 500 tokens.

The key constraint: the agent must post the `run_command` output verbatim as the MR note. No summarizing, no reformatting. This ensures the deterministic report reaches the MR exactly as generated.

## Baseline regression detection

When a baseline exists from a previous run (stored in `.kassandra/baselines/`), [`generate-report.py`](scripts/generate-report.py) compares current p95 latencies against baselines and flags regressions:
- Within 10%: no flag
- 10-50% slower: warning
- 50%+ slower: regression alert

## Test coverage

57 unit tests across three modules:

| Module | Tests | Coverage |
|--------|-------|----------|
| `test_builder.py` | 21 | Graph construction, node/edge types, property extraction |
| `test_retriever.py` | 17 | BFS traversal, diff parsing, fuzzy matching, edge cases |
| `test_integration.py` | 19 | End-to-end: spec → graph → retrieval → text output |

All tests run in ~0.1 seconds. No external dependencies. No network calls.

```bash
$ uv run pytest tests/ -v
# 57 passed in 0.06s
```
