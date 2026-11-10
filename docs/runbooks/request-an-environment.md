# Request an environment

**Status: works locally and through the console. Not yet used by a real team.**

## Through the console (operators)

1. Open the console and choose **New environment**.
2. Fill in name, team, kind (dev, test, prod), size (small, medium, large) and admin groups.
3. The environment appears as *Building* with a 10-segment progress bar. Open it to see the pipeline stage by stage.
4. When it turns *Ready*, the **Findings** tab shows its first scan. The result is a grade (`healthy`, `needs attention`, `at risk`) plus the 14 baseline controls.

If the request breaks policy (for example a wildcard admin group), the status is *Rejected by policy*, the **Pipeline** tab shows the stage and the reason, and nothing was created. Fix the request and submit again with a new name.

## Through the API

`POST /spaces` with `{"name","team","environment","size","admin_groups"}`. See `docs/reference.md` for rules and the full API. Poll `GET /spaces/<name>` until `status` is `ready`.

## Through a pull request (pipeline only)

1. Copy `requests/_example.tfvars` to `requests/<team>-<environment>.tfvars`.
2. Set `team`, `environment`, `size`, `admin_groups` and any `allow_ingress_from_namespaces`.
3. Open a pull request. A platform reviewer checks the plan and approves.
4. On merge the pipeline applies the change.

The GitHub Actions workflow behind this path has never run; its plan and apply steps are placeholders. Use the console or API until it is wired to a real cluster and state backend.

## What the team receives

A namespace, quota, limits, network policy, role bindings for its admin groups, labels, and its AWS resources: bucket `<name>-data`, queue `<name>-events`, secret `<name>/app`, log group `/curve-metrics/<name>`, role `<name>-app`. A service account `app` and a ConfigMap `cloud-resources` hold the names for the workload.

## Metrics

Request time and ready time come from the pipeline (`seconds_to_ready` in the console). Locally they are laptop timings and mean nothing for a company. Record real ones from real requests only.
