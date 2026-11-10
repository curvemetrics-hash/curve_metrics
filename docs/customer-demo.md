# Showing it to a customer, and how they use it

This is a local reference build (kind and LocalStack). Say so in the first minute. Do not say it implements the utility model claims, and do not call a demo "adoption". See `docs/HANDOFF.md` section 2.

## Run the demo (about 15 minutes of prep)

```bash
make up                          # LocalStack and kind, once
make rollout-demo                # optional: fills the Rollouts tab with real run history (about 10 min)
make spaces                      # the console at http://127.0.0.1:8080
```

Put the console on a shared screen. Have one terminal open next to it.

## A 15-minute walk-through

| Minute | Show | Say |
|---|---|---|
| 0-2 | **How it works** tab | A team asks for an environment with five fields. Everything else is the standard. |
| 2-6 | Request `demo-dev` in **Environments**; watch the ten pipeline stages light up | Format, tests, plan, policy gate, apply, verify. About a minute locally. |
| 6-8 | Open the finished environment: 14 controls, all pass | Default-deny network, quota, encrypted bucket and queue, least-privilege role. These are engineering checks, not a certification. |
| 8-10 | Request a bad one, for example admin group `*` (`local/fixtures/bad-wildcard-admin.tfvars`) | It is rejected at the policy gate, before anything exists. |
| 10-12 | In a terminal, delete the network policy with `kubectl`; press **Scan**; then **Re-apply blueprint** | Drift is detected and put back. |
| 12-15 | **Rollouts** tab: pick a version, **Preview changes**; show the history of a canary failure with rollback and a blocked preview | A new blueprint version goes to a canary first. A failure rolls back and stops. Pins move only after verification. |
| optional | **Activity** tab | Who requested what, and what the worker is running. Every write is recorded. |

## How a customer's teams use it

1. **Operator (an application team member):** asks for an environment through the console, the API (`POST /spaces`), or a pull request with one settings file. They get a namespace, limits, network policy, role bindings and their AWS resources.
2. **Platform team (admins):** owns the blueprint. They change it once, publish a version, and use the Rollouts page (or `python3 -m rollout preview <version>`, then `rollout <version>`) to move all environments.
3. **Reviewer or auditor (viewer):** opens the console to see which environments are healthy, what is open and when each was last checked. Admins can read the audit log.

## What is not ready for a customer yet

- **Hosting:** the cloud deployment (Render, Cloudflare, AWS) is written and tested locally but has never run. Until it does, a customer sees a screen share of the local build. Login exists in the code and is only tested with generated keys.
- **Real platform:** nothing has run on OpenShift, real AWS or GitHub Actions.
- **Controls:** the 14 baseline controls and 42 checks are not mapped to CIS, SOC 2 or ISO. Several checks fail on a fresh environment because the blueprint lacks the feature (see `docs/compliance-spaces.md`); explain that before they ask.
- **Baseline:** local timings are not their baseline. Measure how long an environment takes them today.
- **Retire and per-team permissions:** not built.
