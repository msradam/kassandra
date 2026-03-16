# Devpost Submission — Kassandra

> Copy-paste into each Devpost field. Markdown is supported.

---

## Title

Kassandra — AI Performance Testing Agent for GitLab MRs

## Tagline

Catches performance regressions before production — generates k6 tests from MR diffs, executes them, and posts Mermaid-charted reports.

---

## Inspiration

Performance testing is the first thing cut when deadlines get tight. Writing load tests is tedious, maintaining them is worse, and interpreting raw k6 output in CI logs requires expertise most teams don't have. We wanted an agent that does the entire loop — from reading a code diff to posting a clear, visual performance report — so developers can catch regressions without writing a single test.

The name comes from Greek mythology: Kassandra was gifted with prophecy but cursed so no one would believe her. This Kassandra sees your performance problems before production does — and posts the proof directly in your MR.

## What it does

When you `@mention` Kassandra on any GitLab merge request, it:

1. **Reads the MR diff** to identify new or changed API endpoints
2. **Retrieves API context** via a novel OpenAPI GraphRAG module — only the schemas relevant to changed endpoints, not the entire spec
3. **Generates a k6 load test** with open-model executors, per-endpoint thresholds, response validation, and authentication flows
4. **Commits the test** to the MR branch (it becomes part of the code review)
5. **Executes the test** — app startup, health check, k6 run, cleanup — all in one process
6. **Posts a rich performance report** as an MR comment with Mermaid latency charts, threshold tables, collapsible per-endpoint details, and AI analysis

No CI YAML changes. No per-project agent code. Just drop an `AGENTS.md` config file in any repo and mention Kassandra.

## How we built it

**Platform:** GitLab Duo Workflow — the agent runs as a Duo Workflow with `read_file`, `run_command`, `create_file_with_contents`, `create_commit`, and `create_merge_request_note` tools.

**Key components:**

- **OpenAPI GraphRAG** (Python, NetworkX): Parses OpenAPI `$ref` structures into a directed graph, then uses BFS traversal to extract only the schemas relevant to changed endpoints. This achieves **96% context reduction** (799 chars vs 18,777 for full spec) — the LLM gets exactly what it needs, nothing more.

- **Deterministic report generation** (Python): k6 JSON output is converted to Markdown with Mermaid `xychart-beta` bar charts and pie charts. The report format is guaranteed — the LLM extracts and posts it, never generates it freehand.

- **Single-invocation execution** (Bash): App startup + k6 + cleanup all run in one `run_command` call via a helper script. This prevents the Duo Workflow runtime from hanging on orphan child processes.

- **AGENTS.md convention**: Each project defines its SLOs, auth config, and execution command in a single file. Kassandra reads it and follows it — truly project-agnostic.

**Demo apps:** Two self-contained demos (Python/FastAPI banking API + Node.js/Express bookshop) with intentional performance patterns — aggregation queries, rate limiting, deposit caps, N+1 queries.

## Challenges we ran into

- **Duo Workflow context threshold**: Long prompts cause the agent to enter infinite tool-routing loops. We discovered the hard way that flow prompt + AGENTS.md + openapi.json must stay under a threshold. Solution: slim 20-line flow prompt, ~48-line AGENTS.md, and GraphRAG to minimize spec context.

- **Orphan process hanging**: Running app startup and k6 as separate `run_command` calls leaves the app process running, which the Duo Workflow runtime interprets as a hung command. Solution: single bash script that manages the full lifecycle.

- **Report quality**: Early runs produced inconsistent report formatting. Solution: deterministic `generate-report.py` pipeline with delimiter-based extraction — the agent posts the report verbatim, then may append its own analysis.

## Accomplishments that we're proud of

- **Caught a real bug on first run** (MR !39): Kassandra detected a 100% failure rate on a new Calliope Books endpoint, correctly diagnosed an Express.js route ordering bug (`/api/books/suggestions` shadowed by `/api/books/:id`), and recommended the exact fix — all autonomously. This is the real value: catching issues before production.
- **Clean runs across Python/FastAPI** (MRs !36, !37, !38): 2,841 requests across 3 Midas Bank features, all thresholds passing, zero self-correction commits.
- **Novel OpenAPI GraphRAG** — no prior art combines OpenAPI graph structure + graph-based retrieval + LLM context injection. 96% context reduction means the agent gets exactly the right schemas without wasting tokens on irrelevant spec content.
- **Project-agnostic design** — tested across Python/FastAPI and Node.js/Express with no agent code changes. Drop an AGENTS.md and go.
- **Truly autonomous workflow** — from `@mention` to posted report with zero human intervention. The agent reads the diff, reads the config, generates the test, commits it, executes it, and posts the results.

## What we learned

- LLM agents need **guardrails on output format** — deterministic report generation beats hoping the model formats things consistently.
- **Context is everything** — GraphRAG's 96% reduction isn't just about cost savings; it's about giving the LLM exactly the right information to generate accurate tests.
- Duo Workflow's **single-tool execution model** requires careful orchestration — you can't assume background processes or multi-step shell sessions.
- Short, focused prompts outperform long, detailed ones in workflow agents — the model routes tools better with less instruction.

## What's next for Kassandra

- **Regression detection**: Compare results across MR runs to flag performance changes over time
- **Multi-protocol support**: gRPC and GraphQL endpoint detection and test generation
- **Baseline profiles**: Auto-generate baseline performance profiles on merge to main
- **GitLab CI integration**: Optional CI pipeline stage for scheduled performance testing alongside on-demand @mention triggers

## Built with

- GitLab Duo Workflow (Anthropic-powered agent platform)
- Python
- NetworkX (graph algorithms)
- k6 (load testing)
- FastAPI (Python demo)
- Node.js / Express (Node demo)
- Mermaid (chart rendering)
- SQLite / sql.js (embedded databases)

---

> **Tracks:** Grand Prize, Most Technically Impressive, Most Impactful, Easiest to Use, GitLab & Anthropic
