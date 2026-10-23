"""Scoped candidates, critic coverage, contradiction and dependent invalidation."""
from __future__ import annotations
from copy import deepcopy
from typing import Any
if __package__:
    from .contracts_v0_1_10 import ContractError, REASON_CODES, identifier, identifiers, object_fields, require, text
    from .evidence_v0_1_10 import EvidenceLedger
else:
    from contracts_v0_1_10 import ContractError, REASON_CODES, identifier, identifiers, object_fields, require, text
    from evidence_v0_1_10 import EvidenceLedger

OUTCOMES = {
    "study_disposition": {"completed", "terminated", "withdrawn", "suspended", "ongoing", "unknown"},
    "primary_endpoint_result": {"met", "not_met", "mixed", "not_evaluable", "unknown"},
    "safety_assessment": {"acceptable_in_studied_scope", "signal_identified", "unacceptable", "unknown"},
    "programme_decision": {"continued", "paused", "discontinued", "unknown"},
    "regulatory_decision": {"approved", "rejected", "pending", "not_applicable", "unknown"},
}


def normalize_items(rows: list, kind: str, request: dict, ledger: EvidenceLedger) -> tuple[list, list]:
    """Isolate malformed items without granting researcher-proposed acceptance."""
    require(kind in {"outcome", "hypothesis"}, "clinical_candidate_kind_invalid")
    require(isinstance(rows, list) and len(rows) <= 32, "clinical_candidate_batch_invalid")
    result, issues, seen = [], [], set()
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("item_id"), str):
            require(row["item_id"] not in seen, "clinical_item_duplicate")
            seen.add(row["item_id"])
    seeds = {x["assertion_id"]: x for x in request["context"]["source_assertions"]}
    for index, original in enumerate(rows):
        try:
            common = {"item_id", "subject_id", "statement", "supporting_evidence_ids",
                      "contradicting_evidence_ids", "depends_on"}
            extra = {"dimension", "value", "trial_ids"} if kind == "outcome" else {
                "source_assertion_id", "reason_code", "scope", "proposed_verdict", "alternative_explanations",
                "validation_indicators", "falsification_condition", "lesson"}
            row = object_fields(original, common | extra)
            identifier(row["item_id"])
            require(row["subject_id"] == request["subject_id"], "clinical_candidate_subject_mismatch")
            text(row["statement"])
            support = ledger.refs(row["supporting_evidence_ids"])
            against = ledger.refs(row["contradicting_evidence_ids"])
            dependencies = identifiers(row["depends_on"])
            if kind == "outcome":
                require(isinstance(row["dimension"], str) and row["dimension"] in OUTCOMES and
                        isinstance(row["value"], str) and row["value"] in OUTCOMES[row["dimension"]],
                        "clinical_outcome_value_invalid")
                trials = identifiers(row["trial_ids"], maximum=32)
                allowed_trials = set(request["context"]["subject"]["trial_ids"])
                require(set(trials) <= allowed_trials, "clinical_outcome_trial_scope_mismatch")
                evidence_trials = {t for ref in support for t in ledger.items[ref]["trial_ids"]}
                require(row["value"] in {"unknown", "not_evaluable"} or not trials or
                        set(trials) <= evidence_trials, "clinical_outcome_trial_evidence_missing")
            else:
                source_id = row["source_assertion_id"]
                require(source_id is None or (isinstance(source_id, str) and source_id in seeds),
                        "clinical_seed_unknown")
                require(isinstance(row["reason_code"], str) and row["reason_code"] in REASON_CODES,
                        "clinical_reason_code_invalid")
                require(isinstance(row["proposed_verdict"], str) and row["proposed_verdict"] in {
                    "untested", "supported", "refuted", "inconclusive"}, "clinical_hypothesis_verdict_invalid")
                text(row["scope"], maximum=2000)
                text(row["falsification_condition"], maximum=2000)
                for name in ("alternative_explanations", "validation_indicators"):
                    require(isinstance(row[name], list) and 1 <= len(row[name]) <= 8,
                            "clinical_hypothesis_plan_invalid")
                    for value in row[name]:
                        text(value, maximum=2000)
                require(row["lesson"] is None or isinstance(row["lesson"], str), "clinical_lesson_invalid")
                if row["lesson"] is not None:
                    text(row["lesson"], maximum=2000)
            normalized = {**deepcopy(row), "kind": kind, "supporting_evidence_ids": support,
                "contradicting_evidence_ids": against, "depends_on": dependencies,
                "review_status": "unreviewed", "review_reason": None, "accepted": False}
            if kind == "hypothesis":
                normalized.update(source_assertion=deepcopy(seeds.get(row["source_assertion_id"])),
                    verdict="untested", causal_status="hypothesis", memory_eligibility=False,
                    test_result=None, external_truth_verified=False)
            result.append(normalized)
        except ContractError as exc:
            if exc.code in {"clinical_candidate_subject_mismatch", "clinical_outcome_trial_scope_mismatch"}:
                raise
            issues.append({"kind": kind, "item_index": index, "code": exc.code})
    return result, issues


def validate_dependencies(items: list[dict]) -> None:
    """Require known, acyclic item references, including across candidate kinds."""
    table = {item["item_id"]: item for item in items}
    require(len(table) == len(items), "clinical_item_duplicate")
    active, done = set(), set()
    def visit(key: str) -> None:
        require(key in table, "clinical_dependency_unknown")
        require(key not in active, "clinical_dependency_cycle")
        if key in done:
            return
        active.add(key)
        for dependency in table[key]["depends_on"]:
            visit(dependency)
        active.remove(key)
        done.add(key)
    for key in table:
        visit(key)


def withhold(item: dict, reason: str) -> None:
    """Demote a candidate without deleting the scientist's original hypothesis."""
    item.update(accepted=False, review_reason=reason)
    if item["kind"] == "hypothesis":
        item.update(verdict="inconclusive", memory_eligibility=False)


def enforce_consistency(items: list[dict]) -> list[dict]:
    """Reject conflicting canonical outcomes and invalidate dependent acceptance."""
    issues = []
    outcomes: dict[tuple, list[dict]] = {}
    for item in items:
        if item["kind"] == "outcome" and item["accepted"]:
            for trial in item["trial_ids"] or [None]:
                outcomes.setdefault((item["dimension"], trial), []).append(item)
    for group in outcomes.values():
        known=[item for item in group if item['value'] != 'unknown']
        if known and len({item['value'] for item in known})==1:
            # Unknown is a local absence of a conclusion, not contrary evidence.
            # Keep the original candidate but reconcile its accepted projection.
            for item in group:
                if item['value'] == 'unknown':
                    withhold(item,'Resolved by reviewed outcome '+known[0]['item_id']+' for the same dimension and trial scope')
            group=known
        if len({item["value"] for item in group}) > 1:
            for item in group:
                withhold(item, "Conflicting outcomes for the same dimension and trial scope")
                issues.append({"code": "clinical_outcome_conflict", "item_id": item["item_id"]})
    changed = True
    while changed:
        changed = False
        accepted_ids = {x["item_id"] for x in items if x["accepted"]}
        for item in items:
            if item["accepted"] and not set(item["depends_on"]) <= accepted_ids:
                withhold(item, "Dependent premise was not accepted")
                issues.append({"code": "clinical_dependency_withheld", "item_id": item["item_id"]})
                changed = True
    return issues


def review_items(items: list[dict], verdicts: Any, ledger: EvidenceLedger, *, assigned_ids=None) -> tuple[list[dict], list[dict]]:
    """Accept only explicitly covered items; absence of a verdict is not completion."""
    reviewed = deepcopy(items)
    validate_dependencies(reviewed)
    assigned = {item["item_id"] for item in reviewed} if assigned_ids is None else set(assigned_ids)
    require(assigned <= {item["item_id"] for item in reviewed}, "clinical_critic_identity_invalid")
    if verdicts is None:
        return reviewed, [{"code": "clinical_critic_unavailable"}]
    require(isinstance(verdicts, list), "clinical_critic_items_invalid")
    mapped: dict[str, dict] = {}
    for row in verdicts:
        object_fields(row, {"item_id", "verdict", "rationale", "supporting_evidence_ids",
                           "contradicting_evidence_ids", "scope_preserved"})
        require(isinstance(row["item_id"], str) and row["item_id"] in assigned and row["item_id"] not in mapped,
                "clinical_critic_identity_invalid")
        require(isinstance(row["verdict"], str) and row["verdict"] in {
            "accepted", "needs_evidence", "contradicted", "invalid"}, "clinical_critic_verdict_invalid")
        text(row["rationale"], maximum=4000)
        require(type(row["scope_preserved"]) is bool, "clinical_critic_scope_invalid")
        mapped[row["item_id"]] = row
    issues = []
    for item in reviewed:
        if item["item_id"] not in assigned:
            continue
        decision = mapped.get(item["item_id"])
        if decision is None:
            issues.append({"code": "clinical_critic_item_not_reviewed", "item_id": item["item_id"]})
            continue
        try:
            support = ledger.refs(decision["supporting_evidence_ids"])
            against = ledger.refs(decision["contradicting_evidence_ids"])
            require(set(support) <= set(item["supporting_evidence_ids"]) and
                    set(against) <= set(item["contradicting_evidence_ids"]), "clinical_critic_evidence_mismatch")
            accepted = decision["verdict"] == "accepted" and decision["scope_preserved"] and not item.get("unresolved_dependency_ids")
            if accepted:
                if item["kind"] == "outcome" and item["value"] not in {"unknown", "not_evaluable"}:
                    ledger.assert_usable(support, outcome_dimension=item["dimension"])
                proposed = item.get("proposed_verdict")
                if proposed in {"supported", "refuted"}:
                    ledger.assert_usable(support if proposed == "supported" else against)
            item.update(review_status="automated_reviewed", review_reason=decision["rationale"], accepted=accepted)
            if accepted:
                # Only the critic-confirmed source subset becomes a reviewed graph edge.
                item["supporting_evidence_ids"] = support
                item["contradicting_evidence_ids"] = against
            if item["kind"] == "hypothesis":
                item["verdict"] = item["proposed_verdict"] if accepted else "inconclusive"
                item["memory_eligibility"] = accepted and item["verdict"] == "supported" and bool(item["lesson"])
        except ContractError as exc:
            # A completed review followed by the deterministic evidence gate is
            # a terminal inconclusive disposition, never a certified conclusion.
            if exc.code == 'clinical_definitive_evidence_missing':
                item.update(accepted=False, review_status='automated_reviewed', review_reason=exc.code)
                if item['kind'] == 'hypothesis':
                    item.update(verdict='inconclusive', memory_eligibility=False)
            issues.append({"code": exc.code, "item_id": item["item_id"]})
    issues.extend(enforce_consistency(reviewed))
    return reviewed, issues
