from __future__ import annotations

from collections import defaultdict
from typing import Any


class ReconciliationError(ValueError):
    """Raised when global finding reconciliation detects a blocking inconsistency."""


def _text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReconciliationError(f"{field} must be non-empty text.")
    return value.strip()


def reconcile_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a compact cross-specialist ledger and preserve global conflicts.

    Conflicts are tracked both within one requirement/date/jurisdiction identity
    and across date/jurisdiction variants for the same entity + requirement.
    The function never resolves a disagreement by majority vote.
    """

    if not isinstance(findings, list):
        raise ReconciliationError("findings must be a list.")

    finding_ids: set[str] = set()
    by_exact_key: dict[
        tuple[str, str, str | None, str | None],
        list[dict[str, Any]],
    ] = defaultdict(list)
    by_requirement: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for finding in findings:
        if not isinstance(finding, dict):
            raise ReconciliationError("Every finding must be an object.")
        finding_id = _text(finding.get("finding_id"), field="finding_id")
        if finding_id in finding_ids:
            raise ReconciliationError("Finding IDs must be globally unique.")
        finding_ids.add(finding_id)

        entity_id = _text(finding.get("entity_id"), field="entity_id")
        requirement_id = _text(finding.get("requirement_id"), field="requirement_id")
        state = finding.get("evidence_state")
        if state not in {"supported", "contradicted", "insufficient", "not_applicable"}:
            raise ReconciliationError("Invalid finding evidence state.")

        date = finding.get("date")
        jurisdiction = finding.get("jurisdiction")
        if date is not None and (not isinstance(date, str) or not date.strip()):
            raise ReconciliationError("Finding date must be non-empty text or null.")
        if jurisdiction is not None and (
            not isinstance(jurisdiction, str) or not jurisdiction.strip()
        ):
            raise ReconciliationError("Finding jurisdiction must be non-empty text or null.")

        exact_key = (entity_id, requirement_id, date, jurisdiction)
        requirement_key = (entity_id, requirement_id)
        by_exact_key[exact_key].append(finding)
        by_requirement[requirement_key].append(finding)

    conflicts: list[dict[str, Any]] = []
    conflict_signatures: set[tuple[Any, ...]] = set()
    accepted_ids: list[str] = []

    def add_conflict(
        *,
        conflict_type: str,
        entity_id: str,
        requirement_id: str,
        items: list[dict[str, Any]],
    ) -> None:
        signature = (
            conflict_type,
            entity_id,
            requirement_id,
            tuple(sorted(item["finding_id"] for item in items)),
        )
        if signature in conflict_signatures:
            return
        conflict_signatures.add(signature)
        conflicts.append(
            {
                "conflict_type": conflict_type,
                "entity_id": entity_id,
                "requirement_id": requirement_id,
                "finding_ids": sorted(item["finding_id"] for item in items),
                "states": sorted({item["evidence_state"] for item in items}),
                "dates": sorted({item["date"] for item in items if item.get("date") is not None}),
                "jurisdictions": sorted(
                    {
                        item["jurisdiction"]
                        for item in items
                        if item.get("jurisdiction") is not None
                    }
                ),
            }
        )

    for key, items in by_exact_key.items():
        states = {item["evidence_state"] for item in items}
        if "contradicted" in states or (
            "supported" in states and "insufficient" in states
        ):
            add_conflict(
                conflict_type="evidence_state",
                entity_id=key[0],
                requirement_id=key[1],
                items=items,
            )
        for item in items:
            if item["evidence_state"] == "supported":
                accepted_ids.append(item["finding_id"])

    for (entity_id, requirement_id), items in by_requirement.items():
        supported = [item for item in items if item["evidence_state"] == "supported"]
        if len(supported) < 2:
            continue
        dates = {item.get("date") for item in supported}
        jurisdictions = {item.get("jurisdiction") for item in supported}
        if len(dates) > 1:
            add_conflict(
                conflict_type="date_variation",
                entity_id=entity_id,
                requirement_id=requirement_id,
                items=supported,
            )
        if len(jurisdictions) > 1:
            add_conflict(
                conflict_type="jurisdiction_variation",
                entity_id=entity_id,
                requirement_id=requirement_id,
                items=supported,
            )

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

    if isinstance(blocking_conflict_count, bool) or not isinstance(blocking_conflict_count, int):
        raise ReconciliationError("blocking_conflict_count must be an integer.")
    if blocking_conflict_count < 0:
        raise ReconciliationError("blocking_conflict_count cannot be negative.")
    if len(candidate_finding_ids) != len(set(candidate_finding_ids)):
        raise ReconciliationError("Memory candidate finding IDs must be unique.")

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
        "mutation_authorized": False,
        "preview": preview,
    }
