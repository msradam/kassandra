# Kassandra — Demo Playbook

This file guides Claude Code through a live browser demo of Kassandra, an AI performance testing agent for GitLab merge requests.

## Project URLs

- **GitLab Project**: https://gitlab.com/gitlab-ai-hackathon/participants/3286613
- **MR List**: https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests
- **Agent Trigger Handle**: `@ai-kassandra-performance-test-gitlab-ai-hackathon`

## Demo Applications

| App | Stack | Port | Directory |
|-----|-------|------|-----------|
| Calliope Books | JavaScript / Express / sql.js | 3000 | `demos/calliope-books/` |
| Midas Bank | Python / FastAPI / pysqlite3 | 8000 | `demos/midas-bank/` |
| Hestia Eats | TypeScript / Hono / in-memory | 8080 | `demos/hestia-eats/` |

## Running the Demo (Playwright MCP)

### Prerequisites
- The Playwright MCP server must be connected (check with `/mcp`)
- You need a GitLab personal access token configured for `glab`

### Step-by-Step Demo Flow

#### 1. Navigate to the MR
Open the browser to an existing MR, or create a new one:
```
navigate to: https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests/41
```

#### 2. Show the MR Diff
Scroll down to show the code changes — the promotions feature being added to Hestia Eats (TypeScript/Hono). Click the "Changes" tab to show the diff.

#### 3. Trigger Kassandra
Post a comment on the MR to invoke the agent:
- Click the comment box at the bottom of the MR
- Type: `@ai-kassandra-performance-test-gitlab-ai-hackathon`
- Submit the comment

#### 4. Show Agent Session Starting
After posting, Kassandra replies with a "Performance Test has started" message containing a link to the agent session. Click the link to show the Duo Workflow session view.

#### 5. Wait for Results (2-5 minutes)
The agent:
1. Reads the MR diff
2. Routes to the correct demo app via `AGENTS.md`
3. Runs GraphRAG to extract relevant OpenAPI schemas
4. Generates a k6 load test script
5. Commits the test to the MR branch
6. Executes the test (app startup + k6 run + report generation)
7. Posts the performance report as an MR comment

#### 6. Show the Report
Navigate back to the MR to see the Kassandra Performance Report posted as a comment. The report includes:
- Pass/fail verdict with threshold results
- Regression detection (baseline comparison)
- Per-endpoint latency distribution with Mermaid charts
- Timing breakdown (blocked, connecting, TTFB, etc.)
- Deep validation check results per endpoint

### Creating a New Demo MR

To create a fresh MR for a live demo:

```bash
# Pick a demo app and create a feature branch
git checkout main && git pull gitlab main
git checkout -b feature/demo-<app>-<feature>

# Make changes to the demo app (e.g., add a new endpoint)
# Edit demos/<app>/app.ts (or app.js, app.py)
# Update demos/<app>/openapi.json with the new schema

# Commit and push
git add demos/<app>/
git commit -m "feat: add <feature> to <App Name>"
git push gitlab feature/demo-<app>-<feature>

# Create MR via CLI
glab mr create --title "feat: add <feature> to <App Name>" \
  --description "Add <feature> endpoints for Kassandra to performance test."
```

Then trigger the agent by commenting `@ai-kassandra-performance-test-gitlab-ai-hackathon` on the MR.

### Local Testing with Podman Runner Sim

Before pushing to GitLab, validate locally:

```bash
podman run --rm -v $(pwd):/workspace:Z -w /workspace kassandra-runner-sim \
  bash scripts/run-k6-test.sh k6/kassandra/mr-<IID>-<slug>.js <app-type> '' ''
```

Where `<app-type>` is one of: `calliope`, `midas`, `hestia`.

## Key Architecture

- **Agent config**: `agents/agent.yml` — system prompt with k6 generation rules
- **Flow config**: `flows/flow.yml` — Duo Workflow orchestration
- **Routing**: Root `AGENTS.md` maps MR diff paths to demo-specific configs
- **GraphRAG**: `graphrag/` module extracts relevant OpenAPI schemas from diff context
- **Report generator**: `scripts/kassandra_report.py` produces Markdown + HTML reports
- **Run script**: `scripts/run-k6-test.sh` handles app startup, k6 execution, cleanup

## Existing Demo MRs

| MR | App | Feature | Status |
|----|-----|---------|--------|
| !22 | Calliope Books | Search endpoint | Merged |
| !36 | Calliope Books | GraphRAG validation | Merged |
| !40 | Midas Bank | Spending summary | Open |
| !41 | Hestia Eats | Promotions system | Open |
