"""Build bounded review-pending company results for pharma adapter 0.1.21.

This module converts already validated orchestration state into the public
company result and the internal prepared-state envelope consumed by the review
packet. It never calls Agents, providers, storage, publication, or Dynamic Skill
mutation helpers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from . import legacy_preparation_helpers_v0_1_21 as legacy
    from .memory_citation_selection_v0_1_21 import EvidenceSelection
except ImportError:  # pragma: no cover - flat intake execution
    import legacy_preparation_helpers_v0_1_21 as legacy
    from memory_citation_selection_v0_1_21 import EvidenceSelection


@dataclass(frozen=True)
class CompanyPreparationEvidence:
    """Validated immutable inputs for one review-pending company result."""

    company_id: int
    company_name: str
    review_passes: int
    before_digest: str | None
    before_target_text: str | None
    memory_initialized: bool
    methodology_handle: Any | None
    methodology_learning_text: str
    methodology_learning_candidate: str | None
    methodology_learning_rule_ids: tuple[str, ...]
    methodology_learning_proposal_digest: str | None
    methodology_learning_previous_preserved: bool
    methodology_learning_planner_snapshot_included: bool
    methodology_learning_withheld_reason: str | None
    methodology_plan: Any
    planner_chunks: tuple[dict[str, Any], ...]
    before_benchmark: dict[str, Any]
    projected_after_benchmark: dict[str, Any]
    benchmark_questions: tuple[dict[str, Any], ...]
    research: dict[str, dict[str, Any]]
    joined_research: dict[str, Any]
    strategic: dict[str, Any]
    critic: dict[str, Any]
    synthesis: dict[str, Any]
    memory_candidate: Any
    evidence_selection: EvidenceSelection
    benchmark_non_regression: bool
    benchmark_improvement_count: int
    candidate_changed: bool
    pre_review_candidate_eligible: bool
    research_incomplete: bool
    agent_counts: dict[str, int]
    recovery_trace: tuple[dict[str, Any], ...]


def build_prepared_company_state_v0_1_21(
    evidence: CompanyPreparationEvidence,
) -> dict[str, Any]:
    """Build one result while keeping independent review as a separate gate."""

    before_counts = legacy.benchmark_counts(evidence.before_benchmark)
    after_counts = legacy.benchmark_counts(evidence.projected_after_benchmark)
    joined = evidence.joined_research
    selection = evidence.evidence_selection
    candidate = evidence.memory_candidate
    claim_issues = list(joined.get("claim_evidence_issues", []))
    quality_issues = list(joined.get("claim_quality_issues", claim_issues))
    withheld_claims = list(joined.get("withheld_claims", []))
    withheld_section_ids = list(joined.get("withheld_section_ids", []))

    automated_gate_passed = (
        not evidence.research_incomplete and selection.complete
    )

    if evidence.research_incomplete:
        memory_status = "withheld_incomplete"
    elif not selection.complete:
        memory_status = "withheld_evidence_selection_incomplete"
    elif evidence.pre_review_candidate_eligible:
        memory_status = "review_required"
    else:
        memory_status = "no_change_recommended"

    if evidence.methodology_learning_withheld_reason is not None:
        methodology_status = "withheld_learning_budget"
    elif evidence.methodology_learning_candidate is not None:
        methodology_status = (
            "review_required_incomplete"
            if evidence.research_incomplete
            else "review_required"
        )
    else:
        methodology_status = (
            "withheld_incomplete"
            if evidence.research_incomplete
            else "no_change_recommended"
        )

    result = {
        "company_id": evidence.company_id,
        "company_name": evidence.company_name,
        "status": "completed",
        "business_result_state": (
            "incomplete" if evidence.research_incomplete else "review_pending"
        ),
        "sections": evidence.synthesis["sections"],
        "citation_count": len(joined["citations"]),
        "citation_sources": legacy._citation_output(joined["citations"]),
        "verified_reference_count": 0,
        "accepted_claim_count": len(joined["claims"]),
        "withheld_claim_count": len(withheld_claims),
        "withheld_section_ids": withheld_section_ids,
        "claim_evidence_issue_count": len(claim_issues),
        "claim_evidence_issues": claim_issues,
        "claim_quality_issue_count": len(quality_issues),
        "claim_quality_issues": quality_issues,
        "claim_evidence_projection_digest": joined[
            "claim_evidence_projection_digest"
        ],
        "unsupported_claim_count": len(
            evidence.critic["unsupported_claim_ids"]
        ),
        "contradiction_count": len(evidence.critic["contradiction_items"]),
        "stale_claim_count": len(evidence.critic["stale_claim_ids"]),
        "novel_fact_count": len(candidate.fact_ids),
        "duplicate_memory_fact_count": 0,
        "methodology_planner_call_count": evidence.agent_counts.get(
            legacy.PLANNER_ROLE,
            0,
        ),
        "planner_required_question_count": (
            sum(
                len(focus.questions)
                for focus in evidence.methodology_plan.research_focus
            )
            + len(evidence.methodology_plan.cross_cutting_questions)
        ),
        "planner_focus_item_count": len(
            evidence.methodology_plan.research_focus
        ),
        "planner_unmet_requirement_count": len(
            evidence.critic["unmet_plan_requirements"]
        ),
        "research_role_count": len(legacy.RESEARCH_ROLES),
        "research_claim_count": len(joined["claims"]),
        "specialist_agent_call_count": sum(
            evidence.agent_counts.get(role, 0)
            for role in legacy.RESEARCH_ROLES
        ),
        "search_enabled_agent_call_count": sum(
            evidence.agent_counts.get(role, 0)
            for role in legacy.RESEARCH_ROLES
        ),
        "portfolio_review_passes_requested": evidence.review_passes,
        "portfolio_review_pass_count": len(
            evidence.research["portfolio_researcher"]["_review_trace"]
        ),
        "portfolio_reflection_pass_count": max(
            0,
            len(evidence.research["portfolio_researcher"]["_review_trace"])
            - 1,
        ),
        "portfolio_review_trace": evidence.research[
            "portfolio_researcher"
        ]["_review_trace"],
        "research_resolver_agent_call_count": sum(
            payload["_resolver_call_count"]
            for payload in evidence.research.values()
        ),
        "research_incomplete": evidence.research_incomplete,
        "issues_annex": legacy.issues_annex(evidence.research),
        "agent_schema_incomplete": False,
        "unresolved_agent_responses": [],
        "agent_response_resolver_call_count": evidence.agent_counts.get(
            legacy.RESEARCH_RESOLVER_ROLE,
            0,
        ),
        "agent_response_recovery_trace": [
            dict(item) for item in evidence.recovery_trace
        ],
        "unresolved_research_responses": list(
            joined["unresolved_research_responses"]
        ),
        "research_response_repair_count": sum(
            repair["count"]
            for payload in evidence.research.values()
            for repair in payload["_response_repairs"]
        ),
        "research_response_repairs": [
            {"role": role, **repair}
            for role, payload in evidence.research.items()
            for repair in payload["_response_repairs"]
        ],
        "no_evidence_research_roles": [
            role
            for role in legacy.RESEARCH_ROLES
            if not evidence.research[role]["claims"]
        ],
        "required_section_coverage_count": len(
            evidence.synthesis["sections"]
        ),
        "quality_gate_passed": automated_gate_passed,
        "automated_quality_gate_passed": automated_gate_passed,
        "independent_review_status": "not_reviewed",
        "evidence_selection_complete": selection.complete,
        "evidence_selection_digest": selection.selection_digest,
        "evidence_selection_uncovered_fact_ids": list(
            selection.uncovered_fact_ids
        ),
        "evidence_selection_selected_citation_count": len(
            selection.selected_citations
        ),
        "benchmark_question_count": len(evidence.benchmark_questions),
        "benchmark_before_covered_count": before_counts["covered"],
        "benchmark_before_partially_covered_count": before_counts[
            "partially_covered"
        ],
        "benchmark_after_covered_count": after_counts["covered"],
        "benchmark_after_partially_covered_count": after_counts[
            "partially_covered"
        ],
        "benchmark_improvement_count": evidence.benchmark_improvement_count,
        "benchmark_non_regression": evidence.benchmark_non_regression,
        "benchmark_result_basis": "projected_memory_candidate",
        "memory_mutation_eligible": False,
        "memory_pre_review_candidate_eligible": (
            evidence.pre_review_candidate_eligible
        ),
        "memory_initialized": evidence.memory_initialized,
        "memory_initialization_required": not evidence.memory_initialized,
        "benchmark_before_basis": (
            "existing_memory_agent_review"
            if evidence.memory_initialized
            else "deterministic_absent_memory"
        ),
        "methodology_learning_update_status": methodology_status,
        "methodology_learning_rule_ids": list(
            evidence.methodology_learning_rule_ids
        ),
        "methodology_learning_proposal_digest": (
            evidence.methodology_learning_proposal_digest
        ),
        "methodology_learning_previous_preserved": (
            evidence.methodology_learning_previous_preserved
        ),
        "methodology_learning_planner_snapshot_included": (
            evidence.methodology_learning_planner_snapshot_included
        ),
        "methodology_learning_apply_authority": False,
        "methodology_learning_withheld_reason": evidence.methodology_learning_withheld_reason,
        "methodology_learning_change_id": None,
        "methodology_learning_before_digest": (
            evidence.methodology_handle.content_digest()
            if evidence.methodology_handle is not None
            else None
        ),
        "methodology_learning_after_digest": None,
        "methodology_learning_readback_verified": False,
        "memory_update_status": memory_status,
        "memory_change_id": None,
        "memory_before_digest": evidence.before_digest,
        "memory_after_digest": None,
        "memory_readback_verified": False,
        "residual_uncertainty_count": len(
            evidence.synthesis["residual_uncertainties"]
        ),
    }

    return {
        "company_id": evidence.company_id,
        "company_name": evidence.company_name,
        "result": result,
        "before_digest": evidence.before_digest,
        "before_target_text": evidence.before_target_text,
        "methodology_learning_before_text": (
            evidence.methodology_learning_text
        ),
        "research": evidence.research,
        "joined_research": joined,
        "critic": evidence.critic,
        "strategic": evidence.strategic,
        "residual_uncertainties": evidence.synthesis[
            "residual_uncertainties"
        ],
        "before_benchmark": evidence.before_benchmark,
        "methodology_plan": evidence.methodology_plan,
        "planner_chunks": evidence.planner_chunks,
        "methodology_learning_handle": evidence.methodology_handle,
        "methodology_learning_candidate": (
            evidence.methodology_learning_candidate
        ),
        "methodology_learning_rule_ids": (
            evidence.methodology_learning_rule_ids
        ),
        "methodology_learning_proposal_digest": (
            evidence.methodology_learning_proposal_digest
        ),
        "methodology_learning_previous_preserved": (
            evidence.methodology_learning_previous_preserved
        ),
        "methodology_learning_planner_snapshot_included": (
            evidence.methodology_learning_planner_snapshot_included
        ),
        "methodology_learning_withheld_reason": evidence.methodology_learning_withheld_reason,
        "projected_after_benchmark": evidence.projected_after_benchmark,
        "benchmark_questions": evidence.benchmark_questions,
        "memory_candidate": candidate,
        "citations": joined["citations"],
        "evidence_selection": selection,
        "memory_mutation_eligible": False,
        "pre_review_candidate_eligible": (
            evidence.pre_review_candidate_eligible
        ),
    }


def augment_incomplete_company_state_v0_1_21(
    state: dict[str, Any],
) -> dict[str, Any]:
    """Add explicit review/evidence fields to a legacy incomplete preview."""

    result = state["result"]
    progress = state.get("progress", {})
    joined = progress.get("joined_research", {})
    quality_issues = list(joined.get("claim_quality_issues", []))
    result.update(
        {
            "automated_quality_gate_passed": False,
            "independent_review_status": "not_reviewed",
            "evidence_selection_complete": False,
            "evidence_selection_digest": None,
            "evidence_selection_uncovered_fact_ids": [],
            "evidence_selection_selected_citation_count": 0,
            "accepted_claim_count": len(state.get("retained_claims", [])),
            "withheld_claim_count": len(
                joined.get("withheld_claims", [])
            ),
            "withheld_section_ids": list(
                joined.get("withheld_section_ids", [])
            ),
            "claim_evidence_issue_count": len(quality_issues),
            "claim_evidence_issues": quality_issues,
            "claim_quality_issue_count": len(quality_issues),
            "claim_quality_issues": quality_issues,
            "claim_evidence_projection_digest": joined.get(
                "claim_evidence_projection_digest"
            ),
            "memory_pre_review_candidate_eligible": False,
            "methodology_learning_rule_ids": [],
            "methodology_learning_proposal_digest": None,
            "methodology_learning_previous_preserved": False,
            "methodology_learning_planner_snapshot_included": False,
            "methodology_learning_apply_authority": False,
        }
    )
    state["evidence_selection"] = None
    state["pre_review_candidate_eligible"] = False
    return state
