# Architecture

The original proposal text that was here described a system that was not yet built. It is built now (locally, with a cloud deployment written but never run), so the architecture is documented in `docs/design/`:

| Document | Covers |
|---|---|
| [00 System overview](design/00-system-overview.md) | Whole system diagram, one environment, state locations, decisions |
| [01 Blueprint and modules](design/01-blueprint-and-modules.md) | Modules, inputs, size presets, request-to-resources flow |
| [02 Delivery pipeline](design/02-delivery-pipeline.md) | The ten pipeline stages, local and real-AWS modes, policy gate, drift, GitHub Actions |
| [03 Compliance-Ready Spaces](design/03-compliance-spaces.md) | Console, API, queue and worker, roles, 14 baseline controls and 42 extended checks |
| [04 Rollout Manager](design/04-rollout-manager.md) | Preview, canary, batches, rollback, pins, console and CLI |
| [05 Local environment and testing](design/05-local-environment-and-testing.md) | kind + LocalStack, test layers, testing the cloud build without a cloud |
| [06 Cloud deployment](design/06-cloud-deployment.md) | Render, Cloudflare, AWS, EKS: components, decisions, failure behaviour |

Also: [reference.md](reference.md) (settings, API, roles, jobs, commands), [../deploy/README.md](../deploy/README.md) (deployment runbook), [security.md](security.md), [HANDOFF.md](HANDOFF.md).
