# Handoff

Updated 2026-11-06. Read this first, then `docs/design/00-system-overview.md`. Lookup tables are in `docs/reference.md`.

**If you are an agent picking this up:** work from `/Users/dharmendraahuja/curve_metrics`. Read sections 2 (wording rules), 6 (gaps) and 9 (behaviours not to break) before changing anything. Run `make policy-test` first (no cluster needed, 85 tests) to confirm the baseline. Do not start real-AWS work, create billable resources, push to a remote, or send anything to a company or attorney without the owner's explicit approval. Do not state in any document that the build implements the claims or that a company has adopted it.

## 1. What this is

A reference implementation of blueprinted platform engineering: Terraform/OpenTofu modules and a CI/CD pipeline that create standard Kubernetes environments, plus a console, a checker (14 baseline controls and 42 extended checks) and a Blueprint Rollout Manager on top. It is written to be deployed on Render and Cloudflare with real AWS and EKS behind it, and runs locally on kind and LocalStack. It is aligned with the **title** of German Utility Model No. 20 2025 107 185 (registered 16 Feb 2026), "System for Blueprinted Platform Engineering using Terraform Modules on Kubernetes/Openshift with CI/CD". The owner accepted title-level alignment on 2026-11-05. The claims text was never supplied.

Purpose: evidence for an EB-1A petition that two Indian companies (Curve Metrics, Abhishree Labs) adopt the utility model free of charge. Target timeline: about one month from 2026-10-29.

## 2. Wording rules (important)

- Say "aligned with the title" or "a reference implementation". Never say it implements, is covered by, or infringes the claims.
- Local results (kind + LocalStack) are **not adoption evidence**. Adoption means a company really using it, shown by signed letters and dated records.
- Fixtures (`local/fixtures/`) are not real requests.
- Company problem statements in the letters are still marked PROPOSED. Fill the `[X]` / `[N]` placeholders only with facts the company confirms.
- The project's theme must be the owner's own. Rejected as themes: Sentinel (Abhishree's own idea), the self-healing pipeline, and the compliance checker as a stand-alone product.
- Never write a test result that no run produced. Save real output under `docs/evidence/test-runs/`.
- Do not describe the 14 controls or 42 checks as SOC 2, ISO or CIS compliance.

## 3. Where things are

| Thing | Location |
|---|---|
| Codebase (git, branch `main`, no remote) | `/Users/dharmendraahuja/curve_metrics` |
| Architecture and flow documents | `docs/design/00` to `06` |
| Settings, API, roles, jobs, commands | `docs/reference.md` |
| Deployment runbook (Render, Cloudflare, AWS) | `deploy/README.md` |
| Test evidence logs | `docs/evidence/test-runs/` |
| Letters, licences, attorney email | `/Users/dharmendraahuja/book_piipeline/letters/` (`Curve_Metrics/`, `Abhishree_Labs/`, `Templates/`, `Email_to_Immigration_Attorney.*`) |
| Title-to-build mapping | `docs/patent-alignment.md` |

| Directory | Contents |
|---|---|
| `modules/`, `blueprints/` | The Terraform/OpenTofu modules and the blueprint |
| `scripts/` | Pipeline (`ci.sh`), policy gate, verify, drift, demo, validation, cluster login scripts |
| `spaces/` | Web service, worker, shared store, login, config, collector, 14 controls, 42 checks, console files |
| `rollout/` | Rollout manager (engine, core, service, CLI, catalog, report) |
| `deploy/`, `Dockerfile`, `render.yaml`, `requirements.txt` | Render and Cloudflare deployment: image, services, AWS bootstrap Terraform, cluster read-only role, runbook |
| `tests/` | 85 pytest tests |
| `local/` | LocalStack bootstrap, kind config, fixtures |
| `.github/workflows/` | `ci.yml`, `rollout-demo.yml` (both written, neither run) |

## 4. Get it running

Local, about 5 minutes plus image pulls. Needs Docker (Colima on macOS), OpenTofu, kind, kubectl, Python 3.

```bash
cd /Users/dharmendraahuja/curve_metrics
make up              # LocalStack + kind cluster
make policy-test     # 85 tests, no cluster needed
make ci-alpha        # full pipeline for one environment
make spaces          # console at http://127.0.0.1:8080 (SQLite, embedded worker, no login)
make spaces-e2e      # console end to end, 24 checks
make rollout-demo    # about 10 minutes (the 6-environment script takes about 6)
scripts/validate_all.sh   # everything; last run 2026-11-05, predates the worker
make down            # tear everything down
```

If a `make spaces` is already running, stop it before starting another; it keeps port 8080. After pulling changes, restart it: old processes keep old code.

Cloud: follow `deploy/README.md`. Nothing there has been run.

## 5. Current state

| Area | State |
|---|---|
| Blueprint and 2 modules | Built; 19 module tests pass |
| Pipeline (10 stages) | Built as a script; runs locally, directly and through the queue and worker. Real-AWS mode (`LOCAL=0`) written, never run |
| Console, API, roles, audit log | Built; 85 Python tests pass; login tested with generated keys only |
| Compliance checker | 14 baseline controls and 42 extended checks; checked on the live local cluster, including injected faults |
| Console end to end | 24 of 24 checks pass through the real queue and worker (2026-11-06) |
| Rollout Manager | Built on the shared store; scripted demo re-run 2026-11-06: 12 of 12 checks. Console start and remote catalog not run end to end |
| Shared state | SQLite locally; the same tests also pass on Postgres 16 in Docker |
| Container image | Builds on arm64 with checksum-verified tools; web, worker and cron containers run against Postgres |
| Render, Cloudflare, AWS bootstrap, EKS | Written (`render.yaml`, `deploy/`). **Never deployed.** IAM policies never run against real IAM |
| GitHub Actions | Written, **never run** |
| Real AWS, OpenShift, real cluster | **Untested** |
| Company adoption | **None yet** |

Latest commits (newest first): `de3f8eb` cloud deployment, `ba2b5a0` console redesign, `21a2f58` extended checks, `1c0882d` console and demo guide, `10ddb78` earlier handoff, `69666e4` design documents, `8768623` validation script, `1ef687f` rollout manager, `fdf2484` spaces. Documentation updates made on 2026-11-06 after `de3f8eb` are in the next commit.

## 6. Known gaps and risks

1. Claims never seen. A patent attorney must compare the claims; do not claim coverage before that.
2. GitHub workflows never ran. `scripts/local-up.sh` was only tested on macOS with Colima; expect small fixes on Linux runners.
3. A failing rollout **batch** is tested only with a fake engine. Only a failing canary was tested for real.
4. LocalStack does not enforce IAM, and IRSA needs a real cluster OIDC provider. Real AWS behaviour is unknown. Real AWS costs money and needs the owner's explicit approval first.
5. The 14 baseline controls and the 42 extended checks are the author's choice, not mapped to CIS, SOC 2 or ISO. Five extended checks fail on a fresh environment because the blueprint lacks the feature: Pod Security Admission label, bucket TLS policy, dead-letter queue, secret rotation, egress policy. Decide whether to harden the blueprint.
6. Re-applying does not remove objects added by hand (detected, not removed).
7. The deployment has never run. The first deploy will likely need IAM permission fixes, a kubectl version matching the cluster, and a blueprint catalog (`CATALOG_URL`) and registry before rollouts work.
8. No Postgres migration tool (tables are created if missing). The job lease is a fixed time, not a heartbeat, so a very slow job could run twice. No per-team permissions: any operator can scan any environment. No rate limit inside the app (use Cloudflare). No retire action. The approval stage is automatic in the worker (the request is the approval).
9. LocalStack licence terms need a fresh check before the weekly workflow is relied on.
10. The proposal (`letters/Curve_Metrics/03_...Implementation_Proposal`) does not mention the AWS resources, the console, the checks or the cloud deployment, all added later. Update it if they stay.
11. The scripts `scripts/validate_all.sh`, `drift_check.sh`, `demo_workload.sh` and `test_network_policy.sh` were last run before the queue and worker. They do not touch that code, but they were not re-run.
12. Documents under `docs/templates/` and the letters outside the repository were not reviewed in the 2026-11-06 documentation update.

## 7. What is left (mostly not code)

| Item | Owner | Notes |
|---|---|---|
| Real conversations with Curve Metrics and Abhishree Labs | Dharmendra | Without these there is no adoption evidence |
| Fill letter placeholders with real facts | Dharmendra with each company | Remove PROPOSED only when the company confirms |
| Signed licences and adoption letters | Companies | Store in `docs/evidence/letters/` and `docs/evidence/agreement/` |
| Attorney review of claims and the alignment document | Immigration/patent attorney | Draft email exists |
| Supply the claims text | Dharmendra | Then map claims to the build |
| Create the AWS sandbox account, EKS cluster, Render and Cloudflare accounts, then follow `deploy/README.md` | Dharmendra | First real run; fix what breaks. Needs a billing alert first |
| Create a public GitHub repo and run both workflows | Dharmendra | Fix first-run issues; enables the near-zero-cost weekly demo |
| Real baseline measurement (how long it takes today) | The companies | Local timings are not a baseline |
| Optional: OpenShift test, CIS mapping of controls, real failing-batch test, harden the blueprint for the five failing checks, retire action, per-team permissions, migration tool | Whoever continues | Real AWS needs explicit approval for cost |

## 8. Running costs

Two separate things, do not mix them up:

- **The weekly demo** (public GitHub repo, GitHub Actions, kind and LocalStack created fresh, static report): near zero cost, no hosted service. Written, never run. Upkeep is about two hours a month. Details in `docs/rollout-manager.md`.
- **The hosted console** (decided 2026-11-06): Render web service, worker, cron and Postgres bill monthly; EKS bills a control plane plus nodes; S3, SQS, DynamoDB and Secrets Manager are small. Check current prices before committing, and set an AWS billing alert first. This replaces the earlier "no hosted service" decision for the console.

## 9. Key behaviours to know before changing code

- Size presets live in both `modules/namespace_baseline/main.tf` and `spaces/controls.py`; a test guards them. Change both.
- A missing namespace must fail all 14 controls (`controls.evaluate`) and make every extended check `na`. Do not remove this.
- The extended checks never change `compliant`. Only the 14 baseline controls do. `unknown` is never a pass.
- Rollout pins move only after verification passes.
- A destroyed secret blocks reuse of its name (restore, then force-delete). `purge_secret` and `rollout purge-secrets` are local-only and refused in aws mode; do not use them against real AWS.
- The web service must never get AWS credentials; only the worker has them. State is in the database (`spaces/store.py`), not in files. Web, worker and cron share only the database.
- The app verifies the Cloudflare token itself (`spaces/auth.py`). Do not replace that with "trust the proxy".
- Every role the blueprint creates carries the permissions boundary in real AWS. Do not remove `permissions_boundary_arn`.
- Jobs in one group never overlap (`provision`: create and fix; `rollout`: preview and rollout). The pipeline shares a working directory and a Terraform lock.
- Writes need the header `X-Requested-With: console` when login is on. The console sends it; scripts that call the API in cloud mode must too.
- The console refuses to start without login on a non-local address. Do not add an override to the Render settings.
- Rollout state keys are `rollout/<name>.tfstate`; pipeline state keys are `<name>.tfstate`. Do not mix the two paths for the same environment.
- The version label `curve-metrics/blueprint-version` is how the live version is read; removing it breaks `status` and verification.
- Docker: the `/app` directory must be owned by the app user, and tool downloads use `dpkg --print-architecture`, not `TARGETARCH` (the classic builder does not set it). Both were real bugs.

## 10. Decisions so far

Full table with who made each: `docs/decision-log.md`.

| Date | Decision | Why |
|---|---|---|
| 2026-11-06 | Deploy on Render and Cloudflare with real AWS and EKS behind it | The build had to leave one laptop. Replaces "no hosted service" for the console |
| 2026-11-06 | Web service holds no AWS credentials; worker does, through an assume-only user and scoped roles with a permissions boundary | A flaw in the public service must not reach AWS |
| 2026-11-06 | The app verifies Cloudflare tokens itself | The Render address is public |
| 2026-11-06 | 14 baseline controls decide `compliant`; 42 severity-rated checks sit beside them | Old meaning and tests stay stable |
| 2026-11-05 | Kubernetes alone is enough; OpenShift optional | The owner reads the title as Kubernetes or OpenShift |
| 2026-11-05 | Title-level alignment is accepted | Claims text unavailable |
| 2026-11-05 | Build the Blueprint Rollout Manager on top of Compliance-Ready Spaces | A real, reusable problem: moving many environments to a new standard; not someone else's idea |
| 2026-11-05 | Zero-cost operation: public repo, GitHub Actions, no hosted service | Six-month upkeep at near-zero cost. Superseded for the console on 2026-11-06 |
| 2026-11-05 | Reject Sentinel, self-healing, stand-alone compliance product | Not the owner's own idea, or too little value alone |

## 11. Contacts

Not recorded in the repository. Add names and roles for the owner, each company contact and the attorney before handing over.
