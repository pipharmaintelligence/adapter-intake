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
    """Reconcile only semantically verified findings and preserve contradictions."""

    if not isinstance(findings, list):
        raise ReconciliationError("findings must be a list.")

    finding_ids: set[str] = set()
    by_proposition: dict[
        tuple[str, str, str, str | None, str | None],
        list[dict[str, Any]],
    ] = defaultdict(list)
    accepted_ids: list[str] = []

    for finding in findings:
        if not isinstance(finding, dict):
            raise ReconciliationError("Every finding must be an object.")
        finding_id = _text(finding.get("finding_id"), field="finding_id")
        if finding_id in finding_ids:
            raise ReconciliationError("Finding IDs must be globally unique.")
        finding_ids.add(finding_id)

        entity_id = _text(finding.get("entity_id"), field="entity_id")
        requirement_id = _text(finding.get("requirement_id"), field="requirement_id")
        proposition_id = _text(finding.get("proposition_id"), field="proposition_id")
        polarity = finding.get("polarity")
        if polarity not in {"affirmed", "negated"}:
            raise ReconciliationError("Finding polarity must be affirmed or negated.")

        verification_state = finding.get("verification_state")
        if verification_state not in {"supported", "contradicted", "insufficient"}:
            raise ReconciliationError("Finding must carry a semantic verification state.")

        date = finding.get("date")
        jurisdiction = finding.get("jurisdiction")
        if date is not None and (not isinstance(date, str) or not date.strip()):
            raise ReconciliationError("Finding date must be non-empty text or null.")
        if jurisdiction is not None and (
            not isinstance(jurisdiction, str) or not jurisdiction.strip()
        ):
            raise ReconciliationError("Finding jurisdiction must be non-empty text or null.")

        key = (entity_id, requirement_id, proposition_id, date, jurisdiction)
        by_proposition[key].append(finding)
        if verification_state == "supported":
            accepted_ids.append(finding_id)

    conflicts: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    def add_conflict(conflict_type: str, items: list[dict[str, Any]]) -> None:
        signature = (
            conflict_type,
            tuple(sorted(item["finding_id"] for item in items)),
        )
        if signature in seen:
            return
        seen.add(signature)
        first = items[0]
        conflicts.append(
            {
                "conflict_type": conflict_type,
                "entity_id": first["entity_id"],
                "requirement_id": first["requirement_id"],
                "proposition_id": first["proposition_id"],
                "finding_ids": sorted(item["finding_id"] for item in items),
                "polarities": sorted({item["polarity"] for item in items}),
                "verification_states": sorted(
                    {item["verification_state"] for item in items}
                ),
                "dates": sorted(
                    {item["date"] for item in items if item.get("date") is not None}
                ),
                "jurisdictions": sorted(
                    {
                        item["jurisdiction"]
                        for item in items
                        if item.get("jurisdiction") is not None
                    }
                ),
            }
        )

    for items in by_proposition.values():
        states = {item["verification_state"] for item in items}
        supported = [item for item in items if item["verification_state"] == "supported"]
        if "contradicted" in states or (
            "supported" in states and "insufficient" in states
        ):
            add_conflict("verification_state", items)
        if len({item["polarity"] for item in supported}) > 1:
            add_conflict("opposed_supported_propositions", supported)

    by_requirement_proposition: dict[
        tuple[str, str, str], list[dict[str, Any]]
    ] = defaultdict(list)
    for items in by_proposition.values():
        for item in items:
            if item["verification_state"] == "supported":
                by_requirement_proposition[
                    (item["entity_id"], item["requirement_id"], item["proposition_id"])
                ].append(item)

    for items in by_requirement_proposition.values():
        if len({item.get("date") for item in items}) > 1:
            add_conflict("date_variation", items)
        if len({item.get("jurisdiction") for item in items}) > 1:
            add_conflict("jurisdiction_variation", items)

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
        "reason": "Candidate references only semantically verified findings.",
        "mutation_authorized": False,
        "preview": preview,
    }
