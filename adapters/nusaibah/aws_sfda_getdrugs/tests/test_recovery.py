from __future__ import annotations

import os
import time

from conftest import make_staged, payload, read_json
from devtools.output_lifecycle import (
    JsonSchemaArtifactInspector,
    backup_existing_partition,
    recover_incomplete_runs,
    route_inspected_artifact,
    transition_manifest,
    write_json_atomic,
)


DATE = "2026-07-14"
INSPECTION_CONTEXT = {
    "inspector": {
        "record_schema_pointer": "results.contract",
        "payload_schema_pointer": "payload_contract",
        "records_path": "records",
        "payload_projection": ["records", "page_summary"],
        "payload_schema_version": "sfda_getdrugs.records.v1",
        "max_errors": 100,
    }
}


def recover(node_root, schema_snapshot, retention_policy):
    return recover_incomplete_runs(
        node_root,
        schema_snapshot,
        retention_policy,
        inspector=JsonSchemaArtifactInspector(),
        inspection_context=INSPECTION_CONTEXT,
    )


def test_staged_run_without_inspection_is_reinspected_and_committed(node_root, schema_contract, schema_snapshot, retention_policy) -> None:
    make_staged(node_root, schema_contract, retention_policy, run_id="staged-run", extraction_date=DATE, value=payload({"price": "valid"}), state="staged")
    summary = recover(node_root, schema_snapshot, retention_policy)
    manifest = read_json(node_root / "dataset" / f"extraction_date={DATE}" / "manifest.json")
    assert summary["recovered"] == 1
    assert manifest["state"] == "dataset_committed"
    assert manifest["inspection"]["status"] == "passed"


def test_inspection_failed_run_finishes_moving_to_blocked(node_root, schema_contract, schema_snapshot, retention_policy, adapter) -> None:
    staged = make_staged(node_root, schema_contract, retention_policy, run_id="failed-run", extraction_date=DATE, value=payload({"price": {"secret": "hidden"}}), state="inspection_failed")
    report = adapter.self_inspect(staged / "payload.json", schema_contract)
    write_json_atomic(staged / "inspection.json", report.to_dict())
    summary = recover(node_root, schema_snapshot, retention_policy)
    assert summary["blocked"] == 1
    assert (node_root / "blocked" / "failed-run" / "payload.json").is_file()


def test_backup_created_run_retries_promotion_durably(node_root, schema_contract, schema_snapshot, retention_policy, adapter) -> None:
    first = make_staged(node_root, schema_contract, retention_policy, run_id="first-run", extraction_date=DATE, value=payload({"price": "old"}), state="staged")
    first_report = adapter.self_inspect(first / "payload.json", schema_contract)
    route_inspected_artifact(first, first_report, node_root, DATE, retention_policy)
    staged = make_staged(node_root, schema_contract, retention_policy, run_id="retry-run", extraction_date=DATE, value=payload({"price": "new"}), state="inspection_passed")
    report = adapter.self_inspect(staged / "payload.json", schema_contract)
    write_json_atomic(staged / "inspection.json", report.to_dict())
    partition = node_root / "dataset" / f"extraction_date={DATE}"
    backup = backup_existing_partition(partition, node_root / "backup", report.to_dict())
    manifest = read_json(staged / "manifest.json")
    manifest["inspection"] = report.to_dict()
    manifest["backup_path"] = str(backup.relative_to(node_root)).replace("\\", "/")
    transition_manifest(manifest, "backup_created")
    write_json_atomic(staged / "manifest.json", manifest)
    summary = recover(node_root, schema_snapshot, retention_policy)
    assert summary["recovered"] == 1
    assert partition.is_dir()
    assert backup.is_dir()


def test_old_abandoned_staging_manifest_moves_to_quarantine(node_root, schema_contract, schema_snapshot, retention_policy) -> None:
    staged = make_staged(node_root, schema_contract, retention_policy, run_id="abandoned", extraction_date=DATE, value=payload({"price": "preserved"}), state="created")
    old = time.time() - 30 * 3600
    os.utime(staged, (old, old))
    summary = recover(node_root, schema_snapshot, retention_policy)
    quarantined = node_root / "quarantine" / "abandoned"
    assert summary["quarantined"] == 1
    assert quarantined.is_dir()
    assert read_json(quarantined / "manifest.json")["state"] == "quarantine_committed"
    assert (quarantined / "payload.json").is_file()
