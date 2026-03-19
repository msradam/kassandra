---
marp: true
theme: kassandra
paginate: true
---

<!-- _class: title -->

# Kassandra

## Performance testing agent for GitLab MRs

@mention on any MR → k6 load test → Mermaid-charted report

---

# How it works

```
@ai-kassandra-performance-test-gitlab-ai-hackathon
```

1. Reads the MR diff → identifies changed endpoints
2. OpenAPI GraphRAG → retrieves only relevant schemas (~97% context reduction)
3. Generates & commits a k6 test → arrival-rate executors, SLO thresholds
4. Runs it → app startup, k6, cleanup in one process
5. Posts the report → Mermaid charts, regression detection, per-endpoint breakdowns

No CI config. No manual test writing. One `AGENTS.md` per project.

---

# Results

| MR | App | Requests | Thresholds | Outcome |
|----|-----|----------|------------|---------|
| !36 | Midas Bank (Python/FastAPI) | 74 | 2/2 pass | Clean |
| !37 | Midas Bank (Python/FastAPI) | 863 | 8/8 pass | Clean |
| !39 | Calliope Books (Node/Express) | 576 | 1/3 pass | **Bug caught** |

MR !39: agent detected 100% failure on a new endpoint, diagnosed an Express route ordering bug, recommended the fix. No human intervention.

---

<!-- _class: title -->

# Let's trigger it live

## MR !41 — TypeScript/Hono food delivery API
## Adding promotions endpoints with an N+1 pattern

