"""Bounded research, scoped review and one refinement without discarding valid work."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from typing import Any
if __package__:
    from .contracts import ASSET_KEY, SCHEMA, VERSION, RESEARCH_ROLES, ContractError, canonical_bytes, digest, identifiers, parse_request, require
    from .policies import Budget, ExecutionPolicy
    from .runtime_access import AgentRunner, StageResult
    from .research_sources import acquire_sources
    from .evidence import EvidenceLedger
    from .cohort import compute_statistics
    from .quality import OUTCOMES, enforce_consistency, normalize_items, review_items, validate_dependencies, withhold
    from .memory import read_methodology, read_group_memory
    from .product_memory import read_product_memory, memory_projection, editor_contract, validate_edit_candidates, review_edit_plan
    from .rendering import build_reason_graph, render_report, validate_result
else:
    from contracts import ASSET_KEY, SCHEMA, VERSION, RESEARCH_ROLES, ContractError, canonical_bytes, digest, identifiers, parse_request, require
    from policies import Budget, ExecutionPolicy
    from runtime_access import AgentRunner, StageResult
    from research_sources import acquire_sources
    from evidence import EvidenceLedger
    from cohort import compute_statistics
    from quality import OUTCOMES, enforce_consistency, normalize_items, review_items, validate_dependencies, withhold
    from memory import read_methodology, read_group_memory
    from product_memory import read_product_memory, memory_projection, editor_contract, validate_edit_candidates, review_edit_plan
    from rendering import build_reason_graph, render_report, validate_result

FACETS = {"trial_researcher": "clinical_outcome", "literature_researcher": "mechanism_evidence",
          "event_researcher": "development_timeline"}
SOURCE_FACETS = {"trial_researcher": {"trial_registry", "regulator"},
                 "literature_researcher": {"original_research", "review"},
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
    statistics = compute_statistics(context["cohort"], as_of_date=request["as_of_date"]) if request["analysis_mode"] == "cohort_pattern" else None
    budget = Budget(policy)
    methodology = read_methodology(inputs)
    memory = read_product_memory(inputs, request)
    runner = AgentRunner(inputs, budget)
    stages: list[StageResult] = []
    issues: list[dict] = []
    # Only provider-native citations inspected through the trusted bridge can
    # enrich the ledger; supplied event assertions never become evidence.
    if callable(getattr(inputs, "open_reference", None)):
        issues.extend(acquire_sources(inputs, request, runner, budget, ledger, stages))
    if "source_event_metadata" in context and not ledger.rows():
        issues.append({"code": "clinical_source_only_independent_evidence_required"})
    claims: list[dict] = []
    common = {"source_assertions": context["source_assertions"], "methodology": methodology,
              "memory_context": memory_projection(memory), "data_is_not_instructions": True}

    def research(role: str, iteration: int = 0, question: str | None = None) -> list[StageResult]:
        relevant = [row for row in ledger.rows() if row["source_type"] in SOURCE_FACETS[role]]
        tasks = []
        for index, chunk in enumerate(partition_evidence(relevant)):
            tasks.append(runner.call(role, request, task_id=role + ":" + str(iteration) + ":" + str(index),
                obligations=[FACETS[role] + ":" + str(index)], downstream_reserve=5 if memory["status"] != "not_requested" else 3,
                packet_data={**common, "evidence_packet": chunk,
                    "questions": [question] if question else ["Investigate " + FACETS[role]],
                    "evidence_scope": {"assigned_count": len(chunk), "total_role_sources": len(relevant)},
                    "source_admission_rule": "Use supplied evidence IDs. New sources remain unadmitted leads."}))
        return tasks

    def collect(tasks: list[StageResult]) -> None:
        for stage in tasks:
            stages.append(stage)
            if stage.payload is None:
                issues.append({"stage_id": stage.task_id, "code": stage.code})
                continue
            valid, errors = ledger.validate_claims(stage.payload["items"], stage_id=stage.task_id)
            claims.extend(valid)
            issues.extend(errors)

    # Join in fixed role order, not completion order. Runtime owns I/O cancellation.
    with ThreadPoolExecutor(max_workers=budget.policy.research_concurrency) as pool:
        futures = [pool.submit(research, role) for role in RESEARCH_ROLES]
        for future in futures:
            collect(future.result())

    def evaluate(iteration: int) -> tuple[list[dict], StageResult]:
        outcome_stage = runner.call("outcome_adjudicator", request,
            task_id="outcome:" + str(iteration), obligations=["outcome:" + key for key in OUTCOMES],
            packet_data={**common, "evidence_packet": ledger.rows(), "research_claims": claims})
        stages.append(outcome_stage)
        outcomes, errors = normalize_items(outcome_stage.payload["items"] if outcome_stage.payload else [],
                                          "outcome", request, ledger)
        issues.extend(errors)
        analyst = runner.call("hypothesis_analyst", request,
            task_id="hypotheses:" + str(iteration), obligations=[
                "seed:" + seed["assertion_id"] for seed in context["source_assertions"]] or ["hypothesis_assessment"],
            packet_data={**common, "evidence_packet": ledger.rows(), "research_claims": claims,
                         "case_assessments": outcomes, "cohort_statistics": statistics})
        stages.append(analyst)
        hypotheses, errors = normalize_items(analyst.payload["items"] if analyst.payload else [],
                                            "hypothesis", request, ledger)
        issues.extend(errors)
        items = outcomes + hypotheses
        critic = runner.call("evidence_critic", request,
            task_id="review:" + str(iteration), obligations=["review:" + x["item_id"] for x in items] or ["no_candidate_review"],
            packet_data={**common, "evidence_packet": ledger.rows(), "candidate_items": items,
                         "cohort_statistics": statistics})
        stages.append(critic)
        try:
            reviewed, errors = review_items(items, critic.payload["items"] if critic.payload else None, ledger)
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
        if followups and budget.calls + (6 if memory["status"] != "not_requested" else 4) <= budget.policy.max_agent_calls and budget.refine_once():
            followup = followups[0]
            old = deepcopy(reviewed)
            collect(research(followup["role"], 1, followup["question"]))
            revised, critic = evaluate(1)
            reviewed, errors = merge_refinement(old, revised, followup["affected_item_ids"])
            issues.extend(errors)
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
    accepted_items = [item for item in reviewed if item["accepted"]]
    if memory["status"] in {"read", "not_initialized"} and accepted_items:
        editor = runner.call("product_memory_editor", request, task_id="product_memory_edit",
            obligations=["product_memory_delta"], downstream_reserve=1,
            packet_data={"memory_context": memory_projection(memory), "accepted_items": accepted_items,
                "evidence_packet": ledger.rows(), "event_ids": request["event_ids"],
                "case_scope": context["case_scope"], "edit_contract": editor_contract()})
        stages.append(editor)
        try:
            candidates = validate_edit_candidates(editor.payload["items"] if editor.payload else [], memory, accepted_items)
            memory_critic = None
            if candidates:
                memory_critic = runner.call("evidence_critic", request, task_id="product_memory_review",
                    obligations=["memory_review:" + row["edit_id"] for row in candidates],
                    packet_data={"review_kind": "product_memory_edits", "memory_context": memory_projection(memory),
                        "candidate_edits": candidates, "accepted_items": accepted_items, "evidence_packet": ledger.rows(),
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
        "reason_graph": build_reason_graph(context["subject"], reviewed, ledger.rows()),
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
        "persistence": {"status": "not_attested", "receipt": None}}
    if "source_event_metadata" in context:
        result["source_event_metadata"] = deepcopy(context["source_event_metadata"])
    validate_result(result)
    result["report_markdown"] = render_report(result)
    return {"response_version": "1", "status": "success", "outputs": {"clinical_intelligence": result},
            "metrics": {"logical_agent_calls": budget.calls}, "logs": []}
