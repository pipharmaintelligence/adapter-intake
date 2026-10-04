# Pharma baseline evaluation replay

This development-only asset implements the execution boundary in PI-1988. It replays one synthetic company case through the pinned `0.1.12` business executor using runtime-owned Agent and Fixed Skill authority. It does not establish WP1 baseline measurements or activate specialized review. The design and delivery gates remain in PI-1972.

## Baseline and discovery boundary

- Baseline intake commit: `21cc6b39492cbd3c090de537a2ee27c599f0f0ec`.
- Baseline asset/runtime: `nusaibah.pharma_company_intelligence_lab@0.1.12` / `0.1.97`.
- Evaluation identity: `nusaibah.pharma_company_intelligence_lab_evaluation@0.1.0`.
- The frozen executor is an ordinary Python component. Its only structural differences from the baseline are removal of the runtime `Adapter` import and inheritance. An AST parity test checks every remaining executable statement; helper contracts, Agent definitions, provider policies, budgets and Fixed Skill declarations must match the baseline.
- Only the evaluation wrapper inherits `Adapter`. Package-relative imports support the materialized namespace; scoped external-root loading uses a flat import fallback. Importing replay code must not modify `sys.path`.

## Input and authority

Accept exactly one `evaluation_case.records` entry with `case_id`, `mode=company_research` and bounded synthetic `source_units`; `variables` contains only `case_index` (0–23). Expected answers, adjudication/threshold data and caller authority are rejected. The delegate supplies trusted `invoke_agent` and the exact pinned Fixed Skill. The wrapper forces preview, provides neutral synthetic read-only memory, and rejects mutable Dynamic Skill roles. It does not publish output artifacts.

## Required proof and next gates

1. Run promotion-shape, full pharma and evaluation packaging tests in intake CI.
2. Materialize the exact reviewed intake commit in an isolated Assets checkout. Run the existing P5 package tests, build wheel/sdist, inspect and scan them, then import the installed wheel without an asset-directory path workaround. Verify one production `0.1.12` identity and one evaluation `0.1.0` identity.
3. Promote through the official workflow after source review/merge; package validation must pass before downstream reconciliation or PR creation. Do not hand-edit generated Assets modules or catalogs to bypass P5.
4. Prove exact registration, baseline-equivalent Agent admission, Fixed Skill digest, trusted worker authority and one no-write smoke case before the remaining ten company replays.
5. Record source-backed observations in PI-1985/PI-1987. The thirteen document cases remain `not_executable`; eleven company executions alone do not satisfy the current all-24 WP1 completion gate. Resolve that comparability/scope decision explicitly rather than dropping cases or inventing measurements.

This candidate has not passed registration, live smoke, quality measurement or release gates merely because imports and tests succeed. Production `0.1.12` remains unchanged.
