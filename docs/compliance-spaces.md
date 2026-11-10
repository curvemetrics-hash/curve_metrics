# Compliance-Ready Spaces

A service built on the blueprint pipeline. An operator requests a space through the console or API. The pipeline builds it from the blueprint. A checker then tests it against 14 baseline controls and 42 extended checks and keeps a scan history. The console also runs rollouts and shows an audit log.

**Status: built and tested locally (kind, LocalStack, Docker, Postgres). Written for Render and Cloudflare but never deployed. No company uses it yet. These are local results, not adoption evidence.**

## What it does

| Step | Where |
|---|---|
| `POST /spaces` checks login and role, validates the request, stores it and queues a job | `spaces/server.py`, `spaces/auth.py`, `spaces/store.py` |
| A worker claims the job and runs the pipeline: format, validate, tests, plan, policy gate, apply, verify | `spaces/worker.py`, `spaces/core.py`, `scripts/ci.sh` |
| The checker reads live state from Kubernetes and AWS and evaluates the checks | `spaces/collect.py`, `spaces/controls.py`, `spaces/checks.py` |
| The console lists environments, findings, pipeline stages, rollouts and the audit log | `spaces/static/` |

Run it locally: `make up`, then `make spaces`, then open http://127.0.0.1:8080. Locally there is no login (you are an admin named `local`), the database is a SQLite file and the worker runs inside the same process. Deploying it is in `deploy/README.md`. Settings, API and roles are in `docs/reference.md`.

## Controls (14)

NET-1 default-deny ingress, NET-2 no allow-from-everywhere, ACC-1 no wildcard or cluster-admin, ACC-2 named admin groups, RES-1 quota matches size, RES-2 limit range, OWN-1 ownership labels, STO-1 S3 public access blocked, STO-2 versioning, STO-3 encryption, MSG-1 SQS encryption, LOG-1 log retention, SEC-1 secret exists, SEC-2 IAM policy has no wildcards.

These are engineering controls. Passing them does not make a space SOC 2 or ISO certified.

## Test results (2026-11-05, local)

Log: `docs/evidence/test-runs/spaces-e2e-first-run.txt` (24 checks, 0 failed).

- Two spaces (small/dev and large/prod) created through the API, both 14/14 on the first scan.
- A wildcard-admin request was rejected by the pipeline and created nothing.
- Four managed controls were broken by hand (policy deleted, bucket made public, quota changed, versioning suspended). Each was detected as exactly that one control, the other space was unaffected, and re-applying the blueprint restored 14/14.
- Bad input gives 400, a duplicate name gives 409.
- 85 Python tests pass (`make policy-test`) as of 2026-11-06. The end-to-end run was repeated on 2026-11-06 after the move to a queue and worker: 24 of 24 (`docs/evidence/test-runs/spaces-e2e-queue-2026-11-06.txt`).

| Measure | Local result | Note |
|---|---|---|
| Request to ready | 49 s (both spaces) | Local cluster, LocalStack, one run. Not a production figure. |
| Request to first compliant scan | 52 s | Same run. |
| Manual steps | 0 | After the request is submitted. |
| Baseline at a real company | not measured | Must come from the company. |

## Known limits (found by testing)

- **Re-applying does not remove objects added by hand.** A wildcard role binding created outside the blueprint is detected (ACC-1) but stays after re-apply until someone deletes it. The console says so.
- Provisioning runs one job at a time, because the pipeline shares a working directory.
- LocalStack does not enforce IAM, so access controls are checked by configuration, not by real enforcement.
- Locally there is no login and it listens on 127.0.0.1 only. With `AUTH_MODE=cloudflare` login and roles apply, but they have only been tested with generated keys, never with Cloudflare.
- Permissions are by role, not by team.
- The size presets are duplicated in `spaces/controls.py`; a unit test fails if they drift from the Terraform module.

## Extended checks (42, severity-rated)

The 14 baseline controls decide `compliant`. `spaces/checks.py` adds 42 more checks that never change `compliant`. They produce findings with a severity (high, medium, low), evidence and a remediation hint, and a one-word `grade` for the space: `non-compliant` (baseline fails), `at risk` (an open high finding), `needs attention` (an open medium finding) or `healthy`.

| Area | Checks |
|---|---|
| Workload security | privileged containers, host network/PID/IPC, hostPath, privilege escalation, running as root, dangerous capabilities, floating image tags, literal secrets in env, readiness probes, default service account, missing limits |
| Exposure | NodePort/LoadBalancer services, ingress without TLS, network policy open to 0.0.0.0/0, no egress policy |
| Access | wildcard roles, broad secret read, hand-made admin bindings, cross-namespace service accounts, Pod Security Admission label |
| Drift | unexpected network policies, service account to IAM role link, `cloud-resources` ConfigMap vs real names |
| Runtime faults | crash loops and image pull errors, pods stuck Pending, restart loops, unavailable replicas, quota over 80%, unbound volume claims, warning events in the last hour, failed jobs |
| AWS | bucket policy requires TLS and does not allow everyone, bucket tags, dead-letter queue, queue policy, secret rotation, role trust conditions, extra or inline IAM policies, service-wide wildcard actions, log retention of 30 days or more |

Each check has one of four results: `pass`, `fail`, `na` (nothing to check, or the resource is missing and the baseline already reports that) and `unknown` (the data could not be collected; it is never counted as a pass).

Known limits: thresholds (80% quota, 30-day retention, 5 restarts, 5-minute pending) are the author's choices. Several checks fail on a freshly built environment because the blueprint does not yet do them: Pod Security Admission label, bucket TLS policy, dead-letter queue, secret rotation and egress policy. These are real gaps in the blueprint, shown honestly rather than hidden. Secrets are never read, only their existence. AWS checks still run against LocalStack; real AWS is untested.
