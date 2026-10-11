"""Claim-level, review-only packet for pharma adapter version 0.1.21.

The packet preserves accepted and withheld claims, the admitted citation
catalog, and the exact bounded evidence selection intended for eventual apply.
It grants no apply authority. Core remains the retention and persistence owner.
"""
from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

try:
    from .review_packet_v0_1_16 import canonical_bytes, require_output_bound
except ImportError:  # pragma: no cover - flat intake execution
    from review_packet_v0_1_16 import canonical_bytes, require_output_bound


SCHEMA_VERSION = "pharma_prepared_review.v2"


def build_review_packet_v0_1_21(
    prepared: list[dict[str, Any]],
    *,
    asset_identity: str,
    methodology_digest: str,
    memory_mode: str,
) -> dict[str, Any]:
    """Build one bounded packet from immutable per-company prepared states."""

    companies = [_company_packet(state) for state in prepared]
    body = {
        "schema_version": SCHEMA_VERSION,
        "asset_identity": asset_identity,
        "fixed_methodology_digest": methodology_digest,
        "memory_mode": memory_mode,
        "preparation_stage": "before_mutation",
        "review_state": "not_reviewed",
        "apply_authority": False,
        "companies": companies,
    }
    body["packet_sha256"] = "sha256:" + sha256(
        canonical_bytes(body)
    ).hexdigest()
    require_output_bound(body)
    return json.loads(canonical_bytes(body))


def _company_packet(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("incomplete_schema_preview"):
        return _incomplete_company_packet(state)

    candidate = state["memory_candidate"]
    selection = state["evidence_selection"]
    joined = state["joined_research"]
    memory = _section_proposal(
        role="company_memory",
        section=candidate.target_section,
        text=candidate.markdown,
        baseline_text=state["before_target_text"],
        baseline_digest=state["before_digest"],
    )
    memory.update(
        {
            "fact_ids": list(candidate.fact_ids),
            "pre_review_candidate_eligible": state[
                "pre_review_candidate_eligible"
            ],
            "mutation_eligible": False,
            "evidence_selection_digest": selection.selection_digest,
        }
    )

    learning = _section_proposal(
        role="company_methodology",
        section="Methodology Learning",
        text=state["methodology_learning_candidate"],
        baseline_text=state["methodology_learning_before_text"],
        baseline_digest=state["result"][
            "methodology_learning_before_digest"
        ],
    )
    learning.update(
        {
            "initialized": state["methodology_learning_handle"] is not None,
            "review_required": (
                state["methodology_learning_candidate"] is not None
            ),
            "mutation_eligible": False,
        }
    )

    return {
        "company_id": state["company_id"],
        "company_name": state["company_name"],
        "preparation_status": (
            "incomplete"
            if state["result"]["research_incomplete"]
            else "review_pending"
        ),
        "independent_review_status": "not_reviewed",
        "apply_authority": False,
        "memory_proposal": memory,
        "methodology_proposal": learning,
        "accepted_claims": [dict(item) for item in joined["claims"]],
        "withheld_claims": [
            dict(item) for item in joined.get("withheld_claims", [])
        ],
        "claim_evidence": _claim_evidence(joined),
        "evidence_granularity": "claim",
        "research_role_evidence": _role_evidence(state["research"]),
        "evidence_selection": _evidence_selection(selection),
        "memory_apply_citations": selection.public_citations(),
        "methodology_plan": state["methodology_plan"].to_agent_input(),
        "planner_requirements": list(
            state["methodology_plan"].requirement_catalog()
        ),
        "planner_chunks": list(state["planner_chunks"]),
        "critic": state["critic"],
        "strategic": state["strategic"],
        "benchmark": {
            "questions": list(state["benchmark_questions"]),
            "before": state["before_benchmark"],
            "projected": state["projected_after_benchmark"],
            "basis": "projected_memory_candidate",
            "committed": None,
        },
        "issues_annex": state["result"]["issues_annex"],
        "claim_evidence_issues": list(
            joined.get("claim_evidence_issues", [])
        ),
        "unresolved_agent_responses": state["result"][
            "unresolved_agent_responses"
        ],
        "residual_uncertainties": state["residual_uncertainties"],
    }


def _incomplete_company_packet(state: dict[str, Any]) -> dict[str, Any]:
    result = state["result"]
    return {
        "company_id": state["company_id"],
        "company_name": state["company_name"],
        "preparation_status": "incomplete",
        "independent_review_status": "not_reviewed",
        "apply_authority": False,
        "memory_proposal": {
            **_section_proposal(
                role="company_memory",
                section="Current Public Research",
                text=None,
                baseline_text="",
                baseline_digest=None,
            ),
            "fact_ids": [],
            "pre_review_candidate_eligible": False,
            "mutation_eligible": False,
            "evidence_selection_digest": None,
        },
        "methodology_proposal": {
            **_section_proposal(
                role="company_methodology",
                section="Methodology Learning",
                text=None,
                baseline_text="",
                baseline_digest=None,
            ),
            "initialized": None,
            "review_required": False,
            "mutation_eligible": False,
        },
        "accepted_claims": list(state.get("retained_claims", [])),
        "withheld_claims": [],
        "claim_evidence": None,
        "evidence_granularity": "claim; preparation incomplete",
        "research_role_evidence": _role_evidence(
            state.get("retained_research", {})
        ),
        "evidence_selection": {
            "schema_version": "pharma_memory_evidence_selection.v1",
            "selection_digest": None,
            "complete": False,
            "maximum_citations": 24,
            "fact_coverage": [],
            "uncovered_fact_ids": [],
            "omitted_counts_by_role": [],
            "selected_citation_refs": [],
        },
        "memory_apply_citations": [],
        "methodology_plan": (
            state["progress"]["methodology_plan"].to_agent_input()
            if state.get("progress", {}).get("methodology_plan")
            else None
        ),
        "planner_requirements": state.get("progress", {}).get(
            "planner_requirements",
            [],
        ),
        "planner_chunks": state.get("progress", {}).get(
            "planner_chunks",
            [],
        ),
        "critic": state.get("progress", {}).get("critic"),
        "strategic": state.get("progress", {}).get("strategic"),
        "benchmark": {
            "questions": [],
            "before": None,
            "projected": None,
            "basis": "not_evaluated",
            "committed": None,
        },
        "issues_annex": result["issues_annex"],
        "claim_evidence_issues": result.get("claim_evidence_issues", []),
        "unresolved_agent_responses": result[
            "unresolved_agent_responses"
        ],
        "residual_uncertainties": [
            "Preparation is incomplete; no candidate is approved."
        ],
    }


def _claim_evidence(joined: dict[str, Any]) -> dict[str, Any]:
    index = joined["claim_evidence_index"]
    return {
        "schema_version": index.schema_version,
        "index_digest": index.index_digest,
        "projection_digest": joined["claim_evidence_projection_digest"],
        "records": [
            {
                "claim_id": item.claim_id,
                "role": item.role,
                "section_id": item.section_id,
                "evidence_state": item.evidence_state,
                "citation_refs": list(item.citation_refs),
                "qualifiers": list(item.qualifiers),
                "issue_code": item.issue_code,
            }
            for item in index.records
        ],
        "citations": [
            {
                **item.public_value(),
                "role": item.role,
                "pass_number": item.pass_number,
                "ordinal": item.ordinal,
            }
            for item in index.citations
        ],
    }


def _evidence_selection(selection: Any) -> dict[str, Any]:
    return {
        "schema_version": selection.schema_version,
        "selection_digest": selection.selection_digest,
        "complete": selection.complete,
        "maximum_citations": selection.maximum_citations,
        "fact_coverage": [
            {
                "fact_id": item.fact_id,
                "status": item.status,
                "selected_citation_refs": list(
                    item.selected_citation_refs
                ),
                "available_citation_refs": list(
                    item.available_citation_refs
                ),
                "reason_code": item.reason_code,
            }
            for item in selection.fact_coverage
        ],
        "uncovered_fact_ids": list(selection.uncovered_fact_ids),
        "omitted_counts_by_role": [
            {"role": role, "count": count}
            for role, count in selection.omitted_counts_by_role
        ],
        "selected_citation_refs": [
            item.citation_ref for item in selection.selected_citations
        ],
    }


def _role_evidence(research: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "role": role,
            "sections": payload["sections"],
            "uncertainties": payload["uncertainties"],
            "citations": [
                {
                    "locator": citation.locator,
                    "title": citation.title,
                    "source_kind": citation.source_kind,
                    "provider_family": citation.provider_family,
                }
                for citation in payload["_citations"]
            ],
        }
        for role, payload in research.items()
    ]


def _section_proposal(
    *,
    role: str,
    section: str,
    text: str | None,
    baseline_text: str | None,
    baseline_digest: str | None,
) -> dict[str, Any]:
    replacement = None if text is None else text.rstrip() + "\n"
    return {
        "role": role,
        "target_section": section,
        "baseline_content_digest": baseline_digest,
        "baseline_section_text": baseline_text,
        "replacement_text": replacement,
        "replacement_sha256": (
            None if replacement is None else _digest(replacement)
        ),
    }


def _digest(value: str) -> str:
    return "sha256:" + sha256(value.encode("utf-8")).hexdigest()
