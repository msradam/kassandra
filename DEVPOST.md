# Devpost Submission — Kassandra

> Copy-paste into each Devpost field. Markdown is supported.

---

## Title

Kassandra — AI Performance Testing Agent for GitLab MRs

## Tagline

Drop an AGENTS.md in any repo, @mention on a merge request, get a full k6 performance report with Mermaid charts. No CI config, no manual test writing.

---

## Inspiration

Performance testing gets skipped. Everyone knows it matters, but when the deadline's Thursday and the feature isn't done yet, nobody's writing load tests. And when they do, the results are raw k6 stdout buried in CI logs — numbers that require real expertise to interpret.

We wanted to close that gap entirely. An agent that reads the MR diff, understands what endpoints changed, generates a proper k6 test, runs it, and posts a visual report right in the MR. The developer doesn't write a single test or configure any CI pipeline.

The name is from Greek mythology — Kassandra had the gift of prophecy but was cursed so no one would believe her. Our Kassandra sees performance problems before production does, and posts the proof where you can't ignore it.

## What it does

Comment `@ai-kassandra-performance-test-gitlab-ai-hackathon` on any merge request. Kassandra:

1. Reads the MR diff to find new or changed API endpoints
2. Uses a novel OpenAPI GraphRAG module to extract only the relevant API schemas — not the whole spec, just what matters for the changed endpoints (96% context reduction)
3. Generates a k6 load test with open-model executors, per-endpoint SLO thresholds, and deep response validation
4. Commits the test script to the MR branch so it's visible in code review
5. Starts the application, runs the test, shuts everything down
6. Posts a performance report as an MR comment — Mermaid latency charts, threshold pass/fail tables, regression detection against baselines, per-endpoint breakdowns

No CI YAML changes. No per-project agent code. Just an `AGENTS.md` config file defining your SLOs and auth.

### It actually catches bugs

On MR !39, Kassandra tested a new search suggestions endpoint on our Calliope Books demo. Every single request returned a 404. The agent diagnosed the root cause: an Express.js route ordering issue where `/api/books/:id` shadowed `/api/books/suggestions`. It recommended the exact fix. That's the whole point — catching problems before production, autonomously.

## How we built it

**Platform:** GitLab Duo Workflow with `read_file`, `run_command`, `create_file_with_contents`, `create_commit`, and `create_merge_request_note` tools.

**Three key engineering decisions:**

1. **OpenAPI GraphRAG** — We built a deterministic knowledge graph using NetworkX that parses OpenAPI `$ref` structures into a directed graph. When an MR changes an endpoint, BFS traversal (depth 2) collects only the relevant schemas. On the Midas Bank spec, this reduces context from 18,777 characters to 799 — the LLM gets exactly what it needs without wasting tokens on unrelated schemas. We couldn't find prior art combining OpenAPI graph structure with retrieval-augmented generation, so this appears to be novel.

2. **Deterministic report generation** — Early experiments showed the LLM producing inconsistent report formatting. We moved report generation entirely to a Python script (`generate-report.py`) that converts k6 JSON output into Markdown with Mermaid `xychart-beta` bar charts and pie charts. The format is guaranteed. The agent extracts and posts the report verbatim, then optionally appends its own analysis.

3. **Single-invocation execution** — The Duo Workflow `run_command` tool hangs if a child process is left running. So we wrote `run-k6-test.sh` — a single bash script that handles app startup, health check, k6 execution, report generation, and cleanup. One process, clean exit.

**Demo applications:** Three self-contained apps covering different stacks — Python/FastAPI (banking), JavaScript/Express (bookshop), TypeScript/Hono (food delivery). Each has intentional performance patterns (N+1 queries, aggregation, rate limiting) for Kassandra to detect. All use embedded databases or in-memory stores, zero external dependencies.

## Challenges we ran into

**Duo Workflow context limits.** Long prompts cause the agent to enter tool-routing loops — it keeps calling the same tool repeatedly without making progress. We learned to keep the flow prompt under 20 lines and put the detailed k6 generation rules in `agent.yml`. GraphRAG helps too — sending 800 chars of relevant context instead of 19K of full spec keeps the agent focused.

**Process lifecycle on the runner.** Duo Workflow's `run_command` blocks until the process exits. Starting the app server in one command and k6 in another leaves the server running forever. Everything had to happen in a single script with a trap handler for cleanup.

**Report consistency.** We went through several iterations where the agent would "improve" the report formatting on its own. Mermaid syntax is sensitive — one wrong indent and the chart breaks. Moving to deterministic generation with delimiter-based extraction (`=== KASSANDRA REPORT START/END ===`) solved it completely.

**Polyglot routing.** Getting the agent to test the right application (not just the first demo it finds) required explicit diff-path routing. The root `AGENTS.md` maps file paths to demo-specific configs: changes under `demos/midas-bank/` → load Midas Bank's SLOs and execution command.

## Accomplishments we're proud of

- **Caught a real bug autonomously** (MR !39) — 100% failure rate detected, root cause correctly diagnosed, exact fix recommended
- **Clean runs across three stacks** — Python/FastAPI, Node.js/Express, TypeScript/Hono, all with the same agent and flow config
- **96% context reduction via GraphRAG** — novel approach to giving LLMs only the API context they need
- **Zero-config onboarding** — drop an `AGENTS.md`, @mention Kassandra, done
- **57 unit tests** for the GraphRAG module, running in under 0.1 seconds

## What we learned

- LLM agents need guardrails on output format. "Generate a nice report" doesn't work reliably. Deterministic pipelines do.
- Context quality matters more than context quantity. GraphRAG's 96% reduction isn't about saving tokens — it's about giving the model exactly the right information so it generates accurate tests.
- Short prompts outperform detailed ones in workflow agents. The model routes tools better with less instruction.
- The Duo Workflow platform is surprisingly capable once you work around its constraints. Single-tool execution, no persistent state, limited context — but the abstractions (agent + flow + tools) let you build real automation.

## What's next for Kassandra

- **Multi-protocol support** — gRPC and GraphQL endpoint detection and test generation
- **Baseline profiles on main** — automatically run performance tests on merge to build regression baselines
- **Custom SLO alerting** — integrate with GitLab issues to auto-create tickets when performance degrades
- **Community adoption** — publish the `AGENTS.md` convention so other projects can onboard without forking Kassandra

## Built with

- GitLab Duo Workflow
- Python + NetworkX (GraphRAG)
- k6 (load testing)
- FastAPI (Python demo)
- Express (Node.js demo)
- Hono (TypeScript demo)
- Mermaid (chart rendering in GitLab)

---

> **Tracks:** Grand Prize, Most Technically Impressive, Most Impactful, GitLab & Anthropic
