# Project Configuration for AI Agents

## General
- Application: RealWorld Conduit (Node.js, Express, Sequelize, SQLite)
- Source: /tmp/realworld/ (cloned by setup_script)
- GitHub: https://github.com/cirosantilli/node-express-sequelize-realworld-example-app
- Test framework: k6 (JavaScript/ES modules)
- Gold-standard k6 tests: k6/ directory

## Performance Testing (Kassandra)

### SLOs
- Default: p95 < 2000ms, error rate < 1%
- Auth endpoints: p95 < 1000ms
- Article listing/feed: p95 < 1500ms
- Search/filter: p95 < 2000ms

### Load Profiles
- Review environment: max 50 VUs, 2-3 min duration
- Always compare against target branch (relative, not absolute)

### Critical Paths
- POST /api/users (registration)
- POST /api/users/login (authentication)
- GET /api/articles (article listing with pagination)
- GET /api/articles/feed (authenticated user feed)
- GET /api/tags (tag listing)

### Auth
- Register: POST /api/users with {"user":{"username":"...","email":"...","password":"..."}}
- Login: POST /api/users/login with {"user":{"email":"...","password":"..."}}
- Token: Response contains {"user":{"token":"..."}}
- Auth header: Authorization: Token {token}
- Demo users (if demo data loaded): user0@mail.com / asdf

### Excluded Paths
- None (all endpoints are testable)

### Review Environment
- Pattern: http://localhost:3000
- API prefix: /api

### API Endpoints (~20 RealWorld spec)
- POST /api/users — register
- POST /api/users/login — login
- GET /api/user — get current user (auth)
- PUT /api/user — update user (auth)
- GET /api/profiles/:username — get profile
- POST /api/profiles/:username/follow — follow user (auth)
- DELETE /api/profiles/:username/follow — unfollow user (auth)
- GET /api/articles — list articles (query: tag, author, favorited, limit, offset)
- GET /api/articles/feed — feed articles (auth)
- POST /api/articles — create article (auth)
- GET /api/articles/:slug — get article
- PUT /api/articles/:slug — update article (auth)
- DELETE /api/articles/:slug — delete article (auth)
- POST /api/articles/:slug/comments — add comment (auth)
- GET /api/articles/:slug/comments — get comments
- DELETE /api/articles/:slug/comments/:id — delete comment (auth)
- POST /api/articles/:slug/favorite — favorite article (auth)
- DELETE /api/articles/:slug/favorite — unfavorite article (auth)
- GET /api/tags — get tags

### Test Conventions
- Directory: k6/
- Naming: kebab-case (e.g., article-crud-load.js)
- Use groups for logical grouping
- Include handleSummary() for JSON output
- Tag requests with endpoint and scenario
- Use name tags for URL grouping on parameterized paths (/articles/:slug)
