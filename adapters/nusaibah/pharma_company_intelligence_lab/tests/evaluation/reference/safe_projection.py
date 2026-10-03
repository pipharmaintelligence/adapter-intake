from __future__ import annotations

import re
from typing import Any

from review_contracts import ReviewContractError, validate_review_result


SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _safe_identifier(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or SAFE_IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{field} must be a bounded safe identifier.")
    return value


def project_review_status(
    result: dict[str, Any],
    *,
    required_requirement_ids: set[str],
    in_scope_source_ids: set[str],
) -> dict[str, Any]:
    """Return bounded operator status from a canonically validated review result."""

    if not isinstance(result, dict):
        raise ValueError("result must be an object.")

    review_result = {
        "schema_version": result.get("schema_version", "review_result.v1"),
        "scope_mode": result.get("scope_mode"),
        "execution_state": result.get("execution_state"),
        "review_outcome": result.get("review_outcome"),
        "coverage": result.get("coverage"),
        "finding_ids": result.get("finding_ids"),
        "limitations": result.get("limitations"),
        "persistence_state": result.get("persistence_state"),
    }
    try:
        validated = validate_review_result(
            review_result,
            required_requirement_ids=required_requirement_ids,
            in_scope_source_ids=in_scope_source_ids,
        )
    except ReviewContractError as exc:
        raise ValueError(str(exc)) from exc

    coverage = validated["coverage"]
    counts = {
        "total": len(coverage),
        "assigned": sum(item["status"] == "assigned" for item in coverage),
        "reviewed": sum(item["status"] == "reviewed" for item in coverage),
        "unreviewed": sum(item["status"] == "unreviewed" for item in coverage),
        "inaccessible": sum(item["status"] == "inaccessible" for item in coverage),
        "excluded_by_scope": sum(item["status"] == "excluded_by_scope" for item in coverage),
    }

    return {
        "schema_version": "review_status_projection.v1",
        "execution_state": validated["execution_state"],
        "review_outcome": validated["review_outcome"],
        "scope_mode": validated["scope_mode"],
        "coverage_counts": counts,
        "finding_count": len(validated["finding_ids"]),
        "limitation_count": len(validated["limitations"]),
        "persistence_state": validated["persistence_state"],
        "stop_reason": _safe_identifier(result.get("stop_reason"), field="stop_reason"),
        "next_action": _safe_identifier(result.get("next_action"), field="next_action"),
        "raw_content_included": False,
    }
