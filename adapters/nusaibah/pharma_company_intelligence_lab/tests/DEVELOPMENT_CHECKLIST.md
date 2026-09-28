# PI-1951 Release and Certification Checklist

Asset candidate: `nusaibah.pharma_company_intelligence_lab@0.1.0`

This file is development-only and is excluded from promoted runtime package bytes.

## Version policy

- Keep `0.1.0` unchanged while work remains only in adapter-intake and before the final Assets package PR is merged.
- Do not bump the adapter version for local test fixes, Agent-definition work, prompt/DTO refinement, CI fixes, or intake-package corrections made before publication.
- Do not open the final Assets promotion PR until **all PRE-PUBLICATION gates below are green**.
- Once `0.1.0` is merged/deployed as an immutable packaged identity:
  - bump to `0.1.1` only if the required fix changes adapter code, manifest, reviewed helpers, dependency contract, or portable Skill bytes;
  - do not bump for server configuration, ProviderVault, binding, admission, infrastructure, or provider-side fixes that leave package bytes unchanged.
- Track changing gate evidence in Linear PI-1951 so evidence updates do not churn package bytes.

# PRE-PUBLICATION RELEASE CANDIDATE — MUST ALL PASS BEFORE ASSETS PROMOTION PR

## P1. Product and contract completeness

- [x] Asset identity and package target fixed.
- [x] Batch contract uses bounded `company_ids`.
- [x] Governed Companies input is pre-resolved before remote Python execution.
- [x] Exact per-company isolation rules defined.
- [x] Canonical section/subsection IDs, titles, and order are adapter-owned.
- [x] Fixed methodology Skill package defined.
- [x] Dynamic Skill read/mutable roles declared.
- [x] Dossier file output is a separate lifecycle from runtime result and memory mutation.
- [ ] Final business-case output DTO fields are frozen for v0.1.0.
- [ ] Final prompt/role ownership for all seven Agents is frozen.
- [ ] Final memory-update policy and thresholds are frozen.
- [ ] Final publication behavior (preview/apply/publish) is frozen.

## P2. Runtime prerequisites

- [ ] PI-1952 merged in Assets.
- [ ] Runtime wheel containing PI-1952 released.
- [ ] `adapter.dependencies.json` minimum version updated to that released wheel.
- [ ] Development venv installed wheel matches required minimum.
- [ ] Gemini 3.8 Flash LOW/MEDIUM/HIGH thinking policy proven in runtime tests.
- [ ] Gemini 3.1 Pro high-thinking behavior remains regression-safe.

## P3. Seven packaged Vertex Agent definitions

- [ ] `portfolio_researcher` added and locally validated.
- [ ] `market_researcher` added and locally validated.
- [ ] `regulatory_risk_researcher` added and locally validated.
- [ ] `strategic_analyst` added and locally validated.
- [ ] `evidence_critic` added and locally validated.
- [ ] `intelligence_synthesizer` added and locally validated.
- [ ] `memory_benchmark_reviewer` added and locally validated.
- [ ] Search authority exists only on the three research roles.
- [ ] Non-search roles cannot introduce ungrounded public facts by contract.
- [ ] All Agent outputs use bounded structured JSON contracts.
- [ ] Model/thinking/max-output policy is explicit per role.
- [ ] Provider/model configuration remains runtime-owned, not caller-owned.

## P4. Adapter orchestration completeness

- [ ] Exact requested/resolved company-id parity enforced.
- [ ] Caller company order restored deterministically.
- [ ] Company context object is recreated per loop item.
- [ ] Cross-company Agent output rejected.
- [ ] Research fan-out joins evidence only within the same company.
- [ ] Strategic analysis consumes same-company joined evidence only.
- [ ] Critic runs before synthesis/mutation.
- [ ] Canonical DTO renderer is the only final section-title renderer.
- [ ] Phase 1 completes/validates all companies before any memory mutation.
- [ ] Preview mode cannot mutate.
- [ ] Apply uses expected digest.
- [ ] Fresh readback/history/change-id verification is required.
- [ ] Later-company apply failure never claims rollback of an already committed prior partition.
- [ ] Benchmark runs against the resulting/current memory only.
- [ ] Runtime result, memory mutation, and file publication statuses remain distinct.

## P5. Deterministic contract and regression tests

- [x] Empty/duplicate/non-integer/oversized company-id batches rejected.
- [x] Resolved company set must exactly equal requested set.
- [x] Caller order restoration tested.
- [x] Missing/unknown/duplicate/reordered sections rejected.
- [x] Missing/unknown/duplicate/reordered subsections rejected.
- [x] Provider-authored titles cannot change canonical titles.
- [x] Cross-company memory candidate rejected.
- [x] Local-root import passes.
- [x] Packaged dotted import passes.
- [ ] Cross-company Agent envelope rejected.
- [ ] Wrong Agent role/schema/company rejected.
- [ ] Malformed Agent JSON rejected.
- [ ] Missing mandatory evidence rejected.
- [ ] Unsupported-claim threshold tested.
- [ ] Contradiction/stale/missing-section critic paths tested.
- [ ] Content/item/token bounds tested.
- [ ] Preview-no-mutation tested.
- [ ] Apply expected-digest mismatch tested.
- [ ] Mutation receipt/readback/history mismatch tested.
- [ ] File-publication prepared != file-published tested.
- [ ] Full two-company fake-runtime fixture passes with zero external calls.

## P6. Local developer proof

- [ ] Syntax/import gate passes with selected project interpreter.
- [ ] Full deterministic unit suite passes.
- [ ] Fixture run for `[13, 59]` passes.
- [ ] Fixed Skill package validation passes.
- [ ] Portable Skill working-tree digest matches manifest.
- [ ] `obs-asset-diagnose --quick` passes for exact asset root.
- [ ] Local preflight passes.
- [ ] Forbidden package-content scan passes.
- [ ] No secrets, URLs, auth headers, storage paths, raw provider payloads, or raw OBS/Core responses exist in package.

## P7. Adapter-intake source-control gates

- [x] Single-adapter `obs-adapter-intake-check` passes.
- [x] Repository-wide `obs-adapter-intake-check --root .` passes.
- [x] Local-root import proof passes.
- [x] Packaged dotted import proof passes.
- [x] Portable Skill digest verified from exact committed Git bytes for the then-current foundation commit.
- [x] Promotion planner proved package layout on the foundation commit.
- [ ] After all P1-P6 implementation is complete, rerun single-adapter intake check on FINAL RC SHA.
- [ ] Rerun repository-wide intake check on FINAL RC SHA.
- [ ] Verify final worktree clean.
- [ ] Verify final portable Skill digest from exact FINAL RC Git bytes.
- [ ] Run final `obs-asset-promote --precommit-status passed`.
- [ ] Push FINAL RC SHA and prove local/remote SHA equality.
- [ ] Freeze FINAL RC SHA. No checklist/evidence commits after this point.

## P8. Final non-mutating Assets package validation

- [ ] Dispatch `pi-obs-python-runtime.yml` using FINAL RC SHA.
- [ ] Materializer resolves exact intake SHA.
- [ ] Manifest publication passes in CI.
- [ ] Python runtime catalog/hash generation passes.
- [ ] Packaged adapter registry import tests pass.
- [ ] Portable Skill package tests pass.
- [ ] Wheel/sdist build passes.
- [ ] Package archive inspection passes.
- [ ] Forbidden-content scan passes.
- [ ] ECS parity/evidence steps pass where applicable.
- [ ] Full required Assets CI for the validation workflow is green.

## PRE-PUBLICATION RELEASE GATE

Do **not** create the final Assets promotion PR unless P1 through P8 are all green.

When P1-P8 pass:
- [ ] Record FINAL RC intake SHA in PI-1951.
- [ ] Dispatch `adapter-intake-promote-pr.yml` with that exact SHA.
- [ ] `allow_manifest_removals=false`.
- [ ] Review generated Assets PR diff before merge.
- [ ] Require Assets PR CI fully green.
- [ ] Merge and deploy exact `0.1.0` packaged identity.

# POST-DEPLOY CERTIFICATION — DOES NOT AUTOMATICALLY REQUIRE A VERSION BUMP

## C1. Governed environment binding

- [ ] `test_database_lake / Companies` binding maps `company_id <- company_ids`.
- [ ] Batch retrieval `[13,59]` yields exactly 13 and 59.
- [ ] `company_memory` resolves per scalar loop company ID.
- [ ] `company_memory_update` resolves per scalar loop company ID.
- [ ] Dossier output destination/policy is admitted.

## C2. Remote Agent admission

- [ ] All seven roles pass `obs-agent-runtime-admit` dry-run.
- [ ] Exact model/thinking/search policies are correct in the admission plan.
- [ ] All seven roles reach `applied` or `no_change`.
- [ ] No credential/provider secret crosses into adapter package.

## C3. Primitive live proofs

- [ ] Governed Companies batch input passes.
- [ ] Fixed Skill delivery passes.
- [ ] Dynamic Skill read passes for company 13.
- [ ] Dynamic Skill read passes for company 59.
- [ ] Each of the three search-enabled research Agents passes independently.
- [ ] Strategic analyst passes.
- [ ] Evidence critic passes.
- [ ] Synthesizer passes.
- [ ] Benchmark reviewer passes.

## C4. Composition live proofs

- [ ] Same-company three-Agent research fan-out/join passes.
- [ ] Both companies produce exact canonical DTO hierarchy.
- [ ] Full `[13,59]` preview run completes with zero mutations.
- [ ] Cross-company contamination checks remain zero.
- [ ] Phase-1 quality gate completes for both companies before apply.
- [ ] Controlled company 13 mutation + readback/history passes.
- [ ] Controlled company 59 mutation + readback/history passes.
- [ ] Benchmark improvement/no-change decision is evidence-backed.

## C5. Dossier file publication

- [ ] Runtime result projection proven independently.
- [ ] Output-policy dry-run passes.
- [ ] Publish confirmation uses a fresh idempotency key.
- [ ] Output operation reaches terminal success.
- [ ] Physical dossier artifact exists.
- [ ] Published file is rendered from the exact canonical DTO registry.

## C6. Final certification

- [ ] Full two-company Vertex batch completes within the asset deadline.
- [ ] Every requested company completes; partial success is not green.
- [ ] Canonical titles/hierarchy are identical across company outputs.
- [ ] Citation/quality counters are internally consistent.
- [ ] Memory lane and file-publication lane each have independent proof.
- [ ] PI-1951 records intake SHA, Assets PR, deployed version, binding/admission evidence, live run UUIDs, and final verdict.

## Version-bump decision after deployment

If a post-deploy gate fails:
1. identify the first failing boundary;
2. fix environment/binding/admission/provider/runtime owner without bumping the adapter when package bytes do not change;
3. bump to `0.1.1` only if the required fix changes immutable `0.1.0` adapter package bytes.
