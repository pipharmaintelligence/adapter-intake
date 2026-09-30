# PI-1965 — Pharma 0.1.6 Planner Reliability Checklist

Asset candidate: `nusaibah.pharma_company_intelligence_lab@0.1.6`

This checklist is development-only and is not part of promoted runtime bytes.

## Scope

- [x] New immutable asset version `0.1.6`.
- [x] Planner contract/chain moves to `1.0.2`.
- [x] Planner `max_tokens=8192`.
- [x] Planner `thinking_level=medium` unchanged.
- [x] Planner `response_format=json_object` unchanged.
- [x] Other seven Agent contracts/chains remain `1.0.1`.
- [x] No provider/model/provider-vault change.
- [x] No retry or failover policy change.
- [x] No input-role or binding-contract change.
- [x] No Fixed Skill identity/digest change.
- [x] No Dynamic Skill authority change.
- [x] No output/publication contract change.

## Shared-file coexistence

- [x] `agent_contract.py` unchanged from `0.1.5`.
- [x] `methodology_contract.py` unchanged from `0.1.5`.
- [x] `input_contract.py` unchanged from `0.1.5`.
- [x] `dossier_contract.py` unchanged from `0.1.5`.
- [x] `memory_contract.py` unchanged from `0.1.5`.
- [x] `adapter.dependencies.json` unchanged from `0.1.5`.
- [ ] Promotion P3 confirms no `shared_runtime_file_conflict`.

## Routed compact planner response and methodology learning

- [x] Python owns deterministic routing from the canonical dossier section registry.
- [x] `company_methodology` is declared as company-scoped read-only procedural memory.
- [x] `company_methodology_update` is declared as company-scoped mutable procedural memory.
- [x] Planner receives only the selected section's learned methodology slice.
- [x] Learned methodology cannot override Fixed Skill or current benchmark authority.
- [x] Learning candidate is built only after the evidence critic passes.
- [x] Preview mode never mutates methodology memory.
- [x] Apply mode uses one complete snapshot with expected-digest protection, fresh readback, and history verification.
- [x] Every mandatory research section is routed exactly once.
- [x] Known benchmark coverage becomes a deterministic priority hint.
- [x] Unknown priority may be selected by only that section-sized planner call.
- [x] Planner receives section/subsection TOC slice, section-scoped benchmark evidence, and bounded global methodology rules only.
- [x] Section response contracts declare compact list/text bounds.
- [x] Python merges section chunks into one complete methodology plan.
- [x] Final plan passes existing shared methodology validation plus stricter 0.1.6 compact bounds.
- [x] Existing reviewed `pharma_agent_business_schema_invalid` code is reused for compact-contract failures.
- [x] Strict JSON/business validation remains enabled.
- [x] No truncated response can be treated as successful by the merged Assets P0 runtime.

## Local/intake proof

- [ ] Syntax/import checks pass.
- [ ] Unit tests pass.
- [ ] Local-root import passes.
- [ ] Packaged dotted import is proven by promotion/package CI.
- [ ] `obs-adapter-intake-check --adapter-yaml adapters/nusaibah/pharma_company_intelligence_lab/adapter.yaml` passes.
- [ ] Repository-wide intake check passes.
- [ ] Exact intake commit SHA is recorded.
- [ ] Promotion dry-run/planner is ready.

## Remote proof after promotion

- [ ] Exact `0.1.6` governed Companies binding ready.
- [ ] Methodology planner `1.0.2` admission dry-run ready.
- [ ] Methodology planner `1.0.2` admission applied/no-change.
- [ ] Worker catalog resolves exact `nusaibah.pharma_company_intelligence_lab:0.1.6`.
- [ ] Company 13 preview reaches benchmark reviewer successfully.
- [ ] Company 13 preview reaches and completes methodology planner.
- [ ] Later roles are evaluated at their first live boundary.
