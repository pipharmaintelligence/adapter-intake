"""Version-owned, inert evidence gaps and bounded review issues.

No provider, storage, approval or mutation authority lives in this helper.
Historical helpers stay immutable for previously promoted adapter versions.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

try:
    from .agent_contract import RESEARCH_ROLE_SECTIONS
    from .dossier_contract import CANONICAL_SECTIONS
    from .research_diagnostics_v0_1_17 import unresolved_research_payload
except ImportError:  # flat intake execution
    from agent_contract import RESEARCH_ROLE_SECTIONS
    from dossier_contract import CANONICAL_SECTIONS
    from research_diagnostics_v0_1_17 import unresolved_research_payload


QUALITY_RULES = frozenset({
    "research_citations_missing", "no_evidence_not_disposed", "critic_rejected",
    "citation_coverage_insufficient", "unsupported_claims_remaining",
    "required_sections_missing", "planner_requirements_unsatisfied",
})
GAP_TEXT = "No verified evidence is available for this item in this review."
PENDING_TEXT = "Final review is incomplete; no approved candidate was prepared for this section."
MAX_ISSUES_PER_COMPANY = 32  # bounded ordinary/resolver quotas are smaller


def diagnostic(*, role: str, stage: str, rule: str, field: str) -> dict[str, str]:
    return {"schema_version": "proof_failure_detail.v1", "proof_kind": "agent_contract",
            "role": role, "stage": stage, "rule": rule, "field": field}


def recoverable_quality(error: Exception) -> bool:
    proof = getattr(error, "proof_failure_detail", None)
    return (getattr(error, "code", None) == "pharma_agent_business_schema_invalid"
            and isinstance(proof, dict) and proof.get("stage") == "pre_synthesis_quality"
            and proof.get("rule") in QUALITY_RULES)


def no_evidence_payload(*, role: str, company_id: int) -> dict[str, Any]:
    value = unresolved_research_payload(role=role, company_id=company_id)
    value["uncertainties"] = [GAP_TEXT]
    for section in value["sections"]:
        section["content"] = "" if section["subsections"] else GAP_TEXT
        for subsection in section["subsections"]:
            subsection["content"] = GAP_TEXT
    return value


def issue(proof: dict[str, Any], *, category: str = "response_invalid",
          action: str = "withheld", withheld_claim_count: int = 0,
          pass_number: int | None = None) -> dict[str, Any]:
    # Callers supply static validator diagnostics, never exception prose/raw replies.
    return {"role": proof.get("role", "orchestration"), "stage": proof.get("stage", "agent_response_payload"),
            "field": proof.get("field", "business_payload"), "rule": proof.get("rule", "schema_invalid"),
            "category": category, "action": action,
            "section_ids": list(RESEARCH_ROLE_SECTIONS.get(proof.get("role"), ())),
            "withheld_claim_count": withheld_claim_count, "pass_number": pass_number}


def annex(research: dict[str, Any], proof: dict[str, Any] | None = None) -> dict[str, Any]:
    items = [deepcopy(payload["_issue"]) for payload in research.values() if payload.get("_issue")]
    if proof is not None:
        category = ("evidence_unavailable" if proof["rule"] == "no_usable_research_evidence"
                    else "quality_rejected" if proof["stage"] == "pre_synthesis_quality"
                    else "response_invalid")
        items.append(issue(proof, category=category, action="dependent_stages_skipped"))
    return {"schema_version": "pharma_review_issues.v1", "issue_count": len(items),
            "items": items[:MAX_ISSUES_PER_COMPANY], "truncated": len(items) > MAX_ISSUES_PER_COMPANY,
            "canonical_candidates_withheld": bool(items)}


def retained_research(research: dict[str, Any], critic: dict[str, Any] | None) -> dict[str, Any]:
    """Keep source-backed work pending review; remove known rejected role prose too.

    Existing evidence has role-level rather than claim/span-level linkage. Thus a
    rejected claim withholds that role's whole prose, not just its claims array.
    Unscoped contradictions cannot safely be attributed to one role.
    """
    withheld_roles: set[str] = set()
    if critic:
        rejected = [*critic["unsupported_claim_ids"], *critic["stale_claim_ids"]]
        for claim_id in rejected:
            role = claim_id.split(":", 1)[0]
            if role in research:
                withheld_roles.add(role)
            else:
                withheld_roles.update(research)  # unknown reference: no guessing
        if critic["contradiction_items"]:
            withheld_roles.update(research)
    return {role: payload for role, payload in research.items()
            if payload.get("_citations") and role not in withheld_roles}


def partial_sections(research: dict[str, Any]) -> list[dict[str, Any]]:
    available = {section["section_id"]: section for payload in research.values()
                 for section in payload["sections"]}
    sections = []
    for spec in CANONICAL_SECTIONS:
        if spec.section_id in available:
            sections.append(deepcopy(available[spec.section_id]))
        else:
            sections.append({"section_id": spec.section_id,
                             "content": "" if spec.subsections else PENDING_TEXT,
                             "subsections": [{"subsection_id": sub.subsection_id, "content": PENDING_TEXT}
                                             for sub in spec.subsections]})
    return sections
