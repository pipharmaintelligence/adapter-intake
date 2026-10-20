"""Deterministic denominators and descriptive metrics; no model-authored tests."""
from __future__ import annotations
from copy import deepcopy
from typing import Any
if __package__:
    from .contracts_v0_1_5 import digest, identifier, iso_date, object_fields, require
else:
    from contracts_v0_1_5 import digest, identifier, iso_date, object_fields, require


def compute_statistics(cohort: Any, *, as_of_date: str) -> dict:
    """Count declared units without turning selected events into a population estimate.

    Duplicate identical units count once. Conflicting or overlapping units invalidate
    the calculation. Unknown/ongoing outcomes remain separate from known outcomes.
    """
    if cohort is None:
        return {"status": "not_run", "reason": "cohort_not_supplied", "p_value": None}
    data = object_fields(cohort, {"snapshot_ref", "unit_of_analysis", "denominator_complete",
        "selection", "metric", "window_start", "window_end", "rows"})
    identifier(data["snapshot_ref"])
    require(isinstance(data["unit_of_analysis"], str) and data["unit_of_analysis"] in {
        "trial", "product_indication", "programme", "approval", "event"}, "clinical_cohort_unit_invalid")
    require(type(data["denominator_complete"]) is bool, "clinical_cohort_denominator_invalid")
    require(isinstance(data["selection"], str) and data["selection"] in {
        "eligible_all", "failure_only", "unknown"}, "clinical_cohort_selection_invalid")
    require(isinstance(data["metric"], str) and data["metric"] in {
        "success_rate", "attribute_prevalence"}, "clinical_cohort_metric_invalid")
    require(iso_date(data["window_start"]) <= iso_date(data["window_end"]) <= as_of_date,
            "clinical_cohort_window_invalid")
    require(isinstance(data["rows"], list) and len(data["rows"]) <= 1000, "clinical_cohort_rows_invalid")
    base = {"schema_version": "clinical_cohort_statistics.v1", "snapshot_ref": data["snapshot_ref"],
        "snapshot_digest": digest(data), "unit_of_analysis": data["unit_of_analysis"],
        "metric": data["metric"], "p_value": None, "confidence_interval": None,
        "method": "descriptive_deduplicated_counts", "inference": "not_performed"}
    if not data["denominator_complete"] or data["selection"] != "eligible_all":
        return {**base, "status": "not_run", "reason": "eligible_denominator_not_established"}
    units: dict[str, dict] = {}
    duplicate_count = 0
    for original in data["rows"]:
        row = object_fields(original, {"unit_id", "group", "eligible", "observed_on", "outcome", "attribute"})
        key = identifier(row["unit_id"])
        identifier(row["group"])
        require(type(row["eligible"]) is bool, "clinical_cohort_eligibility_invalid")
        require(isinstance(row["outcome"], str) and row["outcome"] in {
            "success", "failure", "unknown", "ongoing"}, "clinical_cohort_outcome_invalid")
        require(row["attribute"] is None or type(row["attribute"]) is bool, "clinical_cohort_attribute_invalid")
        require(data["window_start"] <= iso_date(row["observed_on"]) <= data["window_end"],
                "clinical_cohort_row_outside_window")
        if key in units:
            if units[key] != row:
                return {**base, "status": "not_run", "reason": "conflicting_or_overlapping_unit_records"}
            duplicate_count += 1
        else:
            units[key] = deepcopy(row)
    groups = []
    for name in sorted({row["group"] for row in units.values()}):
        own = [r for r in units.values() if r["eligible"] and r["group"] == name]
        if data["metric"] == "success_rate":
            known = [r for r in own if r["outcome"] in {"success", "failure"}]
            numerator = sum(r["outcome"] == "success" for r in known)
        else:
            known = [r for r in own if r["attribute"] is not None]
            numerator = sum(r["attribute"] is True for r in known)
        denominator = len(known)
        groups.append({"group": name, "eligible_count": len(own), "known_count": denominator,
            "numerator": numerator, "denominator": denominator, "unknown_count": len(own) - denominator,
            "estimate": numerator / denominator if denominator else None})
    if not any(group["denominator"] for group in groups):
        return {**base, "status": "not_run", "reason": "no_known_eligible_observations",
                "groups": groups, "duplicate_rows_removed": duplicate_count}
    return {**base, "status": "descriptive", "groups": groups, "duplicate_rows_removed": duplicate_count,
            "limitations": ["No causal or population inference", "Unknown and ongoing outcomes excluded from known denominator"]}


def run_approved_test(*_: Any, **__: Any) -> dict:
    """Report nonexecution until an inferential method and cohort are reviewed."""
    return {"status": "not_run", "reason": "inferential_method_not_qualified", "p_value": None}
