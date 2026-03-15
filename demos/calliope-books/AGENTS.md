# Project Configuration for AI Agents

## General
- Application: Calliope Books (Node.js, Express, better-sqlite3)
- Source: demos/calliope-books/
- Test framework: k6 (JavaScript/ES modules)

## Performance Testing (Kassandra)

### Workflow
The execution command below handles EVERYTHING — app startup, branch checkout, health check, k6 run, cleanup. You MUST use it exactly as written. Do NOT build your own startup command.

1. Read the MR diff to identify new/changed endpoints
2. Write k6 test script to k6/kassandra/mr-{MR_IID}-{slug}.js
3. Commit the script to the MR branch
4. Execute:
   ```
   run_command: bash scripts/run-k6-test.sh k6/kassandra/mr-{MR_IID}-{slug}.js calliope "" {source_branch}
   ```
   This checks out the source branch, starts the app, runs k6, kills the app — all in one process.
5. Analyze k6 output and post results to MR

### SLOs
- Default: p95 < 1500ms, error rate < 1%
- Auth endpoints: p95 < 800ms
- Book listing/search: p95 < 1000ms
- Book detail (with reviews): p95 < 1500ms

### API Reference
- OpenAPI spec: `openapi.json` (static file in repo)
- Read the spec for exact request/response schemas, status codes, and field names
- Seed credentials: email=reader@calliope.dev, password=calliope123
- Auth: POST /api/auth/login → response has `token` field (NOT `access_token`) → Bearer {token}

### Excluded Paths
- /api/health

### Test Conventions
- Directory: k6/kassandra/
- Naming: mr-{MR_IID}-{slug}.js
- Include handleSummary() for JSON output to k6/kassandra/results/
- Tag requests with endpoint name
