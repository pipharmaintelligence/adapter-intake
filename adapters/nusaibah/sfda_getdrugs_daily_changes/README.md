# SFDA daily changes — PI-1710 file-binding preparation

This packet prepares `sfda.getdrugs_daily_changes:0.1.0` for the governed two-file input contract without changing its Python comparison callable.

## Prepared contract

Both `latest_snapshot` and `previous_snapshot` are declared as `partition_file` roles. Each role selects exactly one `extraction_date` value from its own run variable and requires the bounded materializer contract:

- `key=json_object`
- `format=json`
- `content_type=application/json`
- `record_path=/records`
- `complete_required=true`

The preparation profile uses logical `@input.<role>.source` and `@input.<role>.node` references. It contains no retrieval handle, credential, provider URL, storage location, provider payload, or publication target.

## Safety status

This is preparation only. It does not activate or create a production binding, and it is not a live cutover profile. Keep `OBS_ASSET_INPUT_BINDING_FILE_MODES_ENABLED=false`.

Do not start the live SFDA cutover until all of the following are true:

- PI-1709 is merged and the mode-aware UI is available.
- PI-1714 is Done.
- A controlled non-SFDA GCS signed-read proof has passed.
- The Core migration and compatible Core/Assets deployments are confirmed.
- The proposed SFDA file binding is reviewed and remains non-eligible until the cutover window.

## Cutover checklist

1. Confirm the existing materialized SFDA binding is active and record its identity as the rollback target.
2. Confirm the two extraction-date partitions exist and pass Core readiness.
3. Create the new two-role `partition_file` binding without activating it.
4. Review lake, node, partition-key, materializer, byte, and record bounds.
5. Enable file-mode creation only for the controlled window.
6. Activate the reviewed file binding and run one variables-only remote proof.
7. Verify both role selections, signed-request freshness, output summary, cleanup, and observability evidence.
8. Disable the old materialized binding only after the proof is accepted.

## Rollback checklist

1. Stop new SFDA file-mode admissions.
2. Disable the candidate file binding.
3. Reactivate the recorded materialized SFDA binding.
4. Restore `OBS_ASSET_INPUT_BINDING_FILE_MODES_ENABLED=false`.
5. Verify one known materialized run through hosted or controlled infrastructure.
6. Preserve Core, Assets, and worker logs; do not reproduce failures on the protected workstation.

The repository fixture remains local-only diagnostic material. It is not part of the promoted Assets package.
