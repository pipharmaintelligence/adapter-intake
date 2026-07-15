from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import ADAPTER_ROOT, payload, read_json
from sfda_self_inspection import SchemaContractError, load_node_schema, sha256_file


def test_valid_payload_inspects_exact_file_and_all_records(
    tmp_path: Path, adapter, schema_contract
) -> None:
    staged_payload = tmp_path / "payload.json"
    staged_payload.write_text(
        json.dumps(payload({"price": "10"}, {"price": "20"}, {"price": "30"})),
        encoding="utf-8",
    )

    report = adapter.self_inspect(staged_payload, schema_contract)

    assert report.status == "passed"
    assert report.records_inspected == 3
    assert report.records_failed == 0
    assert report.payload_sha256 == sha256_file(staged_payload)


def test_inspection_validates_every_record_and_bounds_value_free_errors(
    tmp_path: Path, adapter, schema_contract
) -> None:
    records = [{"price": "ok"} for _ in range(150)]
    for index in range(150):
        records[index]["price"] = {"secret": f"rejected-{index}"}
    staged_payload = tmp_path / "payload.json"
    staged_payload.write_text(json.dumps(payload(*records)), encoding="utf-8")

    report = adapter.self_inspect(staged_payload, schema_contract)
    encoded_report = json.dumps(report.to_dict())

    assert report.status == "failed"
    assert report.records_inspected == 150
    assert report.records_failed == 150
    assert report.error_count == 100
    assert len(report.errors) == 100
    assert report.errors_truncated is True
    assert "rejected-" not in encoded_report
    assert "secret" not in encoded_report


def test_schema_hash_mismatch_fails_closed(node_root: Path) -> None:
    pointer_path = node_root / "schema" / "current.json"
    pointer = read_json(pointer_path)
    pointer["schema_sha256"] = "0" * 64
    pointer_path.write_text(json.dumps(pointer), encoding="utf-8")

    with pytest.raises(SchemaContractError, match="schema_hash_mismatch"):
        load_node_schema(node_root)


def test_missing_schema_fails_closed(node_root: Path) -> None:
    (node_root / "schema" / "current.json").unlink()

    with pytest.raises(SchemaContractError, match="schema_pointer_missing"):
        load_node_schema(node_root)


def test_external_schema_reference_is_rejected(node_root: Path) -> None:
    pointer = read_json(node_root / "schema" / "current.json")
    schema_path = node_root / "schema" / pointer["schema_file"]
    schema = read_json(schema_path)
    schema["results"]["contract"]["properties"]["price"] = {
        "$ref": "https://example.invalid/schema.json"
    }
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    pointer["schema_sha256"] = sha256_file(schema_path)
    (node_root / "schema" / "current.json").write_text(json.dumps(pointer), encoding="utf-8")

    with pytest.raises(SchemaContractError, match="external_schema_ref_rejected"):
        load_node_schema(node_root)


def test_current_v1_schema_has_94_consistent_optional_fields() -> None:
    schema_root = ADAPTER_ROOT / "schema_admin" / "schema"
    pointer = read_json(schema_root / "current.json")
    schema = read_json(schema_root / pointer["schema_file"])
    contract = schema["results"]["contract"]
    property_names = set(contract["properties"])
    inspection_names = set(contract["inspection"]["keys"])
    column_names = {column["name"] for column in contract["columns"]}
    projected_column_names = {column["name"] for column in schema["columns"]}

    assert len(property_names) == 94
    assert property_names == inspection_names == column_names == projected_column_names
    assert schema["columns"] == contract["columns"]
    assert contract["required"] == []
    assert contract["additionalProperties"] is True
    assert all(column["required"] is False for column in contract["columns"])
    assert all(column["nullable"] is True for column in contract["columns"])
    assert schema["metadata"]["schema_version"] == "aws_sfda_getdrugs_daily_snapshot.v1"
    assert pointer["schema_version"] == "aws_sfda_getdrugs_daily_snapshot.v1"
    expected_schema_file = f"snapshots/sha256-{pointer['schema_sha256']}.json"
    assert pointer["schema_file"] == expected_schema_file
    schema_path = schema_root / pointer["schema_file"]
    assert b"\r" not in schema_path.read_bytes()
    assert sha256_file(schema_path) == pointer["schema_sha256"]
