from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MAX_COMPANY_IDS = 5
SUPPORTED_OBJECTIVE = "company_intelligence_memory"
SUPPORTED_RESEARCH_DEPTHS = frozenset({"deep"})
SUPPORTED_MEMORY_MODES = frozenset({"preview", "apply"})


@dataclass(frozen=True)
class BatchRequest:
    """Validated semantic launch variables for one governed company batch."""

    company_ids: tuple[int, ...]
    objective: str
    research_depth: str
    memory_mode: str
    publish_dossier: bool


def validate_batch_request(inputs: dict[str, Any]) -> BatchRequest:
    """Validate the bounded semantic launch contract."""
    variables = inputs.get("variables", {})
    if not isinstance(variables, dict):
        raise ValueError("inputs.variables must be an object.")

    execution_scope = variables.get("execution_scope", "batch")
    if execution_scope != "batch":
        raise ValueError("variables.execution_scope must equal 'batch'.")

    raw_ids = variables.get("company_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise ValueError("variables.company_ids must be a non-empty list.")
    if len(raw_ids) > MAX_COMPANY_IDS:
        raise ValueError(f"variables.company_ids must contain at most {MAX_COMPANY_IDS} ids.")

    company_ids: list[int] = []
    for value in raw_ids:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("variables.company_ids must contain positive integers only.")
        company_ids.append(value)

    if len(set(company_ids)) != len(company_ids):
        raise ValueError("variables.company_ids must not contain duplicates.")

    objective = str(variables.get("objective", SUPPORTED_OBJECTIVE)).strip()
    if objective != SUPPORTED_OBJECTIVE:
        raise ValueError(f"variables.objective must equal '{SUPPORTED_OBJECTIVE}'.")

    research_depth = str(variables.get("research_depth", "deep")).strip()
    if research_depth not in SUPPORTED_RESEARCH_DEPTHS:
        raise ValueError("variables.research_depth is not supported by v0.1.0.")

    memory_mode = str(variables.get("memory_mode", "preview")).strip()
    if memory_mode not in SUPPORTED_MEMORY_MODES:
        raise ValueError("variables.memory_mode must be 'preview' or 'apply'.")

    publish_dossier = variables.get("publish_dossier", False)
    if not isinstance(publish_dossier, bool):
        raise ValueError("variables.publish_dossier must be boolean.")

    return BatchRequest(
        company_ids=tuple(company_ids),
        objective=objective,
        research_depth=research_depth,
        memory_mode=memory_mode,
        publish_dossier=publish_dossier,
    )


def resolve_company_records(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    """Return governed company records from either supported runtime envelope."""
    companies = inputs.get("companies", [])

    if isinstance(companies, list):
        records = companies
    elif isinstance(companies, dict) and isinstance(companies.get("records"), list):
        records = companies["records"]
    else:
        raise ValueError("inputs.companies must be a record list or records envelope.")

    if not all(isinstance(record, dict) for record in records):
        raise ValueError("inputs.companies records must be objects.")

    return [dict(record) for record in records]


def order_records_for_request(
    records: list[dict[str, Any]],
    request: BatchRequest,
) -> list[dict[str, Any]]:
    """Require exact batch identity parity and return caller-ordered rows."""
    by_id: dict[int, dict[str, Any]] = {}
    for record in records:
        company_id = record.get("company_id")
        if isinstance(company_id, bool) or not isinstance(company_id, int) or company_id <= 0:
            raise ValueError("Each governed company record must contain a positive integer company_id.")
        if company_id in by_id:
            raise ValueError("Governed company records must not contain duplicate company_id values.")
        by_id[company_id] = record

    requested = set(request.company_ids)
    resolved = set(by_id)
    if requested != resolved:
        raise ValueError("Resolved company_id set must exactly match variables.company_ids.")

    return [by_id[company_id] for company_id in request.company_ids]


def company_name(record: dict[str, Any]) -> str:
    """Return a stable display name from one governed company row."""
    for key in ("company_name", "company", "name", "label"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"Company {record['company_id']}"


def project_company_baseline(record: dict[str, Any]) -> dict[str, Any]:
    """Project one governed company row into bounded scalar business context."""
    projected: dict[str, Any] = {}
    maximum_fields = 48
    maximum_string_chars = 4000

    for key in sorted(record):
        if len(projected) >= maximum_fields:
            break
        if not isinstance(key, str) or not key or len(key) > 128:
            continue
        lowered = key.lower()
        if any(
            fragment in lowered
            for fragment in (
                "password",
                "secret",
                "credential",
                "authorization",
                "token",
                "header",
                "presigned",
                "storage_path",
                "object_key",
                "callback",
                "runtime_manifest",
            )
        ):
            continue

        value = record[key]
        if value is None or isinstance(value, (bool, int, float)):
            projected[key] = value
        elif isinstance(value, str):
            projected[key] = value[:maximum_string_chars]
        elif isinstance(value, list) and len(value) <= 20 and all(
            item is None or isinstance(item, (bool, int, float, str)) for item in value
        ):
            projected[key] = [
                item[:maximum_string_chars] if isinstance(item, str) else item
                for item in value
            ]

    company_id = record.get("company_id")
    if company_id not in projected:
        projected["company_id"] = company_id
    projected["company_name"] = company_name(record)
    return projected
