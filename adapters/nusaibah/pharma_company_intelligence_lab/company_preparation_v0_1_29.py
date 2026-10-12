"""Prepare one bounded enrichment result for version 0.1.29.

The module composes existing deterministic planning, analysis, critique,
synthesis and benchmark helpers with the version-owned claim evidence path. It
builds validated evidence without mutation authority. The version-owned
publication phase uses that evidence automatically through Core capabilities.
"""
from __future__ import annotations

from typing import Any
try:
    from .benchmark_observation_v0_1_29 import observe_benchmark,procedural_snapshot
except ImportError:
    from benchmark_observation_v0_1_29 import observe_benchmark,procedural_snapshot

try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
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
    from .research_execution_v0_1_26 import (
        join_research_v0_1_26,
        run_research_fanout_v0_1_26,
    )
except ImportError:  # pragma: no cover - flat intake execution
    import legacy_preparation_helpers_v0_1_23 as legacy
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
    from research_execution_v0_1_26 import (
        join_research_v0_1_26,
        run_research_fanout_v0_1_26,
    )


def prepare_company_v0_1_29(
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
            "Enrichment preparation is an internal readonly phase."
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
    try:
        from .targeted_inputs_v0_1_27 import TargetedSourceInputs as SourceEvidenceInputs
    except ImportError:
        from targeted_inputs_v0_1_27 import TargetedSourceInputs as SourceEvidenceInputs
    source_inputs = SourceEvidenceInputs(inputs, record=record, memory_text=memory_text,
                                        memory_digest=before_digest)
    inputs = source_inputs
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

    research = run_research_fanout_v0_1_26(
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
    joined = join_research_v0_1_26(research)
    progress.update(research=research, joined_research=joined)
    progress['source_retrieval'] = source_inputs.observations
    progress['retrieved_source_snapshot'] = {
        'entity_id': source_inputs.entity_id, 'snapshot_id': source_inputs.snapshot_id,
        'source_units': source_inputs.units, 'source_digest': source_inputs.source_digest,
        'web_reads': source_inputs.web_reads,
    }

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

    try:
        from .section_critic_v0_1_28 import run_section_critics, select_validated_sections
    except ImportError:
        from section_critic_v0_1_28 import run_section_critics, select_validated_sections
    critic = run_section_critics(
        inputs,
        company_id=company_id,
        company_name_value=company_name_value,
        joined_research=joined,
        strategic=strategic,
        methodology=methodology,
        methodology_plan=methodology_plan,
        planner_chunks=planner_chunks,
    )
    progress["critic"] = critic
    joined = select_validated_sections(joined, critic)
    progress['joined_research'] = joined
    research_incomplete = research_incomplete or any(o['status'] != 'validated' for o in critic['section_outcomes'])

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

    # Publish only source-verified fact deltas; preserve the existing section.
    try:
        from .section_enrichment_v0_1_28 import build_enrichment_candidate
    except ImportError:
        from section_enrichment_v0_1_28 import build_enrichment_candidate
    candidate, enrichment = build_enrichment_candidate(candidate, before_target_text or "", joined["claims"])

    selection = select_memory_citations(
        fact_ids=candidate.fact_ids,
        evidence_index=joined["claim_evidence_index"],
        maximum_citations=legacy.MAX_CITATIONS_PER_COMPANY,
    )

    try:
        from .benchmark_projection_v0_1_28 import projected_memory_document
    except ImportError:
        from benchmark_projection_v0_1_28 import projected_memory_document
    benchmark_memory=projected_memory_document(memory_state['handle'],candidate,selection.public_citations())
    projected_after_benchmark = observe_benchmark(
        inputs,
        company_id=company_id,
        company_name_value=company_name_value,
        memory_text=benchmark_memory,
        questions=methodology.benchmark_questions,
        stage="proposed",
    )
    benchmarks_scored=before_benchmark['status']=='completed' and projected_after_benchmark['status']=='completed'
    benchmark_non_regression, improvement_count = (_benchmark_change(before_benchmark,projected_after_benchmark)
        if benchmarks_scored else (None,None))

    candidate_changed = candidate.markdown.strip() != (
        before_target_text or ""
    ).strip()
    pre_review_candidate_eligible = (
        bool(candidate.fact_ids)
        and candidate_changed
        and benchmark_non_regression
        and selection.complete
    )

    planner_snapshot = None
    # A partial section critique may publish verified memory deltas, but must
    # never masquerade as an overall passed planner-learning snapshot.
    if benchmark_non_regression and critic['recommendation']=='pass':
        planner_snapshot = legacy._build_methodology_learning_candidate(
            company_id=company_id,
            planner_chunks=planner_chunks,
            critic=critic,
            methodology_plan=methodology_plan,
            benchmark_non_regression=True,
        )

    if planner_snapshot is None and critic['recommendation']=='pass':
        planner_snapshot=procedural_snapshot(company_id,planner_chunks,before_benchmark,projected_after_benchmark)
    methodology_proposal = (
        build_methodology_learning_proposal(
            methodology_learning_text,
            planner_snapshot=planner_snapshot,
        )
        if critic['recommendation']=='pass'
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
    state = build_prepared_company_state_v0_1_21(evidence)
    state['result']['retrieved_source_snapshot'] = progress['retrieved_source_snapshot']
    state['result']['source_retrieval'] = source_inputs.observations
    state['result']['section_enrichment'] = enrichment
    state['result']['input_packing'] = source_inputs.packing_trace
    state['result']['source_toolkit_call_count'] = source_inputs.toolkit_calls
    state['review_baselines'] = {}
    for role, handle in (('company_memory', memory_state['handle']),
                         ('company_methodology', methodology_handle)):
        provenance = None if handle is None else handle.provenance()
        state['review_baselines'][role] = {
            'package_digest': None if provenance is None else getattr(provenance, 'package_digest', None),
            'snapshot_id': None if provenance is None else getattr(provenance, 'snapshot_id', None),
        }
    state['candidate_changed'] = candidate_changed
    state['benchmark_non_regression'] = benchmark_non_regression
    observation={'status':'scored' if benchmarks_scored else 'unscored','is_publication_authority':False,
        'non_regression':benchmark_non_regression,'baseline':before_benchmark['status'],
        'proposed':projected_after_benchmark['status'],
        'diagnostics':[b['diagnostic'] for b in (before_benchmark,projected_after_benchmark) if 'diagnostic' in b]}
    state['result']['benchmark_observation']=observation
    state['result']['benchmark_non_regression']=benchmark_non_regression
    state['result']['benchmark_improvement_count']=improvement_count
    for prefix,benchmark in (('before',before_benchmark),('after',projected_after_benchmark)):
        if benchmark['status']=='unscored':
            for suffix in ('covered_count','partially_covered_count'):
                state['result']['benchmark_'+prefix+'_'+suffix]=None
    state['result']['benchmark_result_basis']='full_memory_document_advisory'

    return state


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
        return observe_benchmark(
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

    ranks = {"not_covered": 0, "partially_covered": 1, "covered": 2}
    old = {q["question_id"]: ranks[q["coverage"]] for q in before["results"]}
    new = {q["question_id"]: ranks[q["coverage"]] for q in after["results"]}
    unchanged_scope = set(old) == set(new)
    non_regression = unchanged_scope and all(new[q] >= rank for q, rank in old.items())
    return non_regression, sum(new.get(q, -1) > rank for q, rank in old.items())
