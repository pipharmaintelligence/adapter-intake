from __future__ import annotations

from typing import Any

COMPANY_ID_FIELDS: tuple[str, ...] = ("company_id", "id")
COMPANY_NAME_FIELDS: tuple[str, ...] = ("company", "company_name", "name")


def build_company_name_upserts(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Build logical upsert candidates for a governed model/database output.

    The returned payload is intent only. Core/Assets decide whether an approved
    output policy can perform the actual database upsert.
    """

    candidates: list[dict[str, Any]] = []
    value_fields: list[str] = []

    for record in records:
        company_id = _first_value(record, COMPANY_ID_FIELDS)
        current_name = _first_value(record, COMPANY_NAME_FIELDS)
        name_field = _first_present_key(record, COMPANY_NAME_FIELDS) or "company"
        id_field = _first_present_key(record, COMPANY_ID_FIELDS) or "id"
        if company_id is None or current_name is None:
            continue

        current_name_text = str(current_name).strip()
        if current_name_text == "":
            continue

        new_name = current_name_text if current_name_text.startswith("Best ") else f"Best {current_name_text}"
        if name_field not in value_fields:
            value_fields.append(name_field)
        candidates.append(
            {
                "operation": "upsert",
                "match": {id_field: company_id},
                "values": {name_field: new_name},
                "source": {
                    "original_name_field": name_field,
                    "original_name_present": True,
                },
            }
        )

    return {
        "format": "json",
        "write_mode": "upsert",
        "target_kind": "model_database_output",
        "candidate_count": len(candidates),
        "key_fields": ["id"],
        "value_fields": value_fields or ["company"],
        "candidates": candidates,
    }


def _first_value(record: dict[str, Any], fields: tuple[str, ...]) -> Any:
    for field in fields:
        if field in record and record[field] is not None:
            return record[field]
    return None


def _first_present_key(record: dict[str, Any], fields: tuple[str, ...]) -> str | None:
    for field in fields:
        if field in record:
            return field
    return None
