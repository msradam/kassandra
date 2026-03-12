# Project Configuration for AI Agents

## General
- Application: FastAPI Shop (Python, FastAPI, SQLAlchemy, SQLite)
- Source: /tmp/fastapi-shop/ (cloned by setup_script)
- GitHub: https://github.com/zamaniamin/fastapi-shop
- Test framework: k6 (JavaScript/ES modules)
- Gold-standard k6 tests: k6/ directory

## Performance Testing (Kassandra)

### SLOs
- Default: p95 < 2000ms, error rate < 1%
- Auth endpoints: p95 < 1000ms
- Product listing: p95 < 1500ms
- Order creation: p95 < 3000ms

### Load Profiles
- Review environment: max 50 VUs, 2-3 min duration
- Always compare against target branch (relative, not absolute)

### Critical Paths
- POST /api/auth/register (registration)
- POST /api/auth/login (authentication)
- GET /api/products (product listing)
- POST /api/orders (order creation)

### Auth
- Register: POST /api/auth/register
- Login: POST /api/auth/login
- Token type: JWT Bearer
- Auth header: Authorization: Bearer {token}
- Demo data: created by demo.py script

### Excluded Paths
- /docs
- /redoc
- /openapi.json
- /health

### Review Environment
- Pattern: http://localhost:8000
- Swagger UI: http://localhost:8000/docs

### API Endpoints
- POST /api/auth/register — register user
- POST /api/auth/login — login
- GET /api/products — list products (pagination, filtering)
- GET /api/products/:id — get product
- POST /api/products — create product (auth)
- PUT /api/products/:id — update product (auth)
- DELETE /api/products/:id — delete product (auth)
- GET /api/categories — list categories
- POST /api/categories — create category (auth)
- GET /api/orders — list orders (auth)
- POST /api/orders — create order (auth)
- GET /api/orders/:id — get order (auth)

### Test Conventions
- Directory: k6/
- Naming: kebab-case (e.g., product-catalog-load.js)
- Use groups for logical grouping
- Include handleSummary() for JSON output
- Tag requests with endpoint and scenario
- Use name tags for URL grouping on parameterized paths (/products/:id)
