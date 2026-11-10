# Decision log

Record each decision with its date, who made it and why. Add new entries at the top.

| Date | Decision | Made by | Why |
|---|---|---|---|
| 2026-11-06 | Deploy the console, worker and database on Render, behind Cloudflare Access, with real AWS and EKS behind it | Dharmendra (the choice of Render and Cloudflare); the design details were proposed by Claude | The build had to leave one laptop. **This replaces the earlier "no hosted service, near-zero cost" decision for the console.** The weekly demo on GitHub Actions can still run at near-zero cost |
| 2026-11-06 | The web service holds no AWS credentials; a separate worker does | Proposed by Claude | A flaw in the public service must not reach AWS |
| 2026-11-06 | The app verifies the Cloudflare token itself | Proposed by Claude | The `onrender.com` address is public; trusting "it came through Cloudflare" would leave it open |
| 2026-11-06 | Every team IAM role carries a permissions boundary | Proposed by Claude | Otherwise the pipeline role could create a role more powerful than itself |
| 2026-11-06 | Keep the 14 baseline controls as the only thing that decides `compliant`; add 42 severity-rated checks beside it | Dharmendra asked for wider checks; the split was Claude's | Existing meaning and tests stay stable, and new findings do not silently change old results |
| 2026-11-06 | Postgres for shared state, SQLite locally, no migration tool yet | Proposed by Claude | One code path for both; a migration tool can wait until the schema changes |
| 2026-11-05 | Kubernetes alone is enough; OpenShift optional | Dharmendra, as recorded in the handoff | The title reads Kubernetes or OpenShift |
| 2026-11-05 | Title-level alignment is accepted | Dharmendra, as recorded in the handoff | The claims text was unavailable |
| 2026-11-05 | Build the Blueprint Rollout Manager on top of Compliance-Ready Spaces | Dharmendra, as recorded in the handoff | A real, reusable problem: moving many environments to a new standard; not someone else's idea |
| 2026-11-05 | Reject Sentinel, self-healing pipeline and a stand-alone compliance product as themes | Dharmendra, as recorded in the handoff | Not the owner's own idea, or too little value alone |
| 2026-11-05 | Zero-cost operation: public repo, GitHub Actions, no hosted service | Dharmendra, as recorded in the handoff | Six months of upkeep at near-zero cost. **Superseded for the console on 2026-11-06 (see above)** |
