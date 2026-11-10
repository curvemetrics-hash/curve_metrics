# Implementation plan

**Status, 2026-11-06: the build (phase 2) exists as a reference implementation and runs locally. Phases 0, 1 and 3 to 5 depend on a real company and have not started. Dates are targets and assume the licence agreement is signed first.**

| Phase | Work | Owner | Output | Status |
|---|---|---|---|---|
| 0. Baseline | Record current provisioning time and manual steps for recent requests, before any build | Curve Metrics sponsor and platform lead | Baseline record in `docs/metrics-and-results.md` | Not started. Needs the company |
| 1. Design | Agree blueprint contents, sizes and policies with security and platform | Curve Metrics, Dharmendra Ahuja | Approved `docs/architecture.md` | Done as design documents (`docs/design/`), not yet agreed with a company |
| 2. Build | Write modules, blueprint, pipeline and metrics collection in Curve Metrics' own repository | Curve Metrics engineers, with starter material supplied | Working pipeline in a sandbox | Built locally, in this repository, not in a company's. Cloud deployment written, never deployed |
| 3. Live use | Onboard teams and run real requests | Curve Metrics | Dated pipeline logs and metrics | Not started |
| 4. Review | Compare against baseline, record the Continuation Decision | Both | Signed review note | Not started |
| 5. Follow-up | Confirm continued use at about 3 months | Curve Metrics | Follow-up letter | Not started |

## Rules

- No build starts before the baseline is recorded.
- All code is reviewed and merged by Curve Metrics engineers in Curve Metrics' repository.
- Use real requests only. Do not create requests just to generate numbers.
- Agree a minimum sample size before live use starts: [N] real requests.

## Weekly check-in (short, written)

Use `docs/templates/weekly-checkin.md`. Keep each one with the evidence.

## Deployment to Render and Cloudflare

Decided 2026-11-06. Written and tested locally; see `deploy/README.md` and `docs/design/06-cloud-deployment.md`.

| Step | Owner | Status |
|---|---|---|
| AWS sandbox account, EKS cluster | Dharmendra | Not started |
| `deploy/aws/bootstrap` (state, roles, boundary) | Dharmendra, then fix IAM on first run | Written, validated, never applied |
| Render services from `render.yaml`, Cloudflare Access | Dharmendra | Not started |
| First end-to-end run on real AWS, then fix what breaks | Dharmendra with help | Not started |
| Real baseline measurement and live use | The companies | Not started |
