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

### Auth
- Login: POST /api/auth/login with {"email": "reader@calliope.dev", "password": "calliope123"}
- Token type: JWT Bearer → Authorization: Bearer {token}

### Excluded Paths
- /api/health

### API Endpoints
- POST /api/auth/register — register user
- POST /api/auth/login — login
- GET /api/books — list books (query: genre, author, search, limit, offset)
- GET /api/books/:id — get book with reviews
- POST /api/books — create book (auth)
- GET /api/books/:id/reviews — list reviews
- POST /api/books/:id/reviews — add review (auth, rating 1-5)

### Test Conventions
- Directory: k6/kassandra/
- Naming: mr-{MR_IID}-{slug}.js
- Include handleSummary() for JSON output to k6/kassandra/results/
- Tag requests with endpoint name
