# ClinicalTrials.gov lookup 0.1.0 — promotion and dual-substrate certification checklist

**Scope:** `nusaibah.clinical_trials_lookup@0.1.0` in adapter-intake PR #147, target `local_worker` **and** `ecs`. This is an evidence ledger. **A manifest allowance and green intake CI are not live readiness.**

**Current source-reviewed configuration:** shared manifest allows `["local_worker","ecs"]`, default `local_worker`, 120-second execution timeout. Adapter semantics are common to both substrates; no direct provider HTTP, credentials, output publishing, retries, or runtime-owned execution are added to the business adapter. `adapter.dependencies.json` has no third-party dependencies and declares minimum runtime `0.1.113`; verify the exact installed/runtime image wheel and current latest release before using that minimum as proof of feature availability.

## Gate register

| Gate | Status at authoring | Exact success criterion |
| --- | --- | --- |
| P0 adapter syntax/offline deterministic tests | **PASS, LOCAL**: 31/31 provider-free tests; publication templates validated in earlier local review | GitHub intake workflow also runs `tests/test_clinical_trials_lookup.py` at exact PR head on Python 3.10 |
| P0 manifest ECS contract | **CONFIGURED, NOT PACKAGE-PROVEN** | 0.1.0 execution allows `local_worker` and `ecs`, default is one allowed substrate; installed package validator passes |
| P0 intake content scanning | **CHECK CI** | No forbidden files, data, secrets, provider targets, raw payloads, run results, or notebooks copied |
| P1 immutable intake source | **CHECK FINAL PR HEAD SHA** | Exact 40-character GitHub SHA from successful CI; workflow dispatch uses that SHA, not branch name |
| P2 official promotion plan | **NOT RUN** | Assets `obs-asset-promote` / official planner reports `status=ready`; no mutation |
| P3 cumulative materialization | **NOT RUN** | Materializer preserves existing Assets identities and stages this new key/version atomically, no shared-file conflicts |
| P4 generated package metadata | **NOT RUN** | Generated PHP asset manifest, Python catalog and ECS deployable evidence agree for exact identity |
| P5 package CI | **NOT RUN** | Packaged dotted import, Python tests, Laravel metadata validation, wheel and sdist build/inspection, forbidden-content checks |
| P6 exact-head review / merge | **DRAFT** | All required checks successful, reviewer approval if required, diff limited to this asset + scoped intake CI |
| P7 merged | **NOT YET** | Actual merge SHA, not just mergeability |
| P8 local_worker deployed | **NOT PROVEN** | Running worker build/package/catalog digest matches admitted `0.1.0` |
| P8 ECS image | **NOT BUILT/DEPLOYED HERE** | Current Assets promotion workflow performs conditional **local image build and smoke** when ECS enabled; collect job-step results, image ID, bundle/wheel hash |
| P8 ECS ECR / task release | **NOT PROVEN** | Separate explicit ECR push/digest and signed ECS deployment/task definition proof; promotion workflow's image-build step alone does not push/deploy |
| Governed source config | **PARTIAL PASS** | Operator verified `@clinical_trials_gov_v2` `rt_src_421eba0e307942b781e252ba0f631691` `active/ready` with 9/9 checks, public authority, no node needed |
| Source allowed substrates | **UNKNOWN** | Read the source's `allowed_substrates` safe projection. The source was originally authored for `local_worker` in the prior guide; do not assume `ecs` was selected. DLM UI edit currently only changes display label: changing an active source's substrate policy requires reviewing an existing Core-authorized amend path and lifecycle; do not create a duplicate |
| Runtime Source input role admission | **NOT PROVEN** | Three exact roles are admitted: `trials_search_runtime`, `trials_detail_runtime`, `trials_phase3_runtime` with explicitly selected distinct source references |
| Selected-executor primitive test `local_worker` | **NOT RUN** | `obs-runtime-source-verify` safe terminal `passed`, correct executor revision, source ID and `verified_substrate=local_worker` |
| Selected-executor primitive test ECS | **NOT RUN** | Equivalent trusted verification **actually executed on ECS** with `verified_substrate=ecs` and recorded worker/image digest |
| Study root JSON/pagination semantics | **NOT PROVEN LIVE** | Observed `records[0].studies` root and optional `nextPageToken/totalCount` preserved; `records_path` blank; safe counts only in shared report |
| Seven operations on both substrates | **NOT PROVEN LIVE** | Prove describe, study_search, study_get, study_batch, arms_get, outcomes_get, results_get with source and adapter terminal truth; basic scalar before complex Essie/cursor |
| Provider error/retry/cursor contract | **NOT PROVEN LIVE** | Provider 404/429/5xx fail closed, opaque cursor and advanced Essie pass trusted validation, no adapter-owned transport/retry |
| Callable child + future consumer | **NOT PROVEN** | Separate approved direct callable-child admission; current nested callable and lazy-child preparation constraints remain |
| Remote MCP publication | **NOT IN SCOPE** | Seven schemas remain `templates_only`; public tool publication is not automatic |

## Promotion workflow

Use the **existing** Assets workflow `.github/workflows/adapter-intake-promote-pr.yml` after the exact intake PR head has successful tests. Inputs should be:

```text
intake_repository: pipharmaintelligence/adapter-intake
intake_ref: <FINAL_VERIFIED_40_CHAR_INTAKE_COMMIT_SHA>
intake_adapter_yaml: adapters/nusaibah/clinical_trials_lookup/adapter.yaml
base_branch: main
draft: true
allow_manifest_removals: false
```

Its source-reviewed steps: checkout exact intake SHA; materialize one declared package; publish manifests and Python catalog; run focused package tests and wheel/sdist inspection; reconcile ECS base runtime artifact; resolve promoted asset ECS plan; when `ecs_enabled=true`, build image and run local health smoke; upload safe build evidence; open/update an Assets package PR. **It does not auto-merge, push ECS image to ECR, deploy tasks, or prove signed provider execution.** Confirm whether image build is PASS, SKIPPED or FAILED, never infer from overall workflow green alone. A new asset is not deployed before its own release gates.

## Proof scope and no-touch areas

Current Core readiness was supplied by the operator (all nine checks pass for one source) and is NOT proof of worker input-role admission, source `ecs` allowance, private request target, or live provider records.

Do not modify `clinical_failure_intelligence@0.1.1`, Core, DLM UI, Assets shared validators, provider HTTP transport, credential configuration, nor production queues merely to make this intake PR green. Correct a proven failure at the owning contract. Keep 0.1.0 fixed until the intended feature set is completed and promotion released.

For live proof, collect only safe `rt_src_...`, asset/version, immutable SHAs, executor revisions, source status/reason codes, terminal run IDs, result counts and hashes. Never post provider records, headers, tokens, request target configuration, raw payloads, or execution material.
