# Project Configuration for AI Agents

## General
- Application: Calliope Books (Node.js, Express, better-sqlite3)
- Source: demos/calliope-books/
- Test framework: k6 (JavaScript/ES modules)
- Gold-standard k6 tests: k6/ directory

## Performance Testing (Kassandra)

### SLOs
- Default: p95 < 1500ms, error rate < 1%
- Auth endpoints: p95 < 800ms
- Book listing/search: p95 < 1000ms
- Book detail (with reviews): p95 < 1500ms

### Load Profiles
- Review environment: max 50 VUs, 2-3 min duration
- Always compare against target branch (relative, not absolute)

### Critical Paths
- POST /api/auth/login (authentication)
- GET /api/books (listing + search)
- GET /api/books/:id (detail with reviews)
- POST /api/books/:id/reviews (write path)

### Auth
- Register: POST /api/auth/register with {"username", "email", "password"}
- Login: POST /api/auth/login with {"email", "password"}
- Token type: JWT Bearer
- Auth header: Authorization: Bearer {token}
- Demo user: reader@calliope.dev / calliope123

### Excluded Paths
- /api/health

### Review Environment
- Pattern: http://localhost:3000
- App type: `calliope`
- **Execution:** Use a SINGLE `run_command` that starts the app, runs k6, and kills the app. Never start the app in a separate command — `run_command` hangs if child processes survive.
  ```
  bash scripts/run-k6-test.sh {script_path} calliope
  ```
  The helper script handles startup, health check, k6 execution, and cleanup.

### API Endpoints
- POST /api/auth/register — register user
- POST /api/auth/login — login
- GET /api/books — list books (query: genre, author, search, limit, offset)
- GET /api/books/:id — get book with reviews and avg rating
- POST /api/books — create book (auth)
- PUT /api/books/:id — update book (auth)
- DELETE /api/books/:id — delete book (auth)
- GET /api/books/:id/reviews — list reviews for a book
- POST /api/books/:id/reviews — add review (auth, rating 1-5)

### Test Conventions
- Directory: k6/kassandra/
- Naming: mr-{MR_IID}-{slug}.js (e.g., mr-18-book-search.js)
- Use groups for logical grouping
- Include handleSummary() for JSON output
- Tag requests with endpoint and scenario
- Use name tags for URL grouping on parameterized paths (/books/:id)
