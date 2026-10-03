from __future__ import annotations

from collections import defaultdict
from typing import Any


class ReconciliationError(ValueError):
    """Raised when global finding reconciliation detects a blocking inconsistency."""


def reconcile_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a compact cross-specialist ledger and preserve conflicts."""

    by_key: dict[tuple[str, str, str | None, str | None], list[dict[str, Any]]] = defaultdict(list)
    for finding in findings:
        key = (
            finding["entity_id"],
            finding["requirement_id"],
            finding.get("date"),
            finding.get("jurisdiction"),
        )
        by_key[key].append(finding)

    conflicts: list[dict[str, Any]] = []
    accepted_ids: list[str] = []

    for key, items in by_key.items():
        states = {item["evidence_state"] for item in items}
        if "contradicted" in states or (
            "supported" in states and "insufficient" in states
        ):
            conflicts.append(
                {
                    "entity_id": key[0],
                    "requirement_id": key[1],
                    "date": key[2],
                    "jurisdiction": key[3],
                    "finding_ids": [item["finding_id"] for item in items],
                    "states": sorted(states),
                }
            )
        for item in items:
            if item["evidence_state"] == "supported":
                accepted_ids.append(item["finding_id"])

    return {
        "schema_version": "review_consistency_ledger.v1",
        "accepted_finding_ids": sorted(set(accepted_ids)),
        "conflicts": conflicts,
        "blocking_conflict_count": len(conflicts),
    }


def gate_memory_candidates(
    *,
    candidate_finding_ids: list[str],
    accepted_finding_ids: set[str],
    blocking_conflict_count: int,
    preview: bool,
) -> dict[str, Any]:
    """Keep memory eligibility separate from mutation authority."""

    if blocking_conflict_count:
        return {
            "eligible": False,
            "reason": "Blocking cross-section conflicts remain.",
            "mutation_authorized": False,
        }
    if not set(candidate_finding_ids).issubset(accepted_finding_ids):
        return {
            "eligible": False,
            "reason": "Memory candidate contains an unaccepted finding.",
            "mutation_authorized": False,
        }
    return {
        "eligible": True,
        "reason": "Candidate references only accepted findings.",
        "mutation_authorized": False if preview else False,
    }
