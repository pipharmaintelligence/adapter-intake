# Pharma baseline evaluation replay

This development-only asset implements the execution boundary in PI-1988. It replays one synthetic company case through the pinned `0.1.12` business executor using runtime-owned Agent and Fixed Skill authority. It does not establish WP1 baseline measurements or activate specialized review. The design and delivery gates remain in PI-1972.

## Baseline and discovery boundary

- Baseline intake commit: `21cc6b39492cbd3c090de537a2ee27c599f0f0ec`.
- Baseline asset/runtime: `nusaibah.pharma_company_intelligence_lab@0.1.12` / `0.1.97`.
- Evaluation identity: `nusaibah.pharma_company_intelligence_lab_evaluation@0.1.1`; retained `0.1.0` remains available.
- The frozen executor is an ordinary Python component. Its only structural differences from the baseline are removal of the runtime `Adapter` import and inheritance. An AST parity test checks every remaining executable statement; helper contracts, Agent definitions, provider policies, budgets and Fixed Skill declarations must match the baseline.
- Only the evaluation wrapper inherits `Adapter`. Package-relative imports support the materialized namespace; scoped external-root loading uses a flat import fallback. Importing replay code must not modify `sys.path`.

## Input and authority

Accept exactly one `evaluation_case.records` entry with `case_id`, `mode=company_research` and bounded synthetic `source_units`; `variables` contains only `case_index` (0–23). Expected answers, adjudication/threshold data and caller authority are rejected. The delegate supplies trusted `invoke_agent` and the exact pinned Fixed Skill. The wrapper forces preview, provides neutral synthetic read-only memory, and rejects mutable Dynamic Skill roles. It does not publish output artifacts.

## Required proof and next gates

1. Run promotion-shape, full pharma and evaluation packaging tests in intake CI.
2. Materialize the exact reviewed intake commit in an isolated Assets checkout. Run the existing P5 package tests, build wheel/sdist, inspect and scan them, then import the installed wheel without an asset-directory path workaround. Verify one production `0.1.12` identity and one evaluation identity per declared version (`0.1.0` and `0.1.1`).
3. Promote through the official workflow after source review/merge; package validation must pass before downstream reconciliation or PR creation. Do not hand-edit generated Assets modules or catalogs to bypass P5.
4. Prove exact registration, baseline-equivalent Agent admission, Fixed Skill digest, trusted worker authority and one no-write smoke case before the remaining ten company replays.
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
