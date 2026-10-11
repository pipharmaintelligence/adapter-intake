"""Prepare one bounded review-pending pharma company result for version 0.1.21.

The module composes existing deterministic planning, analysis, critique,
synthesis and benchmark helpers with the version-owned claim evidence path. It
builds preview evidence only. Independent review remains required and no
Dynamic Skill mutation is authorized here.
"""
from __future__ import annotations

from typing import Any

try:
    from . import legacy_preparation_helpers_v0_1_21 as legacy
    from .candidate_validation_v0_1_21 import require_candidate_fact_ids
    from .company_result_v0_1_21 import (
        CompanyPreparationEvidence,
        build_prepared_company_state_v0_1_21,
    )
    from .memory_citation_selection_v0_1_21 import select_memory_citations
    from .methodology_learning_v0_1_21 import (
        build_methodology_learning_proposal,
    )
    from .preparation_context_v0_1_21 import PreparationContextInputs
    from .research_execution_v0_1_21 import (
        join_research_v0_1_21,
        run_research_fanout_v0_1_21,
    )
except ImportError:  # pragma: no cover - flat intake execution
    import legacy_preparation_helpers_v0_1_21 as legacy
    from candidate_validation_v0_1_21 import require_candidate_fact_ids
    from company_result_v0_1_21 import (
        CompanyPreparationEvidence,
        build_prepared_company_state_v0_1_21,
    )
    from memory_citation_selection_v0_1_21 import select_memory_citations
    from methodology_learning_v0_1_21 import (
        build_methodology_learning_proposal,
    )
    from preparation_context_v0_1_21 import PreparationContextInputs
    from research_execution_v0_1_21 import (
        join_research_v0_1_21,
        run_research_fanout_v0_1_21,
    )


def prepare_company_v0_1_21(
    inputs: Any,
    *,
    request: Any,
    record: dict[str, Any],
    methodology: Any,
    review_passes: int,
    preflight: tuple[Any, Any] | None = None,
    progress: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepare one company with claim-level evidence and no mutation authority."""

    if request.memory_mode != "preview":
        raise RuntimeError(
            "Pharma 0.1.21 apply requires an admitted independent review receipt."
        )

    progress = progress if progress is not None else {}
    company_id = int(record["company_id"])
    company_name_value = legacy.company_name(record)
    baseline = legacy.project_company_baseline(record)

    memory_state = (
        preflight[0]
        if preflight is not None
        else legacy._read_company_memory(
            inputs,
            company_id=company_id,
            allow_absent=True,
        )
    )
    memory_text = memory_state["text"]
    before_digest = memory_state["digest"]
    before_target_text = memory_state["target_text"]
    memory_initialized = memory_state["handle"] is not None

    methodology_handle, methodology_learning_text = (
        preflight[1]
        if preflight is not None
        else legacy._load_methodology_learning(
            inputs,
            company_id=company_id,
        )
    )
    inputs = PreparationContextInputs(
        inputs, learned_methodology_text=methodology_learning_text,
    )

    before_benchmark = _before_benchmark(
        inputs,
        company_id=company_id,
        company_name_value=company_name_value,
        memory_text=memory_text,
        memory_initialized=memory_initialized,
        benchmark_questions=methodology.benchmark_questions,
    )

    methodology_plan, _planner_call_count, planner_chunks = (
        legacy._run_methodology_planner(
            inputs,
            company_id=company_id,
            company_name_value=company_name_value,
            baseline=baseline,
            request=request,
            methodology=methodology,
            before_benchmark=before_benchmark,
            learned_methodology_text=methodology_learning_text,
        )
    )
    progress.update(
        methodology_plan=methodology_plan,
        planner_chunks=planner_chunks,
        planner_requirements=list(methodology_plan.requirement_catalog()),
    )

    research = run_research_fanout_v0_1_21(
        inputs,
        company_id=company_id,
        company_name_value=company_name_value,
        baseline=baseline,
        memory_text=memory_text,
        request=request,
        methodology_plan=methodology_plan,
        methodology=methodology,
        learned_methodology_text=methodology_learning_text,
        review_passes=review_passes,
    )
    joined = join_research_v0_1_21(research)
    progress.update(research=research, joined_research=joined)

    research_incomplete = any(
        payload.get("_unresolved_response")
        or payload.get("_claim_evidence_incomplete")
        for payload in research.values()
    )
    if not joined["claims"]:
        raise legacy.UnresolvedAgentResponse(
            legacy.evidence_diagnostic(
                role="orchestration",
                stage="pre_synthesis_quality",
                rule="no_usable_research_evidence",
                field="claims",
            )
        )

    strategic = legacy._run_strategic(
        inputs,
        company_id=company_id,
        company_name_value=company_name_value,
        baseline=baseline,
        memory_text=memory_text,
        joined_research=joined,
        methodology_plan=methodology_plan,
    )
    progress["strategic"] = strategic

    critic = legacy._run_critic(
        inputs,
        company_id=company_id,
        company_name_value=company_name_value,
        joined_research=joined,
        strategic=strategic,
        methodology=methodology,
        methodology_plan=methodology_plan,
    )
    progress["critic"] = critic
    legacy._require_pre_synthesis_quality(
        research,
        critic,
        methodology_plan=methodology_plan,
    )

    synthesis, candidate = legacy._run_synthesis(
        inputs,
        company_id=company_id,
        company_name_value=company_name_value,
        baseline=baseline,
        memory_text=memory_text,
        joined_research=joined,
        strategic=strategic,
        critic=critic,
        methodology=methodology,
        methodology_plan=methodology_plan,
    )
    progress["synthesis"] = synthesis

    accepted_claim_ids = tuple(
        joined["claim_evidence_index"].accepted_claim_ids
    )
    require_candidate_fact_ids(
        fact_ids=candidate.fact_ids,
        accepted_claim_ids=accepted_claim_ids,
    )

    selection = select_memory_citations(
        fact_ids=candidate.fact_ids,
        evidence_index=joined["claim_evidence_index"],
        maximum_citations=legacy.MAX_CITATIONS_PER_COMPANY,
    )

    projected_after_benchmark = legacy._run_benchmark(
        inputs,
        company_id=company_id,
        company_name_value=company_name_value,
        memory_text=candidate.markdown,
        questions=methodology.benchmark_questions,
        stage="proposed",
    )
    benchmark_non_regression, improvement_count = _benchmark_change(
        before_benchmark,
        projected_after_benchmark,
    )

    candidate_changed = candidate.markdown.strip() != (
        before_target_text or ""
    ).strip()
    pre_review_candidate_eligible = (
        bool(candidate.fact_ids)
        and candidate_changed
        and benchmark_non_regression
        and selection.complete
        and not research_incomplete
    )

    planner_snapshot = None
    if benchmark_non_regression and not research_incomplete:
        planner_snapshot = legacy._build_methodology_learning_candidate(
            company_id=company_id,
            planner_chunks=planner_chunks,
            critic=critic,
            methodology_plan=methodology_plan,
            benchmark_non_regression=True,
        )

    methodology_proposal = (
        build_methodology_learning_proposal(
            methodology_learning_text,
            planner_snapshot=planner_snapshot,
        )
        if benchmark_non_regression
        else None
    )
    methodology_learning_candidate = (
        methodology_proposal.candidate
        if methodology_proposal is not None and methodology_proposal.changed
        else None
    )

    agent_counts = inputs.company_agent_counts(company_id)
    evidence = CompanyPreparationEvidence(
        company_id=company_id,
        company_name=company_name_value,
        review_passes=review_passes,
        before_digest=before_digest,
        before_target_text=before_target_text,
        memory_initialized=memory_initialized,
        methodology_handle=methodology_handle,
        methodology_learning_text=methodology_learning_text,
        methodology_learning_candidate=methodology_learning_candidate,
        methodology_learning_rule_ids=(
            () if methodology_proposal is None else methodology_proposal.rule_ids
        ),
        methodology_learning_proposal_digest=(
            None
            if methodology_proposal is None
            else methodology_proposal.proposal_digest
        ),
        methodology_learning_previous_preserved=(
            False
            if methodology_proposal is None
            else methodology_proposal.previous_learning_preserved
        ),
        methodology_learning_planner_snapshot_included=(
            False
            if methodology_proposal is None
            else methodology_proposal.planner_snapshot_included
        ),
        methodology_learning_withheld_reason=(
            None if methodology_proposal is None else methodology_proposal.withheld_reason
        ),
        methodology_plan=methodology_plan,
        planner_chunks=planner_chunks,
        before_benchmark=before_benchmark,
        projected_after_benchmark=projected_after_benchmark,
        benchmark_questions=tuple(methodology.benchmark_questions),
        research=research,
        joined_research=joined,
        strategic=strategic,
        critic=critic,
        synthesis=synthesis,
        memory_candidate=candidate,
        evidence_selection=selection,
        benchmark_non_regression=benchmark_non_regression,
        benchmark_improvement_count=improvement_count,
        candidate_changed=candidate_changed,
        pre_review_candidate_eligible=pre_review_candidate_eligible,
        research_incomplete=research_incomplete,
        agent_counts=agent_counts,
        recovery_trace=tuple(inputs.company_recovery_trace(company_id)),
    )
    return build_prepared_company_state_v0_1_21(evidence)


def _before_benchmark(
    inputs: Any,
    *,
    company_id: int,
    company_name_value: str,
    memory_text: str,
    memory_initialized: bool,
    benchmark_questions: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Evaluate existing memory or project deterministic absence."""

    if memory_initialized:
        return legacy._run_benchmark(
            inputs,
            company_id=company_id,
            company_name_value=company_name_value,
            memory_text=memory_text,
            questions=benchmark_questions,
            stage="before",
        )

    return {
        "schema_version": legacy.BENCHMARK_SCHEMA_VERSION,
        "company_id": company_id,
        "role": legacy.BENCHMARK_ROLE,
        "status": "completed",
        "results": [
            {
                "question_id": question["question_id"],
                "coverage": "not_covered",
                "evidence_basis": "No company memory package is initialized.",
            }
            for question in benchmark_questions
        ],
    }


def _benchmark_change(
    before: dict[str, Any],
    after: dict[str, Any],
) -> tuple[bool, int]:
    """Return non-regression and improvement under the retained scoring rule."""

    before_counts = legacy.benchmark_counts(before)
    after_counts = legacy.benchmark_counts(after)
    before_score = (
        before_counts["covered"] * 2
        + before_counts["partially_covered"]
    )
    after_score = (
        after_counts["covered"] * 2
        + after_counts["partially_covered"]
    )
    return (
        after_score >= before_score,
        legacy.benchmark_improvement_count(before, after),
    )
