# Local testing

Everything runs on one machine with no cloud account and no cost. LocalStack provides the AWS services (S3, DynamoDB, IAM, SQS, Secrets Manager, CloudWatch Logs, STS) and kind provides Kubernetes. It uses its own kubeconfig (`.local/kubeconfig`) and never touches `~/.kube/config` or any real cluster.

## Requirements

Docker (for example Colima), OpenTofu 1.6 or later, kind, kubectl, Python 3.

## Run

```bash
make up           # start LocalStack and a local kind cluster, create state bucket and lock table
make test         # module tests (mocked providers): 13 baseline + 6 cloud
make policy-test  # Python tests: policy gate, controls, extended checks, API, HTTP, login, store, rollout (85)
make spaces       # the console at http://127.0.0.1:8080 (SQLite, embedded worker, no login)
make spaces-e2e   # console end to end against the cluster (24 checks)
make ci-alpha     # full pipeline for a dev environment (Kubernetes objects and AWS resources)
make ci-beta      # full pipeline for a large prod environment
make ci-bad       # must be rejected (wildcard admin group)
make drift-alpha  # scheduled drift check
make demo-alpha   # run a workload in the environment that uses its S3, SQS, secret and log group
make netpol-alpha # prove the network policies are enforced (traffic actually blocked or allowed)
make all          # everything above, in order
make down         # remove the cluster, LocalStack and local files
```

## What each pipeline stage does

1. Format check. 2. Validate. 3. Module unit tests. 4. Init with remote state in LocalStack (one state file per environment). 5. Plan. 6. Policy gate (required labels, quota, limit range, default-deny policy, no cluster-admin, no wildcard group). 7. Approval (automatic only when `AUTO_APPROVE=1`). 8. Apply. 9. Verify the live namespace. 10. Record a metric.

## What one environment contains

Each request creates, in one apply (20 resources):

| Layer | Resources | How the workload uses them |
|---|---|---|
| Kubernetes | Namespace; resource quota with CPU, memory, pod, storage (`requests.storage`, `persistentvolumeclaims`) and ingress (`count/ingresses`) limits; limit range; network policies (default-deny, same-namespace, ingress controller, optional allow-list); role bindings | The environment itself and its guardrails |
| AWS (LocalStack) | S3 bucket (private, versioned, encrypted), SQS queue (encrypted), Secrets Manager secret, CloudWatch log group (30-day retention), IAM role and policy (specific actions on those resources only) | The workload stores objects, sends messages, reads its secret and writes logs |
| Binding | ServiceAccount `app` annotated with the IAM role ARN; ConfigMap `cloud-resources` with the bucket, queue URL, secret name, log group and role ARN | The workload runs as `app` and reads its resource names from the ConfigMap |

## Results of the local run on 5 November 2026

| Check | Result |
|---|---|
| Module tests | 18 of 18 pass (13 baseline, 5 cloud). A sixth cloud test was added on 2026-11-06 (19 pass) |
| Policy gate tests | 14 of 14 pass |
| Dev environment (small) through full pipeline | 20 resources applied, 10 of 10 cluster checks and 11 of 11 AWS checks pass, state written to LocalStack |
| Prod environment (large, two admin groups) | Applied, same checks pass |
| Wildcard admin group request | Rejected by input validation, pipeline exits non-zero, nothing created |
| Re-plan after apply | No changes (idempotent) |
| Manual change to the quota | Detected as drift, corrected through the pipeline |
| Destroy then rebuild | Rebuilt, checks pass |
| Network policy enforcement | Same namespace reachable, unrelated namespace blocked, allow-listed namespace reachable, control (no policy) reachable. With all policies deleted by hand the test fails on the blocked case; after the pipeline re-applied them it passes again |
| Demo workload in the dev environment | Wrote an object to S3, sent an SQS message, read the secret, wrote a log event; all confirmed in LocalStack |
| Clean run from nothing (`make down` then `make all`) | All targets completed |

Raw output of the final run, with `make all` exit code 0: `docs/evidence/test-runs/local-run-2026-11-05-final.txt`. Earlier runs, kept for the record: `local-run-2026-11-05.txt` (before AWS resources) and `local-run-2026-11-05-with-aws.txt`.

Faults found and fixed while producing the final run: the network policy test first raced with its own cleanup (namespaces still terminating), and deleting only the default-deny policy turned out not to open any traffic because the other policies also isolate every pod, so the sabotage check deletes all policies instead. Earlier: the demo workload failed on a second run (it reused a log stream name), and a clean start sometimes failed because attaching LocalStack to the cluster network briefly interrupted its port, so `local-up.sh` now waits until LocalStack answers steadily.

Timings in the metric files are local and say nothing about real provisioning times at Curve Metrics.

## Results added on 2026-11-06

After the move to a shared database, job queue and worker, and the addition of login, roles and the 42 extended checks:

| Check | Result |
|---|---|
| Python tests | 85 of 85 pass (`docs/evidence/test-runs/pytest-2026-11-06.txt`) |
| Module tests | 19 of 19 pass |
| Console end to end (real pipeline on kind and LocalStack, through the queue and worker) | 24 of 24 pass (`spaces-e2e-queue-2026-11-06.txt`) |
| Rollout manager demo on the shared store (6 environments, 12 checks) | 12 of 12 pass (`rollout-demo-store-2026-11-06.txt`) |
| Shared-state tests on Postgres 16 | 8 of 8 pass (output not saved) |
| Container image and containers | pass (`docker-image-checks-2026-11-06.txt`) |

The 2026-11-05 results above predate this change. `scripts/validate_all.sh` has not been re-run since.

## Check against the implementation proposal

The proposal (`letters/Curve_Metrics/03_Curve_Metrics_Implementation_Proposal`) is the specification for this build.

| Proposal item | Status |
|---|---|
| Namespace, quota and limits, default-deny network policy, role bindings, standard labels | Built and tested |
| Ingress defaults | Built: ingress controller network policy (namespace configurable, for example `openshift-ingress`) and an ingress-count quota |
| Storage defaults | Built: storage and PVC-count quota. A default storage class is cluster-specific and not set here |
| Small, medium and large sizes | Built and tested |
| One settings file per environment, one reviewed request | Built; the review is automatic only in local mode |
| Remote state with locking, one state per environment | Built (LocalStack S3 and DynamoDB) |
| Pipeline: format, validate, tests, plan, approval, apply | Built as a local script; GitHub Actions workflow written but not run |
| Metrics from pipeline timestamps | Built (local) |
| Pipeline credentials from a secret store | Not built (placeholder in the workflow) |
| Real sandbox cluster, OpenShift, acceptance with real teams | Not done |

The AWS resources (S3, SQS, Secrets Manager, logs, IAM) are an addition requested after the proposal was written. The proposal does not mention them and should be updated if they stay.

## What local testing cannot show

OpenShift behaviour, real AWS behaviour, the GitHub Actions workflow, Render, Cloudflare, Curve Metrics' real process or any measured benefit. Specifically for AWS: LocalStack does not enforce IAM permissions, so the demo proves the resources exist, are configured to standard and are reachable, not that the role's limits are enforced. IAM roles for service accounts need a real cluster OIDC provider, which is only a placeholder here. EKS and ECR are not emulated by the free LocalStack edition, so cluster-side AWS integration (real IRSA) is untested. See `docs/patent-alignment.md`.

## Full validation run (2026-11-05)

`scripts/validate_all.sh` runs every check against the local kind cluster and LocalStack and ends with an inventory of the AWS resources that exist. Log: `docs/evidence/test-runs/full-validation-2026-11-05.txt`.

Result: 10 of 10 steps passed in about 13.5 minutes (module tests, Python tests, pipeline for the dev and prod fixtures, wildcard-admin rejection, drift check, demo workload, network policy enforcement, Compliance-Ready Spaces end to end, rollout manager demo).

At the end LocalStack held only the two intended environments (`team-alpha-dev`, `team-beta-prod`) plus the state and metrics buckets. Environments created and destroyed by the tests leave their secrets "scheduled for deletion" (a recovery window, as in real AWS); these are cleared for local use only with `python3 -m rollout purge-secrets`.

Limits: this is an emulator. LocalStack does not enforce IAM, so IAM policies are checked by content, not by real enforcement, and real AWS behaviour is untested.
