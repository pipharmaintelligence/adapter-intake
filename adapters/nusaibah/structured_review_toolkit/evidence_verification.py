from __future__ import annotations

import hashlib
import json
from typing import Any


class EvidenceVerificationError(ValueError):
    """Raised when a finding cannot be safely verified."""


SEMANTIC_STATES = frozenset({"supported", "contradicted", "insufficient"})


def _stable_digest(value: Any) -> str:
    """Return a deterministic digest for JSON-compatible semantic verifier inputs."""

    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise EvidenceVerificationError(
            "Semantic verifier input must be JSON-compatible."
        ) from exc
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def finding_semantic_input_digest(
    finding: dict[str, Any],
    evidence_index: dict[str, dict[str, Any]],
) -> str:
    """Bind one verifier verdict to the exact finding and evidence content."""

    refs = list(finding.get("evidence_refs", []))
    contradiction_refs = list(finding.get("contradicting_evidence_refs", []))
    all_refs = refs + contradiction_refs
    unknown = [ref for ref in all_refs if ref not in evidence_index]
    if unknown:
        raise EvidenceVerificationError("Finding references unknown evidence.")

    material = {
        "finding": finding,
        "evidence": [
            {"ref": ref, "record": evidence_index[ref]}
            for ref in all_refs
        ],
    }
    return _stable_digest(material)


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
    verifier must therefore return a bounded verdict tied to the exact finding and
    evidence content digest, not only reusable IDs.
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

    verification_input_digest = finding_semantic_input_digest(finding, evidence_index)
    if semantic_verdict.get("input_digest") != verification_input_digest:
        raise EvidenceVerificationError(
            "Semantic verifier verdict does not match the exact finding/evidence content."
        )

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

    # A positive supplied verdict cannot upgrade a non-positive finding state.
    if finding.get("evidence_state") == "contradicted":
        semantic_state = "contradicted"
    elif finding.get("evidence_state") != "supported" and semantic_state == "supported":
        semantic_state = "insufficient"

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
        "verification_input_digest": verification_input_digest,
        "semantic_verifier_id": semantic_verdict.get("verifier_id"),
        "reason_code": semantic_verdict.get("reason_code"),
    }
