# 06. Cloud deployment (Render and Cloudflare)

Status: written and tested locally. **Not deployed anywhere.** Runbook: `deploy/README.md`.

## Why the laptop design had to change

The first build assumed one machine: JSON files under `.local/`, a thread inside the web process running the pipeline,
`docker run` for the AWS CLI, no login. None of that survives Render, where the web service and the worker are separate
containers with throwaway disks.

## Components

| Component | Code | Role |
|---|---|---|
| Web service | `spaces/server.py` | serves the console, authenticates, authorises, validates, queues. Holds no cloud credentials |
| Worker | `spaces/worker.py`, `spaces/core.py` | claims jobs, runs `scripts/ci.sh`, scans, rollouts. Holds the AWS credentials |
| Cron | `spaces/cron.py` | queues a scan for every ready environment |
| Shared state | `spaces/store.py` | Postgres on Render, SQLite locally. Documents, job queue, audit log |
| Login | `spaces/auth.py` | verifies Cloudflare Access tokens; roles viewer, operator, admin |
| Settings | `spaces/config.py` | environment variables; refuses unsafe combinations at startup |

## Request flow

```
operator -> Cloudflare Access (login) -> web: verify token, check role, validate, write 'space' + job, audit
worker:  claim job -> write request file -> scripts/ci.sh (10 stages, stage written to the database as it runs)
         -> scan -> status 'ready' | 'rejected' (failed at or before the policy gate) | 'failed'
browser: polls /spaces and /jobs/<id> every few seconds
```

## Decisions

| Decision | Reason |
|---|---|
| The app verifies the Cloudflare token itself | The `onrender.com` address is public. Trusting "it came through Cloudflare" would leave it open |
| The web service holds no AWS credentials | A bug or token theft in the public service cannot touch AWS |
| Worker uses an assume-only IAM user, then a scoped role | A leaked key can do nothing except ask for the two roles; the pipeline role is limited by name patterns |
| Every team role carries a permissions boundary | Otherwise the pipeline role could create a role with more power than itself |
| A separate read-only role for scans | Scanning cannot change anything, even by mistake |
| Jobs in one group never overlap (`provision`, `rollout`) | They share a working directory and the Terraform lock; two at once would corrupt a run |
| A job whose worker dies is retried after its lease, up to 3 times | Render restarts workers on every deploy |
| POSTs need `X-Requested-With: console` (when login is on) | Blocks cross-site form posts using the user's Cloudflare cookie |
| Strict Content-Security-Policy, scripts only from the app | The page was split into files so no inline script is needed |
| The console refuses to start without login on a public address | A forgotten setting must not expose it |
| Local mode kept (SQLite, embedded worker, LocalStack, kind) | The same code is tested with no cloud account |

## Failure behaviour

| Failure | Result |
|---|---|
| Worker restarts mid-job | Job returns to the queue after its lease (20 minutes for a build, 60 for a rollout), then reruns. Terraform state in S3 with a lock keeps the rerun safe |
| Database unreachable | `/healthz` fails; Render restarts the service. The worker retries with a delay |
| Cloudflare keys rotate | Unknown key id triggers a refresh of the key set (at most once a minute) |
| Scan cannot reach the cluster | The job fails with the reason; the environment keeps its last good scan |
| Two people ask for a scan | They share one queued job |

## Not done

- Not deployed. IAM permissions have not met real IAM.
- Postgres has no migration tool; tables are created if missing. A schema change needs a migration step first.
- The job lease is a fixed time, not a heartbeat: a very slow job can be started twice.
- No per-team permissions: a viewer sees every environment, an operator can scan any environment.
- No rate limit inside the app (use the Cloudflare rule).
- Rollout catalog and registry need setting up by hand (`CATALOG_URL`, registry import).
