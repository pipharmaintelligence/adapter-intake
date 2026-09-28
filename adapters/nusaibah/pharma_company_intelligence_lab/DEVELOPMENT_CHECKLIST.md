# PI-1951 Development Checklist

Asset: `nusaibah.pharma_company_intelligence_lab@0.1.0`

A checked item proves only the named gate. It does not imply a later stage is ready.

## A. Source and package foundation

- [x] Canonical source repo is `pipharmaintelligence/adapter-intake`.
- [x] Asset identity and package target are fixed.
- [x] Batch launch contract uses bounded `company_ids`.
- [x] Governed `companies` rows are pre-resolved before remote Python execution.
- [x] Exact company isolation rules are documented.
- [x] Canonical dossier section/subsection registry is adapter-owned.
- [x] Portable methodology Skill files are part of the reviewed package.
- [x] Output contract declares JSON dry-run publication with self-inspection.
- [x] Dynamic Skill read/mutable roles are declared by scalar loop `company_id`.
- [ ] Minimum runtime version is bumped to the first released wheel containing PI-1952.

## B. DTO and deterministic contract tests

- [x] `company_ids` empty/duplicate/non-integer/oversize cases are tested.
- [x] Resolved company set must exactly equal requested company set.
- [x] Caller order is preserved after governed retrieval.
- [x] Unknown/missing/duplicate/reordered section IDs fail.
- [x] Unknown/missing/duplicate/reordered subsection IDs fail.
- [x] Provider-authored titles cannot change canonical output titles.
- [ ] Cross-company Agent output is rejected.
- [x] Memory candidate company mismatch is rejected.
- [ ] Preview mode cannot mutate memory.
- [ ] Apply requires expected digest and readback/history proof.
- [x] Local-root import passes.
- [x] Packaged dotted import passes.

## C. Vertex runtime prerequisite

- [ ] PI-1952 merged in Assets.
- [ ] Runtime wheel containing PI-1952 is released.
- [ ] Installed development wheel matches the required minimum.
- [ ] Gemini 3.8 Flash thinking policy is proven by runtime tests.

## D. Packaged Agent definitions

- [ ] `portfolio_researcher` definition added and locally validated.
- [ ] `market_researcher` definition added and locally validated.
- [ ] `regulatory_risk_researcher` definition added and locally validated.
- [ ] `strategic_analyst` definition added and locally validated.
- [ ] `evidence_critic` definition added and locally validated.
- [ ] `intelligence_synthesizer` definition added and locally validated.
- [ ] `memory_benchmark_reviewer` definition added and locally validated.
- [ ] Search authority exists only on the three research roles.
- [ ] Every Agent uses a bounded structured JSON response contract.

## E. Local authoring proof

- [ ] Syntax/import gate passes with selected project interpreter.
- [ ] Deterministic unit tests pass.
- [ ] Fixture run for `[13, 59]` passes without provider calls.
- [ ] Fixed Skill package validation and digest pass.
- [ ] `obs-asset-diagnose --quick` passes for the exact asset root.
- [ ] Local preflight passes.
- [ ] Forbidden package-content scan passes.

## F. Adapter-intake gates

- [ ] `obs-adapter-intake-check --adapter-yaml ...` passes.
- [ ] Repository-wide `obs-adapter-intake-check --root .` passes.
- [ ] Worktree is clean after commit.
- [ ] Portable Skill digest is verified from exact committed Git bytes.
- [ ] `obs-asset-promote ... --precommit-status passed` returns promotion-plan ready.
- [ ] Exact intake commit is pushed and remote SHA equality is proven.

## G. Assets materialization and CI

- [ ] Pinned intake-ref validation workflow passes in Assets.
- [ ] Assets promotion PR is generated from the exact intake SHA.
- [ ] Manifest publication passes.
- [ ] Runtime catalog/hash generation passes.
- [ ] Packaged dotted import tests pass.
- [ ] Portable Skill package tests pass.
- [ ] Assets CI is fully green.
- [ ] Assets promotion PR is merged.
- [ ] Exact packaged version is deployed.

## H. Governed environment admission

- [ ] `test_database_lake / Companies` binding maps `company_id <- company_ids`.
- [ ] Batch retrieval `[13, 59]` returns exactly company IDs 13 and 59.
- [ ] `company_memory` read role resolves per scalar loop company ID.
- [ ] `company_memory_update` mutable role resolves per scalar loop company ID.
- [ ] All seven Agent roles pass remote admission dry-run.
- [ ] All seven Agent roles are applied or already identical.

## I. Live proof progression

- [ ] Governed Companies batch input primitive passes.
- [ ] Fixed Skill primitive passes.
- [ ] Dynamic Skill read primitive passes for 13.
- [ ] Dynamic Skill read primitive passes for 59.
- [ ] Each research Agent primitive passes independently.
- [ ] Same-company three-Agent research join passes.
- [ ] Strategic analysis passes.
- [ ] Evidence critic passes.
- [ ] Synthesizer returns exact canonical DTO for both companies.
- [ ] Full `[13, 59]` preview batch passes with zero mutations.
- [ ] Phase-1 quality gate passes for every company before apply starts.
- [ ] Company 13 mutation + fresh readback/history proof passes.
- [ ] Company 59 mutation + fresh readback/history proof passes.
- [ ] Cross-company contamination checks remain zero.
- [ ] Memory benchmark improves or explicitly records no justified improvement.

## J. Dossier file publication

- [ ] Runtime result projection is proven separately from file publication.
- [ ] Output-policy dry-run passes for `intelligence_dossier`.
- [ ] Publish confirmation uses a fresh idempotency key.
- [ ] Final output operation reaches terminal success.
- [ ] Published dossier is rendered from the same canonical DTO registry.
- [ ] File existence is proven independently of Dynamic Skill mutation.

## K. Final certification

- [ ] Full two-company Vertex batch completes within the asset execution deadline.
- [ ] Every requested company completes; partial batch is not accepted as green.
- [ ] Canonical section/subsection IDs and titles are identical across company outputs.
- [ ] All citations/quality counters are bounded and internally consistent.
- [ ] Memory and file-output lanes both have independent acceptance evidence.
- [ ] PI-1951 has the exact intake SHA, Assets PR, deployed version, live run UUID, and final verdict.
