from __future__ import annotations

from typing import Any


AGENT_FIELDS: list[str] = [
    "id",
    "agent",
    "headquarter",
    "address_line1",
    "address_line2",
    "telephone",
    "website",
    "description",
    "created_at",
    "updated_at",
]



def normalize_agent_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return one agent record with the approved 10-field output shape.

    The record is already delivered by the governed runtime input path. This
    helper does not fetch from DLM Core, OBS, storage, or a database.

    """

    return {field: record.get(field) for field in AGENT_FIELDS}


def build_dump_agents_by_agent_id(
    records: list[dict[str, Any]],
    limit: int = 10,
) -> dict[str, Any]:
    """Build logical per-agent JSON output for the first N agents.

    This does not write folders or files. Partition intent is represented as
    structured metadata only. Runtime/Core owns any future materialization.
    """

    results: list[dict[str, Any]] = []

    for record in records[:limit]:
        normalized = normalize_agent_record(record)
        agent_id = normalized.get("id")

        results.append(
            {
                "partition": {
                    "agent_id": agent_id,
                },
                "filename": "agent.json",
                "logical_key": f"agent_id:{agent_id}",
                "record": normalized,
            }
        )

    return {
        # The target DLM node allows JSON files.
        # Partition semantics stay explicit in separate metadata below.
        "format": "json",
        "layout": "partitioned",
        "partition_style": "hive",
        "partition_key": "agent_id",
        "filename": "agent.json",
        "record_count": len(results),
        "fields": AGENT_FIELDS,
        "results": results,
    }


def build_dump_agents_full(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the full logical agents dump from runtime-delivered records.

    This output contains all records delivered to the adapter by the governed
    runtime input. It does not fetch additional records and does not write
    files.
    """

    normalized_records = [normalize_agent_record(record) for record in records]

    return {
        "format": "json",
        "record_count": len(normalized_records),
        "fields": AGENT_FIELDS,
        "records": normalized_records,
    }
