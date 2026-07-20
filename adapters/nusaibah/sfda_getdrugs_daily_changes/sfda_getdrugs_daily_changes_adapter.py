from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from adapters.base import Adapter

try:
    from system.native_file import NativeFileInputError, get_native_file_input
except ImportError:
    NativeFileInputError = Exception
    get_native_file_input = None

try:
    from .daily_changes_self_inspection import InspectionReport, inspect_staged_payload
except ImportError:
    InspectionReport = Any
    inspect_staged_payload = None


class SfdaGetDrugsDailyChangesAdapter(Adapter):
    key = "sfda.getdrugs_daily_changes"
    version = "0.1.0"

    def self_inspect(
        self,
        staged_payload: Path,
        schema_contract: dict[str, Any],
    ) -> InspectionReport:
        if inspect_staged_payload is None:
            raise RuntimeError("daily_changes_self_inspection_unavailable")
        return inspect_staged_payload(staged_payload, schema_contract)

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        latest_records, latest_meta = _records_and_metadata(inputs, "latest_snapshot")
        previous_records, previous_meta = _records_and_metadata(inputs, "previous_snapshot")

        max_change_rows = _read_int(context, "max_change_rows", default=1000)

        latest_index, duplicate_latest = _index_records(latest_records)
        previous_index, duplicate_previous = _index_records(previous_records)

        latest_keys = set(latest_index)
        previous_keys = set(previous_index)

        added_keys = sorted(latest_keys - previous_keys)
        removed_keys = sorted(previous_keys - latest_keys)
        changed_keys = sorted(
            key
            for key in latest_keys & previous_keys
            if _row_hash(latest_index[key]) != _row_hash(previous_index[key])
        )

        changes: list[dict[str, Any]] = []

        for key in added_keys:
            if len(changes) >= max_change_rows:
                break
            changes.append(
                _addition_change(
                    key=key,
                    row=latest_index[key],
                    latest_meta=latest_meta,
                    previous_meta=previous_meta,
                )
            )

        for key in changed_keys:
            if len(changes) >= max_change_rows:
                break
            changes.append(
                _changed_change(
                    key=key,
                    latest_row=latest_index[key],
                    previous_row=previous_index[key],
                    latest_meta=latest_meta,
                    previous_meta=previous_meta,
                )
            )

        for key in removed_keys:
            if len(changes) >= max_change_rows:
                break
            changes.append(
                _removed_change(
                    key=key,
                    row=previous_index[key],
                    latest_meta=latest_meta,
                    previous_meta=previous_meta,
                )
            )

        total_change_count = len(added_keys) + len(changed_keys) + len(removed_keys)
        omitted_change_count = max(0, total_change_count - len(changes))
        latest_date = _meta_date(latest_meta)
        previous_date = _meta_date(previous_meta)

        return {
            "response_version": "1",
            "status": "success",
            "outputs": {
                "data": {
                    "trace": {
                        "trace_date": latest_date,
                        "extraction_date": latest_date,
                        "previous_extraction_date": previous_date,
                        "latest_extraction_date": latest_date,
                        "comparison_window": "daily_previous_partition",
                        "source_node_key": "sfda_getdrugs_daily_snapshot",
                    },
                    "summary": {
                        "latest_count": len(latest_records),
                        "previous_count": len(previous_records),
                        "added_count": len(added_keys),
                        "changed_count": len(changed_keys),
                        "removed_count": len(removed_keys),
                        "duplicate_latest_count": duplicate_latest,
                        "duplicate_previous_count": duplicate_previous,
                        "emitted_change_count": len(changes),
                        "omitted_change_count": omitted_change_count,
                        "truncated": omitted_change_count > 0,
                    },
                    "changes": changes,
                }
            },
            "metrics": {
                "latest_count": len(latest_records),
                "previous_count": len(previous_records),
                "added_count": len(added_keys),
                "changed_count": len(changed_keys),
                "removed_count": len(removed_keys),
                "emitted_change_count": len(changes),
            },
            "logs": [
                {
                    "level": "info",
                    "message": "SFDA daily snapshot changes computed.",
                }
            ],
        }


def _records_and_metadata(inputs: dict[str, Any], role: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    value = inputs.get(role)
    if not isinstance(value, dict):
        return [], {}

    metadata = value.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    if value.get("mode") == "python_native_file":
        if get_native_file_input is None:
            return [], metadata

        try:
            native = get_native_file_input(inputs, role, allowed_formats={"json", "jsonl", "ndjson"})
        except NativeFileInputError:
            return [], metadata

        if native.format == "json":
            decoded = native.read_json()
            if isinstance(decoded, dict):
                records = decoded.get("records", [])
                decoded_metadata = decoded.get("metadata", {})
                if isinstance(decoded_metadata, dict) and not metadata:
                    metadata = decoded_metadata
                return _dict_rows(records), metadata
            if isinstance(decoded, list):
                return _dict_rows(decoded), metadata

        return _dict_rows(list(native.iter_jsonl_objects())), metadata

    return _dict_rows(value.get("records", [])), metadata


def _dict_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _index_records(records: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], int]:
    indexed: dict[str, dict[str, Any]] = {}
    duplicates = 0

    for row in records:
        key = _record_key(row)
        if not key:
            continue

        if key in indexed:
            duplicates += 1
            continue

        indexed[key] = row

    return indexed, duplicates


def _record_key(row: dict[str, Any]) -> str:
    registration = _clean(_first(row, "registration_number", "registerNumber", "RegNo", "reg_no"))
    if registration:
        return f"reg:{registration.lower()}"

    source_id = _clean(_first(row, "id"))
    if source_id:
        return f"id:{source_id}"

    parts = [
        _clean(_first(row, "trade_name", "tradeName", "TradeName")).lower(),
        _clean(_first(row, "scientific_name", "scientificName", "ScientificName")).lower(),
        _clean(_first(row, "manufacturer_name", "ManufacturerName")).lower(),
        _clean(_first(row, "agent", "Agent")).lower(),
    ]
    composite = "|".join(parts)

    if not composite.strip("|"):
        return ""

    digest = hashlib.sha256(composite.encode("utf-8")).hexdigest()
    return f"hash:{digest}"


def _addition_change(
    *,
    key: str,
    row: dict[str, Any],
    latest_meta: dict[str, Any],
    previous_meta: dict[str, Any],
) -> dict[str, Any]:
    return {
        "change_type": "added",
        "record_key": key,
        "registration_number": _display_registration(row),
        "trade_name": _clean(_first(row, "trade_name", "tradeName", "TradeName")),
        "scientific_name": _clean(_first(row, "scientific_name", "scientificName", "ScientificName")),
        "manufacturer_name": _clean(_first(row, "manufacturer_name", "ManufacturerName")),
        "agent": _clean(_first(row, "agent", "Agent")),
        "latest_row_hash": f"sha256:{_row_hash(row)}",
        "previous_row_hash": None,
        "changed_fields": [],
        "previous_extraction_date": _meta_date(previous_meta),
        "latest_extraction_date": _meta_date(latest_meta),
    }


def _changed_change(
    *,
    key: str,
    latest_row: dict[str, Any],
    previous_row: dict[str, Any],
    latest_meta: dict[str, Any],
    previous_meta: dict[str, Any],
) -> dict[str, Any]:
    return {
        "change_type": "changed",
        "record_key": key,
        "registration_number": _display_registration(latest_row),
        "trade_name": _clean(_first(latest_row, "trade_name", "tradeName", "TradeName")),
        "scientific_name": _clean(_first(latest_row, "scientific_name", "scientificName", "ScientificName")),
        "manufacturer_name": _clean(_first(latest_row, "manufacturer_name", "ManufacturerName")),
        "agent": _clean(_first(latest_row, "agent", "Agent")),
        "latest_row_hash": f"sha256:{_row_hash(latest_row)}",
        "previous_row_hash": f"sha256:{_row_hash(previous_row)}",
        "changed_fields": _changed_fields(previous_row, latest_row),
        "previous_extraction_date": _meta_date(previous_meta),
        "latest_extraction_date": _meta_date(latest_meta),
    }


def _removed_change(
    *,
    key: str,
    row: dict[str, Any],
    latest_meta: dict[str, Any],
    previous_meta: dict[str, Any],
) -> dict[str, Any]:
    return {
        "change_type": "removed",
        "record_key": key,
        "registration_number": _display_registration(row),
        "trade_name": _clean(_first(row, "trade_name", "tradeName", "TradeName")),
        "scientific_name": _clean(_first(row, "scientific_name", "scientificName", "ScientificName")),
        "manufacturer_name": _clean(_first(row, "manufacturer_name", "ManufacturerName")),
        "agent": _clean(_first(row, "agent", "Agent")),
        "latest_row_hash": None,
        "previous_row_hash": f"sha256:{_row_hash(row)}",
        "changed_fields": [],
        "previous_extraction_date": _meta_date(previous_meta),
        "latest_extraction_date": _meta_date(latest_meta),
    }


_VOLATILE_COMPARE_FIELDS = {
    "row_number",
    "source_page",
}


def _row_hash(row: dict[str, Any]) -> str:
    comparable = {
        key: value
        for key, value in row.items()
        if key not in _VOLATILE_COMPARE_FIELDS
    }
    encoded = json.dumps(comparable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _changed_fields(previous_row: dict[str, Any], latest_row: dict[str, Any]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    keys = sorted((set(previous_row) | set(latest_row)) - _VOLATILE_COMPARE_FIELDS)

    for key in keys:
        previous_value = previous_row.get(key)
        latest_value = latest_row.get(key)
        if _canonical_json(previous_value) == _canonical_json(latest_value):
            continue

        field_change: dict[str, Any] = {"field": key}

        if _is_scalar(previous_value) and _is_scalar(latest_value):
            field_change["old_value"] = previous_value
            field_change["new_value"] = latest_value
        else:
            field_change["old_value_kind"] = _value_kind(previous_value)
            field_change["new_value_kind"] = _value_kind(latest_value)
            field_change["old_value_hash"] = f"sha256:{_value_hash(previous_value)}"
            field_change["new_value_hash"] = f"sha256:{_value_hash(latest_value)}"

        fields.append(field_change)

    return fields


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _value_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _value_kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _display_registration(row: dict[str, Any]) -> str:
    return _clean(_first(row, "registration_number", "registerNumber", "RegNo", "reg_no"))


def _first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return ""


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _meta_date(metadata: dict[str, Any]) -> str:
    return _clean(_first(metadata, "extraction_date", "partition_date", "date"))


def _read_int(source: dict[str, Any], key: str, default: int) -> int:
    value = source.get(key)
    if isinstance(value, int) and value > 0:
        return value
    return default


if __name__ == "__main__":
    import json as _json

    fixture = Path(__file__).resolve().parent / "fixtures" / "sfda_getdrugs_daily_changes.inputs.json"
    payload = _json.loads(fixture.read_text(encoding="utf-8"))
    result = SfdaGetDrugsDailyChangesAdapter().invoke(payload, {"max_change_rows": 1000})
    print(_json.dumps(result, ensure_ascii=False, indent=2))