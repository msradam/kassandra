# Project Configuration for AI Agents

## General
- Application: PageTurn (Python, FastAPI, in-memory storage)
- Source: pageturn/ directory
- Test framework: k6 (JavaScript/ES modules)
- Gold-standard k6 tests: k6/ directory

## Performance Testing (Kassandra)

### SLOs
- Default: p95 < 1500ms, error rate < 0.5%
- Auth endpoints: p95 < 800ms
- Batch endpoints: p95 < 4000ms
- Search endpoints: p95 < 2000ms

### Load Profiles
- Review environment: max 50 VUs, 2-3 min duration
- Always compare against target branch (relative, not absolute)

### Critical Paths
- /api/auth/login
- /api/books (GET - search)
- /api/books/batch

### Excluded Paths
- /api/health
- /docs
- /redoc
- /openapi.json

### Review Environment
- Pattern: http://localhost:8000
- Auth: username=admin, password=pageturn123

### Test Conventions
- Directory: k6/
- Reference scripts: k6/foundations/
- Naming: kebab-case (e.g., book-search-load.js)
- Use groups for logical grouping
- Include handleSummary() for JSON output
- Tag requests with endpoint and scenario
