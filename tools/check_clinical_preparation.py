"""Offline draft-contract checks, not an admitted adapter or authority verifier."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "docs" / "clinical-intelligence-preparation"
SCHEMAS = {
    path.name.removesuffix(".schema.json"): json.loads(path.read_text(encoding="utf-8"))
    for path in (DESIGN / "schemas").glob("*.schema.json")
}
REGISTRY = Registry().with_resources(
    (schema["$id"], Resource.from_contents(schema)) for schema in SCHEMAS.values()
)
PRODUCT_COUNTS = {
    "accepted": "product_with_accepted_assessment_count",
    "partial": "product_with_partial_assessment_count",
    "missing": "missing_product_count",
    "blocked": "blocked_product_count",
    "outdated": "outdated_product_count",
}
COMPLETENESS = ("membership_complete", "selection_complete", "execution_complete",
                "evidence_complete", "scientific_review_complete")


class DraftContractError(ValueError):
    """Reports a fixed code, never echoes the submitted payload."""


def require(ok: bool, code: str) -> None:
    if not ok:
        raise DraftContractError(code)


def keyed(rows: list[dict], key: str) -> dict:
    result = {row[key]: row for row in rows}
    require(len(result) == len(rows), "duplicate_semantic_identity")
    return result


def check_scope(data: dict) -> None:
    membership = data["membership"]
    members = keyed(membership["eligible_products"], "product_id")
    selected = keyed(data["selected_products"], "product_id")
    class_id = data["pharmacological_class_id"]
    require(all(row["pharmacological_class_id"] == class_id for row in members.values()), "cross_class_membership")
    require(all(members.get(key) == row for key, row in selected.items()), "selected_member_identity_mismatch")
    require(not membership["complete"] or not membership["unresolved"], "complete_membership_has_unresolved_identity")
    excluded = keyed(membership["excluded"], "product_id")
    require(not set(excluded).intersection(members), "eligible_excluded_overlap")
    if data["scope_mode"] == "all_known_in_snapshot":
        require(set(selected) == set(members), "all_known_selection_incomplete")
    cases = keyed(data["selected_cases"], "case_ref")
    require(all(row["product_id"] in selected for row in cases.values()), "case_product_outside_selection")
    if "legacy_class_mapping" in data:
        require(data["legacy_class_mapping"]["pharmacological_class_id"] == class_id, "legacy_mapping_class_mismatch")


def check_coverage(data: dict) -> None:
    products = keyed(data["product_dispositions"], "product_id")
    cases = keyed(data["case_dispositions"], "case_ref")
    require(data["selected_product_count"] == len(products), "selected_product_count_mismatch")
    require(data["assessment_case_count"] == len(cases), "case_count_mismatch")
    pcounts = Counter(row["state"] for row in products.values())
    ccounts = Counter(row["state"] for row in cases.values())
    require(all(data[field] == pcounts[state] for state, field in PRODUCT_COUNTS.items()), "product_denominator_mismatch")
    require(all(data[state + "_case_count"] == ccounts[state]
                for state in ("completed", "partial", "deferred", "missing", "blocked", "outdated")), "case_denominator_mismatch")
    require(data["selected_product_count"] <= data["eligible_product_count"], "selection_exceeds_eligible")
    total = data["inventory_member_count"]
    require(total is None or total >= data["eligible_product_count"], "inventory_denominator_mismatch")
    require(data["membership_complete"] is not True or total is not None, "complete_membership_denominator_unknown")
    sources = keyed(data["evidence_coverage_by_source"], "source_kind")
    if data["evidence_complete"] is True:
        require(all(sources.get(kind, {}).get("complete") is True for kind in ("clinicaltrials", "pubmed")),
                "required_source_coverage_incomplete")
    if data["scientific_review_complete"] is True:
        require(data["evidence_complete"] is True and data["assessment_case_count"] > 0
                and data["completed_case_count"] == data["assessment_case_count"]
                and data["product_with_accepted_assessment_count"] == data["selected_product_count"],
                "scientific_coverage_incomplete")


def check_review(data: dict) -> None:
    scope, coverage = data["class_scope"], data["coverage"]
    check_scope(scope)
    check_coverage(coverage)
    selected = keyed(scope["selected_products"], "product_id")
    cases = keyed(scope["selected_cases"], "case_ref")
    dispositions = keyed(coverage["case_dispositions"], "case_ref")
    require({row["product_id"] for row in coverage["product_dispositions"]} == set(selected), "product_coverage_scope_mismatch")
    require(set(dispositions) == set(cases), "case_coverage_scope_mismatch")
    require(coverage["eligible_product_count"] == len(scope["membership"]["eligible_products"]), "eligible_count_mismatch")
    require(coverage["membership_complete"] == scope["membership"]["complete"], "membership_completeness_mismatch")
    for row in coverage["product_dispositions"]:
        if row["state"] == "accepted":
            case_refs = [key for key, case in cases.items() if case["product_id"] == row["product_id"]]
            require(bool(case_refs) and all(dispositions[key]["state"] == "completed" for key in case_refs),
                    "accepted_product_has_incomplete_cases")
    if coverage["scientific_review_complete"] is True:
        require(scope["case_inventory_complete"] is True, "case_inventory_incomplete")
        critic = data["independent_critic"]
        require(critic["status"] == "passed" and critic["review_ref"] is not None
                and not critic["unresolved_finding_refs"], "scientific_review_critic_incomplete")
    assessments = keyed(data["assessment_refs"], "case_ref")
    for case_ref, assessment in assessments.items():
        require(case_ref in cases and assessment["product_id"] == cases[case_ref]["product_id"],
                "assessment_reference_outside_case_scope")
    for case_ref, disposition in dispositions.items():
        if disposition["state"] == "completed":
            require(assessments.get(case_ref, {}).get("quality") == "accepted", "completed_case_retained_assessment_missing")
    generalized = coverage["class_generalization_supported"]
    if generalized:
        require(scope["scope_mode"] == "all_known_in_snapshot" and
                all(coverage[key] is True for key in COMPLETENESS), "class_generalization_not_eligible")
    for finding in data["findings"]:
        require(set(finding["product_ids"]).issubset(selected), "finding_outside_scope")
        require(not (finding["scope"] == "class" and finding["interpretation"] == "supported") or generalized,
                "unsupported_class_finding")
    for stratum in data["strata"]:
        require(set(stratum["product_ids"]).issubset(selected), "stratum_outside_scope")


def validate(kind: str, data: dict) -> None:
    """Shape and selected cross-field invariants only; establishes no authority."""
    schema = SCHEMAS[kind]
    validator = Draft202012Validator(schema, registry=REGISTRY, format_checker=FormatChecker())
    require(not any(validator.iter_errors(data)), "draft_schema_invalid")
    if kind == "class-scope":
        check_scope(data)
    elif kind == "coverage":
        check_coverage(data)
    elif kind == "class-review":
        check_review(data)
    elif kind == "assessment-handoff":
        require(data["subject"]["product_id"] == data["case"]["product_id"], "assessment_case_identity_mismatch")
        require(data["quality"] != "accepted" or not data["unresolved_reason_codes"], "accepted_assessment_has_unresolved_gaps")
    elif kind == "gateway-request" and data["operation"] == "request_assessment":
        classes = data.get("pharmacological_class_ids", [])
        if classes:
            require(all(row["pharmacological_class_id"] in classes for row in data.get("supplied_identity_context", [])),
                    "supplied_context_cross_class")
            require(all(row["pharmacological_class_id"] in classes for row in data.get("legacy_class_mappings", [])),
                    "legacy_mapping_class_mismatch")
    elif kind == "gateway-response":
        require(len(json.dumps(data, ensure_ascii=False).encode("utf-8")) <= 32768, "public_projection_too_large")
        coverage = data["coverage"]
        if coverage is not None and coverage["class_generalization_supported"]:
            require(data["scope_mode"] == "all_known_in_snapshot" and all(coverage[key] is True for key in COMPLETENESS)
                    and coverage["selected_product_count"] > 0
                    and coverage["selected_product_count"] == coverage["product_with_accepted_assessment_count"],
                    "public_generalization_not_eligible")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=sorted(SCHEMAS))
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    validate(args.kind, json.loads(args.input.read_text(encoding="utf-8")))
    print("Draft contract valid; authority, science and runtime readiness not established.")


if __name__ == "__main__":
    main()
