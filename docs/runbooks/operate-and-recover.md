# Operate and recover

**Status: the operations marked "built" work locally. The cloud runbook for the deployment itself is `deploy/README.md`.**

## Check an environment (operator)

Open it in the console and press **Scan now**, or wait for the daily scan. Fix findings from the top: high first. Each finding shows the evidence and a fix. A scan that says "could not be checked" means data was unavailable, not that the check passed.

## Put an environment back to the standard (admin) — built

Press **Re-apply blueprint** (shown when a baseline control fails). It re-runs the pipeline and restores everything the blueprint manages. **It does not remove objects added by hand**: a wildcard role binding created outside the blueprint is detected but stays until someone deletes it.

## Change an environment

Edit its request through the pipeline. Never change a managed environment by hand; a hand change shows up as a failed control or a drift finding.

## Move many environments to a new blueprint version (admin) — built

1. Publish the new version as a git tag in the blueprint repository.
2. **Rollouts**, choose the version, **Preview changes**. Read the result. If it says resources would be destroyed, stop and understand why.
3. **Start rollout**. The canary goes first and is verified, then batches. A failure rolls that environment back and stops the rollout; later batches are never touched.
4. Read the history. A pin moves only after an environment passes verification.

## Roll back a version — built

Start a rollout to the older tag. Rollback re-applies the earlier version; it cannot restore something changed outside the blueprint or data in a destroyed resource.

## Rebuild an environment

Not a button. Run the pipeline for its request against a clean namespace. A destroyed Secrets Manager secret stays in a recovery window and blocks reuse of its name until restored (also true on real AWS).

## Retire an environment — not built

There is no retire action in the console or API. Locally, `tofu destroy` with the request file does it (see `scripts/test_spaces_e2e.sh` cleanup). For real AWS, decide who may do this and add a gated action before relying on it.

## Detect hand changes

The daily scan (cron) compares live state to the standard. Locally `make drift-alpha` runs `tofu plan -detailed-exitcode`; exit 2 means drift.

## When something goes wrong

| Symptom | Look at |
|---|---|
| Environment stuck *Building* | **Activity**, queue: is a job running or failed? Worker logs show one line per job |
| *Rejected by policy* | **Pipeline** tab: the stage and the reason |
| Scan fails | the job's error in **Activity**: usually the cluster or AWS is unreachable |
| Console shows "Sign in required" | Cloudflare Access session expired; reload |
| A deploy interrupted a job | it is queued again after its lease (up to 3 attempts); avoid deploying during a rollout |
