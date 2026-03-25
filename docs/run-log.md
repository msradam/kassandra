# Kassandra Run Log

All MR triggers from !36–!75. Each completed run produced a valid k6 report posted to the MR.

## Summary

- **MR range**: !36–!75 (40 MRs)
- **Not triggered**: 3 (!44, !45, !49)
- **Triggered**: 37
  - **Completed** (k6 executed, report posted): **23**
  - **Agent ran, k6 did not execute**: 4
  - **Agent started, no output**: 10

## Completed runs (23)

| MR | App | Status | Requests | VUs | req/s | Duration | Fail% | Thresholds | Notes |
|----|-----|--------|----------|-----|-------|----------|-------|------------|-------|
| !36 | Midas Bank | PASS | — | 5 | — | 40s | rate-limited | 2/2 | Early run, different report format. Transfer rate limiting test. |
| !37 | Midas Bank | PASS | 863 | — | — | 60.1s | — | 5/5 | Spending summary endpoint. |
| !39 | Calliope Books | FAIL | 576 | 55 | 22.9 | — | — | 1/3 | **Route ordering bug: 100% failure on /suggestions.** |
| !40 | Midas Bank | FAIL | 419 | 35 | 16.7 | 25.1s | 58.2% | 1/1 | Withdrawal endpoint. |
| !41 | Hestia Eats | PASS | 728 | 75 | 29.1 | 25.0s | 2.1% | 8/8 | Promotions system. Clean run. |
| !43 | Hestia Eats | PASS | 500 | 10 | 20.0 | 25.1s | 0.0% | 2/2 | Review analytics. |
| !46 | Hestia Eats | FAIL | 453 | — | — | 30s | 100% | — | Order history. Critical failure (auth/endpoint issue). |
| !47 | Midas Bank | PASS | 404 | 5 | 20.1 | 20.1s | 0.0% | 1/1 | Spending trends, 5 VUs. |
| !50 | Midas Bank | PASS | 602 | 5 | 30.1 | 20.0s | 0.0% | 3/3 | Spending trends, 5 VUs. |
| !51 | Midas Bank | PASS | 203 | 5 | 10.1 | 20.1s | 0.0% | 1/1 | Spending trends, 5 VUs. |
| !52 | Midas Bank | PASS | 202 | 5 | 10.1 | 20.0s | 0.0% | 2/2 | Spending trends, 5 VUs. |
| !53 | Midas Bank | FAIL | 2,431 | 13 | 94.8 | 25.6s | 46.7% | 2/2 | Spending trends, 13 VUs. First load spike. |
| !55 | Midas Bank | FAIL | 1,193 | 9 | 58.4 | 20.4s | 4.5% | 2/2 | Spending trends, 9 VUs. |
| !60 | Midas Bank | FAIL | 1,357 | 61 | 52.5 | 25.8s | 17.6% | 4/6 | Spending trends, 60 VUs. |
| !63 | Midas Bank | PASS | 1,427 | 60 | 57.0 | 25.0s | 0.0% | 4/4 | Spending trends, 60 VUs. Post-tuning. |
| !64 | Midas Bank | FAIL | 1,238 | 60 | 49.1 | 25.2s | 11.0% | 6/8 | Spending trends, 60 VUs. |
| !65 | Midas Bank | FAIL | 308 | 60 | 25.7 | 12.0s | 22.7% | 4/4 | Spending trends, 60 VUs. Short run. |
| !66 | Midas Bank | PASS | 2,814 | 60 | 112.5 | 25.0s | 49.5% | 4/4 | Spending trends, 60 VUs. High fail% but thresholds pass (by design). |
| !69 | Midas Bank | FAIL | 2,828 | 60 | 113.1 | 25.0s | 60.6% | 3/5 | **SQLite thread-safety bug. spending_trends p95=47.0ms.** |
| !72 | Midas Bank | FAIL | 657 | 60 | 54.9 | 12.0s | 42.6% | 4/4 | Spending trends post-fix iteration. |
| !73 | Midas Bank | FAIL | 2,117 | 60 | 84.6 | 25.0s | 32.9% | 4/4 | Spending trends iteration. |
| !74 | Midas Bank | FAIL | 2,830 | 60 | 112.9 | 25.1s | 49.4% | 8/8 | Spending trends. Risk: `fetchall()` flagged. |
| !75 | Calliope Books | FAIL | 306 | 60 | 25.5 | 12.0s | 22.9% | 8/8 | Book recommendations. 4,042 validation checks. |

## spending_trends p95 trajectory

| MR | VUs | spending_trends p95 (ms) | Context |
|----|-----|--------------------------|---------|
| !47 | 5 | 3.8 | Baseline |
| !50 | 5 | 3.7 | Stable |
| !51 | 5 | 4.1 | Stable |
| !53 | 13 | 8.4 | +127% from baseline, first load spike |
| !55 | 9 | 4.9 | Back down at lower VUs |
| !60 | 61 | 8.0 | High VUs, pre-tuning |
| !63 | 60 | 3.9 | Post-tuning |
| !64 | 60 | 6.7 | Variance |
| !66 | 60 | 4.5 | Stable |
| !69 | 60 | 47.0 | Thread-safety bug introduced |
| !72 | 60 | 3.7 | Post-fix iteration |
| !73 | 60 | 3.7 | Stable |
| !74 | 60 | 3.6 | Stable |

## Incomplete runs

### Agent ran, k6 did not execute (4)
- **!54**: Agent committed k6 script but didn't run it
- **!56**: Agent posted "encountered technical difficulties"
- **!68**: Agent posted "Unable to Execute" (MR was closed)
- **!71**: Agent posted "Test execution encountered an issue"

### Agent started, no report posted (10)
!38, !42, !48, !57, !58, !59, !61, !62, !67, !70

### Not triggered (3)
!44, !45, !49 — no agent mention in MR notes.

## Cross-stack coverage

| App | Completed runs | MRs |
|-----|---------------|-----|
| Midas Bank | 19 | !36, !37, !40, !47, !50–!53, !55, !60, !63–!66, !69, !72–!74 |
| Calliope Books | 2 | !39, !75 |
| Hestia Eats | 2 | !41, !43 |

## Qwen A/B test results (local, via Ollama)

| Spec | Full-spec coverage | GraphRAG coverage | Full latency | GraphRAG latency | Speed improvement |
|------|--------------------|-------------------|-------------|------------------|-------------------|
| Midas Bank | 12/12 | 12/12 | 216.9s | 145.5s | 33% |
| Calliope Books | 8/8 | 8/8 | 162.7s | 52.2s | 68% |
| Hestia Eats | 10/17 | 15/17 | 229.9s | 92.0s | 60% |
