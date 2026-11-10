# Security

**Status: the controls below exist in code and are tested locally. The cloud deployment has never run, and the IAM policies have never been run against real IAM. This is not a security audit or a certification.**

## Controls built into every environment

- Default-deny ingress network policy; allowances only for the same namespace, the ingress controller and named namespaces.
- Resource quota and limit range on every namespace.
- Role bindings only for named groups. A wildcard group is refused at validation; `cluster-admin` and open subjects fail the policy gate and the baseline controls.
- Standard labels for ownership, team, environment and size.
- AWS side: private, versioned, encrypted bucket; encrypted queue; secret; log group with retention; a role limited to those resources. In real AWS the role also carries a **permissions boundary**, so it can never be made more powerful than the boundary allows.

The 14 baseline controls and 42 extended checks verify these continuously (`docs/compliance-spaces.md`).

## Who can do what

Login is Cloudflare Access. The app verifies the token itself (RS256 signature, issuer, audience, expiry); it does not trust a request because it arrived through Cloudflare. Without a valid token every call except `/healthz` returns 401.

| Role | May |
|---|---|
| viewer | read |
| operator | request environments, scan, preview a rollout |
| admin | re-apply, start a rollout, replace the registry, read the audit log |

Roles come from `ADMIN_EMAILS`, `OPERATOR_EMAILS` and `ACCESS_DEFAULT_ROLE`. Every write is recorded in the audit log (who, role, action, target, time). Permissions are not per team: any operator can scan any environment.

## Credentials

| Where | What | Notes |
|---|---|---|
| Web service | database URL, Cloudflare settings | **No AWS credentials at all** |
| Worker | keys of an IAM user that can only assume two roles | The entrypoint moves the keys into an AWS profile and removes them from the process environment, so tools use the assumed role |
| Pipeline role | creates and changes environments | Limited by resource-name patterns; may create roles only with the boundary attached; may not remove or swap the boundary; cannot read secret values |
| Read-only role | used for scans | Reads configuration only. The cluster side is `deploy/k8s/checker-readonly.yaml`: no secrets, no write verbs |
| Terraform state | S3 bucket, versioned, encrypted, TLS-only, private; DynamoDB lock | No access key is created by Terraform, so none lands in state |
| Repository | nothing secret | Secrets are entered in the Render dashboard |

Rotate the worker's key by creating a new one, updating Render, redeploying the worker and deleting the old key.

## Web hardening

- Content-Security-Policy allows scripts only from the app itself; no inline script. Also `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`, HSTS.
- Writes need the header `X-Requested-With: console`, which blocks cross-site form posts that would ride on the user's Cloudflare cookie.
- Request bodies over 64 KB are refused. Only three static files are served, by exact name.
- The console refuses to start without login on a public address.
- API responses are not cached. Errors never include stack traces.
- Add a Cloudflare rate-limit rule; the app has none of its own.

## What the checker never does

It never reads secret values (only that the secret exists), never writes, and in a real deployment uses the read-only role.

## Evidence and privacy

- Extracts shared outside Curve Metrics (for example for the licensor's records) are redacted: no secrets, credentials, personal data, internal hostnames or customer names.
- Each extract is approved in writing by Curve Metrics before it is shared.
- The audit log and scan results contain email addresses and environment names. Treat database backups accordingly.

## Known gaps

- **Never run on real IAM.** The pipeline policy was written from the blueprint; expect to add a missing action on first use.
- No per-team permissions; no rate limiting in the app; no migration tool for the database.
- LocalStack does not enforce IAM, so local runs prove configuration, not enforcement.
- The pipeline's approval stage is automatic in the worker (`AUTO_APPROVE=1`). Approval is the operator's request itself; there is no second reviewer.
- A viewer can read every environment's findings, which describe weaknesses.
- Access review cadence: [to confirm with the company]. Policy checks to enforce in CI beyond the plan gate: [to confirm].
