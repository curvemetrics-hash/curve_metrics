# Blueprint Rollout Manager

**Status: built and tested locally (kind and LocalStack). Preview and start from the console and API are built and unit tested; the cloud path (real clusters, a remote blueprint catalog) has never run. No company uses it yet. Local results are not evidence of adoption.**

## The problem

A platform team keeps a standard blueprint for environments. The blueprint changes: security asks for a new rule, a default changes. Then someone has to update every existing environment. With 30 or 100 environments this is done by hand, partly, or not at all, and the environments drift from the standard.

## What it does

Every environment is pinned to a blueprint version (a git tag in the blueprint repository). To move to a new version:

1. **Preview:** show what would change in each environment, and change nothing. A preview that would destroy something stops the rollout unless the operator allows it.
2. **Canary:** apply to one environment first, then check it with the 14 compliance controls and the version label.
3. **Batches:** apply to the rest in batches, checking each. A failure rolls that environment back and stops the rollout, so later batches are never touched.
4. **Pins** move only after an environment passes its check.

## Where it runs

| How | Who can | Notes |
|---|---|---|
| Console, **Rollouts** page: pick a version, **Preview changes**, **Start rollout** | preview: operators; start: admins | queued as a job; the worker runs it; every start is audited |
| Command line: `python3 -m rollout ...` | whoever can run it | the same code, same shared state |

The registry (environments and their pinned versions) and the run history are stored in the shared database, not in files. Import a registry with `python3 -m rollout registry-import FILE` or `PUT /rollout/registry`. In the cloud the catalog is a git repository you name in `CATALOG_URL`; see `deploy/README.md`.

## Try it

```bash
make up                       # local cluster + AWS emulator
make rollout-demo             # 10 environments, a good release, a bad release (about 10 minutes)
python3 -m rollout --help
```

The demo builds a catalog with three releases: v1.0.0 (today's blueprint), v1.1.0 (log retention 30 to 90 days) and v1.2.0 (a regression that removes the default-deny network policy). Use your own catalog by setting `CATALOG_DIR` (a local path) or `CATALOG_URL` (a git URL, cloned by the worker) to any git repo containing `blueprints/` and `modules/` with version tags.

## Results (2026-11-05, local, one run each)

Logs: `docs/evidence/test-runs/rollout-demo-run.txt` and `rollout-demo-script-run.txt`.

| What | Result |
|---|---|
| Provision 10 environments (5 in parallel) | 115 s |
| Preview v1.1.0 across 10 environments | each shows 2 in-place changes, nothing destroyed |
| Roll out v1.1.0 to all 10 | 198 s, all verified, retention confirmed 90 |
| v1.2.0 without override | blocked by the preview (82 s); nothing changed |
| v1.2.0 with `--allow-destroy` | canary failed NET-1, rolled back; other 9 untouched; all 10 still on v1.1.0 and compliant |

Clean scripted run (`scripts/rollout_demo.sh 6`, 12 checks, 0 failed, exit 0): 6 environments provisioned in 72 s, v1.1.0 rolled out in 98 s, v1.2.0 blocked by the preview, then stopped at the canary and rolled back, with all environments left on v1.1.0 and compliant. Two earlier attempts of this script failed because a destroyed secret blocks reuse of its name (also true on real AWS, where it needs a restore before a forced delete); the demo cleanup now does that, for local use only.

**Re-run on 2026-11-06 after moving registry and runs to the shared store** (`scripts/rollout_demo.sh 6`, log `docs/evidence/test-runs/rollout-demo-store-2026-11-06.txt`): 12 checks, 0 failed, exit 0. 6 environments provisioned in 77 s; v1.1.0 rolled out in 143 s; v1.2.0 blocked by the preview, then stopped at the canary and rolled back, all environments left on v1.1.0 and compliant.

These are timings on a laptop with an emulator. They show the mechanism, not production speed. A real baseline (how long a change takes by hand) has to come from a company.

## Explaining it to users

- README: the problem in one paragraph, the 10-minute demo, the flow above.
- The demo output is the explanation: preview, canary, rollout, and a bad release being stopped.
- Audience: platform teams with more than about 10 environments. Adoption means forking the registry and pointing it at their own catalog and cluster.

## Running it for six months at near-zero cost (the demo path)

This describes the GitHub Actions demo only. The hosted console on Render has monthly costs; see `deploy/README.md` and `docs/decision-log.md`.


| Piece | Where | Cost |
|---|---|---|
| Code, registry, releases | public GitHub repository | $0 |
| Weekly demo run | GitHub Actions (free for public repositories) | $0 |
| Kubernetes | kind, created inside each run | $0 |
| AWS emulation | LocalStack, image version pinned | $0 (check its current licence terms) |
| Report | static `site/index.html` (artifact, or GitHub Pages) | $0 |

For this demo path there is no hosted service: users run the tool in their own CI against their own clusters. The hosted console is a separate, paid choice made on 2026-11-06.

Upkeep: pinned tool versions; the weekly workflow (`.github/workflows/rollout-demo.yml`) re-runs the whole demo so drift shows up within a week; changelog and semantic versions; about two hours a month to review failures and updates; the latest two versions supported.

## Known limits

- **The weekly workflow has not been run on GitHub.** `scripts/local-up.sh` was only tested on macOS with Colima.
- The rollout code was moved onto the shared store on 2026-11-06 and the scripted demo was re-run afterwards (below). Starting a rollout from the console, and the remote catalog, were not exercised end to end.
- Batch-failure handling (stop, roll back the failing environment, leave later batches alone) is covered by unit tests with a fake engine, not by a real failing batch. The real failure tested was at the canary.
- Rollback re-applies the previous version. If a change was applied outside the blueprint, or a resource was destroyed and had data, rollback cannot bring that back.
- Verification uses the 14 engineering controls, which are my own choices and not mapped to a published standard.
- Applies in the same batch run in parallel against one cluster and one emulator; larger fleets need a concurrency limit tuned to the real cluster.
- LocalStack does not enforce IAM; real AWS behaviour is untested.
