# Alignment with the utility model

Registered right: German Utility Model (Gebrauchsmuster) No. 20 2025 107 185, "System for blueprinted Platform Engineering using Terraform Modules on Kubernetes/Openshift with CI/CD", registered 16 February 2026.

**Basis of this check: the registered title only.** The claims text has not been supplied, so this is an element-by-element match against the title, not a claim-by-claim legal comparison. A patent attorney should check the claims before anyone relies on this document. Do not describe the implementation as covered by, or as infringing, any claim.

## Mapping to the title

| Element in the title | Implementation | Where | Status |
|---|---|---|---|
| Blueprinted platform engineering | A standard team environment blueprint with small, medium and large sizes, selected by a per-environment settings file | `blueprints/standard_team_env/`, `local/fixtures/` | Built, tested locally |
| Terraform modules | Two reusable, validated modules composed by the blueprint: the namespace baseline (labels, quota, limits, network policy, role bindings) and the team cloud bindings (S3, SQS, secret, logs, IAM, service account, config map) | `modules/namespace_baseline/`, `modules/team_cloud_bindings/` | Built; 19 module tests pass |
| On Kubernetes | Applied to a local Kubernetes 1.31 cluster (kind) through the Kubernetes provider | `scripts/ci.sh`, `local/kind-config.yaml` | Verified on a throwaway local cluster |
| On OpenShift | The title reads "Kubernetes/Openshift", which the owner confirms means either platform, so Kubernetes alone satisfies it. OpenShift-specific resources (Projects, security context constraints, Routes) are not exercised; the ingress controller namespace is a setting (`openshift-ingress`) | `blueprints/standard_team_env/variables.tf` | Optional, not tested |
| With CI/CD | Pipeline stages run by `scripts/ci.sh`: format, validate, unit test, remote state init, plan, policy gate, approval, apply, verify, metric. In the cloud design a worker process runs the same script from a queue, in a container. A GitHub Actions definition exists | `scripts/ci.sh`, `spaces/worker.py`, `.github/workflows/ci.yml` | Stages run locally, also through the queue and worker; **GitHub Actions workflow not run yet; cloud deployment not run** |

## What LocalStack is and is not

LocalStack emulates AWS services. Here it provides the remote state backend (S3 and DynamoDB lock table) and the team's AWS resources (S3, SQS, Secrets Manager, CloudWatch Logs, IAM), created by a second Terraform module (`modules/team_cloud_bindings`) that the same blueprint composes. This is consistent with "Terraform modules" and platform engineering, but the registered title does not mention AWS, so the AWS resources are supporting infrastructure for the Kubernetes environment, not the registered subject matter. Real AWS behaviour (permissions, encryption keys, regional endpoints) is not tested by LocalStack, and it does not enforce IAM.

## Known gaps

1. OpenShift is optional (the owner confirms the title means Kubernetes or OpenShift) and is not tested. Test it later if a claim or a company requires it.
2. Network policies are enforced on the local kind cluster (tested: allowed and blocked traffic, with a control case). Enforcement on a company's real cluster depends on its network plugin and is not tested.
3. The pipeline runs by script locally and through the local queue and worker. The GitHub Actions workflow has not run, and its plan and apply steps are placeholders until Curve Metrics' cluster and state backend are defined. The Render and Cloudflare deployment (`deploy/README.md`) has never run.
4. Local fixtures are not real requests, and the local run is not evidence of adoption or of any measured benefit.
5. The claims must be compared by a patent attorney.
