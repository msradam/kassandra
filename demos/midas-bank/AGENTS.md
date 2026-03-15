# Project Configuration for AI Agents

## General
- Application: Midas Bank (Python, FastAPI, sqlite3)
- Source: demos/midas-bank/
- Test framework: k6 (JavaScript/ES modules)
- OpenAPI spec: Available at http://localhost:8000/openapi.json when app is running

## Performance Testing (Kassandra)

### Workflow
The execution command below handles EVERYTHING — app startup, branch checkout, health check, k6 run, cleanup. You MUST use it exactly as written. Do NOT build your own startup command.

1. Read the MR diff to identify new/changed endpoints
2. Start the app and fetch OpenAPI spec to understand exact schemas:
   ```
   run_command: bash -c 'cd demos/midas-bank && pip3 install -r requirements.txt -q 2>/dev/null; python3 -m uvicorn app:app --port 8000 &>/tmp/midas.log & sleep 3; curl -s http://localhost:8000/openapi.json; kill %1 2>/dev/null; wait 2>/dev/null'
   ```
   Use the OpenAPI JSON output to understand request/response schemas for your k6 script.
3. Write k6 test script to k6/kassandra/mr-{MR_IID}-{slug}.js
4. Commit the script to the MR branch
5. Execute:
   ```
   run_command: bash scripts/run-k6-test.sh k6/kassandra/mr-{MR_IID}-{slug}.js midas "" {source_branch}
   ```
   This checks out the source branch, starts the app, runs k6, kills the app — all in one process.
6. Analyze k6 output and post results to MR

### SLOs
- Default: p95 < 1500ms, error rate < 1%
- Auth endpoints: p95 < 800ms
- Account listing: p95 < 1000ms
- Transfers: p95 < 2000ms
- Transaction history: p95 < 1500ms

### Auth
- Login: POST /api/auth/login with {"email": "banker@midas.dev", "password": "midas123"}
- Token type: JWT Bearer → Authorization: Bearer {token}

### Excluded Paths
- /api/health, /docs, /redoc, /openapi.json

### Test Conventions
- Directory: k6/kassandra/
- Naming: mr-{MR_IID}-{slug}.js
- Include handleSummary() for JSON output to k6/kassandra/results/
- Tag requests with endpoint name
