from __future__ import annotations

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


def project_review_status(result: dict[str, Any]) -> dict[str, Any]:
    """Return bounded operator status without prompts, evidence text, or provider payloads."""

    execution_state = result["execution_state"]
    review_outcome = result["review_outcome"]
    if execution_state not in ALLOWED_EXECUTION_STATES:
        raise ValueError("Invalid execution state.")
    if review_outcome not in ALLOWED_REVIEW_OUTCOMES:
        raise ValueError("Invalid review outcome.")

    coverage = result["coverage"]
    counts = {
        "total": len(coverage),
        "reviewed": sum(item["status"] == "reviewed" for item in coverage),
        "unreviewed": sum(item["status"] == "unreviewed" for item in coverage),
        "inaccessible": sum(item["status"] == "inaccessible" for item in coverage),
        "excluded_by_scope": sum(item["status"] == "excluded_by_scope" for item in coverage),
    }

    return {
        "schema_version": "review_status_projection.v1",
        "execution_state": execution_state,
        "review_outcome": review_outcome,
        "scope_mode": result["scope_mode"],
        "coverage_counts": counts,
        "finding_count": len(result["finding_ids"]),
        "limitation_count": len(result["limitations"]),
        "persistence_state": result["persistence_state"],
        "stop_reason": result.get("stop_reason"),
        "next_action": result.get("next_action"),
        "raw_content_included": False,
    }
