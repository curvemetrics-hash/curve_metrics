# 05 Local environment and testing

Everything runs on one machine with no cloud account and no cost.

## Architecture

```mermaid
flowchart LR
    subgraph Host["Developer machine (macOS, Colima)"]
        T[tofu, kubectl, kind, python3]
        subgraph Docker
            LS[curve-localstack<br/>LocalStack 3.8<br/>:4566]
            KC[kind cluster<br/>curve-metrics-local<br/>Kubernetes 1.31.2]
        end
    end
    T --> LS
    T --> KC
    LS ---|"docker network kind<br/>http://curve-localstack:4566"| KC
```

LocalStack services: S3, DynamoDB, IAM, SQS, Secrets Manager, CloudWatch Logs, STS. The kubeconfig is `.local/kubeconfig`; `~/.kube/config` is never used.

Requirements: Docker (Colima), OpenTofu 1.6+ (1.13.2 used), kind, kubectl, Python 3.

## Flow: `make up`

```mermaid
flowchart TD
    A[start curve-localstack if absent] --> B[wait for health]
    B --> C[tofu apply local/bootstrap:<br/>state bucket, lock table, metrics bucket]
    C --> D[kind create cluster if absent]
    D --> E[preload aws-cli image]
    E --> F[docker network connect kind curve-localstack]
    F --> G[wait for 5 consecutive health answers<br/>the attach briefly interrupts the port]
    G --> H[kubectl get nodes]
```

`make down` removes the cluster, the container and local files.

## Test layers

| Layer | Command | What it proves |
|---|---|---|
| Module unit tests | `make test` | 19 tests with mocked providers (13 baseline, 6 cloud) |
| Python tests | `make policy-test` | 85 tests: policy gate (14), controls (5), extended checks (9), rollout core (12), API (7), HTTP (12), login (9), store (8). No cluster needed |
| Pipeline, dev | `make ci-alpha` | 20 resources, 10 cluster checks, 11 AWS checks |
| Pipeline, prod | `make ci-beta` | Large size, two admin groups |
| Negative case | `make ci-bad` | Wildcard admin is rejected, nothing created |
| Drift | `make drift-alpha` | No drift after apply |
| Workload | `make demo-alpha` | S3 write, SQS send, secret read, log write |
| Network enforcement | `make netpol-alpha` | Blocked and allowed traffic, with a control case and sabotage check |
| Spaces end to end | `make spaces-e2e` | 24 checks through the real queue and worker, with a scratch SQLite database |
| Rollout demo | `make rollout-demo` | 12 checks, about 10 minutes |
| Everything | `make all` or `scripts/validate_all.sh` | 10 steps plus a LocalStack inventory |

## Testing the cloud build without a cloud

| What | How | Proves |
|---|---|---|
| Postgres path | start `postgres:16-alpine` in Docker, then `TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/platform python3 -m pytest tests/test_store.py` (needs `psycopg`) | the same storage and queue tests pass on Postgres: concurrent writes, exclusive job groups, crash retry |
| Login | `tests/test_auth.py` and `tests/test_http.py` generate an RSA key and sign tokens | signature, issuer, audience, expiry, algorithm and tampering checks; roles; cross-site header; path traversal; queue to worker |
| Image | `docker build -t curve-platform:test .` then the `docker run` checks | tools present and checksummed, refuses to start unsafe, AWS keys removed from the environment, app directory writable |
| Containers together | run the web, worker and cron containers against the Postgres container | `/healthz` reaches Postgres; 401 without login; cron queues scans |

Saved output: `docs/evidence/test-runs/pytest-2026-11-06.txt`, `docker-image-checks-2026-11-06.txt`, `spaces-e2e-queue-2026-11-06.txt`. What none of this can show: Cloudflare's real keys and login page, Render's runtime, real IAM, EKS.

## Last recorded full validation

2026-11-05: 10 of 10 steps passed in about 13.5 minutes. LocalStack ended with only the two intended environments plus the state and metrics buckets. Log: `docs/evidence/test-runs/full-validation-2026-11-05.txt`.

## Fixtures

`local/fixtures/team-alpha-dev.tfvars` (dev, small, allow-list `kube-system`), `team-beta-prod.tfvars` (prod, large, two admin groups), `bad-wildcard-admin.tfvars` (must be rejected). They are test fixtures, not real requests, and are not evidence of any real use.

## Faults found while testing (worth knowing)

- The network policy test raced with its own cleanup while namespaces were terminating.
- Deleting only default-deny opens nothing, because the other policies also isolate every pod; the sabotage check deletes all policies.
- The demo workload failed on a second run because it reused a log stream name.
- A clean start sometimes failed because attaching LocalStack to the cluster network interrupted its port; `local-up.sh` now waits for steady answers.
- Destroyed secrets stay in a recovery window and block name reuse; `purge-secrets` clears them for local use.

## What local testing cannot show

OpenShift behaviour, real AWS behaviour (LocalStack does not enforce IAM), real IRSA, Render, Cloudflare, the GitHub Actions workflows, any company's real process, or any measured benefit. The 2026-11-05 full validation predates the queue and worker; `make spaces-e2e`, the rollout demo (`scripts/rollout_demo.sh 6`) and the unit tests were re-run after; `scripts/validate_all.sh` was not.
