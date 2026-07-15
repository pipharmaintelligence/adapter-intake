"""Generate the current SFDA node schema from a value-free full-crawl inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from .sfda_getdrugs_adapter import SfdaGetDrugsAdapter
except ImportError:
    from sfda_getdrugs_adapter import SfdaGetDrugsAdapter


NODE_KEY = "aws_sfda_getdrugs_daily_snapshot"
NODE_SCHEMA_VERSION = "aws_sfda_getdrugs_daily_snapshot.v1"
PAYLOAD_SCHEMA_VERSION = "sfda_getdrugs.records.v1"
EXPECTED_FIELD_COUNT = 94
TYPE_ORDER = ("null", "boolean", "integer", "number", "string", "array", "object")


def json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    raise TypeError("unsupported_json_value")


def build_inventory(records: list[Any]) -> dict[str, Any]:
    observed: dict[str, set[str]] = {}
    present: dict[str, int] = {}
    normalized_count = 0
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            continue
        normalized = SfdaGetDrugsAdapter._normalize_record(record, index=index)
        normalized_count += 1
        for key, value in normalized.items():
            if not isinstance(key, str):
                continue
            observed.setdefault(key, set()).add(json_type(value))
            present[key] = present.get(key, 0) + 1

    fields = []
    for key in sorted(observed):
        types = [name for name in TYPE_ORDER if name in observed[key]]
        fields.append({
            "name": key,
            "types": types,
            "present_count": present[key],
            "missing_count": normalized_count - present[key],
            "nullable": "null" in types,
        })
    if len(fields) != EXPECTED_FIELD_COUNT:
        raise RuntimeError(f"normalized_field_count_{len(fields)}_expected_{EXPECTED_FIELD_COUNT}")
    return {
        "schema_version": "sfda_value_free_type_inventory.v1",
        "values_included": False,
        "source_records_inspected": len(records),
        "normalized_records_inspected": normalized_count,
        "field_count": len(fields),
        "fields": fields,
    }


def build_schema(inventory: dict[str, Any]) -> dict[str, Any]:
    fields = inventory["fields"]
    properties: dict[str, Any] = {}
    columns: list[dict[str, Any]] = []
    keys: list[str] = []
    for field in fields:
        name = field["name"]
        types = field["types"]
        declared_type: str | list[str] = types[0] if len(types) == 1 else types
        properties[name] = {"type": declared_type}
        primary_type = next((item for item in types if item != "null"), "null")
        columns.append({
            "name": name,
            "type": primary_type,
            "types": types,
            # Column policy is nullable-tolerant even when the representative
            # crawl did not happen to contain a null for this field.
            "nullable": True,
            "required": False,
        })
        keys.append(name)

    return {
        "metadata": {
            "document_type": "node_schema",
            "node_key": NODE_KEY,
            "schema_version": NODE_SCHEMA_VERSION,
            "generation_mode": "value_free_full_crawl_inventory",
            "values_included": False,
            "records_inspected": inventory["normalized_records_inspected"],
        },
        "payload_schema_version": PAYLOAD_SCHEMA_VERSION,
        "payload_contract": {
            "$id": PAYLOAD_SCHEMA_VERSION,
            "type": "object",
            "properties": {
                "records": {"type": "array"},
                "page_summary": {"type": "object"},
            },
            "required": ["records", "page_summary"],
            "additionalProperties": False,
        },
        "results": {
            "schema_type": "json_schema",
            "format": "json",
            "contract": {
                "type": "object",
                "properties": properties,
                "required": [],
                "additionalProperties": True,
                "inspection": {"keys": keys},
                "columns": columns,
            },
        },
        # DLM Core's schema-management projection exposes columns at the
        # document root, while adapter inspection owns results.contract.
        # Keep both views identical so one immutable contract serves both.
        "columns": columns,
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.write_text(encoded, encoding="utf-8", newline="\n")


def generate(inputs_file: Path, output_root: Path) -> dict[str, Any]:
    payload = json.loads(inputs_file.read_text(encoding="utf-8-sig"))
    role = payload.get("sfda_response") if isinstance(payload, dict) else None
    records = role.get("records") if isinstance(role, dict) else None
    if not isinstance(records, list):
        raise RuntimeError("sfda_response_records_missing")
    inventory = build_inventory(records)
    schema = build_schema(inventory)
    schema_path = output_root / "schema" / "snapshots" / "pending.json"
    write_json(schema_path, schema)
    schema_sha256 = hashlib.sha256(schema_path.read_bytes()).hexdigest()
    immutable_path = schema_path.with_name(f"sha256-{schema_sha256}.json")
    schema_path.replace(immutable_path)
    pointer = {
        "node_key": NODE_KEY,
        "schema_version": NODE_SCHEMA_VERSION,
        "schema_file": f"snapshots/{immutable_path.name}",
        "schema_sha256": schema_sha256,
        "validation_mode": "nullable_tolerant",
    }
    write_json(output_root / "schema" / "current.json", pointer)
    write_json(output_root / "sfda_getdrugs.value_free_type_inventory.json", inventory)
    return {
        "field_count": inventory["field_count"],
        "records_inspected": inventory["normalized_records_inspected"],
        "schema_version": NODE_SCHEMA_VERSION,
        "schema_sha256": schema_sha256,
        "values_included": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs-file", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.inputs_file.resolve(), args.output_root.resolve()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
