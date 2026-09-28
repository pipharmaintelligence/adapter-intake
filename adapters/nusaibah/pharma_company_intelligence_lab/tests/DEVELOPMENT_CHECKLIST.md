# PI-1951 / PI-1954 — 0.1.1 Admission-Correction Checklist

Asset candidate: `nusaibah.pharma_company_intelligence_lab@0.1.1`

This file is development-only and excluded from promoted runtime bytes.

## Why 0.1.1 exists

`0.1.0` was successfully validated, promoted through the documented workflow, and merged into Assets. Remote Agent admission then exposed an immutable-package defect:

- all eight roles referenced shared registry identity `provider:text_generation@1.0.0`;
- the methodology planner used registry metadata `pi_1954_adaptive_methodology_planner`;
- the other seven roles used `pi_1951_pharma_company_intelligence_lab`;
- the established Assets shared registry uses `pi_1895_capability_lab`;
- current Assets admission treats registry metadata as identity-significant and correctly returned `agent_runtime_provisioning_conflict`.

Because the fix changes immutable manifest bytes, the correction is `0.1.1`. Do not rewrite `0.1.0`.

## Non-negotiable 0.1.1 compatibility rules

- [x] `adapter.yaml` version is `0.1.1`.
- [x] Manifest default is `0.1.1`.
- [x] Intake manifest carries only current version `0.1.1`; Assets materialization must preserve published `0.1.0`.
- [x] All eight roles reuse one byte-equivalent `provider:text_generation@1.0.0` registry entry.
- [x] Shared registry metadata is canonical: `provisioning_source=pi_1895_capability_lab`.
- [x] Agent-specific provenance remains on chain metadata only.
- [x] Model, thinking, search, citation, provider-vault selectors, prompts, budgets, safety policy, and chain identities are unchanged from `0.1.0`.
- [x] Fixed Skill version/digest/bytes are unchanged.
- [x] Dynamic Skill roles and dossier output contract are unchanged.
- [x] No cross-company benchmark/ranking/scoring requirement exists; `[13,59]` is isolation/composition proof only.

## Runtime compatibility

- [x] Minimum runtime remains `pi-obs-python-runtime>=0.1.84`.
- [x] Developer proved local wheel `0.1.88`.
- [x] Current Assets admission service keys registry state by handle/version/owner and compares registry metadata.
- [x] Current Assets admission supports multi-Agent role selection and dry-run/apply.
- [x] Current Vertex transport supports declared Gemini models, thinking levels, JSON mode, and provider grounding.
- [x] Adapter code owns no credentials, direct provider transport, storage, Core calls, workers, or publication authority.

## Deterministic regression requirements

- [ ] Full deterministic suite passes after 0.1.1 changes.
- [ ] New test proves adapter.yaml == manifest default == sole intake version `0.1.1`.
- [ ] New test proves all eight registry entries are exactly canonical and byte-equivalent.
- [ ] New test proves chain-specific provenance remains outside shared registry metadata.
- [ ] Existing model/thinking/search policy tests pass unchanged.
- [ ] Existing Agent prompt/authority tests pass unchanged.
- [ ] Existing cross-company isolation and preview-zero-mutation tests pass unchanged.
- [ ] Existing expected-digest/readback/history safety tests pass unchanged.
- [ ] Local-root and packaged dotted imports pass.
- [ ] `git diff --check` passes.

## Local/intake certification

- [ ] Working tree is clean on the exact 0.1.1 RC SHA.
- [ ] Local HEAD equals remote branch SHA.
- [ ] `obs-asset-diagnose --quick` is ready.
- [ ] Single-adapter `obs-adapter-intake-check` is ready.
- [ ] Repo-wide `obs-adapter-intake-check --root .` is ready.
- [ ] `obs-asset-promote --precommit-status passed` reports `promotion_plan_ready`.
- [ ] Promotion plan copies exactly the reviewed adapter/helpers/support/Skill set.
- [ ] Portable Skill digest remains `sha256:2fa082aca1c100abb60a4bf77aa4cf796da2707bb951a3b51f11948efd2dd564`.

## Pinned Assets P8

- [ ] Dispatch `pi-obs-python-runtime.yml` with exact immutable 0.1.1 intake SHA.
- [ ] Materializer reports preservation of published `0.1.0` and addition of `0.1.1`.
- [ ] Manifest publication is green.
- [ ] Runtime catalog publication is green.
- [ ] Packaged adapter import tests are green.
- [ ] Portable Skill digest portability is green.
- [ ] Wheel/sdist build is green.
- [ ] Archive inspection and forbidden-content scan are green.
- [ ] ECS parity/evidence checks are green where applicable.
- [ ] Full required Assets CI is green.

## Promotion

Only after every local/intake/P8 gate above is green:

- [ ] Dispatch `adapter-intake-promote-pr.yml` with exact 0.1.1 RC SHA.
- [ ] `allow_manifest_removals=false`.
- [ ] Review generated Assets PR only; do not recreate it manually.
- [ ] Confirm generated package preserves `0.1.0` and adds `0.1.1`.
- [ ] Require all relevant Assets PR CI green.
- [ ] Merge/deploy exact `0.1.1`.

## Remote admission — first post-deploy proof

Run dry-run for all eight roles on `0.1.1`:

- [ ] methodology_planner -> ready.
- [ ] portfolio_researcher -> ready.
- [ ] market_researcher -> ready.
- [ ] regulatory_risk_researcher -> ready.
- [ ] strategic_analyst -> ready.
- [ ] evidence_critic -> ready.
- [ ] intelligence_synthesizer -> ready.
- [ ] memory_benchmark_reviewer -> ready.

Then apply:

- [ ] all eight roles -> `applied` or `no_change`.
- [ ] do not use `--update-existing` merely to suppress a conflict.
- [ ] no credentials/provider secrets cross into package or logs.

## Live proof after admission

- [ ] one primitive provider Agent execution succeeds.
- [ ] each search-enabled researcher succeeds independently.
- [ ] Fixed Skill delivery succeeds.
- [ ] Dynamic Skill read succeeds.
- [ ] one-company complete composition succeeds.
- [ ] `[13,59]` preview succeeds with zero cross-company contamination and zero mutations.
- [ ] controlled same-company Dynamic Skill apply/readback/history succeeds.
- [ ] dossier publication is proven separately.

## Release verdict rule

`0.1.1` is not LIVE_PROVEN merely because local tests, P8, promotion, or admission are green. Record each maturity dimension independently in PI-1954.
