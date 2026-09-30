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

## Compact planner response

- [x] Provider-visible contract declares compact list/text/total bounds.
- [x] Adapter enforces the same limits after shared methodology validation.
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
