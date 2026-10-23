"""Value-safe scientific/business disposition independent from report size.

A completed assessment is not a clinical success, a Skill commit, or a business
investment recommendation. All durable effects remain runtime-owned.
"""
from __future__ import annotations
from copy import deepcopy

if __package__:
    from .contracts_v0_1_11 import ASSET_KEY, SCHEMA, VERSION, canonical_bytes, digest, require
    from .rendering_v0_1_11 import build_reason_graph, render_report
    from .case_context_v0_1_11 import evidence_breadth
else:
    from contracts_v0_1_11 import ASSET_KEY, SCHEMA, VERSION, canonical_bytes, digest, require
    from rendering_v0_1_11 import build_reason_graph, render_report
    from case_context_v0_1_11 import evidence_breadth


def source_request_plan(request: dict, prepared: dict) -> list[dict]:
    """Describe remaining source needs only; these are not executed adapter calls."""
    subject = request["context"]["subject"]
    supplied = {(row["source_asset"], row["operation"], observation.get("nct_id"))
                for row in prepared["sources"] for observation in row.get("observations", [])}
    publication_trials = {trial for row in prepared["evidence"]
                          if row["source_id"].startswith("pubmed:") for trial in row["trial_ids"]}
    tasks = []
    trials = subject["trial_ids"]
    if trials:
        for trial in trials:
            if not trial.startswith("NCT"):
                continue
            for operation in ("study_get", "results_get"):
                if ("nusaibah.clinical_trials_lookup@0.1.1", operation, trial) not in supplied:
                    tasks.append({"source_asset": "nusaibah.clinical_trials_lookup@0.1.1",
                        "operation": operation, "selectors": {"nct_id": trial},
                        "priority": "primary_evidence", "execution": "not_requested"})
            if trial not in publication_trials:
                tasks.append({"source_asset": "nusaibah.pubmed_evidence@0.1.0",
                    "operation": "trial_publications", "selectors": {"nct_id": trial},
                    "next_after_discovery": ["article_get", "abstract_get"],
                    "priority": "corroboration", "execution": "not_requested"})
    elif subject.get("product_name"):
        tasks.append({"source_asset": "nusaibah.clinical_trials_lookup@0.1.1",
            "operation": "study_search", "selectors": {"intervention": subject["product_name"],
                "condition": subject.get("indication")}, "priority": "resolve_trial_identity",
            "execution": "not_requested"})
    return tasks


def causal_priorities(hypotheses: list[dict]) -> list[dict]:
    """Order existing questions by reviewed support, never by invented causal probability.

    The full original candidates remain in hypothesis_results. Grouping uses the
    admitted reason code and exact scope, not fuzzy merging of scientific claims.
    """
    groups = {}
    for item in hypotheses:
        if item.get('review_status') != 'automated_reviewed':
            tier = 'unreviewed'
        elif item.get('accepted') and item.get('verdict') == 'supported':
            tier = 'reviewed_support'
        elif item.get('verdict') == 'refuted':
            tier = 'reviewed_counterevidence'
        else:
            tier = 'reviewed_unresolved'
        key = (tier, item['reason_code'], item['scope'])
        groups.setdefault(key, []).append(item)
    order = {'reviewed_support': 0, 'reviewed_unresolved': 1,
             'reviewed_counterevidence': 2, 'unreviewed': 3}
    return [{
        'review_tier': tier, 'reason_code': reason, 'scope': scope,
        'candidate_ids': [item['item_id'] for item in rows],
        'supporting_evidence_ids': sorted({ref for item in rows for ref in item['supporting_evidence_ids']}),
        'contradicting_evidence_ids': sorted({ref for item in rows for ref in item['contradicting_evidence_ids']}),
        'question_and_discriminating_tests_in_candidate_ids': [item['item_id'] for item in rows],
        'causal_certainty_claimed': False,
    } for (tier, reason, scope), rows in sorted(groups.items(), key=lambda pair:
        (order[pair[0][0]], pair[0][1], pair[0][2]))]


def decision_summary(result: dict) -> dict:
    """Project only reviewed outcomes and explicit unresolved work into decisions."""
    accepted = [item for item in result["case_assessments"] if item["accepted"]]
    scientific = {dimension: [{"item_id": item["item_id"], "value": item["value"],
        "evidence_ids": item["supporting_evidence_ids"]} for item in accepted if item["dimension"] == dimension]
        for dimension in ("study_disposition","primary_endpoint_result", "safety_assessment", "programme_decision", "regulatory_decision")}
    definitive = [item for item in accepted if item["value"] not in {"unknown", "not_evaluable", "not_applicable"}]
    preflight = result["quality"]["status"] == "preflight"
    disposition = ("not_assessed" if preflight else "needs_evidence" if not definitive else
                   "partial_review" if result["quality"]["status"] != "completed" else "assessed")
    questions = [{"hypothesis_id": item["item_id"], "verdict": item["verdict"],
        "indicators": deepcopy(item["validation_indicators"]),
        "falsification_condition": item["falsification_condition"]}
        for item in result["hypothesis_results"]]
    return {"schema_version": "clinical_decision_summary.v1", "disposition": disposition,
        "product_id": result["subject"]["product_id"], "clinical_dimensions": scientific,
        "decision_questions": questions, "predictive_success_probability": None,
        "causal_priorities": causal_priorities(result['hypothesis_results']),
        "causal_priority_basis": "reviewed support and exact scope; not causal certainty or a success probability",
        "commercial_recommendation": "not_assessed", "automated_review_only": True,
        "review_coverage":{"outcomes":len(result['case_assessments']),
            "hypotheses":len(result['hypothesis_results']),
            "reviewed":sum(item.get('review_status')=='automated_reviewed' for item in result['case_assessments']+result['hypothesis_results']),
            "unreviewed":sum(item.get('review_status')=='unreviewed' for item in result['case_assessments']+result['hypothesis_results'])},
        "evidence_breadth":evidence_breadth(result['evidence']),
        "next_action": "review_input_contract" if preflight else
            "acquire_or_reconcile_evidence" if disposition in {"needs_evidence", "partial_review"} else
            "review_product_delta" if result["memory_update"].get("operations") else "none"}


def memory_decision(result: dict) -> dict:
    """Provide bounded decision metadata; it is not a commit or archive receipt."""
    plan = result["memory_update"]
    operations = plan.get("operations", [])
    return {"schema_version": "clinical_memory_decision.v1",
        "status": plan["status"], "candidate_present": bool(operations),
        "operation_count": len(operations), "candidate_digest": digest(operations),
        "candidate_bytes": len(canonical_bytes(operations)),
        "write_attempted": False, "commit_observed": False, "readback_verified": False,
        "history_verified": False, "journal_status": "not_attested",
        "reason": plan.get("reason"), "independent_from_report": True}


def finalize_output(result: dict, *, max_bytes: int = 4_194_304) -> dict:
    """Compact optional presentation only; never shrink the canonical evidence/delta."""
    result["decision_summary"] = decision_summary(result)
    result["memory_decision"] = memory_decision(result)
    report = render_report(result)
    result["report_markdown"] = report
    result["presentation"] = {"report_status": "included", "omitted_fields": []}
    if len(canonical_bytes(result)) > max_bytes:
        result["presentation"]["omitted_fields"].append({"field": "report_markdown",
            "bytes": len(report.encode("utf-8")), "digest": digest(report)})
        result["report_markdown"] = "Report omitted for transport; the canonical assessment is unchanged.\n"
        result["presentation"]["report_status"] = "omitted_for_transport"
    # Safe provider semantic metadata can be large. Receipts/counts and canonical
    # evidence stay; omitted optional whole metadata fields are accounted exactly.
    if len(canonical_bytes(result)) > max_bytes:
        for index, stage in enumerate(result["execution"]["stages"]):
            metadata = stage.get("semantic_metadata")
            if metadata:
                result["presentation"]["omitted_fields"].append({
                    "field": "execution.stages." + str(index) + ".semantic_metadata",
                    "bytes": len(canonical_bytes(metadata)), "digest": digest(metadata)})
                stage["semantic_metadata"] = {}
    if len(canonical_bytes(result)) > max_bytes:
        result['quality']['issues'].append({'code':'clinical_canonical_result_size_warning',
            'warning_threshold_bytes':max_bytes,'canonical_content_preserved':True,
            'transport_policy_owner':'runtime'})
        if result['quality']['status']=='completed':
            result['quality']['status']='partial'
        result['decision_summary']=decision_summary(result)
    return result


def preflight_result(request: dict, ledger: object, statistics: dict | None) -> dict:
    """Return contract-only inspection with zero Agents, Skill reads or writes."""
    prepared = request["prepared_sources"]
    result = {"schema_version": SCHEMA, "asset": ASSET_KEY + "@" + VERSION,
        "assessment_id": "preflight:" + digest(request).split(":")[1][:32],
        "request_id": request["request_id"], "analysis_mode": request["analysis_mode"],
        "as_of_date": request["as_of_date"], "subject": request["context"]["subject"],
        "source_assertions": deepcopy(request["context"]["source_assertions"]),
        "research_claims": [], "case_assessments": [], "hypothesis_results": [],
        "cohort_statistics": statistics, "evidence": ledger.rows(),
        "reason_graph": build_reason_graph(request["context"]["subject"], [], ledger.rows(),
            case_scope=request["context"].get("case_scope"), terminology=prepared["terminology"]),
        "quality": {"status": "preflight", "issues": deepcopy(prepared["issues"]) +
            ([{"code": "clinical_prepared_source_coverage_partial", "omitted_windows": len(prepared["omissions"])}]
             if prepared["omissions"] else []),
            "automated_review_only": True, "scientific_accuracy_certified": False,
            "external_truth_verified": False, "required_roles_completed": {},
            "limitations": ["Contract preflight only; no source execution or scientific review"]},
        "execution": {"stages": [], "logical_agent_calls": 0, "reference_reads": 0,
            "refinement_rounds": 0, "model_repair_calls": 0,
            "resume": {"available": False, "reason": "durable_stage_retention_not_qualified"}},
        "memory_update": {"status": "not_requested", "operations": [], "write_attempted": False},
        "persistence": {"status": "not_attested", "receipt": None},
        "prepared_sources": {key: deepcopy(value) for key, value in prepared.items() if key != "evidence"},
        "source_request_plan": source_request_plan(request, prepared)}
    return finalize_output(result)
