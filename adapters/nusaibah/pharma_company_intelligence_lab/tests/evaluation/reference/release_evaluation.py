from __future__ import annotations

from typing import Any


class ReleaseEvaluationError(ValueError):
    """Raised when release-quality evidence is incomplete or inconsistent."""


def evaluate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute finite-set quality metrics without hiding critical failures."""

    if not cases:
        raise ReleaseEvaluationError("Evaluation cases are required.")

    material_total = material_supported = 0
    noncritical_tp = noncritical_fp = noncritical_fn = 0
    critical_expected = critical_recovered = 0
    unsupported_high_impact = 0
    complete_accounting = True

    for case in cases:
        material_total += int(case["material_claim_count"])
        material_supported += int(case["supported_material_claim_count"])
        noncritical_tp += int(case["noncritical_true_positive"])
        noncritical_fp += int(case["noncritical_false_positive"])
        noncritical_fn += int(case["noncritical_false_negative"])
        critical_expected += int(case["critical_expected"])
        critical_recovered += int(case["critical_recovered"])
        unsupported_high_impact += int(case["accepted_unsupported_high_impact"])
        complete_accounting = complete_accounting and bool(case["all_obligations_disposed"])

    def ratio(numerator: int, denominator: int) -> float | None:
        return None if denominator == 0 else numerator / denominator

    precision = ratio(noncritical_tp, noncritical_tp + noncritical_fp)
    recall = ratio(noncritical_tp, noncritical_tp + noncritical_fn)
    faithfulness = ratio(material_supported, material_total)
    critical_recall = ratio(critical_recovered, critical_expected)

    return {
        "schema_version": "review_release_evaluation.v1",
        "case_count": len(cases),
        "material_claim_count": material_total,
        "factual_faithfulness": faithfulness,
        "noncritical_precision": precision,
        "noncritical_recall": recall,
        "critical_recall": critical_recall,
        "accepted_unsupported_high_impact": unsupported_high_impact,
        "complete_accounting": complete_accounting,
    }


def release_gate(
    metrics: dict[str, Any],
    *,
    calibrated_faithfulness_min: float,
    calibrated_precision_min: float,
    calibrated_recall_min: float,
) -> dict[str, Any]:
    """Apply finite-set gates; thresholds must be externally calibrated."""

    if any(
        value is None
        for value in (
            metrics["factual_faithfulness"],
            metrics["noncritical_precision"],
            metrics["noncritical_recall"],
            metrics["critical_recall"],
        )
    ):
        raise ReleaseEvaluationError("Required quality denominator is missing.")

    blockers = {
        "unsupported_high_impact": metrics["accepted_unsupported_high_impact"] != 0,
        "critical_recall": metrics["critical_recall"] != 1.0,
        "review_accounting": not metrics["complete_accounting"],
        "factual_faithfulness": metrics["factual_faithfulness"] < calibrated_faithfulness_min,
        "noncritical_precision": metrics["noncritical_precision"] < calibrated_precision_min,
        "noncritical_recall": metrics["noncritical_recall"] < calibrated_recall_min,
    }
    return {
        "passed": not any(blockers.values()),
        "blockers": blockers,
    }
