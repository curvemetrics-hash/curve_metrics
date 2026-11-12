# Curve Metrics — EB-1A Patent Adoption & Product Delivery Roadmap

**Planning baseline:** 12 November 2026  
**Patent reference:** German Utility Model No. 20 2025 107 185  
**Target platform:** Kubernetes (OpenShift is optional and not a delivery requirement)  
**Purpose:** Build a credible implementation and adoption record that may support an EB-1A petition.  
**Status:** Planning estimate, not a legal opinion or guaranteed immigration outcome.

## 1. Correct objective

This programme is designed to establish that the inventor's original work is being genuinely adopted and used, that the inventor's personal contribution is documented, and that the use produces measurable value.

**We do not need to implement or map every patent claim simply to document adoption for an EB-1A petition.** A claim-by-claim chart may be useful for a separate patent-coverage/legal analysis, but it is not the central deliverable of this adoption programme.

For EB-1A, the relevant possible criterion is 8 C.F.R. § 204.5(h)(3)(v): original scientific, scholarly, artistic, athletic or business-related contributions of major significance in the field. USCIS guidance recognizes patents, licences, testimonials and evidence of commercial use as potentially relevant evidence, but a patent or licence by itself does not necessarily establish major significance. The case must be supported by credible evidence of the work's significance and considered in the context of the whole petition, including the final merits determination.

This roadmap supports evidence-building. It does not determine eligibility. Immigration counsel should decide which EB-1A criteria the complete petition will rely on and how this evidence fits the overall case.

## 2. What success should look like

By the end of this programme, we want to be able to show:

1. The utility model exists, its legal/ownership status has been checked, and the inventor's role is documented.
2. The relevant company or companies have formally authorized and genuinely adopted the technology under valid written terms.
3. The platform is actually deployed and used in a real company workflow—not merely demonstrated locally or described in a proposal.
4. Contemporaneous records establish what the inventor personally designed, developed or led.
5. The company can explain why it selected the system, what problem it solved, how it is used and what changed.
6. Actual results are measured against a defensible baseline.
7. Knowledgeable decision-makers and, where possible, independent experts corroborate the contribution and its significance.
8. The evidence is consistent, dated, verifiable and suitable for review by immigration counsel.

Adoption by two organizations can strengthen the record, particularly where they are genuinely separate users with real operational use. Do not imply independent adoption if the organizations are affiliated, controlled by the same people or merely signing supportive letters without real use. Counsel should assess independence and evidentiary weight.

## 3. Existing product baseline

The current Curve Metrics repository is a useful local reference build. Repository documentation reports:
- Versioned standard-team blueprint and reusable Terraform modules.
- Kubernetes namespace, quotas, limits, network policies, role bindings and standard labels.
- Ten-stage provisioning script.
- Console, API, queue and worker.
- 14 baseline controls and 42 extended checks.
- Blueprint version rollout with preview, canary, batches and rollback.
- Reported local results: 19 module tests, 85 Python tests, 24 console end-to-end checks and 12 rollout-demo checks.

The repository also states that real AWS/EKS and hosted deployment have not been run, GitHub Actions have not been run, and company adoption has not yet occurred. These are repository-reported local results, not production/customer evidence.

For the EB-1A adoption objective, the immediate priority is not to add every advanced feature described in the patent. It is to turn the strongest existing capabilities into a secure, usable product, deploy it in a real environment and prove genuine use and impact.

### Product scope for the first adoption

Prioritize the smallest complete, valuable product slice:
- Self-service request for a standardized Kubernetes environment.
- Versioned Terraform/OpenTofu blueprint and reusable modules.
- Automated plan, validation, policy gate, approved apply and verification.
- Resource quotas, network policies, role bindings and standard labels.
- Post-provision checks and clear compliance/findings output.
- Blueprint re-application/rollout with preview and safe rollback where needed.
- Audit trail showing who requested, approved and executed each operation.

Do not delay adoption to build optional features such as a full graph compiler, signed OCI module registry, CRD/operator control plane, Merkle ledger, dedicated secret broker, ephemeral preview manager or adaptive cost optimizer unless a real adopter's use case requires them or counsel/technical review identifies a specific reason to prioritize them.

## 4. Evidence collection plan

### A. Patent and authorship
- Official registration certificate and register extract showing number, title, owner and status.
- Complete specification and drawings as context; claim chart only if needed for separate patent advice.
- Certified/appropriate translations if required by counsel.
- Inventorship/ownership records and signed licence or authorization.
- Dated design notes, architecture decisions, source-control history, commits, code reviews and technical materials demonstrating the beneficiary's own contribution.
- Clear distinction between the inventor's work and work performed by employees, contractors or other contributors.

### B. Formal adoption
For each adopting company, retain:
- Executed licence, assignment or permission agreement with exact scope, territory, term, permitted production/client use and consideration (including royalty-free terms where applicable).
- Signed adoption decision or internal approval by an authorized decision-maker.
- A specific statement of the business/technical problem that led to adoption.
- Architecture approval, implementation plan, accountable product/platform owner and intended users.
- Actual deployment record: environment, date, release/version, sanitized resource inventory and responsible team.
- Real request records, change tickets, CI/CD run IDs, plan/apply logs, verification outputs, audit records and usage history.
- Proof of ongoing use over time, not just a one-time demo.
- If applicable, contracts, purchase orders, invoices or other commercial records. Do not characterize a free internal licence as revenue or paid commercial adoption.

### C. Impact and significance
Establish a baseline before or at the start of real use. Measure after adoption:
- Request-to-ready time.
- Manual platform-team steps/hours per environment.
- Time to onboard a team.
- Number/percentage of environments conforming to the approved baseline.
- Provisioning failure rate and recovery time.
- Drift detection and remediation time.
- Security/configuration findings before and after.
- Infrastructure cost where reliable billing data is available.
- Number of teams, users, environments, repeated deployments and duration of use.

For every metric record definition, data source, sample size, measurement period, assumptions and responsible company owner. Compare like with like. Do not use kind/LocalStack laptop timings as a client baseline or production result.

### D. Corroboration by knowledgeable people
Obtain detailed letters from actual adopters and qualified experts. Good letters should explain:
- The writer's title, expertise and basis of personal knowledge.
- The company's actual prior problem and why existing approaches were inadequate.
- How the technology was evaluated and why it was selected.
- Which parts were actually deployed and how often they are used.
- The beneficiary's specific original contribution and role.
- Concrete operational results and why those results matter beyond a routine internal project.
- Whether the writer is independent or has a relationship/interest in the beneficiary or company.

Letters should be corroborated by dated technical and business records. Generic praise, unsupported superlatives or letters that say "adopted" without proof of use are weak.

### E. External recognition and overall EB-1A case
- Preserve independent publications, conference invitations, expert commentary, citations, awards, judging work, selective memberships, remuneration evidence or leading/critical-role evidence where genuinely applicable.
- Do not manufacture press, endorsements, usage or metrics.
- EB-1A normally requires a one-time major award or evidence meeting at least three of the listed regulatory criteria, followed by a final merits assessment. This project may support the original-contribution criterion and possibly other criteria only where the facts genuinely satisfy them.
- Coordinate the complete case strategy and evidence weighting with immigration counsel.

## 5. Delivery phases and target dates

### Phase 0 — Confirm legal basis and inventor contribution
**Estimate:** 1–2 weeks | **Target:** 12–25 November 2026

- [ ] Verify the official registration record, registered title, number, owner and current status.
- [ ] Confirm the supplied specification matches the registered document.
- [ ] Confirm inventor/contributor attribution and ownership chain.
- [ ] Locate and verify the executed Curve Metrics licence and any second-company licence/authorization.
- [ ] Confirm rights to use the invention in client, hosted and production deployments.
- [ ] Ask immigration counsel which EB-1A criterion/criteria this evidence is intended to support.
- [ ] Ask patent counsel about any separate ownership, licensing or patent-law issue; do not turn this into a requirement to chart every claim for EB-1A adoption.

**Exit:** Patent and licence documents verified; contribution narrative and evidence responsibilities identified.

### Phase 1 — Secure genuine adopters and define the pilot
**Estimate:** 2–3 weeks | **Target:** 26 November–16 December 2026

For each intended adopter (e.g. Curve Metrics and Abhishree Labs, if each genuinely intends to use it):
- [ ] Identify an authorized executive/platform decision-maker and actual operational sponsor.
- [ ] Hold a discovery session and document the real platform-engineering problem.
- [ ] Confirm whether the organization will use the system, where, for which teams and for what workflow.
- [ ] Agree the pilot scope, success measures, baseline, sample size and duration.
- [ ] Execute the correct licence/adoption/authorization documents before use.
- [ ] Identify security, data, cloud budget and infrastructure approvals.
- [ ] Record why the organization selected this technology and what alternatives were considered.

**Exit:** At least one real pilot sponsor, approved use case, signed use authorization and agreed measurement plan. A letter of intent alone is not adoption.

### Phase 2 — Productize the existing core for safe real use
**Estimate:** 6–9 weeks | **Target:** 17 December 2026–19 February 2027

- [ ] Remove all sample hardcoded API keys, sample accounts and plaintext password handling; enforce secure identity.
- [ ] Make production provisioning fail closed when OpenTofu/Terraform, cluster credentials, state backend or cloud prerequisites are missing; never simulate success in production.
- [ ] Enforce team/project-level authorization and least privilege.
- [ ] Implement a genuine independent approval step for production changes.
- [ ] Fix the request-to-Terraform path so selected blueprint/services are either honored or not presented as functional options.
- [ ] Harden CORS, CSP, CSRF protection, secrets handling, audit access and rate limits.
- [ ] Validate repeatable provisioning, idempotency, drift detection, failed apply and rollback.
- [ ] Run CI in the actual selected CI/CD provider; pin dependencies/actions and retain artifacts.
- [ ] Add useful operator logs, health checks, backups, restore and basic alerting.
- [ ] Create release notes, operator guide and security/deployment runbook.
- [ ] Keep a dated contribution record showing the beneficiary's design/engineering leadership.

**Exit:** Secure release candidate, automated tests passing, production simulation disabled, approval and access controls verified, deployment runbook ready.

### Phase 3 — Real Kubernetes pilot and first live use
**Estimate:** 4–6 weeks | **Target:** 22 February–2 April 2027

- [ ] Provision an approved non-production Kubernetes environment for the adopting organization.
- [ ] Deploy the release candidate using real state and approved credentials.
- [ ] Run actual, authorized environment requests from the adopter's workflow.
- [ ] Capture request, approval, plan, apply, verification and audit evidence.
- [ ] Test failure, rejected policy, drift and safe recovery.
- [ ] Onboard the first real team and record training/operational ownership.
- [ ] Capture first user feedback and resolve blocking issues.
- [ ] Record actual usage, environment count and measurement data.

**Exit:** First organization has genuinely used the platform for an agreed workflow; the adopter confirms acceptance; original records are retained.

**Target first pilot/live use:** March 2027, subject to adopter readiness and infrastructure approvals.

### Phase 4 — Production adoption and repeat use
**Estimate:** 4–8 weeks | **Target:** 5 April–28 May 2027

- [ ] Resolve pilot blockers and complete production security review.
- [ ] Obtain written production approval and confirm licence scope.
- [ ] Execute controlled production deployment with rollback tested.
- [ ] Move agreed team/environment workflows into real recurring use.
- [ ] If the second organization is a genuine adopter, deploy and document its own actual use separately.
- [ ] Capture recurring usage, release history, support records and business owner confirmation.
- [ ] Measure outcomes against the agreed baseline and preserve source data.
- [ ] Obtain signed adopter statements only after actual use; describe scope and dates accurately.

**Exit:** At least one controlled production use case with recurring use and verifiable outcomes. Second-adopter evidence is included only if separately real.

**Target first production go-live:** 3 May 2027 (planning target; may move with pilot results and approvals).

### Phase 5 — Demonstrate significance and independent corroboration
**Estimate:** 4–8 weeks, partly parallel with Phases 3–4 | **Target:** May–July 2027

- [ ] Produce before/after report with definitions, source data, sample sizes and period.
- [ ] Quantify actual teams, environments, users, usage frequency and duration.
- [ ] Obtain detailed letters from adopter executives and technical decision-makers.
- [ ] Obtain independent expert assessment where appropriate, based on reviewed technical and adoption evidence.
- [ ] Document why the contribution is original and why its impact is meaningful in the relevant platform-engineering field.
- [ ] Gather genuine external recognition, publication, conference or other relevant evidence if available.
- [ ] Keep conflicts, affiliations and relationships transparent.

**Exit:** Corroborated adoption and impact dossier, not merely a demo, patent certificate or generic recommendation letters.

### Phase 6 — EB-1A evidence pack and launch/continuity plan
**Estimate:** 3–5 weeks | **Target:** July–August 2027

- [ ] Organize patent, authorship, licence, implementation, adoption, metrics and expert evidence.
- [ ] Build a clear chronology of invention → development → licensing/authorization → adoption → impact.
- [ ] Document the beneficiary's personal contribution and leadership with contemporaneous evidence.
- [ ] Review consistency of names, dates, company relationships, licence terms and technical descriptions.
- [ ] Have immigration counsel map evidence to the selected EB-1A criteria and prepare the final merits argument.
- [ ] Prepare a realistic plan for continuing the work in the United States, supported by commitments or a concrete statement as counsel advises.
- [ ] Keep the product live and operating; schedule 30-day and 90-day post-launch reviews.

**Exit:** Counsel-reviewed evidence package and a documented continuing-work plan. Petition filing date is a legal-strategy decision, not a software milestone.

## 6. Schedule summary

| Milestone | Planning target |
|---|---|
| Patent/ownership/licence basis checked | 25 November 2026 |
| Adopter and pilot scope agreed | 16 December 2026 |
| Secure product release candidate | 19 February 2027 |
| First real Kubernetes pilot/live use | March 2027 |
| First production go-live | **3 May 2027** |
| Repeat/second-adopter use and measured impact | May–June 2027 |
| Adoption and impact dossier | July 2027 |
| EB-1A evidence package for counsel review | August 2027 |

### Time estimate and assumptions

- **First real pilot:** approximately 14–20 weeks from 12 November 2026.
- **First production use:** approximately 5–7 months from 12 November 2026.
- **Adoption/impact evidence package:** approximately 8–10 months from 12 November 2026.

Assumes 2–3 experienced engineers, with part-time QA/security/DevOps support; an adopter willing to participate; prompt execution of licence and approvals; and access to a real Kubernetes environment. If one developer performs most work, add roughly 2–4 months. If no company is ready to use it, the software can be built but adoption evidence and the adoption-dependent schedule cannot be guaranteed.

**These are project planning targets, not a prediction or guarantee of EB-1A approval.** Actual adoption dates depend on the organizations' decisions, contracts, infrastructure and use.

## 7. Evidence folder and record discipline

Suggested structure:

```text
docs/evidence/eb1a-adoption/
  00-patent-ownership-and-licence/
  01-inventor-contribution/
  02-adopter-discovery-and-approvals/
  03-baseline-and-success-measures/
  04-design-and-development-history/
  05-release-and-security/
  06-kubernetes-pilot/
  07-production-adoption/
  08-usage-and-impact-metrics/
  09-adopter-letters/
  10-independent-expert-evidence/
  11-external-recognition/
  12-counsel-review/
```

For each evidence item record date, source, owner, context, version/commit and relevance. Retain original records. Redact credentials, secrets, personal data and confidential client details in external copies. Do not create retrospective or fictional logs, usage, metrics, adoption letters or approvals.

## 8. Risks and controls

| Risk | Control |
|---|---|
| Signed agreement but no real use | Require actual deployment and recurring workflow evidence before calling it adopted |
| Patent alone presented as major significance | Corroborate with real use, impact, expert explanation and external recognition where available |
| Related companies described as independent adopters | Disclose ownership/affiliation and let counsel assess weight |
| Free licence described as commercial revenue | Accurately describe royalty-free or internal use; do not claim sales |
| Generic letters | Require specific first-hand basis, detailed use, impact and corroborating records |
| Local emulation presented as client deployment | Label kind/LocalStack as local tests only |
| Weak link to the beneficiary | Preserve inventorship, design decisions, commits, reviews and leadership evidence |
| Security problems block production | Fix credentials, authorization, approval and fail-closed behavior before live deployment |
| EB-1A case relies on only one criterion | Counsel should assess the entire petition and at least three regulatory criteria or a qualifying one-time achievement, plus final merits |

## 9. Weekly governance

- Weekly product/adoption review: delivery, pilot, blockers, evidence and schedule.
- Weekly evidence check: original records saved and indexed.
- Monthly adopter review: actual usage, value, incidents and next adoption scope.
- Every release: commit, tests, approvals, deployment record and rollback plan.
- No adoption claim until real use can be corroborated.
- No EB-1A eligibility or approval promise; counsel owns legal strategy.

## 10. Weekly status template

| Field | Current value |
|---|---|
| Reporting date | 12 November 2026 |
| Current phase | Phase 0 — legal basis and inventor contribution |
| Patent/ownership verified | Pending confirmation |
| Executed adopter licence(s) | Must verify |
| Adopter sponsor(s) | To confirm |
| Product baseline | Local reference build |
| First pilot target | March 2027 |
| First production target | 3 May 2027 |
| EB-1A evidence package target | August 2027 |
| Main blockers | Confirm patent/licence record, adopter commitment, staffing and Kubernetes environment |

---

**Planning conclusion:** Focus first on making Curve Metrics safe and usable, then obtain genuine organizational adoption and prove the impact with contemporaneous records. A concise technical explanation of how the adopted product relates to the patented work is useful; exhaustive claim mapping is not the goal of this EB-1A adoption programme.
