from __future__ import annotations

from typing import Any


class EvidenceVerificationError(ValueError):
    """Raised when a finding cannot be safely verified."""


SEMANTIC_STATES = frozenset({"supported", "contradicted", "insufficient"})


def verify_finding(
    finding: dict[str, Any],
    *,
    entity_id: str,
    evidence_index: dict[str, dict[str, Any]],
    semantic_verdict: dict[str, Any],
) -> dict[str, Any]:
    """Require an explicit semantic verifier result before accepting support.

    Deterministic checks establish identity, provenance, and evidence availability.
    They do not establish that evidence text entails a claim. A separate semantic
    verifier must therefore return a bounded verdict tied to the finding ID and
    exact evidence references.
    """

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

    if finding.get("evidence_state") == "supported" and not refs:
        raise EvidenceVerificationError("Supported findings require evidence references.")

    if not isinstance(semantic_verdict, dict):
        raise EvidenceVerificationError("Semantic verifier verdict is required.")
    if semantic_verdict.get("schema_version") != "review_semantic_verdict.v1":
        raise EvidenceVerificationError("Unsupported semantic verifier schema.")
    if semantic_verdict.get("finding_id") != finding.get("finding_id"):
        raise EvidenceVerificationError("Semantic verdict finding identity mismatch.")

    verdict_refs = semantic_verdict.get("evidence_refs")
    if not isinstance(verdict_refs, list) or verdict_refs != refs:
        raise EvidenceVerificationError("Semantic verdict must bind to exact supporting evidence refs.")

    semantic_state = semantic_verdict.get("state")
    if semantic_state not in SEMANTIC_STATES:
        raise EvidenceVerificationError("Invalid semantic verifier state.")

    high_impact = bool(finding.get("high_impact"))
    inspected_support = [
        ref for ref in refs if evidence_index[ref].get("strength") == "inspected_span"
    ]

    if high_impact and semantic_state == "supported" and not inspected_support:
        semantic_state = "insufficient"

    if contradiction_refs and semantic_state == "supported":
        semantic_state = "contradicted"

    accepted = (
        finding.get("evidence_state") == "supported"
        and semantic_state == "supported"
    )
    return {
        "finding_id": finding["finding_id"],
        "proposition_id": finding["proposition_id"],
        "polarity": finding["polarity"],
        "accepted": accepted,
        "verification_state": semantic_state,
        "semantic_verifier_id": semantic_verdict.get("verifier_id"),
        "reason_code": semantic_verdict.get("reason_code"),
    }


def final_claim_gate(
    *,
    final_claims: list[dict[str, Any]],
    accepted_findings: dict[str, dict[str, Any]],
    semantic_verdicts: dict[str, dict[str, Any]],
) -> None:
    """Block final text unless each claim is semantically equivalent to an accepted finding."""

    if not isinstance(final_claims, list):
        raise EvidenceVerificationError("final_claims must be a list.")

    for claim in final_claims:
        if not isinstance(claim, dict):
            raise EvidenceVerificationError("Final claim must be an object.")
        claim_id = claim.get("claim_id")
        finding_id = claim.get("finding_id")
        if not isinstance(claim_id, str) or not claim_id:
            raise EvidenceVerificationError("Final claim ID is required.")
        if finding_id not in accepted_findings:
            raise EvidenceVerificationError(
                "Final synthesis references a finding that was not accepted."
            )

        verdict = semantic_verdicts.get(claim_id)
        if not isinstance(verdict, dict):
            raise EvidenceVerificationError("Final semantic verifier verdict is required.")
        if verdict.get("schema_version") != "review_final_claim_verdict.v1":
            raise EvidenceVerificationError("Unsupported final claim verdict schema.")
        if verdict.get("claim_id") != claim_id or verdict.get("finding_id") != finding_id:
            raise EvidenceVerificationError("Final claim verdict identity mismatch.")
        if verdict.get("equivalent") is not True:
            raise EvidenceVerificationError(
                "Final claim is not semantically equivalent to its accepted finding."
            )
