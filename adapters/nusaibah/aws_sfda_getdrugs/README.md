# AWS SFDA GetDrugs Assets-queued runtime

This adapter has one production execution path:

`obs-asset-launch -> Assets publish-policy preparation -> Assets queue -> local_worker or ECS -> adapter -> exact-file self-inspection -> direct provider upload`

The adapter normalizes records and validates the exact serialized staging file. It never calls DLM Core and never receives lake credentials. Assets owns run state, queue execution, retries, and observability. The runtime worker uses DLM Core only as a schema and storage control plane; payload bytes upload directly from the worker to the selected GCP or AWS provider.

## Runtime flow

1. `obs-asset-launch` validates `asset_launcher.v2` with `output_lifecycle.mode=assets_queued_runtime`.
2. The helper submits through `devtools.asset_policy_runner`; it has no dataset publication authority.
3. Assets queues the workflow for `local_worker` or ECS.
4. The runtime worker executes `aws.sfda.getdrugs`, serializes the `drugs` output once, and writes those exact bytes to temporary staging.
5. The worker loads the current node schema through the Core control plane, verifies its immutable snapshot SHA-256, and calls `SfdaGetDrugsAdapter.self_inspect` on the staged file.
6. A passing file is uploaded directly to the configured lake provider through Core-issued output-write authority. Assets and Core receive bounded metadata, checksums, and inspection evidence only.
7. A failed inspection stops before dataset publication and is recorded as a failed Assets run without changing the current dataset.

For full source-fetch observability, use `--runtime-source-inputs-file`; this makes the selected worker substrate resolve the crawl. `--request-file` remains a local-worker compatibility mode that crawls before submitting the resolved adapter input to Assets.

## Current node schema

The administrative contract remains `aws_sfda_getdrugs_daily_snapshot.v1`; no v2 is created. DLM UI/Core node create or edit publishes `current.json` and its immutable hash-named snapshot to the lake provider. The current contract has 94 aligned entries in `properties`, `results.contract.inspection.keys`, and `columns`.

## Two-page local_worker validation
## Retention boundary

The launcher declares conservative local lifecycle defaults: seven backups, 30 backup days, 14 blocked/quarantine days, and 24 staging hours. These values are enforced only when the generic local filesystem lifecycle router owns the disposition.

For managed S3 publication, dataset/backup/quarantine retention remains owned by the DLM UI node policy; physical pruning of those provider data objects is still disabled. DLM Core separately supports bounded 10-day cleanup of obsolete generated schema snapshots while protecting `schema/current.json` and its selected SHA-256 target. The adapter never calls S3 deletion APIs and never treats declared node-data metadata as proof that provider objects were pruned.

AWS provider facts for this node:

- lake: `hykshdasds`
- node: `aws_sfda_getdrugs_daily_snapshot`
- dataset root: `lakes/hykshdasds/outputs/sfda_getdrugs/daily_snapshot`

```powershell
obs-asset-launch `
  --adapter-yaml E:\nusaibah_projects\demo_asset_project\adapter-intake-work\adapters\nusaibah\aws_sfda_getdrugs\adapter.yaml `
  --env-file E:\nusaibah_projects\demo_asset_project\.env `
  --runtime-source-inputs-file E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\sfda_getdrugs\run_profiles\sfda_getdrugs.runtime-source.2pages.inputs.json `
  --execution-substrate local_worker `
  --set extraction_date=2026-07-15 `
  --set max_pages=2 `
  --pretty
```

ECS uses the same command with `--execution-substrate ecs`. It requires a runtime image built from the same released wheel.

## Tests

```powershell
python -m pytest -q `
  tests\test_self_inspection.py `
  tests\test_dataset_router.py `
  tests\test_retention.py `
  tests\test_recovery.py
```