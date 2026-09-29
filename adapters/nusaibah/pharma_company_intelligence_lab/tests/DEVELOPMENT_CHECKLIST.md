# PI-1951 / PI-1954 — 0.1.3 Governed Companies Binding Correction Checklist

Asset candidate: `nusaibah.pharma_company_intelligence_lab@0.1.3`

This file is development-only and excluded from promoted runtime bytes.

## Why 0.1.3 exists

`0.1.2` proved the Python orchestration ownership gate and loaded the reviewed adapter, but the live launch supplied a direct `companies` record. That bypassed the intended governed Assets/DLM input binding and therefore did not prove a fresh read from the database-backed company node.

The production contract is:

```text
caller variables.company_ids
        ↓
Assets governed input binding
        ↓
lake_id=test_database_lake
node_key=companies
        ↓
database PK column id
        ↓
resolved records envelope
        ↓
Python normalization
id -> company_id
company -> company_name
```

The manifest change and adapter-owned database-row normalization change the `0.1.3` package bytes, so the correction remains `0.1.3`; do not rewrite `0.1.2`. Shared reviewed helpers must remain compatible with retained published versions.

## Non-negotiable 0.1.3 contract

- [x] `adapter.yaml` version is `0.1.3`.
- [x] Manifest default and sole intake version are `0.1.3`.
- [x] `companies.required=true`.
- [x] `companies.source=binding`.
- [x] `companies.shape=object`.
- [x] `variables.required=true`.
- [x] `variables.source=direct`.
- [x] `variables.shape=object`.
- [x] Exact governed source is `test_database_lake / companies`.
- [x] Governed database identity column is `id`, not `company_id`.
- [x] Governed company-name column is `company`.
- [x] The versioned `0.1.3` adapter module normalizes `id -> company_id` and `company -> company_name` without changing retained shared-helper behavior.
- [x] Adapter rejects conflicting `id` / `company_id`.
- [x] Adapter preserves exact requested/resolved company-set parity.
- [x] Python owns no DLM/Core/database query.
- [x] Direct caller `companies` is forbidden by manifest/runtime ownership.
- [x] Fixed methodology Skill identity/version/digest/bytes are unchanged.
- [x] Dynamic Skill roles and dossier output contract are unchanged.
- [x] All Agent definitions/provider policies remain unchanged from `0.1.2`.
- [x] No cross-company benchmark/ranking/scoring requirement is introduced.

## DLM UI discovery proof

The current DLM UI Input Binding workspace loads Assets workflow-sequence and filters `io_descriptor.input_roles` for binding-capable roles.

Required post-promotion proof:

- [ ] Assets workflow-sequence projects `companies.source=binding`.
- [ ] Assets workflow-sequence projects `variables.source=direct`.
- [ ] DLM UI Input Binding modal offers `companies`.
- [ ] DLM UI does not offer `variables` as a governed binding role.

## Database row-filter boundary

The `companies` node schema uses ordinary database column `id` as its primary key. It is not a DLM partition key.

Current UI inspection shows the Input Binding request form authors `partition_filters_from_variables` from `schema_presentation.partition_fields`. Therefore:

- [x] Do not fake `id` as a partition field.
- [x] Do not encode `id <- company_ids` as a partition mapping merely to make the form green.
- [ ] Before live variables-only execution, prove the supported bounded row/data filter mapping for `id <- company_ids`.
- [ ] If the current UI cannot author that mapping, close the owning Assets/UI contract separately; do not push database/query logic into this adapter.

## Deterministic regression requirements

- [ ] Full pharma deterministic suite passes.
- [x] Test freezes adapter.yaml == manifest default == sole intake version `0.1.3`.
- [x] Test freezes `companies=binding/object`.
- [x] Test freezes `variables=direct/object`.
- [x] Test proves DB-shaped records `id/company` normalize to semantic `company_id/company_name`.
- [x] Test proves conflicting DB/semantic identity fails closed.
- [x] Test proves requested order is restored after governed resolution.
- [x] Test proves sensitive named fields are excluded from projected company baseline.
- [ ] Existing Agent contract tests pass unchanged except version constant.
- [ ] Existing preview/isolation tests pass with DB-shaped records envelope.
- [ ] Existing expected-digest/readback/history safety tests pass unchanged.
- [ ] Local-root and packaged dotted imports pass.
- [ ] `git diff --check` passes.

## Local/intake certification

- [ ] `obs-asset-diagnose --quick --adapter-root <pharma-root> --pretty` is ready.
- [ ] Single-adapter `obs-adapter-intake-check --adapter-yaml <adapter.yaml> --pretty` is ready.
- [ ] Repo-wide `obs-adapter-intake-check --root . --pretty` is ready.
- [ ] `obs-asset-promote --adapter-yaml <adapter.yaml> --precommit-status passed --pretty` reports `promotion_plan_ready`.
- [ ] Portable Skill digest remains `sha256:2fa082aca1c100abb60a4bf77aa4cf796da2707bb951a3b51f11948efd2dd564`.

## Promotion / package proof

Do not merge the adapter-intake PR as part of this work.

After review:

- [ ] Push exact RC SHA.
- [ ] Run pinned Assets validation/materialization against that SHA.
- [ ] Confirm existing published identities are preserved and `0.1.3` is added.
- [ ] Confirm packaged manifest exposes binding-owned `companies`.
- [ ] Confirm runtime catalog publishes exact `0.1.3`.
- [ ] Confirm portable Skill bytes remain unchanged.
- [ ] Confirm package/import/build/forbidden-content checks are green.
- [ ] Review generated Assets PR separately.

## Independent environment prerequisite

The immutable methodology Skill is locally valid but still requires governed publication in the target Assets/Core environment:

```text
nusaibah.pharma-intelligence-methodology@1.0.0
canonical package digest:
sha256:2fa082aca1c100abb60a4bf77aa4cf796da2707bb951a3b51f11948efd2dd564
```

This publication does not require another pharma asset-version bump because the Skill bytes are unchanged.

## Live proof order

Only after binding and Skill publication are ready:

- [ ] Launch variables-only `company_ids=[13]`.
- [ ] Prove governed `test_database_lake/companies` read selected exact DB row `id=13`.
- [ ] Prove `company_memory(company_id=13)` resolves independently.
- [ ] Prove Fixed Skill publication/delivery.
- [ ] Prove first benchmark Agent call.
- [ ] Prove planner/research/critic/synthesis.
- [ ] Prove preview returns zero mutations.
- [ ] Launch variables-only `company_ids=[13,59]`.
- [ ] Prove exact two-row retrieval and no cross-company contamination.
- [ ] Prove apply/readback/history separately after preview closure.

## Release verdict

`0.1.3` is not LIVE_PROVEN merely because the manifest becomes visible in DLM UI or the PR is green. Binding discovery, row-filter execution, Fixed Skill publication/delivery, Agent/provider execution, Dynamic Skill behavior, and final preview/apply behavior remain independent gates.