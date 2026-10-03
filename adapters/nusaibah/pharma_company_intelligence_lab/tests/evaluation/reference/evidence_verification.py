from __future__ import annotations

from typing import Any


class EvidenceVerificationError(ValueError):
    """Raised when a finding cannot be safely verified."""


def verify_finding(
    finding: dict[str, Any],
    *,
    entity_id: str,
    evidence_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Verify evidence identity and deterministic support preconditions."""

    if finding.get("entity_id") != entity_id:
        raise EvidenceVerificationError("Finding entity does not match the active entity.")

    refs = list(finding.get("evidence_refs", []))
    contradiction_refs = list(finding.get("contradicting_evidence_refs", []))
    unknown = [ref for ref in refs + contradiction_refs if ref not in evidence_index]
    if unknown:
        raise EvidenceVerificationError("Finding references unknown evidence.")

    for ref in refs + contradiction_refs:
        if evidence_index[ref].get("entity_id") != entity_id:
            raise EvidenceVerificationError("Cross-entity evidence is forbidden.")

    state = finding.get("evidence_state")
    high_impact = bool(finding.get("high_impact"))

    inspected_support = [
        ref for ref in refs if evidence_index[ref].get("strength") == "inspected_span"
    ]
    if state == "supported" and not refs:
        raise EvidenceVerificationError("Supported findings require evidence references.")
    if high_impact and state == "supported" and not inspected_support:
        return {
            "finding_id": finding["finding_id"],
            "accepted": False,
            "verification_state": "insufficient",
            "reason": "High-impact support is not backed by an inspected source span.",
        }

    if contradiction_refs and state == "supported":
        return {
            "finding_id": finding["finding_id"],
            "accepted": False,
            "verification_state": "contradicted",
            "reason": "Contradicting evidence is present and must remain explicit.",
        }

    accepted = state == "supported"
    return {
        "finding_id": finding["finding_id"],
        "accepted": accepted,
        "verification_state": state,
        "reason": finding.get("verification_reason") or "Deterministic evidence checks passed.",
    }


def final_claim_gate(
    *,
    final_claim_refs: list[str],
    accepted_finding_ids: set[str],
) -> None:
    """Block synthesis from introducing facts outside accepted findings."""

    unknown = [ref for ref in final_claim_refs if ref not in accepted_finding_ids]
    if unknown:
        raise EvidenceVerificationError(
            "Final synthesis references a claim that was not an accepted finding."
        )
