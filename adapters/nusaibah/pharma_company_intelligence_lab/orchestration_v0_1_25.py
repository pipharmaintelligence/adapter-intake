"""Review-gated top-level orchestration for pharma adapter version 0.1.25.

The execution path prepares a bounded dossier, claim-level evidence, an exact
memory evidence selection, and an optional review packet. It rejects apply mode
before any runtime helper or provider call because an admitted independent
review receipt is not yet part of the 0.1.25 contract.
"""
from __future__ import annotations

from typing import Any

try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .candidate_validation_v0_1_21 import CandidateContractError
    from .company_preparation_v0_1_25 import prepare_company_v0_1_25
    from .company_result_v0_1_21 import (
        augment_incomplete_company_state_v0_1_21,
    )
    from .review_packet_v0_1_21 import build_review_packet_v0_1_21
except ImportError:  # pragma: no cover - flat intake execution
    import legacy_preparation_helpers_v0_1_23 as legacy
    from candidate_validation_v0_1_21 import CandidateContractError
    from company_preparation_v0_1_25 import prepare_company_v0_1_25
    from company_result_v0_1_21 import (
        augment_incomplete_company_state_v0_1_21,
    )
    from review_packet_v0_1_21 import build_review_packet_v0_1_21


class IndependentReviewRequiredError(RuntimeError):
    """Safe pre-execution rejection for unadmitted 0.1.25 apply requests."""

    code = "pharma_independent_review_required"
    proof_failure_detail = {
        "schema_version": "proof_failure_detail.v1",
        "proof_kind": "review_authority",
        "role": "orchestration",
        "stage": "pre_execution",
        "rule": "independent_review_required",
        "field": "variables.memory_mode",
    }

    def __init__(self) -> None:
        super().__init__(
            "Pharma 0.1.25 apply requires an admitted independent review receipt."
        )


def _invoke_v0_1_25(
    inputs: Any,
    *,
    asset_identity: str,
) -> dict[str, Any]:
    """Execute one review-pending batch without persistence side effects."""

    request = legacy.validate_batch_request(inputs)
    if request.memory_mode != "preview":
        raise IndependentReviewRequiredError()

    review_passes = legacy.portfolio_review_passes(inputs)
    retain_review_packet = legacy.review_packet_requested(inputs)
    records = legacy.order_records_for_request(
        legacy.resolve_company_context(
            inputs,
            company_ids=request.company_ids,
        ),
        request,
    )
    methodology = legacy.load_methodology(inputs)
    legacy._require_runtime_helpers(inputs)
    bounded_inputs = legacy._BoundedAgentInputs(
        inputs,
        request,
        review_passes=review_passes,
    )

    prepared: list[dict[str, Any]] = []
    for company_iteration, record in enumerate(records, start=1):
        if company_iteration > legacy.MAX_COMPANY_ITERATIONS:
            legacy._iteration_limit_exceeded()
        progress: dict[str, Any] = {}
        try:
            state = prepare_company_v0_1_25(
                bounded_inputs,
                request=request,
                record=record,
                methodology=methodology,
                review_passes=review_passes,
                progress=progress,
            )
        except legacy.UnresolvedAgentResponse as error:
            state = legacy._incomplete_company_state(
                bounded_inputs,
                record=record,
                diagnostic=error.diagnostic,
                progress=progress,
            )
            state = augment_incomplete_company_state_v0_1_21(state)
        except CandidateContractError as error:
            state = legacy._incomplete_company_state(
                bounded_inputs,
                record=record,
                diagnostic=error.proof_failure_detail,
                progress=progress,
            )
            state = augment_incomplete_company_state_v0_1_21(state)
        except legacy.AgentContractValidationError as error:
            if not legacy.recoverable_quality(error):
                raise
            state = legacy._incomplete_company_state(
                bounded_inputs,
                record=record,
                diagnostic=error.proof_failure_detail,
                progress=progress,
            )
            state = augment_incomplete_company_state_v0_1_21(state)
        prepared.append(state)

    review_packet = None
    if retain_review_packet:
        review_packet = build_review_packet_v0_1_21(
            prepared,
            asset_identity=asset_identity,
            methodology_digest=methodology.package_digest,
            memory_mode=request.memory_mode,
        )
        legacy.require_output_bound(
            {
                "company_results": [
                    state["result"] for state in prepared
                ],
                "review_packet": review_packet,
            }
        )

    for state in prepared:
        company_id = state["company_id"]
        state["result"]["agent_response_recovery_trace"] = (
            bounded_inputs.company_recovery_trace(company_id)
        )
        state["result"]["agent_response_resolver_call_count"] = (
            bounded_inputs.company_agent_counts(company_id).get(
                legacy.RESEARCH_RESOLVER_ROLE,
                0,
            )
        )

    company_results = [state["result"] for state in prepared]
    incomplete_count = sum(
        1 for item in company_results if item["research_incomplete"]
    )
    dossier = {
        "schema_version": legacy.DOSSIER_SCHEMA_VERSION,
        "status": "completed",
        "requested_company_count": len(request.company_ids),
        "completed_company_count": len(company_results),
        "failed_company_count": 0,
        "research_incomplete_company_count": incomplete_count,
        "agent_schema_incomplete_company_count": sum(
            item["agent_schema_incomplete"] for item in company_results
        ),
        "business_result_state": (
            "incomplete" if incomplete_count else "review_pending"
        ),
        "independent_review_status": "not_reviewed",
        "publication_requested": request.publish_dossier,
        "publication_state": (
            "runtime_output_ready_for_output_policy"
            if request.publish_dossier
            else "runtime_output_only"
        ),
        "company_results": company_results,
    }
    if review_packet is not None:
        dossier["review_packet"] = review_packet

    return {
        "response_version": "1",
        "status": "success",
        "outputs": {"intelligence_dossier": dossier},
        "logs": [
            {
                "level": "info",
                "message": (
                    "Prepared review-pending pharma intelligence for "
                    f"{len(company_results)} company contexts."
                ),
            }
        ],
        "metrics": {
            "requested_company_count": len(request.company_ids),
            "completed_company_count": len(company_results),
            "logical_agent_invocations": bounded_inputs.agent_call_count,
            "search_enabled_agent_invocations": sum(
                item["search_enabled_agent_call_count"]
                for item in company_results
            ),
            "portfolio_review_pass_count": sum(
                item["portfolio_review_pass_count"]
                for item in company_results
            ),
            "research_response_repair_count": sum(
                item["research_response_repair_count"]
                for item in company_results
            ),
            "research_resolver_agent_call_count": sum(
                item["research_resolver_agent_call_count"]
                for item in company_results
            ),
            "agent_response_resolver_call_count": sum(
                item["agent_response_resolver_call_count"]
                for item in company_results
            ),
            "agent_schema_incomplete_company_count": sum(
                item["agent_schema_incomplete"]
                for item in company_results
            ),
            "incomplete_research_company_count": incomplete_count,
            "methodology_planner_call_count": sum(
                item["methodology_planner_call_count"]
                for item in company_results
            ),
            "planner_required_question_count": sum(
                item["planner_required_question_count"]
                for item in company_results
            ),
            "planner_focus_item_count": sum(
                item["planner_focus_item_count"]
                for item in company_results
            ),
            "planner_unmet_requirement_count": sum(
                item["planner_unmet_requirement_count"]
                for item in company_results
            ),
            "research_role_count": sum(
                item["research_role_count"] for item in company_results
            ),
            "research_claim_count": sum(
                item["research_claim_count"] for item in company_results
            ),
            "citation_count": sum(
                item["citation_count"] for item in company_results
            ),
            "quality_gate_passed_company_count": sum(
                1
                for item in company_results
                if item["automated_quality_gate_passed"]
            ),
            "evidence_selection_complete_company_count": sum(
                1
                for item in company_results
                if item["evidence_selection_complete"]
            ),
            "independent_review_approved_company_count": 0,
            "benchmark_improvement_count": sum(
                item["benchmark_improvement_count"] or 0
                for item in company_results
            ),
            "memory_mutations_made": 0,
            "methodology_learning_mutations_made": 0,
        },
    }


def invoke_v0_1_25(inputs: Any, *, asset_identity: str) -> dict[str, Any]:
    """Compose truthful role recovery with the unchanged review-only authority."""
    try:
        from .invocation_recovery_v0_1_25 import InvocationRecoveryInputs
    except ImportError:
        from invocation_recovery_v0_1_25 import InvocationRecoveryInputs
    legacy.validate_batch_request(inputs)
    forwarded = InvocationRecoveryInputs(inputs)
    response = _invoke_v0_1_25(forwarded, asset_identity=asset_identity)
    dossier = response["outputs"]["intelligence_dossier"]
    dossier["research_response_observations"] = sorted(forwarded.observations,
        key=lambda row: (row["company_id"], row["role"], row["pass_number"] or 0))
    dossier["agent_invocation_response_issues"] = sorted(forwarded.invocation_issues,
        key=lambda row: (row["company_id"], row["role"], row["pass_number"] or 0))
    return response
