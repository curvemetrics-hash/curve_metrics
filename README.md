# Curve Metrics Platform Blueprints

Self-service Kubernetes environments built from versioned Terraform module blueprints and delivered through CI/CD, with a console to request them, check them continuously, and move many of them to a new blueprint version safely.

> **Status: working reference build, run locally.** The modules, blueprint, pipeline, console, worker and rollout manager run and pass their tests on a local kind cluster with LocalStack. A deployment to Render, Cloudflare, AWS and EKS is written and its parts are tested locally (Postgres, Docker, login logic), but it has **never been deployed** and the IAM policies have never run against real IAM. Nothing has run on OpenShift or GitHub Actions, and nothing has been measured at Curve Metrics. Results tables say "to be measured" and must only ever be filled with real, dated figures. Local runs are not evidence of adoption.

## What this is

A team that needs a new environment asks for one with five fields: name, team, kind (dev, test, prod), size (small, medium, large) and admin groups. The pipeline validates it, tests it, applies a policy gate to the plan, applies it, and verifies the result. Every environment starts from the same standard: namespace, resource quota and limits, default-deny network policy, role bindings and standard labels, plus the team's AWS resources (private encrypted S3 bucket, encrypted SQS queue, Secrets Manager secret, log group, least-privilege IAM role) bound to the namespace through a service account and a ConfigMap.

On top of that:

| Part | What it does |
|---|---|
| **Console and API** (`spaces/`) | Request environments, watch the ten pipeline stages, scan, re-apply the blueprint, see an audit log. Login by Cloudflare Access with viewer, operator and admin roles |
| **Checker** | 14 baseline controls decide `compliant`. 42 extended, severity-rated checks add findings with fixes: workload security, exposure, access, drift, runtime faults, AWS configuration |
| **Rollout manager** (`rollout/`) | Move many environments to a new blueprint version: preview, canary, batches, automatic rollback, pins that move only after verification |
| **Worker, queue, shared state** | The web service only queues work. A separate worker, holding the cloud credentials, does it. State is in Postgres (SQLite locally) |

## Technology basis

The approach follows the system registered as German Utility Model (Gebrauchsmuster) No. 20 2025 107 185, "System for blueprinted Platform Engineering using Terraform Modules on Kubernetes/Openshift with CI/CD" (registered 16 February 2026, inventor Dharmendra Ahuja), used under a royalty-free licence agreement with Curve Metrics. This build is aligned with the **title** only; the claims were never supplied. See [NOTICE.md](NOTICE.md) and [docs/patent-alignment.md](docs/patent-alignment.md).

## Quick start (local, no cloud account)

Needs Docker (for example Colima), OpenTofu 1.6 or later, kind, kubectl and Python 3.

```bash
make up            # LocalStack and a local kind cluster
make policy-test   # 85 Python tests, no cluster needed
make ci-alpha      # full pipeline for one environment
make spaces        # console at http://127.0.0.1:8080 (no login locally)
make rollout-demo  # rollout manager demo, about 10 minutes
make down          # remove everything
```

More in [docs/local-testing.md](docs/local-testing.md). To show it to someone: [docs/customer-demo.md](docs/customer-demo.md).

## Deploying to Render and Cloudflare

```
Browser -> Cloudflare (Access login) -> Render web service -> Postgres <- Render worker -> AWS and EKS
                                                                  ^
                                                    Render cron (daily scan)
```

Start with [deploy/README.md](deploy/README.md): setup order, every setting, Cloudflare steps, roles, and what is most likely to need a fix on the first deploy. The image is the [Dockerfile](Dockerfile); the services are in [render.yaml](render.yaml); the AWS side (state, roles, permissions boundary) is `deploy/aws/bootstrap`.

## Documentation map

| Document | Purpose |
|---|---|
| [docs/HANDOFF.md](docs/HANDOFF.md) | **Start here when taking this over:** state, gaps, wording rules, what is left |
| [docs/reference.md](docs/reference.md) | Settings, API, roles, jobs, commands, make targets, where things are |
| [deploy/README.md](deploy/README.md) | Deploying to Render and Cloudflare; running costs; operating it |
| [docs/design/](docs/design/00-system-overview.md) | Architecture and flows, one document per component (00 to 06) |
| [docs/architecture.md](docs/architecture.md) | Index of the design documents |
| [docs/compliance-spaces.md](docs/compliance-spaces.md) | The console, the 14 baseline controls and 42 extended checks, results, limits |
| [docs/rollout-manager.md](docs/rollout-manager.md) | Rollout manager: version pins, preview, canary, batches, rollback |
| [docs/security.md](docs/security.md) | Roles, credentials, web hardening, known gaps |
| [docs/local-testing.md](docs/local-testing.md) | Run and test everything locally; results of the local runs |
| [docs/testing-plan.md](docs/testing-plan.md) | Test levels, pass criteria and the dated results log |
| [docs/customer-demo.md](docs/customer-demo.md) | A 15-minute walk-through and what is not ready for a customer |
| [docs/runbooks/request-an-environment.md](docs/runbooks/request-an-environment.md) | How a team requests an environment |
| [docs/runbooks/operate-and-recover.md](docs/runbooks/operate-and-recover.md) | Checking, re-applying, rolling out, rolling back, troubleshooting |
| [docs/patent-alignment.md](docs/patent-alignment.md) | How the build maps to the utility model title, and the gaps |
| [docs/implementation-plan.md](docs/implementation-plan.md) | Phases, owners, status |
| [docs/metrics-and-results.md](docs/metrics-and-results.md) | Baseline, targets and measured results |
| [docs/decision-log.md](docs/decision-log.md) | Dated record of decisions |
| [docs/evidence/README.md](docs/evidence/README.md) | What evidence to keep, and when |
| [docs/templates/](docs/templates/) | Baseline record, weekly check-in and review note templates |

## Repository layout

```
modules/        reusable Terraform modules (namespace baseline, team cloud bindings)
blueprints/     composed blueprint (standard team environment: small, medium, large)
spaces/         web service, worker, shared state, login, checker, console files
rollout/        rollout manager (engine, core logic, service, CLI, catalog, report)
scripts/        pipeline, policy gate, verification, drift, metrics, local stack, test runs
deploy/         AWS bootstrap Terraform, cluster read-only role, container entrypoint, runbook
Dockerfile, render.yaml, requirements.txt    image and Render services
requests/       one settings file per real environment request (empty until real use)
local/          LocalStack bootstrap, kind config, test fixtures (not real requests)
tests/          85 Python tests
.github/        CI/CD definitions (written, not yet run on GitHub)
docs/           this documentation
```

## Ownership

This repository is owned and controlled by Curve Metrics. Changes are reviewed and approved by Curve Metrics engineers through the normal pull-request process.
