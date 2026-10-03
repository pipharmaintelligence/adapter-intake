from __future__ import annotations

import re
from typing import Any


ALLOWED_EXECUTION_STATES = frozenset({"completed", "incomplete", "blocked", "failed"})
ALLOWED_REVIEW_OUTCOMES = frozenset(
    {
        "review_complete",
        "review_complete_with_evidence_gaps",
        "review_incomplete",
        "blocked",
        "failed",
    }
)
ALLOWED_SCOPE_MODES = frozenset({"exhaustive_in_scope", "focused"})
ALLOWED_PERSISTENCE_STATES = frozenset(
    {"not_requested", "preview_only", "applied", "failed"}
)
ALLOWED_COVERAGE_STATES = frozenset(
    {"assigned", "reviewed", "excluded_by_scope", "inaccessible", "unreviewed"}
)
SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _safe_identifier(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or SAFE_IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{field} must be a bounded safe identifier.")
    return value


def project_review_status(result: dict[str, Any]) -> dict[str, Any]:
    """Return bounded operator status without prompts, evidence text, or provider payloads."""

    execution_state = result["execution_state"]
    review_outcome = result["review_outcome"]
    scope_mode = result["scope_mode"]
    persistence_state = result["persistence_state"]

    if execution_state not in ALLOWED_EXECUTION_STATES:
        raise ValueError("Invalid execution state.")
    if review_outcome not in ALLOWED_REVIEW_OUTCOMES:
        raise ValueError("Invalid review outcome.")
    if scope_mode not in ALLOWED_SCOPE_MODES:
        raise ValueError("Invalid scope mode.")
    if persistence_state not in ALLOWED_PERSISTENCE_STATES:
        raise ValueError("Invalid persistence state.")

    coverage = result["coverage"]
    if not isinstance(coverage, list):
        raise ValueError("coverage must be a list.")
    for item in coverage:
        if not isinstance(item, dict) or item.get("status") not in ALLOWED_COVERAGE_STATES:
            raise ValueError("Coverage contains an invalid status.")

    counts = {
        "total": len(coverage),
        "assigned": sum(item["status"] == "assigned" for item in coverage),
        "reviewed": sum(item["status"] == "reviewed" for item in coverage),
        "unreviewed": sum(item["status"] == "unreviewed" for item in coverage),
        "inaccessible": sum(item["status"] == "inaccessible" for item in coverage),
        "excluded_by_scope": sum(item["status"] == "excluded_by_scope" for item in coverage),
    }

    finding_ids = result["finding_ids"]
    limitations = result["limitations"]
    if not isinstance(finding_ids, list) or not isinstance(limitations, list):
        raise ValueError("finding_ids and limitations must be lists.")

    return {
        "schema_version": "review_status_projection.v1",
        "execution_state": execution_state,
        "review_outcome": review_outcome,
        "scope_mode": scope_mode,
        "coverage_counts": counts,
        "finding_count": len(finding_ids),
        "limitation_count": len(limitations),
        "persistence_state": persistence_state,
        "stop_reason": _safe_identifier(result.get("stop_reason"), field="stop_reason"),
        "next_action": _safe_identifier(result.get("next_action"), field="next_action"),
        "raw_content_included": False,
    }
