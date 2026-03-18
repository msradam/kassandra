# Kassandra — Demo Script (3 minutes)

Use this script to record the DevPost submission video. The video should show Kassandra's full workflow from @mention to performance report, with voiceover explaining what's happening.

## Pre-recording setup

1. Make sure MR !41 (Hestia Eats promotions) has a completed Kassandra report. If not, trigger it first and wait for results.
2. Open a browser tab to the GitLab MR list: `https://gitlab.com/gitlab-ai-hackathon/participants/3286613/-/merge_requests`
3. Have a second tab ready for the agent session link (you'll click through to it during recording).
4. Screen recording at 1280x720 or higher.

## Script

### 0:00–0:20 — The Problem (voiceover over MR list)

Show the MR list. Voiceover:

> "Performance testing gets skipped. Everyone knows it matters, but nobody writes load tests when the deadline is tomorrow. And when someone does run k6, the results are raw numbers in CI logs that take real expertise to interpret."

> "Kassandra fixes this. It's a GitLab Duo Workflow agent that reads your MR diff, generates a k6 test, runs it, and posts a visual performance report — all from a single @mention."

### 0:20–0:50 — Trigger Kassandra (live)

Click into MR !41 (Hestia Eats promotions). Briefly show the diff — TypeScript code adding promotions endpoints.

> "Here's a merge request adding a promotions feature to a TypeScript food delivery API. Let's see how Kassandra handles it."

Scroll to the comment box. Type `@ai-kassandra-performance-test-gitlab-ai-hackathon` and submit.

> "That's it. One @mention. No CI config, no test scripts to write."

### 0:50–1:10 — Show the Agent Working

Kassandra replies within seconds with a "Performance Test has started" message. Click the agent session link.

> "Kassandra picks up the MR through GitLab's Duo Workflow platform. It reads the diff, figures out which demo app is being changed — in this case Hestia Eats — and loads the project-specific SLOs and API spec."

Show the agent session UI briefly — the tool calls appearing (read_file, run_command, etc.)

> "The agent uses our GraphRAG module to extract only the schemas relevant to the changed endpoints — 96% less context than sending the whole OpenAPI spec. Then it generates a k6 test and commits it to the branch."

### 1:10–1:30 — Explain Architecture (voiceover, can show code briefly)

> "Three things make this work reliably. First, OpenAPI GraphRAG — a deterministic knowledge graph that gives the LLM exactly the right API context. Second, deterministic report generation — the Mermaid charts and tables come from a Python script, not from the LLM. Third, single-invocation execution — app startup, k6, and cleanup all run in one process so the Duo Workflow runtime doesn't hang."

(Optional: briefly flash the project structure in an editor or terminal)

### 1:30–2:30 — The Report (the main event)

Navigate back to MR !41. The Kassandra Performance Report should be posted as a comment.

Scroll through it slowly. Let each section land:

> "Here's the report. Pass/fail verdict at the top — all thresholds met."

Show the threshold table.

> "Latency distribution per endpoint — the bar chart shows p50, p95, p99 for each route. These render natively in GitLab using Mermaid."

Show the Mermaid bar chart.

> "Timing breakdown — how long each phase takes. Blocked, connecting, TLS, waiting for first byte."

Show the timing table.

> "And validation results — Kassandra doesn't just check status codes. It validates response structure, field types, business logic constraints."

Show the checks section.

> "Every MR gets this level of detail. No manual work."

### 2:30–2:50 — The Bug Catch (MR !39)

If time allows, quickly switch to MR !39 or show a screenshot.

> "On a previous MR, Kassandra caught a real bug. A new Express endpoint was returning 404 on every request. Kassandra detected 100% failure, diagnosed the root cause — a route ordering issue — and recommended the exact fix. That's what it's for."

### 2:50–3:00 — Closing

> "Kassandra. Drop an AGENTS.md in any repo, @mention on a merge request, get a full performance report. Built on GitLab Duo Workflow for the AI Hackathon 2026."

Show the project URL: `https://gitlab.com/gitlab-ai-hackathon/participants/3286613`

---

## Automated recording (alternative)

If you prefer to record just the report scroll-through:

```bash
npx tsx scripts/record-demo.ts
```

This opens a headed browser, navigates to MR !41, waits for the report to load, and smooth-scrolls through it. Video saves as `.webm` in `.playwright-mcp/`.

## Tips

- Keep voiceover conversational, not rehearsed. Judges can tell.
- The report is the star — spend at least 60 seconds on it.
- Don't rush the Mermaid charts. Let them render and sit for a beat.
- If the agent takes too long live, cut to a pre-recorded session and note "we're skipping ahead."
- Make sure GitLab is in light mode for readability on video.
