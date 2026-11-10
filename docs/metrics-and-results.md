# Metrics and results

**Targets are hypotheses, not outcomes.** Fill the "Measured" column only with real, dated figures and say where they came from.

| Metric | Baseline (date, source) | Target | Measured (period, source) |
|---|---|---|---|
| Time from request to ready environment | [X] | [e.g. under 30 minutes] | to be measured |
| Manual steps per environment | [X] | [e.g. 0 to 1] | to be measured |
| Time to onboard a new team | [X] | [e.g. under 1 day] | to be measured |
| Environments differing from the standard | [X] | [e.g. 0] | to be measured |
| Platform-team hours per request | [X] | [e.g. under 0.5] | to be measured |

## How measured

- Request time and ready time come from pipeline timestamps. Locally they are written to the LocalStack metrics bucket; in a cloud deployment they are written to the shared database (`metric` records) and `seconds_to_ready` is shown in the console.
- Locally recorded figures come from a laptop with an emulator. They are not a baseline and not a result.
- Manual steps are counted from the old process and the new one by the platform lead.
- Sample size for each figure is stated next to it.

## Sample sizes

| Figure | Number of requests | Period |
|---|---|---|
| | | |

Report small samples honestly. A modest, verifiable result is better evidence than a large number that cannot be checked.
