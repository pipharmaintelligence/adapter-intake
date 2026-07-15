from __future__ import annotations

from pathlib import Path

import pytest

import devtools.output_lifecycle as publisher
from conftest import ADAPTER_ROOT, make_staged, payload, read_json
from sfda_self_inspection import sha256_file


DATE = "2026-07-14"


def inspect_and_route(node_root, schema_contract, retention_policy, adapter, *, run_id: str, value):
    staged = make_staged(
        node_root,
        schema_contract,
        retention_policy,
        run_id=run_id,
        extraction_date=DATE,
        value=value,
    )
    report = adapter.self_inspect(staged / "payload.json", schema_contract)
    disposition = publisher.route_inspected_artifact(staged, report, node_root, DATE, retention_policy)
    return disposition, report


def test_valid_payload_goes_only_to_dataset(node_root, schema_contract, retention_policy, adapter) -> None:
    disposition, report = inspect_and_route(
        node_root, schema_contract, retention_policy, adapter,
        run_id="valid-run", value=payload({"price": "10"}),
    )
    partition = node_root / "dataset" / f"extraction_date={DATE}"
    manifest = read_json(partition / "manifest.json")
    assert disposition == "written"
    assert (partition / "payload.json").is_file()
    assert not (partition / "inspection.json").exists()
    assert list((node_root / "blocked").iterdir()) == []
    assert manifest["inspection"]["payload_sha256"] == report.payload_sha256 == sha256_file(partition / "payload.json")


def test_invalid_payload_goes_only_to_blocked(node_root, schema_contract, retention_policy, adapter) -> None:
    disposition, _report = inspect_and_route(
        node_root, schema_contract, retention_policy, adapter,
        run_id="invalid-run", value=payload({"price": {"secret": "not-reported"}}),
    )
    blocked = node_root / "blocked" / "invalid-run"
    assert disposition == "blocked"
    assert (blocked / "payload.json").is_file()
    assert read_json(blocked / "manifest.json")["disposition"] == "blocked"
    assert list((node_root / "dataset").iterdir()) == []
    assert "not-reported" not in (blocked / "inspection.json").read_text(encoding="utf-8")


def test_invalid_payload_leaves_existing_dataset_unchanged(node_root, schema_contract, retention_policy, adapter) -> None:
    inspect_and_route(node_root, schema_contract, retention_policy, adapter, run_id="first-valid", value=payload({"price": "old"}))
    partition_payload = node_root / "dataset" / f"extraction_date={DATE}" / "payload.json"
    original_checksum = sha256_file(partition_payload)
    inspect_and_route(node_root, schema_contract, retention_policy, adapter, run_id="later-invalid", value=payload({"price": {"secret": "bad"}}))
    assert sha256_file(partition_payload) == original_checksum
    assert (node_root / "blocked" / "later-invalid").is_dir()


def test_replacing_partition_creates_backup_with_schema_evidence(node_root, schema_contract, retention_policy, adapter) -> None:
    inspect_and_route(node_root, schema_contract, retention_policy, adapter, run_id="old-run", value=payload({"price": "old"}))
    inspect_and_route(node_root, schema_contract, retention_policy, adapter, run_id="new-run", value=payload({"price": "new"}))
    backups = list((node_root / "backup" / f"extraction_date={DATE}").iterdir())
    assert len(backups) == 1
    manifest = read_json(backups[0] / "manifest.json")
    assert manifest["disposition"] == "backup"
    assert manifest["node_schema_version"] == "aws_sfda_getdrugs_daily_snapshot.v1"
    assert len(manifest["node_schema_sha256"]) == 64


def test_promotion_failure_restores_backup(node_root, schema_contract, retention_policy, adapter, monkeypatch) -> None:
    inspect_and_route(node_root, schema_contract, retention_policy, adapter, run_id="stable-run", value=payload({"price": "stable"}))
    partition_payload = node_root / "dataset" / f"extraction_date={DATE}" / "payload.json"
    original_checksum = sha256_file(partition_payload)
    staged = make_staged(node_root, schema_contract, retention_policy, run_id="failing-run", extraction_date=DATE, value=payload({"price": "replacement"}))
    report = adapter.self_inspect(staged / "payload.json", schema_contract)

    def fail_promotion(*_args, **_kwargs):
        raise OSError("simulated_promotion_failure")

    monkeypatch.setattr(publisher, "atomic_promote_to_dataset", fail_promotion)
    with pytest.raises(OSError, match="simulated_promotion_failure"):
        publisher.route_inspected_artifact(staged, report, node_root, DATE, retention_policy)
    assert sha256_file(partition_payload) == original_checksum
    assert staged.is_dir()


def test_partition_lock_prevents_concurrent_replacement(node_root, schema_contract, retention_policy, adapter) -> None:
    staged = make_staged(node_root, schema_contract, retention_policy, run_id="concurrent-run", extraction_date=DATE, value=payload({"price": "concurrent"}))
    report = adapter.self_inspect(staged / "payload.json", schema_contract)
    partition_name = f"extraction_date={DATE}"
    with publisher.partition_lock(node_root, partition_name, timeout_seconds=0.01):
        with pytest.raises(publisher.PartitionLockError):
            publisher.route_inspected_artifact(staged, report, node_root, DATE, retention_policy, lock_timeout_seconds=0.01)
    assert staged.is_dir()


def test_helper_submits_one_assets_observed_runtime_publisher() -> None:
    source = (ADAPTER_ROOT / "sfda_full_crawl_publish.py").read_text(encoding="utf-8")
    launcher = read_json(ADAPTER_ROOT / "sfda_getdrugs.launcher.json")
    asset = read_json(ADAPTER_ROOT / "sfda_getdrugs.asset.json")
    validation = asset["versions"]["0.1.0"]["output_contracts"]["drugs"]["validation"]
    assert "devtools.asset_policy_runner" in source
    assert "publish_to_node" in source
    assert '"--runtime-owned-output-write"' in source
    assert '"--confirm-publish"' not in source
    assert "route_inspected_artifact" not in source
    assert ".self_inspect(" not in source
    assert launcher["schema_version"] == "asset_launcher.v2"
    assert launcher["boundary"]["authority"] == "assets_publish_policy_prepare"
    assert launcher["output_lifecycle"]["mode"] == "assets_queued_runtime"
    assert launcher["output_lifecycle"]["submission"]["provider_transfer"] == "presigned_provider_direct"
    assert launcher["execution"]["allowed_substrates"] == ["local_worker", "ecs"]
    assert asset["execution"]["allowed_substrates"] == ["local_worker", "ecs"]
    assert validation["self_inspection"] == {"enforce": True, "on_fail": "fail"}
    assert launcher["retention"] == {
        "backup_count": 7,
        "backup_days": 30,
        "blocked_days": 14,
        "quarantine_days": 14,
        "staging_hours": 24,
        "environment": launcher["retention"]["environment"],
    }
    assert launcher["managed_provider_retention"]["physical_cleanup_enabled"] is False
    assert publisher.validate_output_lifecycle_contract(launcher, asset, release_stage="production") == []
