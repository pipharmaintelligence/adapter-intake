# Clinical consumer 0.1.1 - implementation checklist

Only this clinical asset and its scoped CI workflow are changed on PR #143.
The source adapters are not changed or tested as providers by this work.

## Implemented in the intake consumer

- [x] Keep version 0.1.1, exact input ownership and source-event compatibility.
- [x] Optional binding-owned prepared evidence bundle; no nested callable or raw transport forwarding.
- [x] Exact source key/version/output and result-integrity validation before paid work.
- [x] ClinicalTrials.gov protocol/results/arm-group separation and NCT candidate handling.
- [x] PubMed PMID metadata/abstract join, date precision and publication notice qualification.
- [x] UMLS separate candidate terminology; no automatic clinical equivalence or class assignment.
- [x] Bounded complete source windows, explicit omissions and original source pointers.
- [x] Grounded/HTTP fallback skips source families already supplied; source APIs remain external.
- [x] Zero-Agent/zero-Skill input preflight.
- [x] Protocol endpoints cannot prove observed efficacy; comparator context cannot prove case outcomes.
- [x] Scope-safe critic packets, original strict validators and valid-sibling containment.
- [x] Trusted SDK output-limit exhaustion produces unresolved work; no truncated JSON or paid replay.
- [x] Canonical product/trial/source/terminology graph with no asserted causal edge.
- [x] Product paragraph delta remains the only memory proposal; multi-product attribution defers edits.
- [x] Explicit scientific/business disposition, evidence questions and no invented success probability.
- [x] Memory decision metadata independent of optional report rendering; no claimed durable journal.
- [x] Schema, prompt hash, package closure, local/isolated import and synthetic fault regressions.

## Deliberately unchanged / awaiting your parallel validation

- [ ] Validate ClinicalTrials.gov, PubMed and UMLS source adapters and live source roles.
- [ ] Qualify the runtime-owned prepared-result handoff and exact binding to this asset.
- [ ] Prove the actual installed runtime, source/model admission and signed child composition.
- [ ] Extend source-specific operations only after their owning adapters validate them.
- [ ] Complete clinical subject/arm attribution review for multi-product events.
- [ ] Validate historical registry snapshots for retrospective as-of investigations.
- [ ] Qualify canonical result retention, worker-loss recovery and retained-source references.
- [ ] Qualify product Skill initialization/CAS/apply, receipt, readback and history; apply remains off.
- [ ] Scientifically adjudicated real case set and downstream calibrated prediction, if later required.
- [ ] Promotion, merge, deployment, ECS, UI and provider configuration: outside this task.

A green fixture is not proof of scientific truth, source availability or durable
persistence. See VERIFICATION.md for the exact run evidence and remaining gates.
