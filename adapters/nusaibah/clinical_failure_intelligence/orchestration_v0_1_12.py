"""Bounded research, scoped review and one refinement without discarding valid work."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from typing import Any
if __package__:
    from .contracts_v0_1_12 import ASSET_KEY, SCHEMA, VERSION, RESEARCH_ROLES, ContractError, canonical_bytes, digest, identifiers, parse_request, require
    from .case_context_v0_1_12 import evidence_breadth
    from .policies_v0_1_12 import Budget, ExecutionPolicy, DeferredWork
    from .runtime_access_v0_1_12 import AgentRunner, StageResult
    from .research_sources_v0_1_12 import acquire_sources, inspect_stage_sources
    from .evidence_v0_1_12 import EvidenceLedger
    from .cohort_v0_1_12 import compute_statistics
    from .quality_v0_1_12 import OUTCOMES, enforce_consistency, normalize_items, review_items, validate_dependencies, withhold
    from .memory_v0_1_12 import read_methodology, read_group_memory
    from .product_memory_v0_1_12 import read_product_memory, memory_projection, editor_contract, validate_edit_candidates, review_edit_plan
    from .rendering_v0_1_12 import build_reason_graph, render_report, validate_result
    from .review_packets_v0_1_12 import critic_batches, scoped_review, isolate_dependencies
    from .decision_outcome_v0_1_12 import finalize_output, preflight_result, source_request_plan
    from .business_recovery_v0_1_12 import correct_business
    from .memory_packets_v0_1_12 import preview_memory
    from .analysis_packets_v0_1_12 import evidence_batches, closed_packet, namespace_candidates, item_evidence, agent_evidence_view
else:
    from contracts_v0_1_12 import ASSET_KEY, SCHEMA, VERSION, RESEARCH_ROLES, ContractError, canonical_bytes, digest, identifiers, parse_request, require
    from case_context_v0_1_12 import evidence_breadth
    from policies_v0_1_12 import Budget, ExecutionPolicy, DeferredWork
    from runtime_access_v0_1_12 import AgentRunner, StageResult
    from research_sources_v0_1_12 import acquire_sources, inspect_stage_sources
    from evidence_v0_1_12 import EvidenceLedger
    from cohort_v0_1_12 import compute_statistics
    from quality_v0_1_12 import OUTCOMES, enforce_consistency, normalize_items, review_items, validate_dependencies, withhold
    from memory_v0_1_12 import read_methodology, read_group_memory
    from product_memory_v0_1_12 import read_product_memory, memory_projection, editor_contract, validate_edit_candidates, review_edit_plan
    from rendering_v0_1_12 import build_reason_graph, render_report, validate_result
    from review_packets_v0_1_12 import critic_batches, scoped_review, isolate_dependencies
    from decision_outcome_v0_1_12 import finalize_output, preflight_result, source_request_plan
    from business_recovery_v0_1_12 import correct_business
    from memory_packets_v0_1_12 import preview_memory
    from analysis_packets_v0_1_12 import evidence_batches, closed_packet, namespace_candidates, item_evidence, agent_evidence_view

FACETS = {"trial_researcher": "clinical_outcome", "literature_researcher": "mechanism_evidence",
          "event_researcher": "development_timeline"}
SOURCE_FACETS = {"trial_researcher": {"trial_registry", "regulator"},
                 "literature_researcher": {"original_research", "review", "publication"},
                 "event_researcher": {"news", "sponsor", "regulator"}}


def partition_evidence(rows: list[dict], maximum_bytes: int = 24000) -> list[list[dict]]:
    """Split between complete source windows, never truncate a scientific passage."""
    chunks: list[list[dict]] = []
    current: list[dict] = []
    for row in rows:
        require(len(canonical_bytes([row])) <= maximum_bytes, "clinical_source_window_requires_partitioning")
        if current and len(canonical_bytes(current + [row])) > maximum_bytes:
            chunks.append(current)
            current = []
        current.append(row)
    if current:
        chunks.append(current)
    return chunks or [[]]


def merge_refinement(old: list[dict], revised: list[dict], affected_ids: list[str]) -> tuple[list[dict], list[dict]]:
    """Keep omitted candidates; revoke acceptance when their premises may have changed."""
    revised_ids = {item["item_id"] for item in revised}
    affected = set(affected_ids) | revised_ids
    while True:
        previous = set(affected)
        affected.update(item["item_id"] for item in old if set(item["depends_on"]) & affected)
        if previous == affected:
            break
    omitted = deepcopy([item for item in old if item["item_id"] not in revised_ids])
    for candidate in omitted:
        if candidate["item_id"] in affected:
            withhold(candidate, "Refinement incomplete")
            candidate["review_status"] = "unreviewed"
    combined = revised + omitted
    issues = []
    if omitted:
        issues.append({"code": "clinical_refinement_omitted_candidates_preserved",
                       "item_ids": [item["item_id"] for item in omitted]})
    validate_dependencies(combined)
    issues.extend(enforce_consistency(combined))
    return combined, issues


def run_analysis(inputs: Any, *, policy: ExecutionPolicy | None = None) -> dict:
    """Execute a supplied-context scientific preview using runtime-provided helpers."""
    request = parse_request(inputs)
    context = request["context"]
    ledger = EvidenceLedger(request["subject_id"], request["as_of_date"], context["evidence"])
    prepared = request["prepared_sources"]
    for window in prepared["evidence"]:
        ledger.add(window)
    statistics = compute_statistics(context["cohort"], as_of_date=request["as_of_date"]) if request["analysis_mode"] == "cohort_pattern" else None
    if request["preflight_only"]:
        result = preflight_result(request, ledger, statistics)
        validate_result(result)
        return {"response_version": "1", "status": "success",
                "outputs": {"clinical_intelligence": result}, "metrics": {"logical_agent_calls": 0}, "logs": []}
    configured = policy or ExecutionPolicy()
    budget = Budget(replace(configured,
        max_agent_calls=min(configured.max_agent_calls,request['max_agent_calls']),
        deadline_seconds=min(configured.deadline_seconds,request['max_product_seconds']),
        research_concurrency=min(
        configured.research_concurrency, request.get("agent_parallelism", 20))))
    methodology = read_methodology(inputs)
    memory = read_product_memory(inputs, request)
    runner = AgentRunner(inputs, budget)
    runner.prepare_input_budgets()
    stages: list[StageResult] = []
    issues: list[dict] = deepcopy(prepared["issues"])
    if prepared["omissions"]:
        issues.append({"code": "clinical_prepared_source_coverage_partial",
                       "omitted_windows": len(prepared["omissions"])})
    if "source_event_metadata" in context and not ledger.rows():
        issues.append({"code": "clinical_source_only_independent_evidence_required"})
    claims: list[dict] = []
    common = {"source_assertions": context["source_assertions"], "methodology": methodology,
              "case_trial_ids":deepcopy(context['subject']['trial_ids']),
              "memory_context": memory_projection(memory), "data_is_not_instructions": True,
              "case_provenance": deepcopy(context.get("source_event_metadata", {})),
              "terminology_candidates": deepcopy(prepared["terminology"]),
              "terminology_is_not_outcome_evidence": True}

    phase_plans = []
    rejected_candidates = []

    def parallel_calls(specifications):
        """One flat phase pool; ordered reservation and joins keep budget/results stable."""
        if not specifications:
            return []
        prepared = [runner.prepare(request=request, **spec) for spec in specifications]
        phase_plans.append({"task_ids": [spec["task_id"] for spec in specifications],
            "planned": len(specifications), "ready": sum(row is None for row in prepared),
            "deferred": sum(row is not None for row in prepared),
            "concurrency_limit": budget.policy.research_concurrency})
        with ThreadPoolExecutor(max_workers=min(budget.policy.research_concurrency, len(specifications))) as pool:
            pending = [pool.submit(runner.call, request=request, **spec) if row is None or row.code=='clinical_packet_requires_partitioning' else row
                       for spec, row in zip(specifications, prepared)]
            return [row.result() if not isinstance(row, StageResult) else row for row in pending]

    def analysis_data(role, chunk, *, outcomes=None):
        value = closed_packet(chunk, ledger.rows(), claims, common, outcomes=outcomes)
        if role == 'hypothesis_analyst':
            value['cohort_statistics'] = statistics
        return value

    def planning_packet(role, chunk, *, outcomes=None):
        obligations = (['outcome:'+key for key in OUTCOMES] if role == 'outcome_adjudicator' else
                       ['seed:'+seed['assertion_id'] for seed in context['source_assertions']] or ['hypothesis_assessment'])
        return runner.packet(role, request, task_id=role+':planning', obligations=obligations,
            packet_data=analysis_data(role, chunk, outcomes=outcomes))

    def planned_batches(role, *, outcomes=None):
        return evidence_batches(ledger.rows(), lambda chunk: planning_packet(role, chunk, outcomes=outcomes),
            max_bytes=budget.policy.max_packet_bytes, fits=lambda packet: runner.packet_fits(role, packet))

    def analysis_plan_fits():
        return all(runner.packet_fits(role, planning_packet(role, chunk))
            for role in ('outcome_adjudicator', 'hypothesis_analyst') for chunk in planned_batches(role))

    analysis_reserve = len(planned_batches('outcome_adjudicator'))+len(planned_batches('hypothesis_analyst'))+1+(2 if memory['status']!='not_requested' else 0)

    def research_packets(role: str, iteration: int = 0, question: str | None = None, evidence_ids=None):
        relevant = [row for row in ledger.rows() if row["source_type"] in SOURCE_FACETS[role]]
        if evidence_ids is not None:
            relevant = [row for row in relevant if row['evidence_id'] in evidence_ids]
        tasks = []
        def research_data(chunk):
            return {**common, "evidence_packet": agent_evidence_view(chunk),
                "questions": [question] if question else ["Investigate " + FACETS[role]],
                "evidence_scope": {"assigned_count": len(chunk), "total_role_sources": len(relevant)},
                "source_admission_rule": "Use supplied evidence IDs. New sources remain unadmitted leads."}
        chunks = evidence_batches(relevant, lambda chunk: runner.packet(role, request,
            task_id=role+':planning', obligations=[FACETS[role]+':planning'], packet_data=research_data(chunk)),
            max_bytes=budget.policy.max_packet_bytes, fits=lambda packet: runner.packet_fits(role, packet))
        return [(role + ":" + str(iteration) + ":" + str(index),
                 [FACETS[role] + ":" + str(index)], research_data(chunk)) for index, chunk in enumerate(chunks)]

    initial_research = {role: research_packets(role) for role in RESEARCH_ROLES}
    invalid_initial = not analysis_plan_fits() or any(not runner.packet_fits(role, runner.packet(role, request,
        task_id=task_id, obligations=obligations, packet_data=data))
        for role, tasks in initial_research.items() for task_id, obligations, data in tasks)
    required_initial_calls = sum(map(len, initial_research.values())) + analysis_reserve
    if invalid_initial or required_initial_calls > budget.policy.max_agent_calls:
        issues.append({"code": "clinical_agent_input_preflight_partial",
                       "required_initial_calls": required_initial_calls,
                       "call_budget": budget.policy.max_agent_calls})

    # Known source packets are checked before any optional paid discovery.
    # Discovery may add evidence; recompute the complete initial plan afterwards.
    if not runner.preflight_blocked:
        # Only provider-native citations inspected through the trusted bridge can
        # enrich the ledger; supplied event assertions never become evidence.
        if request["supplementary_search"] and callable(getattr(inputs, "open_reference", None)):
            supplied_families = {row["source_type"] for row in ledger.rows()}
            roles = [role for role in RESEARCH_ROLES
                     if not (SOURCE_FACETS[role] & supplied_families)]
            if (request['analysis_mode']=='mechanistic_case' and
                    evidence_breadth(ledger.rows())['publication_breadth_status']=='limited' and
                    'literature_researcher' not in roles):
                roles.append('literature_researcher')
            # Structured sources are primary; discovery fills actual evidence gaps.
            issues.extend(acquire_sources(inputs, request, runner, budget, ledger, stages, roles=roles))

        analysis_reserve = len(planned_batches('outcome_adjudicator'))+len(planned_batches('hypothesis_analyst'))+1+(2 if memory['status']!='not_requested' else 0)
        initial_research = {role: research_packets(role) for role in RESEARCH_ROLES}
        required_calls = budget.calls + sum(map(len, initial_research.values())) + analysis_reserve
        if required_calls > budget.policy.max_agent_calls or not analysis_plan_fits() or any(not runner.packet_fits(role, runner.packet(role, request,
                task_id=task_id, obligations=obligations, packet_data=data))
                for role, tasks in initial_research.items() for task_id, obligations, data in tasks):
            issues.append({"code": "clinical_agent_input_preflight_partial"})

    def research(role: str, iteration: int = 0, question: str | None = None, evidence_ids=None) -> list[StageResult]:
        tasks = []
        planned = initial_research[role] if iteration == 0 and question is None and evidence_ids is None else research_packets(role, iteration, question, evidence_ids)
        for task_id, obligations, data in planned:
            targeted_search=bool(question and request['supplementary_search'] and
                                 callable(getattr(inputs,'open_reference',None)))
            if targeted_search:
                try:
                    budget.reserve_search(role)
                    data['search_queries']=[question]
                    data['source_admission_rule']+=' Native citations require independent trusted HTTP inspection before use.'
                except DeferredWork as error:
                    issues.append({'code':error.code})
                    targeted_search=False
            tasks.append(runner.call(role, request, task_id=task_id,
                obligations=obligations, downstream_reserve=analysis_reserve,
                packet_data=data))
            if targeted_search and tasks[-1].payload is not None:
                issues.extend(inspect_stage_sources(inputs,request,budget,ledger,tasks[-1]))
        return tasks

    def collect(tasks: list[StageResult]) -> None:
        for stage in tasks:
            stages.append(stage)
            if stage.payload is None:
                issues.append({"stage_id": stage.task_id, "code": stage.code})
                continue
            try:
                candidates = stage.payload["items"]
                scoped = []
                for candidate in candidates:
                    references = ([*candidate.get('supporting_evidence_ids', []),
                                   *candidate.get('contradicting_evidence_ids', [])]
                                  if isinstance(candidate, dict) and
                                  isinstance(candidate.get('supporting_evidence_ids', []), list) and
                                  isinstance(candidate.get('contradicting_evidence_ids', []), list) else [])
                    if stage.evidence_ids is not None and any(not isinstance(ref, str) or ref not in stage.evidence_ids
                                                              for ref in references):
                        issues.append({'stage_id': stage.task_id, 'code': 'clinical_stage_evidence_not_supplied'})
                    else:
                        scoped.append(candidate)
                valid, errors = ledger.validate_claims(scoped, stage_id=stage.task_id)
            except ContractError as error:
                if error.code not in {"clinical_claim_batch_invalid", "clinical_claim_id_duplicate"}:
                    raise
                issues.append({"stage_id": stage.task_id, "code": error.code})
                continue
            if errors and stage.role in RESEARCH_ROLES:
                original_errors=deepcopy(errors)
                bad_indexes={row['item_index'] for row in errors if 'item_index' in row and
                    row['code'] in {'clinical_span_mismatch','clinical_span_offsets_invalid'}}
                rejected=[scoped[index] for index in sorted(bad_indexes)]
                selected_refs={ref for row in rejected for field in
                    ('supporting_evidence_ids','contradicting_evidence_ids') for ref in row.get(field,[])}
                fixed=correct_business(runner,request,stage,
                    packet_data={**common,'evidence_packet':agent_evidence_view(
                        [row for row in ledger.rows() if row['evidence_id'] in selected_refs]),
                        'source_admission_rule':'Correct assigned claim IDs only, against exact supplied windows.'},
                    obligations=['correct_claim:'+row['claim_id'] for row in rejected],
                    rejected_items=rejected,errors=errors,downstream_reserve=analysis_reserve)
                if fixed is not None:
                    stages.append(fixed)
                    revised=fixed.payload['items'] if fixed.payload else []
                    allowed={row['claim_id'] for row in rejected}
                    scope_ok=(isinstance(revised,list) and
                        all(isinstance(row,dict) and row.get('claim_id') in allowed and
                            all(isinstance(row.get(field),list) and all(isinstance(ref,str) and ref in selected_refs
                                for ref in row[field]) for field in ('supporting_evidence_ids','contradicting_evidence_ids'))
                            for row in revised))
                    repaired,remaining=ledger.validate_claims(revised,stage_id=stage.task_id) if scope_ok else ([],[{'code':'clinical_business_correction_scope_invalid'}])
                    valid.extend(repaired)
                    repaired_ids={row['local_claim_id'] for row in repaired}
                    errors=[row for row in errors if scoped[row['item_index']]['claim_id'] not in repaired_ids]
                    errors.extend(remaining)
                    if repaired:
                        fixed.semantic_metadata['business_correction_receipt']={
                            'original_task_id':stage.task_id,'original_errors':original_errors,
                            'repaired_claim_ids':sorted(repaired_ids),'original_output_digest':digest(stage.payload)}
            claims.extend(valid)
            issues.extend(errors)

    # Flatten roles and batches into one phase; no nested role executors.
    initial_specs = [{"role": role, "task_id": task_id, "obligations": obligations,
        "downstream_reserve": analysis_reserve, "packet_data": data}
        for role in RESEARCH_ROLES for task_id, obligations, data in initial_research[role]]
    collect(parallel_calls(initial_specs))

    def normalize_stage(stage: StageResult, kind: str) -> list[dict]:
        try:
            rows = stage.payload["items"] if stage.payload else []
            scope_errors = []
            if stage.evidence_ids is not None and isinstance(rows,list):
                scoped = []
                for row in rows:
                    references = ([*row.get('supporting_evidence_ids',[]),*row.get('contradicting_evidence_ids',[])]
                                  if isinstance(row,dict) and isinstance(row.get('supporting_evidence_ids',[]),list)
                                  and isinstance(row.get('contradicting_evidence_ids',[]),list) else [])
                    if any(not isinstance(ref,str) or ref not in stage.evidence_ids for ref in references):
                        scope_errors.append({'stage_id':stage.task_id,'code':'clinical_stage_evidence_not_supplied'})
                        rejected_candidates.append({'stage_id':stage.task_id,'role':stage.role,
                            'reason':'clinical_stage_evidence_not_supplied','candidate':deepcopy(row),
                            'assigned_evidence_ids':list(stage.evidence_ids),'input_digest':stage.input_digest})
                    else:
                        scoped.append(row)
                rows = scoped
            items, errors = normalize_items(rows,
                                             kind, request, ledger)
            errors.extend(scope_errors)
        except ContractError as error:
            if error.code not in {"clinical_candidate_batch_invalid", "clinical_item_duplicate"}:
                raise
            items, errors = [], [{"stage_id": stage.task_id, "code": error.code}]
        original_errors=deepcopy(errors)
        repairable={'clinical_fields_invalid','clinical_text_invalid','clinical_outcome_value_invalid','clinical_hypothesis_plan_invalid'}
        rejected=[rows[row['item_index']] for row in errors if row.get('code') in repairable and
            isinstance(row.get('item_index'),int) and isinstance(rows[row['item_index']],dict) and
            isinstance(rows[row['item_index']].get('item_id'),str)] if isinstance(rows,list) else []
        if rejected:
            selected_refs={ref for row in rejected for field in ('supporting_evidence_ids','contradicting_evidence_ids')
                for ref in (row.get(field,[]) if isinstance(row.get(field,[]),list) else []) if isinstance(ref,str)}
            fixed=correct_business(runner,request,stage,
                packet_data={**common,'evidence_packet':agent_evidence_view([row for row in ledger.rows() if row['evidence_id'] in selected_refs])},
                obligations=['correct_item:'+row['item_id'] for row in rejected],rejected_items=rejected,
                errors=[row for row in errors if row.get('code') in repairable],downstream_reserve=3)
            if fixed is not None:
                stages.append(fixed)
                allowed={row['item_id'] for row in rejected}
                revised=fixed.payload['items'] if fixed.payload else []
                valid_scope=all(isinstance(row,dict) and row.get('item_id') in allowed and
                    all(isinstance(row.get(field),list) and all(isinstance(ref,str) and ref in selected_refs for ref in row[field])
                        for field in ('supporting_evidence_ids','contradicting_evidence_ids')) for row in revised)
                repaired,remaining=normalize_items(revised,kind,request,ledger) if valid_scope else ([],[{'code':'clinical_business_correction_scope_invalid'}])
                repaired_ids={row['item_id'] for row in repaired};items.extend(repaired)
                errors=[row for row in errors if not isinstance(row.get('item_index'),int) or
                    not isinstance(rows[row['item_index']],dict) or rows[row['item_index']].get('item_id') not in repaired_ids]
                errors.extend(remaining)
                fixed.semantic_metadata['business_correction_receipt']={'original_task_id':stage.task_id,
                    'original_errors':original_errors,'repaired_item_ids':sorted(repaired_ids)}
        issues.extend(errors)
        return items

    def evaluate(iteration: int) -> tuple[list[dict], StageResult]:
        outcomes, hypotheses = [], []
        outcome_chunks = planned_batches('outcome_adjudicator')
        # Reserve only actual downstream phases, never all outcome chunks again.
        hypothesis_reserve = len(planned_batches('hypothesis_analyst'))
        outcome_specs = [{"role": 'outcome_adjudicator',
            "task_id": 'outcome:'+str(iteration)+((':'+str(index)) if len(outcome_chunks)>1 else ''),
            "obligations": ['outcome:'+key for key in OUTCOMES],
            "downstream_reserve": hypothesis_reserve+1+(2 if memory['status']!='not_requested' else 0),
            "packet_data": analysis_data('outcome_adjudicator', chunk)}
            for index, chunk in enumerate(outcome_chunks)]
        for index, outcome_stage in enumerate(parallel_calls(outcome_specs)):
            namespace_candidates(outcome_stage, 'outcome', index, multiple=len(outcome_chunks)>1)
            stages.append(outcome_stage)
            outcomes.extend(normalize_stage(outcome_stage, 'outcome'))
        hypothesis_chunks = planned_batches('hypothesis_analyst', outcomes=outcomes)
        hypothesis_specs = []
        for index, chunk in enumerate(hypothesis_chunks):
            data = analysis_data('hypothesis_analyst', chunk, outcomes=outcomes)
            data['cohort_statistics'] = statistics
            hypothesis_specs.append({"role": 'hypothesis_analyst',
                "task_id": 'hypotheses:'+str(iteration)+((':'+str(index)) if len(hypothesis_chunks)>1 else ''),
                "obligations": ['seed:'+seed['assertion_id'] for seed in context['source_assertions']] or ['hypothesis_assessment'],
                "downstream_reserve": 1+(2 if memory['status']!='not_requested' else 0), "packet_data": data})
        for index, analyst in enumerate(parallel_calls(hypothesis_specs)):
            namespace_candidates(analyst, 'hypothesis', index, multiple=len(hypothesis_chunks)>1)
            stages.append(analyst)
            hypotheses.extend(normalize_stage(analyst, 'hypothesis'))
        items = outcomes + hypotheses
        counts: dict[str, int] = {}
        for item in items:
            counts[item["item_id"]] = counts.get(item["item_id"], 0) + 1
        duplicates = {key for key, count in counts.items() if count > 1}
        if duplicates:
            issues.append({"code": "clinical_cross_stage_item_duplicate", "item_ids": sorted(duplicates)})
            items = [item for item in items if item["item_id"] not in duplicates]
        items, quarantined, dependency_issues = isolate_dependencies(items)
        issues.extend(dependency_issues)
        items.extend(quarantined)
        quarantined = []
        packets = critic_batches(items, ledger.rows(),
            {**common, "cohort_statistics": statistics},
            max(1024, budget.policy.max_packet_bytes - 10000),
            fits=lambda data: runner.packet_fits('evidence_critic', runner.packet('evidence_critic', request,
                task_id='review:'+str(iteration)+':planning',
                obligations=['review:'+x['item_id'] for x in data['candidate_items']] or ['no_candidate_review'],
                packet_data=data))) if items else [{
                **common, "candidate_items": [], "evidence_packet": [], "cohort_statistics": statistics}]
        verdicts, followups, critic_stages = [], [], []
        recovery_reserved = 2 if budget.policy.max_reconciliation_agent_calls-budget.reconciliation_calls>=2 else 0
        critic_specs = [{"role": "evidence_critic",
            "task_id": "review:"+str(iteration)+((":"+str(index)) if len(packets)>1 else ""),
            "obligations": ["review:"+x["item_id"] for x in packet["candidate_items"]] or ["no_candidate_review"],
            "downstream_reserve": (2 if memory["status"]!="not_requested" else 0) + recovery_reserved,
            "packet_data": {**packet,"review_recovery_reserved_calls":recovery_reserved}} for index, packet in enumerate(packets)]
        for spec,stage in zip(critic_specs,parallel_calls(critic_specs)):
            stages.append(stage)
            critic_stages.append(stage)
            if stage.payload is not None:
                current=deepcopy(stage.payload['items'])
                assigned=spec['packet_data']['candidate_items']
                by_id={row['item_id']:row for row in assigned}
                rejected=[row for row in current if isinstance(row,dict) and row.get('item_id') in by_id and
                    any(not isinstance(row.get(field),list) or not all(isinstance(ref,str) and ref in by_id[row['item_id']][field] for ref in row[field])
                        for field in ('supporting_evidence_ids','contradicting_evidence_ids'))]
                identity_counts={key:sum(isinstance(row,dict) and row.get('item_id')==key for row in current) for key in by_id}
                rejected=[row for row in rejected if identity_counts[row['item_id']]==1]
                bad_candidates=[by_id[row['item_id']] for row in rejected]
                fixed=correct_business(runner,request,stage,
                    packet_data={**spec['packet_data'],'candidate_items':bad_candidates},
                    obligations=['review:'+row['item_id'] for row in bad_candidates],rejected_items=rejected,
                    errors=[{'code':'clinical_critic_evidence_mismatch','item_id':row['item_id']} for row in rejected],
                    downstream_reserve=max(0,spec['downstream_reserve']-spec['packet_data']['review_recovery_reserved_calls']))
                if fixed is not None:
                    stages.append(fixed)
                    if fixed.payload:
                        # Correct only rejected IDs, preserve valid original siblings.
                        bad_ids={row['item_id'] for row in rejected}
                        revised=[row for row in fixed.payload['items'] if isinstance(row,dict) and row.get('item_id') in bad_ids]
                        counts={key:sum(row.get('item_id')==key for row in revised) for key in bad_ids}
                        replaced={row['item_id'] for row in revised if counts[row['item_id']]==1}
                        current=[row for row in current if not isinstance(row,dict) or row.get('item_id') not in replaced]
                        current.extend(row for row in revised if row['item_id'] in replaced)
                verdicts.extend(current)
                followups.extend(stage.payload['followup_requests'])
        critic = critic_stages[0]
        if len(critic_stages) > 1:
            # A join record is not another model invocation or a durable checkpoint.
            critic = StageResult("review_join:" + str(iteration), "evidence_critic",
                "completed" if all(x.status == "completed" for x in critic_stages) else "partial",
                digest([x.input_digest for x in critic_stages]),
                {"items": verdicts, "followup_requests": followups}, {})
        reviewed, errors = scoped_review(items,
            verdicts if any(x.payload is not None for x in critic_stages) else None, ledger)
        reviewed.extend(quarantined)
        issues.extend(errors)
        return reviewed, critic

    reviewed, critic = evaluate(0)
    reflection_requested = critic.payload['followup_requests'] if critic.payload else []
    deferred_followups = deepcopy(reflection_requested)
    if reflection_requested and not request['enable_refinement']:
        issues.append({'code':'clinical_reflection_not_requested',
                       'deferred_followup_count':len(reflection_requested)})
    if request["enable_refinement"] and critic.payload:
        followups = critic.payload["followup_requests"]
        for followup in followups:
            require(isinstance(followup, dict) and set(followup) == {"role", "question", "affected_item_ids"},
                    "clinical_followup_contract_invalid")
            require(isinstance(followup["role"], str) and followup["role"] in RESEARCH_ROLES and
                    isinstance(followup["question"], str) and 0 < len(followup["question"]) <= 1000,
                    "clinical_followup_contract_invalid")
            affected = identifiers(followup["affected_item_ids"], allow_empty=False)
            require(set(affected) <= {x["item_id"] for x in reviewed}, "clinical_followup_scope_invalid")
        selected_followup = False
        re_reviewed = False
        if followups and budget.calls + (6 if memory["status"] != "not_requested" else 4) <= budget.policy.max_agent_calls and budget.refine_once():
            followup = followups[0]
            old = deepcopy(reviewed)
            selected = [row for row in reviewed if row['item_id'] in followup['affected_item_ids']]
            evidence_ids = {ref for row in selected for field in ('supporting_evidence_ids','contradicting_evidence_ids')
                            for ref in row[field]}
            try:
                if budget.reflection_task(followup['role'],followup['question'],digest(sorted(evidence_ids))):
                    selected_followup = True
                    before_evidence=digest(ledger.rows())
                    semantic_keys=lambda rows:{digest({k:v for k,v in row.items() if k not in {'claim_id','stage_id'}})
                                               for row in rows}
                    before_claims=semantic_keys(claims)
                    collect(research(followup["role"], 1, followup["question"], evidence_ids=evidence_ids))
                    if digest(ledger.rows())==before_evidence and not (semantic_keys(claims)-before_claims):
                        issues.append({'code':'clinical_reflection_no_progress','affected_item_ids':followup['affected_item_ids']})
                    else:
                        revised, critic = evaluate(1)
                        re_reviewed = True
                        reviewed, errors = merge_refinement(old, revised, followup["affected_item_ids"])
                        issues.extend(errors)
                        deferred_followups = [row for row in deferred_followups if row != followup]
                        deferred_followups.extend(deepcopy(critic.payload['followup_requests'] if critic.payload else []))
            finally:
                budget.finish_reflection()
        deferred = followups[1:] if selected_followup else followups
        if deferred:
            issues.append({'code':'clinical_reflection_followups_deferred',
                'reason':'bounded_reflection_target_or_call_allowance',
                'deferred_followup_count':len(deferred),
                'requests':[{'role':row['role'],'question_digest':digest(row['question']),
                             'affected_item_ids':row['affected_item_ids']} for row in deferred]})
        if re_reviewed and critic.payload and critic.payload['followup_requests']:
            issues.append({'code':'clinical_reflection_round_limit_reached',
                           'deferred_followup_count':len(critic.payload['followup_requests'])})
    hypotheses = [x for x in reviewed if x["kind"] == "hypothesis"]
    outcomes = [x for x in reviewed if x["kind"] == "outcome"]
    if not hypotheses:
        issues.append({"code": "clinical_no_hypotheses_returned"})
    if request["analysis_mode"] == "mechanistic_case":
        represented = {(item["dimension"], trial) for item in outcomes for trial in (item["trial_ids"] or [None])}
        missing = [(dimension, trial) for dimension in OUTCOMES
                   for trial in (context["subject"]["trial_ids"] or [None]) if (dimension, trial) not in represented]
        if missing:
            issues.append({"code": "clinical_outcome_coverage_incomplete",
                           "missing": [{"dimension": d, "trial_id": t} for d, t in missing]})
    seed_ids = {seed["assertion_id"] for seed in context["source_assertions"]}
    missing_seeds = seed_ids - {item["source_assertion_id"] for item in hypotheses}
    if missing_seeds:
        issues.append({"code": "clinical_seed_coverage_incomplete", "assertion_ids": sorted(missing_seeds)})
    if statistics and statistics["status"] == "not_run":
        issues.append({"code": statistics["reason"]})
    product_plan = review_edit_plan([], None, memory, request)
    accepted_items = [item for item in reviewed if item["accepted"] and (
        item["kind"] == "outcome" and item["value"] not in {"unknown", "not_evaluable", "not_applicable"}
        or item["kind"] == "hypothesis" and item["verdict"] in {"supported", "refuted"})]
    ambiguous_product = any(len(event.get("all_product_ids", [])) > 1
        for event in context.get("source_event_metadata", {}).get("events", []))
    if ambiguous_product and memory["status"] != "not_requested":
        product_plan.update(status="deferred", reason="clinical_product_attribution_review_required")
    if memory["status"] in {"read", "not_initialized"} and accepted_items and not ambiguous_product:
        product_plan = preview_memory(runner,request,memory,accepted_items,ledger.rows(),stages,issues)
    # The optional class extension is deliberately after the primary product plan.
    # It cannot authorize a product write or turn a case lesson into a class rule.
    product_plan["class_extension"] = {"enabled": request["enable_pharmacological_class"], "status": "not_requested",
                                       "write_attempted": False, "cross_case_review_required": True}
    if request["enable_pharmacological_class"] and request["memory_mode"] != "off":
        try:
            group_memory = read_group_memory(inputs, request)
            product_plan["class_extension"].update(status="candidate_preview", group_id=group_memory["group_id"],
                memory_status=group_memory["status"], candidate_hypothesis_ids=[h["item_id"] for h in hypotheses if h["memory_eligibility"]])
        except ContractError as error:
            product_plan["class_extension"].update(status="blocked", reason=error.code)
    complete = bool(hypotheses) and not issues and all(stage.status == "completed" for stage in stages) and all(
        item["review_status"] == "automated_reviewed" for item in reviewed)
    result = {"schema_version": SCHEMA, "asset": ASSET_KEY + "@" + VERSION,
        "assessment_id": "assessment:" + digest({"request": request, "methodology": methodology,
                                                   "memory": memory_projection(memory)}).split(":")[1][:32],
        "request_id": request["request_id"], "analysis_mode": request["analysis_mode"],
        "as_of_date": request["as_of_date"], "subject": context["subject"],
        "source_assertions": deepcopy(context["source_assertions"]), "research_claims": claims,
        "case_assessments": outcomes, "hypothesis_results": hypotheses,
        "cohort_statistics": statistics, "evidence": ledger.rows(),
        "reason_graph": build_reason_graph(context["subject"], reviewed, ledger.rows(),
            case_scope=context.get("case_scope"), terminology=prepared["terminology"]),
        "quality": {"status": "completed" if complete else "partial", "issues": issues,
            "automated_review_only": True, "scientific_accuracy_certified": False, "external_truth_verified": False,
            "evidence_scope": "resolved_input_snapshot",
            "limitations": ["Supplied-source support is not independent public verification",
                            "Model-assessed semantic review requires domain quality evaluation"],
            "required_roles_completed": {role: any(stage.role == role for stage in stages) and all(stage.status == "completed" for stage in stages if stage.role == role)
                                         for role in (*RESEARCH_ROLES, "outcome_adjudicator", "hypothesis_analyst", "evidence_critic")}},
        "execution": {"stages": [stage.summary() for stage in stages], "phase_plans": phase_plans,
            "input_reconciliation": {'stages':[stage.summary() for stage in runner.reconciliation_stages],
                'receipts':deepcopy(runner.reconciliation_receipts),'source_text_changed':False}, **budget.proof(),
            "resume": {"available": False, "reason": "durable_stage_retention_not_qualified"}},
        "memory_update": product_plan,
        "persistence": {"status": "not_attested", "receipt": None},
        "prepared_sources": {key: deepcopy(value) for key, value in prepared.items() if key != "evidence"},
        "source_request_plan": source_request_plan(request, prepared)}
    if "source_event_metadata" in context:
        result["source_event_metadata"] = deepcopy(context["source_event_metadata"])
    if __package__:
        from .deferred_work_v0_1_12 import deferred_work, execution_disposition
    else:
        from deferred_work_v0_1_12 import deferred_work, execution_disposition
    result['deferred_work'] = deferred_work(result, runner.task_packets, rejected_candidates, deferred_followups)
    result['execution']['disposition'] = execution_disposition(result)
    result['publication_readiness'] = {
        'status':'prepared_for_governed_publication' if request.get('prepare_result_for_persistence') else 'not_requested',
        'artifact_quality':result['quality']['status'],
        'unreviewed_candidates_are_not_conclusions':True,
        'deferred_work_count':len(result['deferred_work']['tasks']),
        'policy_and_runtime_receipt_required':True,
        'publication_confirmed':False}
    result = finalize_output(result)
    validate_result(result)
    outputs = {"clinical_intelligence": result}
    if request.get("prepare_result_for_persistence", False):
        # Trusted output publication consumes the records envelope; Python never writes a node.
        # Keep the existing callable clinical_intelligence result unchanged by default.
        outputs["clinical_intelligence_records"] = {"records": [deepcopy(result)]}
    return {"response_version": "1", "status": "success", "outputs": outputs,
            "metrics": {"logical_agent_calls": budget.calls}, "logs": []}
