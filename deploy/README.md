# Deploying to Render and Cloudflare

Status: **written and tested locally, never deployed.** The code, image and policies below were exercised on a laptop
(SQLite and Postgres in Docker, kind, LocalStack). Nothing here has run on Render, Cloudflare or real AWS. Expect small
fixes on first deploy, especially IAM permissions (see "First deploy").

## What runs where

```
Browser -> Cloudflare (DNS, TLS, WAF, Access login) -> Render web service (console + API)
                                                         |  queues jobs in Postgres
Render worker (tofu, kubectl, scans, rollouts) <---------+
   |-> AWS: assumes a scoped role (S3, SQS, Secrets, Logs, IAM-with-boundary, state bucket)
   `-> EKS API: kubectl with the same role
Render cron: queues a scan of every ready environment each day
```

| Piece | Holds | Does not hold |
|---|---|---|
| Web service | database URL, Cloudflare settings | any AWS credential |
| Worker | AWS keys (assume-only user), cluster login | nothing public: it has no HTTP port |
| Cron | database URL | AWS credentials |
| Postgres | environments, scans, jobs, audit log, rollout registry | Terraform state (that is in S3) |

## One-time setup, in this order

1. **AWS account**: a dedicated sandbox account and a billing alert. Never an account with other workloads.
2. **EKS cluster** (not built by this repo). Example: `eksctl create cluster --name curve-platform --region <r> --nodes 1 --node-type t3.medium`.
   Then `eksctl utils associate-iam-oidc-provider --cluster curve-platform --approve`. Read the two values the blueprint needs:
   `aws eks describe-cluster --name curve-platform --query cluster.identity.oidc.issuer` (drop `https://` for `OIDC_ISSUER`)
   and the provider ARN from `aws iam list-open-id-connect-providers`.
3. **Bootstrap IAM and state**: `cd deploy/aws/bootstrap && tofu init && tofu apply -var region=<r> -var cluster_name=curve-platform`.
   Note the outputs. Then create the one access key for the Render user:
   `aws iam create-access-key --user-name <render_user output>`. It goes straight into Render, nowhere else.
4. **Cluster access**: give the roles a place in the cluster.
   - Pipeline role: `aws eks create-access-entry --cluster-name curve-platform --principal-arn <pipeline role>` then
     `aws eks associate-access-policy ... --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy --access-scope type=cluster`.
     It needs this much because the blueprint creates namespaces and role bindings.
   - Read-only role: `kubectl apply -f deploy/k8s/checker-readonly.yaml` and the access entry described in that file.
   - Install an ingress controller if teams need one (the blueprint's default network policy expects namespace `ingress-nginx`).
5. **Render**: create a Blueprint from `render.yaml`. Fill every `sync: false` value in the dashboard (table below).
6. **Cloudflare**: see "Cloudflare" below, then paste the team domain and AUD tag into the web service and redeploy.
7. **Check**: open the console. The sidebar should show your email and role. Request one small environment and watch it
   build. Run a scan. Open Activity (admin) and see the audit entry.

## Environment variables

| Variable | Service | Meaning |
|---|---|---|
| `PLATFORM_MODE=aws`, `AUTH_MODE=cloudflare` | all | set in `render.yaml`; the console refuses to start without them on a public address |
| `DATABASE_URL` | all | filled automatically from the Render database |
| `CF_TEAM_DOMAIN`, `CF_ACCESS_AUD` | web | `yourteam.cloudflareaccess.com` and the Access application's AUD tag |
| `ADMIN_EMAILS`, `OPERATOR_EMAILS` | web | who may re-apply and roll out (admin); who may request and scan (operator). `@example.com` matches a domain |
| `ACCESS_DEFAULT_ROLE` | web | `viewer` (default) or `none` to deny anyone not listed |
| `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | worker | the Render IAM user (it can only assume the two roles) |
| `AWS_ROLE_ARN`, `AWS_READONLY_ROLE_ARN` | worker | bootstrap outputs. The entrypoint turns them into profiles and removes the raw keys from the environment |
| `EKS_CLUSTER_NAME` | worker | cluster to log in to |
| `TF_STATE_BUCKET`, `TF_LOCK_TABLE`, `PERMISSIONS_BOUNDARY_ARN` | worker | bootstrap outputs |
| `OIDC_PROVIDER_ARN`, `OIDC_ISSUER` | worker | from step 2 |
| `CATALOG_URL` | worker | git URL of the blueprint repository (version tags) for rollouts; a private repo needs a read-only deploy token in the URL |

## Cloudflare

1. Add the domain to Cloudflare. DNS: `CNAME console -> <your-service>.onrender.com`, proxied (orange cloud). SSL/TLS mode: **Full (strict)**.
2. Zero Trust, Access, Applications, **Self-hosted**: hostname `console.<domain>`. Policy: allow your people (emails, or your identity provider's group).
   Copy the **Application Audience (AUD) tag**, and the **team domain** (`<team>.cloudflareaccess.com`).
3. Put those two values in the web service as `CF_ACCESS_AUD` and `CF_TEAM_DOMAIN`. Do not skip this: the app verifies the Cloudflare token itself,
   so the plain `onrender.com` address is useless without it. Cloudflare Access alone, without the app check, would leave that address open.
4. WAF: add a rate limit rule on `console.<domain>` (for example 100 requests per minute per IP) and turn on managed rules.
5. For automation (CI calling the API): create an Access **service token**, add a policy that allows it, and list its common name in `OPERATOR_EMAILS`.

## Roles

| Role | May |
|---|---|
| viewer | read environments, findings, rollout history |
| operator | request environments, scan, preview a rollout |
| admin | re-apply the blueprint, start a rollout, replace the rollout registry, read the audit log |

Every write is recorded in the audit log with who, what and when.

## Running costs to expect

Render web, worker, cron and Postgres each bill monthly; EKS bills a control plane fee plus nodes; S3, SQS, DynamoDB and Secrets Manager
are small. Do not rely on a number from this file: check current Render and AWS pricing, and set the AWS billing alert in step 1.

## First deploy: what is most likely to need a fix

- **IAM permissions.** The pipeline policy was written from the blueprint, not run against real IAM. Run one environment end to end; if
  `tofu apply` reports `AccessDenied`, add exactly the missing action and re-run. CloudTrail shows what was denied.
- **kubectl version.** Keep `KUBECTL_VERSION` in the Dockerfile within one minor version of the cluster.
- **Worker restarts.** Render stops a worker on every deploy. A job that was running is picked up again after its lease expires
  (up to 3 attempts); Terraform's state lock prevents two runs from overlapping. Avoid deploying while a rollout is running.
- **Rollouts need a catalog.** Set `CATALOG_URL` and import a registry (`PUT /rollout/registry`, or `python -m rollout registry-import FILE`).

## Operating it

- **Rotate the AWS key**: `aws iam create-access-key`, paste into Render, redeploy the worker, then delete the old key.
- **Back up**: use Render's Postgres backups. Terraform state is versioned in S3.
- **Logs**: Render logs show one line per request (method, path, status, who) and per job.
- **Local development** still works with no cloud: `make up`, then `make spaces` (SQLite, embedded worker, LocalStack, kind).
