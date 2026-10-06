# Pharma evaluation: frozen replay and supplied-source preview

Current development candidate: **0.2.2**, using unique literal quote selection and the shared `nusaibah.structured_review_toolkit:0.1.1` to compute exact spans. It preserves specialized parallel reviewers, strict provenance, sequential semantic verification and finite controls. Historical 0.2.0/0.2.1 retain their model-offset contracts. See [quote-candidate developer guide](DEVELOPER_GUIDE.md#quote-selection-candidate-022) for result schemas, offline evaluation and official promotion order. Source tests and installed-runtime bridge proofs do not establish live admission, measured quality or WP1 completion.

This development-only asset retains the frozen execution boundary in PI-1988. Version 0.2.0 adds a separate synthetic supplied-source company review; its result is not comparable to the frozen baseline. See [SUPPLIED_SOURCE_REVIEW.md](SUPPLIED_SOURCE_REVIEW.md) for evidence rules, the bounded model, commands and rollout gates. It replays one synthetic company case through the pinned `0.1.12` business executor using runtime-owned Agent and Fixed Skill authority. Frozen replay does not establish WP1 baseline measurements. The new lane is a narrow preview capability, not completion of the specialized-review plan. The design and delivery gates remain in PI-1972.

## Baseline and discovery boundary

- Baseline intake commit: `21cc6b39492cbd3c090de537a2ee27c599f0f0ec`.
- Baseline asset/runtime: `nusaibah.pharma_company_intelligence_lab@0.1.12` / `0.1.97`.
- Current intake candidate: `nusaibah.pharma_company_intelligence_lab_evaluation@0.2.2`; supplied-source `0.2.0`/`0.2.1` and frozen replay `0.1.0`, `0.1.1`, `0.1.2` remain available.
- The frozen executor is an ordinary Python component. Its only structural differences from the baseline are removal of the runtime `Adapter` import and inheritance. An AST parity test checks every remaining executable statement; helper contracts, Agent definitions, provider policies, budgets and Fixed Skill declarations must match the baseline.
- Only the declared versioned evaluation wrappers inherit `Adapter`. Package-relative imports support the materialized namespace; scoped external-root loading uses a flat import fallback. Importing replay code must not modify `sys.path`.

## Input and authority

Version 0.1.2 also requires `variables.execution_purpose=diagnostic_baseline_replay`; a positive web-smoke purpose is blocked before Agent/Skill calls. See [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) for no-provider preflight and deployment order.

Accept exactly one `evaluation_case.records` entry with `case_id`, `mode=company_research` and bounded synthetic `source_units`; `variables` contains only `case_index` (0â€“23). Expected answers, adjudication/threshold data and caller authority are rejected. The delegate supplies trusted `invoke_agent` and the exact pinned Fixed Skill. The wrapper forces preview, provides neutral synthetic read-only memory, and rejects mutable Dynamic Skill roles. It does not publish output artifacts.

## Required proof and next gates

1. Run promotion-shape, full pharma and evaluation packaging tests in intake CI.
2. Materialize the exact reviewed intake commit in an isolated Assets checkout. Run the existing P5 package tests, build wheel/sdist, inspect and scan them, then import the complete installed wheel without an asset-directory path workaround. Verify one production `0.1.12` identity, all six evaluation identities and both toolkit identities. The 0.2.2 parent and its exact 0.1.1 child must ship together.
3. Promote through the official workflow after source review/merge; package validation must pass before downstream reconciliation or PR creation. Do not hand-edit generated Assets modules or catalogs to bypass P5.
4. Prove exact registration, baseline-equivalent Agent admission, Fixed Skill digest and trusted worker authority. The designated synthetic fixture cannot establish positive public-web research completion. Keep the positive/no-write gate open until a separate admission/acceptance decision is reviewed; do not launch the remaining ten cases merely because diagnostic execution works.
5. Record source-backed observations in PI-1985/PI-1987. The thirteen document cases remain `not_executable`; eleven company executions alone do not satisfy the current all-24 WP1 completion gate. Resolve that comparability/scope decision explicitly rather than dropping cases or inventing measurements.

This candidate has not passed registration, live smoke, quality measurement or release gates merely because imports and tests succeed. Production `0.1.12` remains unchanged.


## Diagnostic revision 0.1.1

The new wrapper enables a closed diagnostic mapping outside the frozen executor.
The original 0.1.0 wrapper remains unchanged and does not enable it. No prompts,
models, Agent definitions, Fixed Skill, retries, deadlines, call limits, thresholds
or quality decisions change. Unknown errors and existing typed errors remain
untouched. A matching message from a runtime delegate is not sufficient: the
exception must originate in the exact pinned critic validator or quality function.

Safe failure codes are `pharma_evaluation_critic_schema_invalid` for invalid critic
business output and `pharma_evaluation_quality_rejected` for a valid negative quality
decision. The bounded `proof_failure_detail` contains role, stage, rule and optional
field identifier; it contains no response text, claim values, held-out answers,
provider credentials or raw exception prose. All six quality-stop rules remain
failures. The diagnostics do not turn a rejected review into a successful dossier.

Use runtime 0.1.98 or a reviewed successor with the matching allowlist fix.
Production baseline runtime 0.1.97 remains the historical measurement pin; record
0.1.98 separately as the diagnostic execution runtime and explicitly review that
difference before baseline replay. Frozen semantic and policy parity do not prove
identical provider runtime behavior. Do not overwrite the 0.1.97 artifact.

After both source changes are reviewed and promoted, verify the exact installed
wheel/hash, evaluation 0.1.1 registration and unchanged Agent/Skill admission.
Run one preview smoke, save its classified outcome and usage, and stop at the first
failure. Diagnose the rule before another launch. The positive PI-1988 smoke and
no-write evidence remain prerequisites for the other ten cases; neither CI nor
these diagnostics satisfies that gate. Keep twelve preview logical calls per
company, four planner iterations, three provider transport attempts per step,
the 1800-second task deadline and separate 60-second cleanup budget.

## Purpose preflight revision 0.1.2

The new version validates explicit diagnostic intent and bounded synthetic inputs before any Agent or Skill call. Projection compatibility is separate from positive web-smoke eligibility. Unsupported positive smoke requests fail with `pharma_evaluation_preflight_rejected`, stage `evaluation_preflight`; missing citations still fail through the unchanged frozen gate. Existing versions, frozen code, Agent/Skill declarations and finite budgets remain unchanged.

The runtime companion adds generic, text-free per-role citation observations to receipts, failed-run status/results and smoke output. Package the reviewed intake commit through the official materializer and install only the final artifact containing both changes. No new .env values or live provider retries are required. Follow [the developer guide](DEVELOPER_GUIDE.md) for proof lanes, commands, deployment gates and future source-review priorities.


## Result visibility in evaluation 0.2.1

Version 0.2.1 reuses the 0.2.0 supplied-source review engine and Agent contracts unchanged. Its required `evaluation_summary` object contains only the actual outcome, execution state, call and finding counts, and preview/publication/comparability flags. Source text, findings, evidence spans, case IDs, and entity IDs remain outside this summary.

Inspect the authorized result with `--output-role evaluation_summary`. This bounded projection is not full findings or independent external truth. `review_complete_with_evidence_gaps` remains a completed review with gaps; no quality gate is weakened.

Original evaluation versions and frozen production 0.1.12 replay remain available. Register/admit the exact new version after official Assets promotion, then verify the installed wheel catalog resolves 0.2.1. An old completed 0.2.0 run cannot acquire a business summary retroactively.

Future full-preview inspection requires explicit governed Core retention and authorized reference reads. Never copy source documents into PHP checkpoints or interpret workflow-state archives as full business results.
