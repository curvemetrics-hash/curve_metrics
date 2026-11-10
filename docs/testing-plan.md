# Testing plan

**Status: local tests run on 5 and 6 November 2026 (see the log below). No tests have been run at Curve Metrics, on OpenShift, on GitHub Actions, on Render, on Cloudflare or against real AWS.** Record every real run in the results table below, with date and outcome. Never record results that were not produced by a run.

| Level | What is tested | How | Pass criterion |
|---|---|---|---|
| Static | Formatting, syntax, input validation | `fmt`, `validate`, linters | No errors |
| Unit | Each module produces the expected resources for each size | Terraform/OpenTofu native tests with mocked providers | All assertions pass |
| Negative | Bad inputs are rejected (invalid size, name, environment) | Tests that expect failure | Rejected with a clear message |
| Integration | A full blueprint applies cleanly to a non-production cluster | Pipeline run against a sandbox project | Environment ready, no errors |
| Security | Default-deny network policy active, no cluster-wide admin, quotas enforced | Automated checks plus manual review | Zero violations |
| Idempotency | Re-applying changes nothing; removal is clean | Second apply, then destroy | Empty plan, no leftovers |
| Acceptance | Pilot teams can request and use an environment unaided | Timed requests with real teams | Meets target times |
| Web and worker | Login, roles, forged tokens, cross-site header, static path traversal, queue to worker flow, policy rejection, failed scan | `tests/test_http.py` over real HTTP with a generated signing key | All pass |
| Shared state | Documents, atomic updates, exclusive job groups, crash retry, audit order | `tests/test_store.py` on SQLite, and on Postgres with `TEST_DATABASE_URL` | All pass on both |
| Checks | Each of the 42 extended checks fails when its fault is injected and passes when clean; missing data reports unknown | `tests/test_checks.py` | All pass |
| Container image | Tools present and checksummed, refuses to start unsafe, AWS keys removed from the environment, app directory writable | `docker build` then `docker run` checks | All pass (output saved) |
| Cloud (real AWS, Render, Cloudflare) | Everything above against the real services | Not possible without accounts | **Not run** |

## Rules

- Tests against clusters run only in a sandbox project created for this work, never in production.
- Test output is saved under `docs/evidence/test-runs/`.
- Run the Postgres variant of the store tests with `TEST_DATABASE_URL=postgresql://... python3 -m pytest tests/test_store.py`. It deletes all rows in that database, so use a throwaway one.

## Results log

| Date | Level | Run by | Result | Link to output |
|---|---|---|---|---|
| 2026-11-05 | Static, unit, negative, integration, security (policy gate), idempotency, drift, rebuild, workload using AWS resources | Claude, on a local kind cluster with LocalStack | All pass (see `docs/local-testing.md`) | `docs/evidence/test-runs/local-run-2026-11-05-final.txt` |
| 2026-11-06 | Python unit, API, HTTP, auth, store, extended checks (85 tests) | Claude, locally, SQLite | 85 passed | `docs/evidence/test-runs/pytest-2026-11-06.txt` |
| 2026-11-06 | Shared-state tests on Postgres 16 (Docker) | Claude, locally | 8 of 8 passed; output not saved | none |
| 2026-11-06 | Spaces end to end after the move to shared store, queue and worker (24 checks, real pipeline on kind and LocalStack) | Claude, locally | 24 passed, 0 failed | `docs/evidence/test-runs/spaces-e2e-queue-2026-11-06.txt` |
| 2026-11-06 | Container image: build, tools, safe-by-default, AWS profile setup | Claude, locally on arm64 | All pass | `docs/evidence/test-runs/docker-image-checks-2026-11-06.txt` |
| 2026-11-06 | Web, worker and cron containers against Postgres 16; `/healthz` and 401 without login | Claude, locally | Pass; output not saved | none |
| 2026-11-06 | Extended checks on the live local cluster, including a deliberately faulty workload that was then deleted | Claude, locally | Faults detected (11 findings); one check was fixed after it missed a crashing pod | none |
| 2026-11-06 | Rollout manager demo after moving registry and runs to the shared store (12 checks) | Claude, locally | 12 passed, 0 failed | `docs/evidence/test-runs/rollout-demo-store-2026-11-06.txt` |
