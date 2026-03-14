# Project Configuration for AI Agents

## General
- Application: Midas Bank (Python, FastAPI, sqlite3)
- Source: demos/midas-bank/
- Test framework: k6 (JavaScript/ES modules)
- Gold-standard k6 tests: k6/ directory

## Performance Testing (Kassandra)

### SLOs
- Default: p95 < 1500ms, error rate < 1%
- Auth endpoints: p95 < 800ms
- Account listing: p95 < 1000ms
- Transfers: p95 < 2000ms (write-heavy, involves balance checks)
- Transaction history: p95 < 1500ms

### Load Profiles
- Review environment: max 50 VUs, 2-3 min duration
- Always compare against target branch (relative, not absolute)

### Critical Paths
- POST /api/auth/login (authentication)
- GET /api/accounts (account listing)
- POST /api/transactions/transfer (money transfer — write path)
- GET /api/transactions (transaction history with pagination)

### Auth
- Register: POST /api/auth/register with {"username", "email", "password"}
- Login: POST /api/auth/login with {"email", "password"}
- Token type: JWT Bearer
- Auth header: Authorization: Bearer {token}
- Demo user: banker@midas.dev / midas123

### Excluded Paths
- /api/health
- /docs
- /redoc
- /openapi.json

### Review Environment
- Pattern: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- App type: `midas`
- **Execution:** Use a SINGLE `run_command` that starts the app, runs k6, and kills the app. Never start the app in a separate command — `run_command` hangs if child processes survive.
  ```
  bash scripts/run-k6-test.sh {script_path} midas "" {source_branch}
  ```
  The 4th argument checks out the MR source branch so the app runs the feature code, not main.

### API Endpoints
- POST /api/auth/register — register user (creates default checking account)
- POST /api/auth/login — login
- GET /api/accounts — list user's accounts (auth)
- GET /api/accounts/:id — get account detail (auth)
- POST /api/accounts — create account (auth)
- GET /api/transactions — list transactions (query: account_id, limit, offset) (auth)
- POST /api/transactions/transfer — transfer between accounts (auth)
- POST /api/transactions/deposit — deposit to account (auth)

### Test Conventions
- Directory: k6/kassandra/
- Naming: mr-{MR_IID}-{slug}.js (e.g., mr-15-transfer.js)
- Use groups for logical grouping
- Include handleSummary() for JSON output
- Tag requests with endpoint and scenario
- Use name tags for URL grouping on parameterized paths (/accounts/:id)
