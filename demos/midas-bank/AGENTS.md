# Project Configuration for AI Agents

## General
- Application: Midas Bank (Python, FastAPI, sqlite3)
- Source: demos/midas-bank/
- Test framework: k6 (JavaScript/ES modules)

## Performance Testing (Kassandra)

### Workflow
The execution command below handles EVERYTHING — app startup, branch checkout, health check, k6 run, cleanup. You MUST use it exactly as written. Do NOT build your own startup command.

1. Read the MR diff to identify new/changed endpoints
2. Write k6 test script to k6/kassandra/mr-{MR_IID}-{slug}.js
3. Commit the script to the MR branch
4. Execute:
   ```
   run_command: bash scripts/run-k6-test.sh k6/kassandra/mr-{MR_IID}-{slug}.js midas "" {source_branch}
   ```
   This checks out the source branch, starts the app, runs k6, kills the app — all in one process.
5. Analyze k6 output and post results to MR

### SLOs
- Default: p95 < 1500ms, error rate < 1%
- Auth endpoints: p95 < 800ms
- Account listing: p95 < 1000ms
- Transfers: p95 < 2000ms
- Transaction history: p95 < 1500ms

### Auth
- Login: POST /api/auth/login with {"email": "banker@midas.dev", "password": "midas123"}
- Token type: JWT Bearer → Authorization: Bearer {token}

### API Endpoints
- POST /api/auth/register — register user (username, email, password)
- POST /api/auth/login — login (email, password)
- GET /api/accounts — list user's accounts (auth)
- POST /api/accounts — create account (auth, name, type: checking/savings)
- POST /api/accounts/{id}/transfer — transfer funds (auth, to_account_id, amount, type)
- GET /api/accounts/{id}/transactions — transaction history (auth)

### Excluded Paths
- /api/health, /docs, /redoc, /openapi.json

### Test Conventions
- Directory: k6/kassandra/
- Naming: mr-{MR_IID}-{slug}.js
- Include handleSummary() for JSON output to k6/kassandra/results/
- Tag requests with endpoint name
