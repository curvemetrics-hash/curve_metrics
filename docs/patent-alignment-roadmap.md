# Curve Metrics — Patent Alignment & Delivery Roadmap

**Patent reference:** German Utility Model No. 20 2025 107 185  
**Title:** System for Blueprinted Platform Engineering using Terraform Modules on Kubernetes/Openshift with CI/CD  
**Planning baseline:** 11 November 2026  
**Target platform:** Kubernetes. OpenShift is an alternative and is not a prerequisite for this plan.  
**Status:** Working engineering plan; dates are estimates, not commitments.

## 1. Objective

Evolve the existing Curve Metrics reference build into a tested, deployable platform whose implementation can be traced element-by-element to the supplied utility-model specification and Claims 1–10.

For each claim element, preserve this chain:

1. Exact requirement in the supplied specification/claim.
2. Architecture decision and component.
3. Source-code location and commit SHA.
4. Unit, integration, negative and recovery tests.
5. Runtime evidence from Kubernetes.
6. Dated evidence artifact and technical/legal review outcome.

This is an engineering roadmap, not a legal opinion. Source code, test results and similar component names do not by themselves establish that a legal claim is met. Patent counsel must review claim interpretation, legal status, ownership and licence scope.

## 2. Patent components and claim scope

The supplied specification identifies these components:

| Ref. | Component | Described responsibility |
|---:|---|---|
| 1 | Blueprint compiler | Type-checks/version-resolves blueprint components and creates an acyclic Terraform-module dependency graph |
| 2 | Module registry | Stores content-addressed module versions, signatures, attestations and compatibility metadata |
| 3 | Policy and compliance engine | Enforces compile-time, pre-provision and post-provision policy and environment overlays |
| 4 | Environment orchestrator | Coordinates graph-based Terraform lifecycle and Kubernetes Custom Resources/controllers |
| 5 | Drift/reconciliation engine | Compares desired, Terraform and live state; computes minimal graph-aware corrective plans |
| 6 | Secretless connection broker | Issues short-lived, identity-bound, just-in-time credentials |
| 7 | Provenance ledger | Retains linked blueprint, module, attestation, policy, plan, drift and runtime evidence in tamper-evident form |
| 8 | CI/CD pipeline controller | Controls signed/attested staged promotion and SLO-aware canary verification |
| 9 | Ephemeral sandbox manager | Creates branch-based preview environments and cleans them up on merge/expiry |
| 11 | Adaptive cost governor | Simulates plan cost and adjusts approved parameters within policy bounds |
| 12 | Multi-tenant isolation fabric | Described as an optional tenant-isolation component |

The supplied Claims section contains Claims 1–10. Claim 1 combines components 1, 2, 3, 4, 8, 5 and 7. Claims 2–10 add specific limitations/components.

Component 12 is described in the specification but is not a separate numbered dependent claim in the supplied Claims section. Track it as an optional product/specification scope item and ask counsel whether it matters to the intended interpretation. Do not invent a Claim 11.

Kubernetes is the selected implementation platform. OpenShift deployment is not a delivery gate.

## 3. Current repository baseline (reviewed 11 November 2026)

This is a working local reference build, not a production deployment. The statuses below are based on repository source and documentation; reported tests were not independently rerun for this roadmap.

| Patent component | Existing Curve Metrics foundation | Main gap |
|---|---|---|
| 1 Blueprint compiler | Versioned standard-team blueprint, typed Terraform variables, two composed modules | No dedicated compiler, component interface contracts, dependency graph generation, cycle detection or compatibility resolution |
| 2 Module registry | Git-based catalog, version tags and version materialization | No enforced content-addressed registry, cryptographic signature verification or required attestations |
| 3 Policy engine | Plan policy gate, 14 baseline controls and 42 extended checks, local post-provision scans | No unified compile/plan/runtime policy context, complete environment overlays, admission/topology/residency/cost gates |
| 4 Orchestrator | API, queue, worker, ten-stage script pipeline and Terraform state/apply | No graph-driven Kubernetes CRDs/controllers or operator reconciliation |
| 5 Drift engine | Terraform drift check, scheduled scans and blueprint re-apply/remediation jobs | No minimal graph-aware corrective sub-plan; re-apply may affect more than the impacted component |
| 6 Secretless broker | OIDC/IRSA-style service-account role wiring | No dedicated broker issuing just-in-time credentials to Terraform and CI/CD; real IAM/OIDC is untested |
| 7 Provenance ledger | Database audit events, job records, scan history and rollout history | Mutable database records; no demonstrated append-only/hash-linked ledger connecting all required artifacts |
| 8 CI/CD controller | Ten-stage local pipeline; rollout preview, canary, batches and rollback | GitHub Actions not run; signing/attestation is not enforced; canary is not SLO-driven workload promotion |
| 9 Ephemeral sandbox | Provisioning and rollout-preview foundations | No branch-created temporary environment with automatic merge/TTL cleanup and retained evidence |
| 11 Cost governor | Size presets and resource quotas | No provider-price simulation or policy-controlled parameter optimization |
| 12 Tenant isolation | Namespace quotas, labels, network policies and role bindings | No complete tenant identity-to-policy overlay fabric or cross-tenant isolation proof |

Repository documentation reports 19 module tests, 85 Python tests, 24 console end-to-end checks and 12 rollout-demo checks passing locally. It also states that real AWS/EKS, GitHub Actions, hosted deployment and company adoption have not yet occurred. These are repository-reported local results, not production evidence.

### Existing issues to address before client production

- Production authentication code contains sample hardcoded credentials/API keys and plaintext password handling; remove these and enforce secure enterprise identity.
- The worker can simulate successful pipeline stages when required tools/backend/cluster configuration is missing. Production must fail closed and label simulation distinctly.
- Approval behavior must be explicit; the local worker flow currently does not provide a second independent approver.
- Team-level authorization is not implemented.
- Request validation accepts blueprint/service choices that are not all passed through to the generated Terraform request.
- Real cloud IAM, workload identity, remote state, restore and hosted deployment behavior require verification.

Preserve the existing working prototype and extend it incrementally; do not replace it without a reviewed reason.

## 4. Delivery phases

### Phase 0 — Patent/document baseline and governance
**Estimate:** 1–2 weeks | **Target:** 11–24 November 2026

- [ ] Verify that the supplied specification is the exact registered/final version.
- [ ] Obtain/verify official DPMA register extract, registration documents and current status.
- [ ] Confirm owner/inventor information and executed licence terms, including permitted client/production/commercial use.
- [ ] Freeze a dated copy of the claims and drawings for engineering traceability.
- [ ] Ask patent counsel to confirm claim interpretation and representation limits.
- [ ] Separate mandatory claim elements from optional specification embodiments.

**Exit:** Official document set and licence basis verified; exact claim text selected; no unsupported claim-coverage statement.

### Phase 1 — Claim-to-code mapping and target architecture
**Estimate:** 1–2 weeks | **Target:** 25 November–8 December 2026

- [ ] Decompose Claim 1 and Claims 2–10 into individual testable elements.
- [ ] Create claim → component → code → test → evidence matrix.
- [ ] Mark each element: gap, implemented, locally verified, integration verified, live verified or client accepted.
- [ ] Assign an engineering owner and reviewer to each element.
- [ ] Define architecture decisions for compiler, registry, policy engine, orchestrator, CRDs/controllers, ledger and broker.
- [ ] Define contracts, event schemas, versioning, failure semantics and security boundaries.
- [ ] Select the production Kubernetes and CI/CD reference environment.
- [ ] Establish quality, security, performance, recovery and audit requirements.

**Exit:** Every element has an owner, implementation path, acceptance test and evidence requirement; target architecture approved.

### Phase 2 — Claim 1 core system, including detailed Claims 2–5
**Estimate:** 12–16 weeks | **Target:** 9 December 2026–30 March 2027

**2A. Blueprint compiler (component 1; Claim 2)**
- [ ] Define a typed, versioned YAML/JSON blueprint schema.
- [ ] Define component inputs/outputs, required/provided interfaces and parameter contracts.
- [ ] Resolve module/provider versions and compatibility metadata.
- [ ] Generate a normalized dependency graph and deterministic execution order.
- [ ] Reject unsatisfied interfaces, incompatible versions and cycles before apply.
- [ ] Produce reproducible compiler outputs and machine-readable diagnostics.

**2B. Signed module registry (component 2; Claim 3)**
- [ ] Select an OCI-compatible or equivalent module registry design.
- [ ] Store immutable/content-addressed module versions.
- [ ] Sign module artifacts and verify signatures before use.
- [ ] Generate/verify build provenance and attestations; select the required SLSA level.
- [ ] Store compatibility metadata and reject untrusted versions.
- [ ] Demonstrate reconstruction using pinned digests.

**2C. Unified policy engine (component 3; Claim 4)**
- [ ] Define policy bundles and environment classes (development, staging, production, regulated where applicable).
- [ ] Bind overlays to blueprint components and inject constraints before planning.
- [ ] Gate plans for quotas, topology, segmentation, encryption, residency and agreed controls.
- [ ] Verify post-provision Kubernetes admission/runtime posture.
- [ ] Return machine-readable decisions and status to orchestration.
- [ ] Keep policy decisions consistent across compile, plan, apply and runtime.

**2D. Kubernetes orchestrator (component 4; Claim 5)**
- [ ] Define CRDs such as Blueprint, BlueprintComponent and promotion/status resources.
- [ ] Implement Kubernetes controllers/operators to reconcile desired state.
- [ ] Coordinate graph-based Terraform init/plan/approval/apply/destroy.
- [ ] Expose phase, readiness, plan reference, errors and outputs through CRD status.
- [ ] Implement checkpoints, retries, locking, idempotency and partial-failure handling.
- [ ] Propagate admission/readiness failures back to orchestrator status.

**2E. Claim 1 vertical slice**
- [ ] Connect compiler, registry, policy engine and orchestrator end to end.
- [ ] Compile a real blueprint request, resolve signed modules, pass policy, create graph-ordered plans and provision Kubernetes resources.
- [ ] Test failures, reproducibility and pinned-version reconstruction.

**Exit:** Components 1–4 integrated; Claim 1 interfaces to components 5, 7 and 8 agreed and connected for an end-to-end vertical slice; Claims 2–5 have test evidence for their added limitations.

### Phase 3 — Remaining Claim 1 components and Claims 6–10
**Estimate:** 8–12 weeks | **Target:** 31 March–22 June 2027

**3A. Secretless broker (component 6; Claim 6)**
- [ ] Implement workload-identity/JIT exchange for CI/CD and Terraform providers.
- [ ] Issue least-privilege short-lived credentials scoped to an operation.
- [ ] Enforce expiry, rotation and revocation.
- [ ] Remove long-lived pipeline secrets where supported.
- [ ] Test denied, expired, revoked and cross-identity cases.

**3B. CI/CD controller and SLO progressive delivery (component 8; Claim 7)**
- [ ] Execute the actual CI workflow with protected environments and approvals.
- [ ] Sign source/build/module artifacts and verify attestations before promotion.
- [ ] Define SLOs and canary signals in the blueprint.
- [ ] Gate dev → staging → production promotion on policy, provenance and SLO evidence.
- [ ] Pause/rollback on threshold breach or missing evidence.
- [ ] Preserve promotion and rollback records in the ledger.

**3C. Ephemeral sandbox (component 9; Claim 8)**
- [ ] Create preview environments from branch/blueprint events.
- [ ] Isolate resources and credentials.
- [ ] Enforce TTL and cleanup on merge, branch closure or expiry.
- [ ] Retain lifecycle evidence after deletion.
- [ ] Test cleanup failures and orphan detection.

**3D. Graph-aware drift (component 5; Claim 9)**
- [ ] Compare blueprint intent, Terraform state and live Kubernetes/provider state.
- [ ] Map drift to dependency-graph nodes and edges.
- [ ] Calculate the smallest corrective subgraph and plan.
- [ ] Freeze unaffected nodes and respect maintenance windows/disruption budgets.
- [ ] Prove that only the selected subgraph changes.
- [ ] Test dependent and unrelated simultaneous drift.

**3E. Adaptive cost governor (component 11; Claim 10)**
- [ ] Integrate provider price catalog and versioned pricing inputs.
- [ ] Estimate cost from graph, module parameters and environment class before apply.
- [ ] Enforce cost envelopes and budget policy.
- [ ] Rewrite only approved tunable values within allowed ranges.
- [ ] Produce before/after plans and required approval records.
- [ ] Test price changes, budget overruns and infeasible requests.

**3F. Multi-tenant isolation (component 12; optional descriptive component)**
- [ ] Decide with product owner and counsel whether it is included in delivery scope.
- [ ] If included, bind tenant identity to namespace, network, storage and policy overlays.
- [ ] Prove cross-tenant isolation with positive and negative tests.

**Exit:** Selected Claims 1–10 features integrated with evidence. Component 12 is either separately tested or explicitly excluded; it is not a separate numbered claim in the supplied claims section.

### Phase 4 — Security, reliability and full-system verification
**Estimate:** 4–6 weeks | **Target:** 23 June–3 August 2027

- [ ] Remove hardcoded sample credentials and plaintext password handling.
- [ ] Enforce enterprise authentication, team-level authorization and least privilege.
- [ ] Prohibit production fallback to static credentials or simulated provisioning.
- [ ] Add dependency, container, IaC, secret and code security scanning.
- [ ] Pin CI actions/dependencies and verify artifact signatures.
- [ ] Test concurrency, retries, controller restarts, partial apply, rollback and disaster recovery.
- [ ] Test ledger integrity, retention, backup and restore.
- [ ] Add metrics, logs, traces, alerts and runbooks.
- [ ] Execute claim traceability tests, negative tests and failure/recovery cases.
- [ ] Obtain independent engineering/security review.

**Exit:** No unresolved critical/high security issues; integration tests, recovery and ledger-integrity checks pass; production runbooks and monitoring ready.

### Phase 5 — Real Kubernetes staging deployment and controlled pilot
**Estimate:** 4–6 weeks | **Target:** 4 August–14 September 2027

- [ ] Provision an isolated, approved non-production Kubernetes environment.
- [ ] Configure real remote state, locking, workload identity and module registry.
- [ ] Deploy compiler, controllers/operators, policy engine, ledger and services.
- [ ] Run real environment requests and staged promotions.
- [ ] Demonstrate policy rejection, drift repair, credential expiry and canary rollback.
- [ ] Capture a complete lifecycle from request through verified runtime state.
- [ ] Complete customer/platform acceptance tests.
- [ ] Record genuine baseline and post-implementation metrics; do not use emulator timings as client results.

**Exit:** Real Kubernetes pilot accepted by designated stakeholders; agreed acceptance criteria passed; no critical unresolved production blocker.

### Phase 6 — Production readiness, client acceptance and launch
**Estimate:** 3–4 weeks | **Target:** 15 September–12 October 2027

- [ ] Complete production security, architecture and operational reviews.
- [ ] Confirm SLOs, ownership, support, incident response and escalation.
- [ ] Validate backup/restore, rollback, access reviews and audit retention.
- [ ] Complete patent claim evidence pack and counsel review.
- [ ] Confirm client approval and contractual/licence permissions for production use.
- [ ] Execute controlled production rollout with tested rollback.
- [ ] Capture launch approval, release commit, deployment records and first production verification.
- [ ] Schedule 30-day and 90-day post-launch reviews.

**Exit:** Production acceptance signed, live environment verified, monitoring/support active, rollback tested and evidence pack complete.

## 5. Timeline and production target

| Milestone | Target |
|---|---|
| Patent/document baseline | 24 November 2026 |
| Claim matrix and architecture approved | 8 December 2026 |
| Claim 1 core vertical slice | March 2027 |
| Claims 1–10 feature implementation target | June 2027 |
| Security/full-system verification | Early August 2027 |
| Real Kubernetes pilot | August–September 2027 |
| Production launch readiness | September–October 2027 |
| **Target production go-live** | **5 October 2027** |
| Contingency window | October–November 2027 |

Planning estimates:
- Limited staging demonstration using current foundations: approximately 4–8 weeks; this is not complete claim implementation.
- Integrated Claim 1 technical demonstration: March 2027 target.
- Claims 1–10 feature-complete engineering: June 2027 target.
- Full production-capable implementation and evidence: approximately **46–50 calendar weeks** from 11 November 2026.

The baseline schedule assumes three experienced engineers (platform/backend, Kubernetes/controllers, infrastructure/CI-CD) with part-time QA, security and DevOps support; timely patent-counsel reviews; prompt decisions; and access to a client-approved Kubernetes staging environment.

If one developer performs most of the work, plan approximately 60–80+ weeks. Staffing, client access, scope and legal review can move the dates. **5 October 2027 is a planning target, not a guarantee.** Reforecast after Phase 1.

## 6. Evidence required to mark an element complete

For every claim element retain:
- Exact claim/paragraph reference and element ID.
- Architecture/design decision.
- Source path and immutable commit SHA.
- Relevant schema/configuration and module/artifact digest.
- Positive, negative and failure/recovery test cases.
- Raw test output and test environment/version.
- Runtime logs, Kubernetes snapshots/status and plan references.
- Signature/attestation verification where relevant.
- Provenance ledger entry and integrity verification.
- Reviewer, review date and pass/fail decision.
- Client acceptance where client use is claimed.

Suggested folder structure:

```text
docs/evidence/patent-alignment/
  00-patent-source/
  01-claim-matrix/
  02-architecture-decisions/
  03-compiler/
  04-module-registry/
  05-policy-engine/
  06-orchestrator/
  07-drift-engine/
  08-secretless-broker/
  09-provenance-ledger/
  10-cicd-progressive-delivery/
  11-ephemeral-sandbox/
  12-cost-governor/
  13-integration-tests/
  14-kubernetes-pilot/
  15-production-acceptance/
```

Never fabricate logs, dates, performance results, client use or approvals. Redact credentials, secrets and customer/personal data before external sharing.

## 7. Risks and decision gates

| Risk | Control |
|---|---|
| Supplied text differs from registered/final version | Verify official document before finalizing mapping |
| Optional description feature mistaken for claim limitation | Counsel and architecture review; separate mandatory claims from optional embodiments |
| Fixed Terraform composition mistaken for compiler | Require generated dependency graph and cycle/interface tests |
| Git tags mistaken for signed registry | Enforce content digest, signature and attestation verification |
| Mutable audit log mistaken for immutable ledger | Demonstrate append-only integrity and release reconstruction |
| Basic drift check mistaken for minimal graph repair | Prove corrective subgraph and freeze of unaffected components |
| Existing canary mistaken for SLO delivery | Use declared SLO metrics and automatic gate/rollback |
| Simulation reported as provisioning | Production must fail closed and label demos distinctly |
| Security defects block client rollout | Resolve authentication, authorization, credentials and least privilege before pilot |
| Client environment/approval delayed | Use internal controlled Kubernetes staging for engineering proof; do not claim client adoption until actual client use |

## 8. Ownership and cadence

Suggested roles:
- Technical lead/platform architect — architecture and claim traceability.
- Kubernetes/controller engineer — CRDs, operators and reconciliation.
- Infrastructure/CI-CD engineer — Terraform, registry, signing, identity and pipelines.
- QA/SRE — test strategy, runtime verification, observability and recovery.
- Security reviewer — identity, policy, supply chain and threat review.
- Patent counsel — claim interpretation, ownership, legal scope and licence.
- Client/platform owner — pilot acceptance, baseline and operational sign-off.

Cadence:
- Weekly engineering review: phase status, blockers, tests, evidence and forecast.
- Every claim element has an owner and reviewer.
- Every completed feature gets a pull request, tests and evidence record.
- Monthly steering review: scope, staffing, risks, cost, legal questions and launch forecast.
- Production requires explicit business, security, platform and client approval.

## 9. First 10 actions

1. Verify supplied specification against the official registered document.
2. Freeze and version the claims used for engineering traceability.
3. Confirm executed licence and permitted client/production use.
4. Build claim-by-claim element matrix for Claim 1 and Claims 2–10.
5. Review/fix production authentication and sample credentials.
6. Add production fail-closed behavior when tools, cluster or backend are missing.
7. Define blueprint schema and compiler acceptance tests.
8. Decide module registry, signing and attestation architecture.
9. Design CRD/controller lifecycle and provenance event schema.
10. Baseline current tests and create the evidence folder before code changes.

## 10. Weekly status template

| Field | Value |
|---|---|
| Reporting date | To update |
| Overall status | Not yet baselined |
| Current phase | Phase 0 |
| Claim elements formally accepted | None yet |
| Open blockers | Official registration confirmation; licence confirmation; claim matrix; staffing |
| Forecast go-live | 5 October 2027 planning target |
| Schedule confidence | Low until staffing, client environment and legal documents are confirmed |
| Evidence location | docs/evidence/patent-alignment/ |

---

**Planning conclusion:** Curve Metrics has a useful local reference implementation and several relevant foundations. Completing the supplied Claims 1–10 architecture is a substantial engineering programme. Use October 2027 as the baseline production target under the stated staffing assumptions, and reforecast after Phase 1.
