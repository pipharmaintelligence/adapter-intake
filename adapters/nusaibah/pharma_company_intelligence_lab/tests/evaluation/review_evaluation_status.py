from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
SUITE_PATH = HERE / "review_evaluation_suite.v1.json"
TAXONOMY_PATH = HERE / "review_criticality_taxonomy.v1.json"


def source_digest(case: dict[str, Any]) -> str:
    """Return the canonical SHA-256 for a frozen synthetic source fixture."""

    canonical = json.dumps(
        case["source_units"],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _valid_calibrated_thresholds(policy: dict[str, Any]) -> bool:
    """Return True only when calibration is recorded with bounded numeric values."""

    if policy.get("status") != "calibrated":
        return False
    owner = str(policy.get("calibration", {}).get("assigned_domain_owner") or "").strip()
    note = str(policy.get("calibration", {}).get("decision_note") or "").strip()
    if not owner or not note:
        return False

    calibrated = policy.get("calibrated_thresholds")
    if not isinstance(calibrated, dict):
        return False
    required = (
        "factual_faithfulness_min",
        "noncritical_precision_min",
        "noncritical_recall_min",
    )
    for field in required:
        value = calibrated.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            return False
    return True


def evaluate_suite(
    suite: dict[str, Any],
    taxonomy: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate whether WP1 has the evidence required to unblock WP2."""

    cases = suite["cases"]
    pending = []
    missing_primary_reviewer = []
    invalid_frozen_digest = []
    disagreements_without_second_review = []
    invalid_completion_expectations = []

    for case in cases:
        adjudication = case["adjudication"]
        identity = case["source_identity"]

        expected_complete = case.get("candidate_expected_complete")
        expectation_reason = str(case.get("completion_expectation_reason") or "").strip()
        if not isinstance(expected_complete, bool) or not expectation_reason:
            invalid_completion_expectations.append(case["case_id"])

        if adjudication["status"] != "adjudicated":
            pending.append(case["case_id"])
            continue

        if not str(adjudication.get("primary_reviewer") or "").strip():
            missing_primary_reviewer.append(case["case_id"])

        if identity["digest_status"] != "frozen":
            invalid_frozen_digest.append(case["case_id"])
        elif identity["content_sha256"] != source_digest(case):
            invalid_frozen_digest.append(case["case_id"])

        if adjudication["disagreement"] and not str(
            adjudication.get("secondary_reviewer") or ""
        ).strip():
            disagreements_without_second_review.append(case["case_id"])

    suite_owner = str(
        suite.get("adjudication_policy", {}).get("assigned_domain_reviewer") or ""
    ).strip()
    taxonomy_owner = str(
        taxonomy.get("adjudication", {}).get("assigned_domain_reviewer") or ""
    ).strip()
    threshold_policy = suite.get("quality_threshold_policy")
    threshold_calibrated = (
        isinstance(threshold_policy, dict)
        and _valid_calibrated_thresholds(threshold_policy)
    )

    blockers = {
        "suite_not_adjudicated": suite.get("status") != "adjudicated",
        "taxonomy_not_adjudicated": taxonomy.get("status") != "adjudicated",
        "domain_reviewer_unassigned": not suite_owner or not taxonomy_owner,
        "pending_cases": bool(pending),
        "missing_primary_reviewer": bool(missing_primary_reviewer),
        "invalid_frozen_digest": bool(invalid_frozen_digest),
        "disagreement_without_second_review": bool(
            disagreements_without_second_review
        ),
        "completion_expectations_incomplete": bool(invalid_completion_expectations),
        "quality_thresholds_not_calibrated": not threshold_calibrated,
    }
    ready = not any(blockers.values())

    return {
        "schema_version": "pharma_review_evaluation_status.v1",
        "safe": True,
        "values_included": False,
        "suite_id": suite["suite_id"],
        "suite_status": suite["status"],
        "taxonomy_version": taxonomy["schema_version"],
        "taxonomy_status": taxonomy["status"],
        "case_count": len(cases),
        "development_count": sum(case["split"] == "development" for case in cases),
        "held_out_count": sum(case["split"] == "held_out" for case in cases),
        "candidate_complete_count": sum(
            case.get("candidate_expected_complete") is True for case in cases
        ),
        "candidate_incomplete_count": sum(
            case.get("candidate_expected_complete") is False for case in cases
        ),
        "adjudicated_count": sum(
            case["adjudication"]["status"] == "adjudicated" for case in cases
        ),
        "pending_domain_review_count": len(pending),
        "missing_primary_reviewer_count": len(missing_primary_reviewer),
        "invalid_frozen_digest_count": len(invalid_frozen_digest),
        "disagreement_without_second_review_count": len(
            disagreements_without_second_review
        ),
        "invalid_completion_expectation_count": len(invalid_completion_expectations),
        "domain_reviewer_assigned": bool(suite_owner and taxonomy_owner),
        "quality_thresholds_calibrated": threshold_calibrated,
        "blockers": blockers,
        "wp1_contract_ready": ready,
        "wp2_unblocked": ready,
    }


def evaluation_status() -> dict[str, Any]:
    """Return a value-safe WP1 readiness report without source text."""

    suite = json.loads(SUITE_PATH.read_text(encoding="utf-8"))
    taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    return evaluate_suite(suite, taxonomy)


def main() -> int:
    report = evaluation_status()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
