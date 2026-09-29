from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, ClassVar

from adapters.base import Adapter

try:
    from .agent_contract import (
        BENCHMARK_SCHEMA_VERSION,
        CRITIC_SCHEMA_VERSION,
        MAX_CITATIONS_OUTPUT,
        RESEARCH_ROLE_SECTIONS,
        RESEARCH_SCHEMA_VERSION,
        STRATEGIC_SCHEMA_VERSION,
        SYNTHESIS_SCHEMA_VERSION,
        benchmark_counts,
        benchmark_improvement_count,
        extract_agent_json,
        validate_benchmark_payload,
        validate_critic_payload,
        validate_research_payload,
        validate_strategic_payload,
        validate_synthesis_payload,
    )
    from .dossier_contract import CANONICAL_SECTIONS, DOSSIER_SCHEMA_VERSION, SECTION_BY_ID
    from .input_contract import (
        BatchRequest,
        company_name,
        order_records_for_request,
        project_company_baseline,
        resolve_company_records,
        validate_batch_request,
    )
    from .memory_contract import MEMORY_TARGET_SECTION, MemoryCandidate
    from .methodology_contract import (
        PLANNER_ROLE,
        PLANNER_SCHEMA_VERSION,
        MethodologyPlan,
        MethodologyResources,
        load_methodology,
        validate_methodology_plan,
    )
except ImportError:  # pragma: no cover - local adapter-root execution path
    from agent_contract import (
        BENCHMARK_SCHEMA_VERSION,
        CRITIC_SCHEMA_VERSION,
        MAX_CITATIONS_OUTPUT,
        RESEARCH_ROLE_SECTIONS,
        RESEARCH_SCHEMA_VERSION,
        STRATEGIC_SCHEMA_VERSION,
        SYNTHESIS_SCHEMA_VERSION,
        benchmark_counts,
        benchmark_improvement_count,
        extract_agent_json,
        validate_benchmark_payload,
        validate_critic_payload,
        validate_research_payload,
        validate_strategic_payload,
        validate_synthesis_payload,
    )
    from dossier_contract import CANONICAL_SECTIONS, DOSSIER_SCHEMA_VERSION, SECTION_BY_ID
    from input_contract import (
        BatchRequest,
        company_name,
        order_records_for_request,
        project_company_baseline,
        resolve_company_records,
        validate_batch_request,
    )
    from memory_contract import MEMORY_TARGET_SECTION, MemoryCandidate
    from methodology_contract import (
        PLANNER_ROLE,
        PLANNER_SCHEMA_VERSION,
        MethodologyPlan,
        MethodologyResources,
        load_methodology,
        validate_methodology_plan,
    )


# Exact packaged ownership marker consumed by Assets at execute-time.
# This adapter orchestrates its Agent roles through inputs.invoke_agent(...).
AGENT_ORCHESTRATION_OWNER = "python_adapter"


RESEARCH_ROLES = (
    "portfolio_researcher",
    "market_researcher",
    "regulatory_risk_researcher",
)
STRATEGIC_ROLE = "strategic_analyst"
CRITIC_ROLE = "evidence_critic"
SYNTHESIS_ROLE = "intelligence_synthesizer"
BENCHMARK_ROLE = "memory_benchmark_reviewer"

MAX_MEMORY_CONTEXT_CHARS = 24000
MAX_CITATIONS_PER_COMPANY = 24


class NusaibahPharmaCompanyIntelligenceLabAdapter(Adapter):
    """Run a governed multi-company intelligence and memory-improvement pipeline.

    The adapter owns deterministic orchestration, schema validation, section
    rendering, quality gates, and company isolation. Runtime-owned helpers own
    provider execution, fixed/Dynamic Skill materialization, credentials,
    storage, retries, publication and remote authority.
    """

    key: ClassVar[str] = "nusaibah.pharma_company_intelligence_lab"
    version: ClassVar[str] = "0.1.3"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        """Execute one bounded company batch with two-phase memory mutation."""
        del context

        request = validate_batch_request(inputs)
        records = order_records_for_request(resolve_company_records(inputs), request)
        methodology = load_methodology(inputs)
        _require_runtime_helpers(inputs)

        prepared: list[dict[str, Any]] = []
        for record in records:
            prepared.append(
                _prepare_company(
                    inputs,
                    request=request,
                    record=record,
                    methodology=methodology,
                )
            )

        mutation_count = 0
        if request.memory_mode == "apply":
            for state in prepared:
                if not state["memory_mutation_eligible"]:
                    state["result"]["memory_update_status"] = "no_change_recommended"
                    continue
                mutation = _apply_company_memory(inputs, state)
                state["result"].update(mutation)
                mutation_count += 1

        company_results = [state["result"] for state in prepared]
        dossier = {
            "schema_version": DOSSIER_SCHEMA_VERSION,
            "status": "completed",
            "requested_company_count": len(request.company_ids),
            "completed_company_count": len(company_results),
            "failed_company_count": 0,
            "publication_requested": request.publish_dossier,
            "publication_state": (
                "runtime_output_ready_for_output_policy"
                if request.publish_dossier
                else "runtime_output_only"
            ),
            "company_results": company_results,
        }

        return {
            "response_version": "1",
            "status": "success",
            "outputs": {"intelligence_dossier": dossier},
            "logs": [
                {
                    "level": "info",
                    "message": (
                        "Completed governed pharma intelligence batch for "
                        f"{len(company_results)} company contexts."
                    ),
                }
            ],
            "metrics": {
                "requested_company_count": len(request.company_ids),
                "completed_company_count": len(company_results),
                "logical_agent_invocations": (len(company_results) * 9) + mutation_count,
                "search_enabled_agent_invocations": len(company_results) * 3,
                "methodology_planner_call_count": sum(
                    item["methodology_planner_call_count"] for item in company_results
                ),
                "planner_required_question_count": sum(
                    item["planner_required_question_count"] for item in company_results
                ),
                "planner_focus_item_count": sum(
                    item["planner_focus_item_count"] for item in company_results
                ),
                "planner_unmet_requirement_count": sum(
                    item["planner_unmet_requirement_count"] for item in company_results
                ),
                "research_role_count": sum(
                    item["research_role_count"] for item in company_results
                ),
                "research_claim_count": sum(
                    item["research_claim_count"] for item in company_results
                ),
                "citation_count": sum(item["citation_count"] for item in company_results),
                "quality_gate_passed_company_count": sum(
                    1 for item in company_results if item["quality_gate_passed"]
                ),
                "benchmark_improvement_count": sum(
                    item["benchmark_improvement_count"] for item in company_results
                ),
                "memory_mutations_made": mutation_count,
            },
        }


def _require_runtime_helpers(inputs: Any) -> None:
    for name in ("invoke_agent", "skill", "dynamic_skill"):
        if not callable(getattr(inputs, name, None)):
            raise RuntimeError(f"Trusted runtime helper is unavailable: {name}.")


def _prepare_company(
    inputs: Any,
    *,
    request: BatchRequest,
    record: dict[str, Any],
    methodology: MethodologyResources,
) -> dict[str, Any]:
    company_id = int(record["company_id"])
    name = company_name(record)
    baseline = project_company_baseline(record)

    memory_handle = inputs.dynamic_skill(
        "company_memory",
        variables={"company_id": str(company_id)},
    )
    provenance = memory_handle.provenance()
    if provenance.mutable is not False:
        raise RuntimeError("company_memory must resolve read-only.")

    memory_text = memory_handle.read()
    if not isinstance(memory_text, str) or not memory_text.strip():
        raise RuntimeError("Existing company memory is empty.")
    if len(memory_text) > MAX_MEMORY_CONTEXT_CHARS:
        raise RuntimeError("Existing company memory exceeds the adapter context bound.")
    if not memory_handle.has_section(MEMORY_TARGET_SECTION):
        raise RuntimeError("Existing company memory is missing the approved update section.")

    before_digest = memory_handle.content_digest()
    before_target_text = memory_handle.section_text(MEMORY_TARGET_SECTION).strip()

    before_benchmark = _run_benchmark(
        inputs,
        company_id=company_id,
        company_name_value=name,
        memory_text=memory_text,
        questions=methodology.benchmark_questions,
        stage="before",
    )

    methodology_plan = _run_methodology_planner(
        inputs,
        company_id=company_id,
        company_name_value=name,
        baseline=baseline,
        request=request,
        methodology=methodology,
        before_benchmark=before_benchmark,
    )

    research = _run_research_fanout(
        inputs,
        company_id=company_id,
        company_name_value=name,
        baseline=baseline,
        memory_text=memory_text,
        request=request,
        methodology_plan=methodology_plan,
    )
    joined = _join_research(research)

    strategic = _run_strategic(
        inputs,
        company_id=company_id,
        company_name_value=name,
        baseline=baseline,
        memory_text=memory_text,
        joined_research=joined,
        methodology_plan=methodology_plan,
    )
    critic = _run_critic(
        inputs,
        company_id=company_id,
        company_name_value=name,
        joined_research=joined,
        strategic=strategic,
        methodology=methodology,
        methodology_plan=methodology_plan,
    )
    _require_pre_synthesis_quality(research, critic)

    synthesis, candidate = _run_synthesis(
        inputs,
        company_id=company_id,
        company_name_value=name,
        baseline=baseline,
        memory_text=memory_text,
        joined_research=joined,
        strategic=strategic,
        critic=critic,
        methodology=methodology,
        methodology_plan=methodology_plan,
    )

    claim_ids = {claim["claim_id"] for claim in joined["claims"]}
    if any(fact_id not in claim_ids for fact_id in candidate.fact_ids):
        raise RuntimeError("Memory candidate referenced a fact_id not present in grounded research.")

    after_benchmark = _run_benchmark(
        inputs,
        company_id=company_id,
        company_name_value=name,
        memory_text=candidate.markdown,
        questions=methodology.benchmark_questions,
        stage="proposed",
    )

    before_counts = benchmark_counts(before_benchmark)
    after_counts = benchmark_counts(after_benchmark)
    improvement_count = benchmark_improvement_count(before_benchmark, after_benchmark)
    before_score = before_counts["covered"] * 2 + before_counts["partially_covered"]
    after_score = after_counts["covered"] * 2 + after_counts["partially_covered"]
    benchmark_non_regression = after_score >= before_score

    citations = joined["citations"]
    candidate_changed = candidate.markdown.strip() != before_target_text
    mutation_eligible = (
        bool(candidate.fact_ids)
        and candidate_changed
        and benchmark_non_regression
    )

    result = {
        "company_id": company_id,
        "company_name": name,
        "status": "completed",
        "sections": synthesis["sections"],
        "citation_count": len(citations),
        "citation_sources": _citation_output(citations),
        "verified_reference_count": 0,
        "unsupported_claim_count": len(critic["unsupported_claim_ids"]),
        "contradiction_count": len(critic["contradiction_items"]),
        "stale_claim_count": len(critic["stale_claim_ids"]),
        "novel_fact_count": len(candidate.fact_ids),
        "duplicate_memory_fact_count": 0,
        "methodology_planner_call_count": 1,
        "planner_required_question_count": (
            sum(len(focus.questions) for focus in methodology_plan.research_focus)
            + len(methodology_plan.cross_cutting_questions)
        ),
        "planner_focus_item_count": len(methodology_plan.research_focus),
        "planner_unmet_requirement_count": len(critic["unmet_plan_requirements"]),
        "research_role_count": len(RESEARCH_ROLES),
        "research_claim_count": len(joined["claims"]),
        "specialist_agent_call_count": 3,
        "search_enabled_agent_call_count": 3,
        "required_section_coverage_count": len(synthesis["sections"]),
        "quality_gate_passed": True,
        "benchmark_question_count": len(methodology.benchmark_questions),
        "benchmark_before_covered_count": before_counts["covered"],
        "benchmark_before_partially_covered_count": before_counts["partially_covered"],
        "benchmark_after_covered_count": after_counts["covered"],
        "benchmark_after_partially_covered_count": after_counts["partially_covered"],
        "benchmark_improvement_count": improvement_count,
        "benchmark_non_regression": benchmark_non_regression,
        "benchmark_result_basis": "projected_memory_candidate",
        "memory_mutation_eligible": mutation_eligible,
        "memory_update_status": (
            "preview_ready" if mutation_eligible else "no_change_recommended"
        ),
        "memory_change_id": None,
        "memory_before_digest": before_digest,
        "memory_after_digest": None,
        "memory_readback_verified": False,
        "residual_uncertainty_count": len(synthesis["residual_uncertainties"]),
    }

    return {
        "company_id": company_id,
        "company_name": name,
        "result": result,
        "before_digest": before_digest,
        "before_benchmark": before_benchmark,
        "methodology_plan": methodology_plan,
        "projected_after_benchmark": after_benchmark,
        "benchmark_questions": methodology.benchmark_questions,
        "memory_candidate": candidate,
        "citations": citations,
        "memory_mutation_eligible": mutation_eligible,
    }



def _run_methodology_planner(
    inputs: Any,
    *,
    company_id: int,
    company_name_value: str,
    baseline: dict[str, Any],