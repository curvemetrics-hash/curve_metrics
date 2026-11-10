# Reference

Lookup tables for everything configurable or callable. For how the parts fit together read `docs/design/00-system-overview.md` first.

## Modes

| Setting | Values | Meaning |
|---|---|---|
| `PLATFORM_MODE` | `local` (default), `aws` | `local`: kind cluster and LocalStack. `aws`: real AWS CLI, real cluster, state bucket in S3 |
| `AUTH_MODE` | `off` (default), `cloudflare` | `off`: everyone is an admin named `local`, allowed on localhost only. `cloudflare`: every request needs a valid Cloudflare Access token |
| `EMBEDDED_WORKER` | `1` (default in local mode), `0` (default in aws mode) | `1` runs the job worker as a thread inside the web process |

The web service refuses to start when: `AUTH_MODE=off` on a non-local `HOST` (unless `ALLOW_INSECURE=1`), `AUTH_MODE=cloudflare` without `CF_TEAM_DOMAIN` and `CF_ACCESS_AUD`, or `PLATFORM_MODE=aws` without `DATABASE_URL` (unless `ALLOW_SQLITE_IN_AWS=1`).

## Environment variables

| Variable | Used by | Meaning | Default |
|---|---|---|---|
| `HOST`, `PORT` | web | listen address | `127.0.0.1`, `8080` (the image sets `HOST=0.0.0.0`; Render sets `PORT`) |
| `DATABASE_URL` | web, worker, cron | `postgresql://...`. Unset means SQLite | unset |
| `SQLITE_PATH` | all | SQLite file when `DATABASE_URL` is unset | `.local/platform.db` |
| `KUBECONFIG` | web, worker | cluster login used for builds | `.local/kubeconfig` |
| `KUBECONFIG_RO` | worker | read-only login used for scans, when set | unset |
| `CF_TEAM_DOMAIN`, `CF_ACCESS_AUD` | web | Cloudflare team domain and Access application audience tag | unset |
| `ADMIN_EMAILS`, `OPERATOR_EMAILS` | web | comma separated; `@example.com` matches a whole domain; a service token's common name also works | empty |
| `ACCESS_DEFAULT_ROLE` | web | role for anyone not listed: `viewer`, `operator`, `admin` or `none` | `viewer` |
| `AWS_REGION` | worker | region | `us-east-1` |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | worker | keys of an IAM user that can only assume the roles below. `deploy/entrypoint.sh` moves them into a profile and removes them from the environment | unset |
| `AWS_ROLE_ARN` | worker | pipeline role (profile `platform`, the default) | unset |
| `AWS_READONLY_ROLE_ARN` | worker | read-only role for scans (profile `readonly`) | unset |
| `EKS_CLUSTER_NAME` | worker | cluster that `scripts/cluster-login.sh` logs in to | unset |
| `TF_STATE_BUCKET`, `TF_LOCK_TABLE` | worker | Terraform remote state and lock table | unset |
| `OIDC_PROVIDER_ARN`, `OIDC_ISSUER` | worker | the cluster's OIDC identity, for the IAM role trust policy | unset |
| `PERMISSIONS_BOUNDARY_ARN` | worker | boundary attached to every team role | unset |
| `CATALOG_URL`, `CATALOG_DIR` | worker | git repository of blueprint versions for rollouts, and where it is cloned | unset, `.local/rollout/catalog` |
| `TF_PLUGIN_CACHE_DIR` | worker | Terraform provider cache (the image sets `/opt/tf-plugins`) | `.local/rollout/plugin-cache` |
| `LOCAL`, `AUTO_APPROVE` | `scripts/ci.sh` | `LOCAL=0` real AWS; `AUTO_APPROVE=1` skips the approval prompt | `1`, unset |
| `TEST_DATABASE_URL` | tests | runs `tests/test_store.py` against Postgres (wipes the tables) | unset |

## Roles

| Role | Can |
|---|---|
| `viewer` | read environments, findings, rollout history, jobs |
| `operator` | also request environments, scan, preview a rollout |
| `admin` | also re-apply the blueprint, start a rollout, replace the rollout registry, read the audit log |

With login on, every `POST`, `PUT` and `DELETE` also needs the header `X-Requested-With: console`.

## HTTP API

| Call | Role | Result |
|---|---|---|
| `GET /healthz` | none | `{"ok": true}`; checks the database |
| `GET /api/me` | viewer | your identity, role, mode |
| `GET /spaces` | viewer | every environment with status and latest result |
| `GET /spaces/<name>` | viewer | one environment: request, status, stage, latest report, scan history |
| `POST /spaces` | operator | `202` and a job id; `400` bad input; `409` name exists |
| `POST /spaces/<name>/scan` | operator | `202` and a job id. With `?wait=N` waits up to N seconds and returns the report (`502` if the scan failed, `504` on timeout) |
| `POST /spaces/<name>/fix` | admin | re-apply the blueprint; `409` if already running |
| `GET /rollout` | viewer | registry, run history, available versions |
| `POST /rollout/preview` | operator | body `{"version": "v1.2.3"}`; queues a preview |
| `POST /rollout/start` | admin | body `{"version", "canary": [...], "batch": 3, "allow_destroy": false}`; `409` if one is running |
| `PUT /rollout/registry` | admin | replace the registry |
| `GET /jobs`, `GET /jobs/<id>` | viewer | queue state |
| `GET /audit` | admin | newest 200 audit entries |
| `GET /`, `GET /static/app.js`, `GET /static/app.css` | viewer | the console |

Errors are JSON `{"error": "..."}`. `401` means login needed, `403` means the role is too low or the header is missing. Request bodies are limited to 64 KB.

## Environment request

| Field | Rule |
|---|---|
| `name` | lowercase DNS label, up to 42 characters; also the namespace and the prefix of every cloud resource |
| `team` | lowercase letters, digits, dashes, up to 31 characters |
| `environment` | `dev`, `test` or `prod` |
| `size` | `small`, `medium` or `large` |
| `admin_groups` | non-empty list of group names; a wildcard is refused by the pipeline |

## Environment status

`provisioning` (queued or building; `stage` 1 to 10 shows progress), `ready` (built and scanned once), `rejected` (failed at or before stage 6, the policy gate; nothing was created), `failed` (failed after stage 6).

Grades from a scan: `non-compliant` (a baseline control fails), `at risk` (open high finding), `needs attention` (open medium finding), `healthy`.

## Jobs

| Kind | Does | Group (never overlaps within a group) | Lease |
|---|---|---|---|
| `create` | build a new environment, then scan | provision | 20 min |
| `fix` | re-apply the blueprint, then scan | provision | 20 min |
| `scan` | read live state and run the 14 + 42 checks | none | 5 min |
| `preview` | plan a version for every environment, change nothing | rollout | 30 min |
| `rollout` | staged rollout | rollout | 60 min |

A job whose worker disappears is queued again when its lease runs out, up to 3 attempts, then marked failed.

## Shared state (`spaces/store.py`)

| Namespace | Holds |
|---|---|
| `space` | one document per environment |
| `rollout_registry` | key `registry`: environments and their pinned versions |
| `rollout_run` | one document per finished rollout |
| `audit` | one document per action: who, role, action, target, time |
| `metric` | pipeline timing records (aws mode; locally they go to the LocalStack metrics bucket) |
| table `jobs` | the queue |

## Command line

| Command | Does |
|---|---|
| `python3 -m spaces.server` | web service (`make spaces`) |
| `python3 -m spaces.worker` | job worker |
| `python3 -m spaces.cron scan-all` | queue a scan for every ready environment |
| `python3 -m rollout demo-registry [N]`, `registry`, `registry-import FILE`, `last-run` | registry |
| `python3 -m rollout provision`, `status`, `preview V`, `rollout V [--canary NAME] [--batch N] [--allow-destroy]`, `report [--live]`, `destroy`, `purge-secrets` | operations (`purge-secrets` is refused in aws mode) |

## Make targets

| Target | Does |
|---|---|
| `up`, `down` | start or remove LocalStack and the kind cluster |
| `test` | module tests (19) |
| `policy-test` | Python tests (85) |
| `ci-alpha`, `ci-beta`, `ci-bad` | pipeline for the dev fixture, the prod fixture, and the bad fixture (must be rejected) |
| `drift-alpha`, `demo-alpha`, `netpol-alpha` | drift check, demo workload, network policy enforcement |
| `spaces`, `spaces-e2e` | the console, and its end-to-end test |
| `rollout-demo`, `rollout-report` | rollout demo with 10 environments; static rollout report |
| `all` | up, test, policy-test and the pipeline targets in order |

## Scripts

| Script | Purpose |
|---|---|
| `scripts/ci.sh` | the ten pipeline stages for one request file (`LOCAL=0` for real AWS) |
| `scripts/policy_check.py` | policy gate on the plan JSON |
| `scripts/verify.sh`, `verify_aws.sh` | live checks after apply |
| `scripts/awscli.sh` | AWS CLI for the current mode (real, or LocalStack through `awslocal.sh`) |
| `scripts/cluster-login.sh` | write the kubeconfig (and the read-only one) for EKS |
| `scripts/record_metric.py` | pipeline timing record |
| `scripts/drift_check.sh`, `demo_workload.sh`, `test_network_policy.sh` | local checks |
| `scripts/local-up.sh`, `local-down.sh`, `validate_all.sh`, `test_spaces_e2e.sh`, `rollout_demo.sh` | local stack and test runs |
| `deploy/entrypoint.sh` | container start: AWS profiles from environment variables |

## Where things are

| Path | Contents |
|---|---|
| `blueprints/`, `modules/` | Terraform/OpenTofu blueprint and its two modules |
| `spaces/` | web service, worker, store, auth, config, collector, controls, checks, console files |
| `rollout/` | rollout manager: engine, core logic, service, CLI, catalog, report |
| `scripts/` | pipeline and helper scripts |
| `local/` | LocalStack bootstrap, kind config, fixtures |
| `deploy/` | AWS bootstrap Terraform, cluster read-only role, container entrypoint, deployment runbook |
| `Dockerfile`, `render.yaml`, `requirements.txt` | image and Render services |
| `tests/` | 85 pytest tests |
| `docs/` | documents; `docs/design/` per-component architecture; `docs/evidence/` dated test output |
