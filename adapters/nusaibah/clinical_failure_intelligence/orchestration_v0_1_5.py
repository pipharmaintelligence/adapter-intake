"""Bounded research, scoped review and one refinement without discarding valid work."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from typing import Any
if __package__:
    from .contracts_v0_1_5 import ASSET_KEY, SCHEMA, VERSION, RESEARCH_ROLES, ContractError, canonical_bytes, digest, identifiers, parse_request, require
    from .policies_v0_1_5 import Budget, ExecutionPolicy, DeferredWork
    from .runtime_access_v0_1_5 import AgentRunner, StageResult
    from .research_sources_v0_1_5 import acquire_sources, inspect_stage_sources
    from .evidence_v0_1_5 import EvidenceLedger
    from .cohort_v0_1_5 import compute_statistics
    from .quality_v0_1_5 import OUTCOMES, enforce_consistency, normalize_items, review_items, validate_dependencies, withhold
    from .memory_v0_1_5 import read_methodology, read_group_memory
    from .product_memory_v0_1_5 import read_product_memory, memory_projection, editor_contract, validate_edit_candidates, review_edit_plan
    from .rendering_v0_1_5 import build_reason_graph, render_report, validate_result
    from .review_packets_v0_1_5 import critic_batches, scoped_review
    from .decision_outcome_v0_1_5 import finalize_output, preflight_result, source_request_plan
    from .analysis_packets_v0_1_5 import evidence_batches, closed_packet, namespace_candidates, item_evidence
else:
    from contracts_v0_1_5 import ASSET_KEY, SCHEMA, VERSION, RESEARCH_ROLES, ContractError, canonical_bytes, digest, identifiers, parse_request, require
    from policies_v0_1_5 import Budget, ExecutionPolicy, DeferredWork
    from runtime_access_v0_1_5 import AgentRunner, StageResult
    from research_sources_v0_1_5 import acquire_sources, inspect_stage_sources
    from evidence_v0_1_5 import EvidenceLedger
    from cohort_v0_1_5 import compute_statistics
    from quality_v0_1_5 import OUTCOMES, enforce_consistency, normalize_items, review_items, validate_dependencies, withhold
    from memory_v0_1_5 import read_methodology, read_group_memory
    from product_memory_v0_1_5 import read_product_memory, memory_projection, editor_contract, validate_edit_candidates, review_edit_plan
    from rendering_v0_1_5 import build_reason_graph, render_report, validate_result
    from review_packets_v0_1_5 import critic_batches, scoped_review
    from decision_outcome_v0_1_5 import finalize_output, preflight_result, source_request_plan
    from analysis_packets_v0_1_5 import evidence_batches, closed_packet, namespace_candidates, item_evidence

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
    budget = Budget(policy)
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
              "memory_context": memory_projection(memory), "data_is_not_instructions": True,
              "case_provenance": deepcopy(context.get("source_event_metadata", {})),
              "terminology_candidates": deepcopy(prepared["terminology"]),
              "terminology_is_not_outcome_evidence": True}

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
            return {**common, "evidence_packet": chunk,
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
        runner.preflight_blocked = True
        issues.append({"code": "clinical_agent_input_preflight_failed",
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
            # Structured sources are primary; discovery fills actual evidence gaps.
            issues.extend(acquire_sources(inputs, request, runner, budget, ledger, stages, roles=roles))

        analysis_reserve = len(planned_batches('outcome_adjudicator'))+len(planned_batches('hypothesis_analyst'))+1+(2 if memory['status']!='not_requested' else 0)
        initial_research = {role: research_packets(role) for role in RESEARCH_ROLES}
        required_calls = budget.calls + sum(map(len, initial_research.values())) + analysis_reserve
        if required_calls > budget.policy.max_agent_calls or not analysis_plan_fits() or any(not runner.packet_fits(role, runner.packet(role, request,
                task_id=task_id, obligations=obligations, packet_data=data))
                for role, tasks in initial_research.items() for task_id, obligations, data in tasks):
            runner.preflight_blocked = True
            issues.append({"code": "clinical_agent_input_preflight_failed"})

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
            claims.extend(valid)
            issues.extend(errors)

    # Join in fixed role order, not completion order. Runtime owns I/O cancellation.
    with ThreadPoolExecutor(max_workers=budget.policy.research_concurrency) as pool:
        futures = [pool.submit(research, role) for role in RESEARCH_ROLES]
        for future in futures:
            collect(future.result())

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
        issues.extend(errors)
        return items

    def evaluate(iteration: int) -> tuple[list[dict], StageResult]:
        outcomes, hypotheses = [], []
        outcome_chunks = planned_batches('outcome_adjudicator')
        for index, chunk in enumerate(outcome_chunks):
            outcome_stage = runner.call('outcome_adjudicator', request,
                task_id='outcome:'+str(iteration)+((':'+str(index)) if len(outcome_chunks)>1 else ''),
                obligations=['outcome:'+key for key in OUTCOMES],
                downstream_reserve=len(outcome_chunks)+1+(2 if memory['status']!='not_requested' else 0),
                packet_data=analysis_data('outcome_adjudicator',chunk))
            namespace_candidates(outcome_stage,'outcome',index,multiple=len(outcome_chunks)>1)
            stages.append(outcome_stage)
            outcomes.extend(normalize_stage(outcome_stage,'outcome'))
        hypothesis_chunks = planned_batches('hypothesis_analyst', outcomes=outcomes)
        for index, chunk in enumerate(hypothesis_chunks):
            data = analysis_data('hypothesis_analyst',chunk,outcomes=outcomes)
            data['cohort_statistics'] = statistics
            analyst = runner.call('hypothesis_analyst',request,
                task_id='hypotheses:'+str(iteration)+((':'+str(index)) if len(hypothesis_chunks)>1 else ''),
                obligations=['seed:'+seed['assertion_id'] for seed in context['source_assertions']] or ['hypothesis_assessment'],
                downstream_reserve=1+(2 if memory['status']!='not_requested' else 0),packet_data=data)
            namespace_candidates(analyst,'hypothesis',index,multiple=len(hypothesis_chunks)>1)
            stages.append(analyst)
            hypotheses.extend(normalize_stage(analyst,'hypothesis'))
        items = outcomes + hypotheses
        counts: dict[str, int] = {}
        for item in items:
            counts[item["item_id"]] = counts.get(item["item_id"], 0) + 1
        duplicates = {key for key, count in counts.items() if count > 1}
        if duplicates:
            issues.append({"code": "clinical_cross_stage_item_duplicate", "item_ids": sorted(duplicates)})
            items = [item for item in items if item["item_id"] not in duplicates]
        packets = critic_batches(items, ledger.rows(),
            {**common, "cohort_statistics": statistics},
            max(1024, budget.policy.max_packet_bytes - 10000),
            fits=lambda data: runner.packet_fits('evidence_critic', runner.packet('evidence_critic', request,
                task_id='review:'+str(iteration)+':planning',
                obligations=['review:'+x['item_id'] for x in data['candidate_items']] or ['no_candidate_review'],
                packet_data=data))) if items else [{
                **common, "candidate_items": [], "evidence_packet": [], "cohort_statistics": statistics}]
        verdicts, followups, critic_stages = [], [], []
        for index, packet in enumerate(packets):
            task_id = "review:" + str(iteration) + (":" + str(index) if len(packets) > 1 else "")
            stage = runner.call("evidence_critic", request, task_id=task_id,
                obligations=["review:" + x["item_id"] for x in packet["candidate_items"]] or ["no_candidate_review"],
                downstream_reserve=2 if memory["status"] != "not_requested" else 0,
                packet_data=packet)
            stages.append(stage)
            critic_stages.append(stage)
            if stage.payload is not None:
                verdicts.extend(stage.payload["items"])
                followups.extend(stage.payload["followup_requests"])
        critic = critic_stages[0]
        if len(critic_stages) > 1:
            # A join record is not another model invocation or a durable checkpoint.
            critic = StageResult("review_join:" + str(iteration), "evidence_critic",
                "completed" if all(x.status == "completed" for x in critic_stages) else "partial",
                digest([x.input_digest for x in critic_stages]),
                {"items": verdicts, "followup_requests": followups}, {})
        try:
            reviewed, errors = scoped_review(items,
                verdicts if any(x.payload is not None for x in critic_stages) else None, ledger)
        except ContractError as error:
            # Invalid dependency graphs cannot enter the output graph. Keep isolated
            # candidates as unresolved and remove only their invalid dependency edges.
            reviewed = deepcopy(items)
            ids = {item["item_id"] for item in reviewed}
            if len(ids) != len(reviewed):
                raise
            if error.code in {"clinical_dependency_unknown", "clinical_dependency_cycle"}:
                for item in reviewed:
                    item["unresolved_dependency_ids"] = item["depends_on"]
                    item["depends_on"] = []
                    withhold(item, "Candidate dependencies require review")
            errors = [{"stage_id": critic.task_id, "code": error.code}]
        issues.extend(errors)
        return reviewed, critic

    reviewed, critic = evaluate(0)
    reflection_requested = critic.payload['followup_requests'] if critic.payload else []
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
        editor = runner.call("product_memory_editor", request, task_id="product_memory_edit",
            obligations=["product_memory_delta"], downstream_reserve=1,
            packet_data={"memory_context": memory_projection(memory), "accepted_items": accepted_items,
                "evidence_packet": item_evidence(accepted_items, ledger.rows()),
                "case_scope": context["case_scope"], "edit_contract": editor_contract()})
        stages.append(editor)
        try:
            candidates = validate_edit_candidates(editor.payload["items"] if editor.payload else [], memory, accepted_items)
            memory_critic = None
            if candidates:
                memory_critic = runner.call("evidence_critic", request, task_id="product_memory_review",
                    obligations=["memory_review:" + row["edit_id"] for row in candidates],
                    packet_data={"review_kind": "product_memory_edits", "memory_context": memory_projection(memory),
                        "candidate_edits": candidates, "accepted_items": accepted_items,
                        "evidence_packet": item_evidence(accepted_items, ledger.rows()),
                        "memory_review_contract": {"required_fields": ["edit_id", "accepted", "scope_preserved",
                            "evidence_supported", "prior_content_preserved", "rationale"]}})
                stages.append(memory_critic)
            product_plan = review_edit_plan(candidates, memory_critic.payload["items"]
                if memory_critic and memory_critic.payload else None, memory, request)
            if memory_critic is not None and memory_critic.status != "completed":
                product_plan.update(status="deferred", reason=memory_critic.code or "memory_review_incomplete")
            if editor.status != "completed":
                product_plan.update(status="deferred", reason=editor.code or "memory_edit_incomplete")
        except ContractError as error:
            product_plan.update(status="deferred", reason=error.code)
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
            "required_roles_completed": {role: all(stage.status == "completed" for stage in stages if stage.role == role)
                                         for role in (*RESEARCH_ROLES, "outcome_adjudicator", "hypothesis_analyst", "evidence_critic")}},
        "execution": {"stages": [stage.summary() for stage in stages], **budget.proof(),
            "resume": {"available": False, "reason": "durable_stage_retention_not_qualified"}},
        "memory_update": product_plan,
        "persistence": {"status": "not_attested", "receipt": None},
        "prepared_sources": {key: deepcopy(value) for key, value in prepared.items() if key != "evidence"},
        "source_request_plan": source_request_plan(request, prepared)}
    if "source_event_metadata" in context:
        result["source_event_metadata"] = deepcopy(context["source_event_metadata"])
    result = finalize_output(result)
    validate_result(result)
    outputs = {"clinical_intelligence": result}
    if request.get("prepare_result_for_persistence", False):
        # Trusted output publication consumes the records envelope; Python never writes a node.
        # Keep the existing callable clinical_intelligence result unchanged by default.
        outputs["clinical_intelligence_records"] = {"records": [deepcopy(result)]}
    return {"response_version": "1", "status": "success", "outputs": outputs,
            "metrics": {"logical_agent_calls": budget.calls}, "logs": []}
