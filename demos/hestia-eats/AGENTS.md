# Hestia Eats — Performance Testing Config

## Application
Go food delivery platform (net/http, in-memory store, port 8080)

## Auth
Bearer token: `hestia-bearer-token-2026` (header: `Authorization: Bearer hestia-bearer-token-2026`)
Pre-seeded user: Alice Chen (user ID 1), 2 delivered orders, 8 restaurants, 45 menu items

## SLOs
- Default: p95 < 500ms
- Search: p95 < 800ms
- Order creation: p95 < 1000ms
- Delivery tracking: p95 < 300ms

## Execution Command
```
bash scripts/run-k6-test.sh k6/kassandra/mr-{MR_IID}-{slug}.js hestia "" {source_branch}
```
