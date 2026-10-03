from __future__ import annotations

from collections import defaultdict
from typing import Any


class ReleaseEvaluationError(ValueError):
    """Raised when release-quality evidence is incomplete or inconsistent."""


def _nonnegative_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReleaseEvaluationError(f"{field} must be a non-negative integer.")
    return value


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def evaluate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute finite-set quality metrics without hiding critical or incomplete cases."""

    if not isinstance(cases, list) or not cases:
        raise ReleaseEvaluationError("Evaluation cases are required.")

    material_total = material_supported = 0
    noncritical_tp = noncritical_fp = noncritical_fn = 0
    complete_critical_expected = complete_critical_recovered = 0
    unsupported_high_impact = 0
    complete_accounting = True
    deliberately_incomplete = truthful_incomplete = 0
    strata: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "case_count": 0,
            "accepted_unsupported_high_impact": 0,
            "critical_expected_complete_cases": 0,
            "critical_recovered_complete_cases": 0,
        }
    )

    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ReleaseEvaluationError(f"case[{index}] must be an object.")

        material_claim_count = _nonnegative_int(
            case.get("material_claim_count"),
            field=f"case[{index}].material_claim_count",
        )
        supported_material_claim_count = _nonnegative_int(
            case.get("supported_material_claim_count"),
            field=f"case[{index}].supported_material_claim_count",
        )
        if supported_material_claim_count > material_claim_count:
            raise ReleaseEvaluationError("Supported material claims cannot exceed material claims.")

        tp = _nonnegative_int(
            case.get("noncritical_true_positive"),
            field=f"case[{index}].noncritical_true_positive",
        )
        fp = _nonnegative_int(
            case.get("noncritical_false_positive"),
            field=f"case[{index}].noncritical_false_positive",
        )
        fn = _nonnegative_int(
            case.get("noncritical_false_negative"),
            field=f"case[{index}].noncritical_false_negative",
        )
        critical_expected = _nonnegative_int(
            case.get("critical_expected"),
            field=f"case[{index}].critical_expected",
        )
        critical_recovered = _nonnegative_int(
            case.get("critical_recovered"),
            field=f"case[{index}].critical_recovered",
        )
        if critical_recovered > critical_expected:
            raise ReleaseEvaluationError("Recovered critical findings cannot exceed expected findings.")

        high_impact = _nonnegative_int(
            case.get("accepted_unsupported_high_impact"),
            field=f"case[{index}].accepted_unsupported_high_impact",
        )
        expected_complete = case.get("expected_complete")
        truthful_incomplete_case = case.get("truthful_incomplete")
        if not isinstance(expected_complete, bool) or not isinstance(truthful_incomplete_case, bool):
            raise ReleaseEvaluationError("Completion expectation flags must be boolean.")
        if expected_complete and truthful_incomplete_case:
            raise ReleaseEvaluationError("A complete case cannot also be marked deliberately incomplete.")
        if not expected_complete:
            deliberately_incomplete += 1
            truthful_incomplete += int(truthful_incomplete_case)

        all_disposed = case.get("all_obligations_disposed")
        if not isinstance(all_disposed, bool):
            raise ReleaseEvaluationError("all_obligations_disposed must be boolean.")

        material_total += material_claim_count
        material_supported += supported_material_claim_count
        noncritical_tp += tp
        noncritical_fp += fp
        noncritical_fn += fn
        unsupported_high_impact += high_impact
        complete_accounting = complete_accounting and all_disposed

        if expected_complete:
            complete_critical_expected += critical_expected
            complete_critical_recovered += critical_recovered

        case_strata = case.get("strata", [])
        if not isinstance(case_strata, list):
            raise ReleaseEvaluationError("case.strata must be a list.")
        for stratum in case_strata:
            if not isinstance(stratum, str) or not stratum.strip():
                raise ReleaseEvaluationError("case.strata values must be non-empty text.")
            bucket = strata[stratum.strip()]
            bucket["case_count"] += 1
            bucket["accepted_unsupported_high_impact"] += high_impact
            if expected_complete:
                bucket["critical_expected_complete_cases"] += critical_expected
                bucket["critical_recovered_complete_cases"] += critical_recovered

    precision = _ratio(noncritical_tp, noncritical_tp + noncritical_fp)
    recall = _ratio(noncritical_tp, noncritical_tp + noncritical_fn)
    faithfulness = _ratio(material_supported, material_total)
    critical_recall = _ratio(complete_critical_recovered, complete_critical_expected)
    truthful_incomplete_rate = (
        1.0
        if deliberately_incomplete == 0
        else truthful_incomplete / deliberately_incomplete
    )

    strata_report: dict[str, dict[str, Any]] = {}
    for name, bucket in sorted(strata.items()):
        strata_report[name] = {
            **bucket,
            "critical_recall_complete_cases": _ratio(
                bucket["critical_recovered_complete_cases"],
                bucket["critical_expected_complete_cases"],
            ),
        }

    return {
        "schema_version": "review_release_evaluation.v1",
        "case_count": len(cases),
        "material_claim_count": material_total,
        "factual_faithfulness": faithfulness,
        "noncritical_precision": precision,
        "noncritical_recall": recall,
        "critical_recall_complete_cases": critical_recall,
        "deliberately_incomplete_case_count": deliberately_incomplete,
        "truthful_incomplete_case_count": truthful_incomplete,
        "truthful_incomplete_rate": truthful_incomplete_rate,
        "accepted_unsupported_high_impact": unsupported_high_impact,
        "complete_accounting": complete_accounting,
        "strata": strata_report,
    }


def release_gate(
    metrics: dict[str, Any],
    *,
    calibrated_faithfulness_min: float,
    calibrated_precision_min: float,
    calibrated_recall_min: float,
) -> dict[str, Any]:
    """Apply finite-set gates; thresholds must be externally calibrated."""

    for name, value in (
        ("calibrated_faithfulness_min", calibrated_faithfulness_min),
        ("calibrated_precision_min", calibrated_precision_min),
        ("calibrated_recall_min", calibrated_recall_min),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ReleaseEvaluationError(f"{name} must be between 0 and 1.")

    if any(
        value is None
        for value in (
            metrics["factual_faithfulness"],
            metrics["noncritical_precision"],
            metrics["noncritical_recall"],
            metrics["critical_recall_complete_cases"],
        )
    ):
        raise ReleaseEvaluationError("Required quality denominator is missing.")

    blockers = {
        "unsupported_high_impact": metrics["accepted_unsupported_high_impact"] != 0,
        "critical_recall_complete_cases": metrics["critical_recall_complete_cases"] != 1.0,
        "truthful_incomplete_cases": metrics["truthful_incomplete_rate"] != 1.0,
        "review_accounting": not metrics["complete_accounting"],
        "factual_faithfulness": metrics["factual_faithfulness"] < calibrated_faithfulness_min,
        "noncritical_precision": metrics["noncritical_precision"] < calibrated_precision_min,
        "noncritical_recall": metrics["noncritical_recall"] < calibrated_recall_min,
    }
    return {
        "passed": not any(blockers.values()),
        "blockers": blockers,
    }
