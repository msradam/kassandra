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
- **MANDATORY startup command** (copy-paste exactly, do NOT modify):
  ```
  bash -c 'cd demos/calliope-books && setsid node app.js > /tmp/calliope.log 2>&1 & disown; sleep 2; exit 0'
  ```
- After startup, verify: `curl -sf http://localhost:3000/api/health`
- If health check fails, check logs: `cat /tmp/calliope.log`

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
- Directory: k6/
- Naming: kebab-case (e.g., book-search-load.js)
- Use groups for logical grouping
- Include handleSummary() for JSON output
- Tag requests with endpoint and scenario
- Use name tags for URL grouping on parameterized paths (/books/:id)
