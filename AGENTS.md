# Project Configuration for AI Agents

## General
- Language: Go
- Framework: Chi router
- Database: PostgreSQL (via pgx)
- Test framework: k6 (JavaScript/ES modules)

## Performance Testing (Kassandra)

### SLOs
- Default: p95 < 2000ms, error rate < 0.5%
- Auth endpoints: p95 < 1000ms
- Batch endpoints: p95 < 5000ms

### Load Profiles
- Review environment: max 50 VUs, 2-3 min duration
- Always compare against target branch (relative, not absolute)

### Critical Paths
- /api/users/token/login
- /api/pizza
- /api/ratings

### Excluded Paths
- /api/status/*
- /metrics
- /debug/*

### Review Environment
- Pattern: https://quickpizza.grafana.com
- Auth: username=default, password=1234

### Test Conventions
- Directory: tests/k6/
- Naming: kebab-case (e.g., batch-recommendation-load.js)
- Import auth from tests/k6/helpers/auth.js
- Use groups for logical grouping
- Include handleSummary() for JSON output
- Tag requests with endpoint and scenario
