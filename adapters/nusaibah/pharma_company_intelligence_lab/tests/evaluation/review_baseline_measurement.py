from __future__ import annotations

from typing import Any

from review_adjudication import adjudication_input_digest
from reference.release_evaluation import ReleaseEvaluationError, evaluate_cases, release_gate


class BaselineMeasurementError(ValueError):
    """Raised when a WP1 baseline measurement record is incomplete or incompatible."""


BASELINE_MEASUREMENT_SCHEMA = "pharma_review_baseline_measurement.v1"
BASELINE_ASSET_KEY = "nusaibah.pharma_company_intelligence_lab"
BASELINE_ASSET_VERSION = "0.1.12"
BASELINE_RUNTIME_VERSION = "0.1.97"
BASELINE_INTAKE_COMMIT = "21cc6b39492cbd3c090de537a2ee27c599f0f0ec"

OBSERVATION_STATES = frozenset({"measured", "not_executable"})
NOT_EXECUTABLE_REASONS = frozenset(
    {
        "baseline_input_contract_incompatible",
        "document_review_input_contract_absent",
        "live_company_selector_absent_from_fixture",
        "runtime_evidence_unavailable",
    }
)


def assess_pinned_baseline_compatibility(
    suite: dict[str, Any],
    asset_version: dict[str, Any],
) -> dict[str, Any]:
    """Describe whether the exact adjudicated fixtures can enter live 0.1.12 unchanged.

    This checks only the pinned baseline input surface. It does not infer future
    evaluation or document-review capability from test/reference code.
    """

    if not isinstance(suite, dict) or not isinstance(asset_version, dict):
        raise BaselineMeasurementError("suite and asset_version must be objects.")

    inputs = asset_version.get("inputs")
    if not isinstance(inputs, dict):
        raise BaselineMeasurementError("Baseline asset inputs are missing.")

    companies = inputs.get("companies")
    variables = inputs.get("variables")
    pinned_shape = (
        isinstance(companies, dict)
        and companies.get("required") is True
        and companies.get("source") == "binding"
        and companies.get("shape") == "object"
        and isinstance(variables, dict)
        and variables.get("required") is True
        and variables.get("source") == "direct"
        and variables.get("shape") == "object"
    )

    cases = suite.get("cases")
    if not isinstance(cases, list) or not cases:
        raise BaselineMeasurementError("Evaluation suite cases are required.")

    case_reports: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise BaselineMeasurementError("Evaluation case must be an object.")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise BaselineMeasurementError("Evaluation case_id is required.")

        source_units = case.get("source_units")
        has_fixture_sources = isinstance(source_units, list) and bool(source_units)
        has_live_company_selector = (
            type(case.get("company_id")) is int and case["company_id"] > 0
        )
        mode = case.get("mode")
        reasons: list[str] = []

        if not pinned_shape:
            reasons.append("baseline_input_contract_incompatible")
        if has_fixture_sources and not has_live_company_selector:
            reasons.append("live_company_selector_absent_from_fixture")
        if mode == "document_review":
            reasons.append("document_review_input_contract_absent")

        case_reports.append(
            {
                "case_id": case_id,
                "mode": mode,
                "direct_execution_compatible": not reasons,
                "reason_codes": reasons,
            }
        )

    compatible_count = sum(item["direct_execution_compatible"] for item in case_reports)
    return {
        "schema_version": "pharma_review_baseline_compatibility.v1",
        "baseline_asset_key": BASELINE_ASSET_KEY,
        "baseline_asset_version": BASELINE_ASSET_VERSION,
        "case_count": len(case_reports),
        "compatible_case_count": compatible_count,
        "incompatible_case_count": len(case_reports) - compatible_count,
        "direct_fixture_execution_supported": compatible_count == len(case_reports),
        "cases": case_reports,
    }


def build_measurement_template(suite: dict[str, Any]) -> dict[str, Any]:
    """Build an exact-suite-bound observation record without inventing measurements."""

    cases = suite.get("cases")
    if not isinstance(cases, list) or not cases:
        raise BaselineMeasurementError("Evaluation suite cases are required.")

    return {
        "schema_version": BASELINE_MEASUREMENT_SCHEMA,
        "suite_id": suite.get("suite_id"),
        "suite_input_digest": adjudication_input_digest(suite),
        "baseline": {
            "asset_key": BASELINE_ASSET_KEY,
            "asset_version": BASELINE_ASSET_VERSION,
            "runtime_version": BASELINE_RUNTIME_VERSION,
            "intake_commit": BASELINE_INTAKE_COMMIT,
        },
        "usage": {
            "execution_seconds": None,
            "source_tokens": None,
            "input_characters": None,
            "answer_tokens": None,
            "thinking_tokens": None,
            "provider_reported_cost": None,
        },
        "cases": [
            {
                "case_id": case["case_id"],
                "status": None,
                "run_id": None,
                "reason_code": None,
                "material_claim_count": None,
                "supported_material_claim_count": None,
                "noncritical_true_positive": None,
                "noncritical_false_positive": None,
                "noncritical_false_negative": None,
                "critical_expected": None,
                "critical_recovered": None,
                "accepted_unsupported_high_impact": None,
                "expected_complete": case["candidate_expected_complete"],
                "truthful_incomplete": None,
                "all_obligations_disposed": None,
                "wrong_company_join_count": None,
                "unauthorized_write_count": None,
                "cap_overrun_count": None,
                "false_complete_count": None,
                "strata": list(case["strata"]),
            }
            for case in cases
        ],
    }


def _nonnegative_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BaselineMeasurementError(f"{field} must be a non-negative integer.")
    return value


def evaluate_baseline_measurement(
    suite: dict[str, Any],
    measurement: dict[str, Any],
) -> dict[str, Any]:
    """Validate observations and compute quality only when all cases are measured."""

    if measurement.get("schema_version") != BASELINE_MEASUREMENT_SCHEMA:
        raise BaselineMeasurementError("Unsupported baseline measurement schema.")
    if measurement.get("suite_id") != suite.get("suite_id"):
        raise BaselineMeasurementError("Measurement suite identity mismatch.")
    if measurement.get("suite_input_digest") != adjudication_input_digest(suite):
        raise BaselineMeasurementError(
            "Measurement does not match the exact adjudicated suite content."
        )

    baseline = measurement.get("baseline")
    expected_baseline = {
        "asset_key": BASELINE_ASSET_KEY,
        "asset_version": BASELINE_ASSET_VERSION,
        "runtime_version": BASELINE_RUNTIME_VERSION,
        "intake_commit": BASELINE_INTAKE_COMMIT,
    }
    if baseline != expected_baseline:
        raise BaselineMeasurementError("Measurement baseline identity mismatch.")

    observations = measurement.get("cases")
    if not isinstance(observations, list):
        raise BaselineMeasurementError("Measurement cases must be a list.")

    expected_cases = {case["case_id"]: case for case in suite["cases"]}
    observed_by_id: dict[str, dict[str, Any]] = {}
    for index, observation in enumerate(observations):
        if not isinstance(observation, dict):
            raise BaselineMeasurementError(f"cases[{index}] must be an object.")
        case_id = observation.get("case_id")
        if case_id not in expected_cases:
            raise BaselineMeasurementError("Measurement contains an unknown case.")
        if case_id in observed_by_id:
            raise BaselineMeasurementError("Measurement contains duplicate case IDs.")
        observed_by_id[case_id] = observation

    if set(observed_by_id) != set(expected_cases):
        raise BaselineMeasurementError(
            "Measurement must account for every adjudicated case exactly once."
        )

    metric_cases: list[dict[str, Any]] = []
    not_executable: list[dict[str, str]] = []
    control_failures = {
        "wrong_company_join_count": 0,
        "unauthorized_write_count": 0,
        "cap_overrun_count": 0,
        "false_complete_count": 0,
    }

    for case_id, expected_case in expected_cases.items():
        observation = observed_by_id[case_id]
        status = observation.get("status")
        if status not in OBSERVATION_STATES:
            raise BaselineMeasurementError(
                f"{case_id}.status must be measured or not_executable."
            )

        if observation.get("expected_complete") is not expected_case.get(
            "candidate_expected_complete"
        ):
            raise BaselineMeasurementError(
                f"{case_id}.expected_complete does not match adjudicated truth."
            )
        if observation.get("strata") != expected_case.get("strata"):
            raise BaselineMeasurementError(
                f"{case_id}.strata does not match adjudicated truth."
            )

        if status == "not_executable":
            reason = observation.get("reason_code")
            if reason not in NOT_EXECUTABLE_REASONS:
                raise BaselineMeasurementError(
                    f"{case_id}.reason_code is not an approved bounded reason."
                )
            not_executable.append({"case_id": case_id, "reason_code": reason})
            continue

        run_id = observation.get("run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            raise BaselineMeasurementError(f"{case_id}.run_id is required.")

        for field in control_failures:
            control_failures[field] += _nonnegative_int(
                observation.get(field),
                field=f"{case_id}.{field}",
            )

        metric_cases.append(
            {
                "material_claim_count": _nonnegative_int(
                    observation.get("material_claim_count"),
                    field=f"{case_id}.material_claim_count",
                ),
                "supported_material_claim_count": _nonnegative_int(
                    observation.get("supported_material_claim_count"),
                    field=f"{case_id}.supported_material_claim_count",
                ),
                "noncritical_true_positive": _nonnegative_int(
                    observation.get("noncritical_true_positive"),
                    field=f"{case_id}.noncritical_true_positive",
                ),
                "noncritical_false_positive": _nonnegative_int(
                    observation.get("noncritical_false_positive"),
                    field=f"{case_id}.noncritical_false_positive",
                ),
                "noncritical_false_negative": _nonnegative_int(
                    observation.get("noncritical_false_negative"),
                    field=f"{case_id}.noncritical_false_negative",
                ),
                "critical_expected": _nonnegative_int(
                    observation.get("critical_expected"),
                    field=f"{case_id}.critical_expected",
                ),
                "critical_recovered": _nonnegative_int(
                    observation.get("critical_recovered"),
                    field=f"{case_id}.critical_recovered",
                ),
                "accepted_unsupported_high_impact": _nonnegative_int(
                    observation.get("accepted_unsupported_high_impact"),
                    field=f"{case_id}.accepted_unsupported_high_impact",
                ),
                "expected_complete": observation["expected_complete"],
                "truthful_incomplete": observation.get("truthful_incomplete"),
                "all_obligations_disposed": observation.get("all_obligations_disposed"),
                "strata": observation["strata"],
            }
        )

    complete = not not_executable and len(metric_cases) == len(expected_cases)
    metrics = None
    gate = None

    if complete:
        try:
            metrics = evaluate_cases(metric_cases)
            thresholds = suite["quality_threshold_policy"]["calibrated_thresholds"]
            gate = release_gate(
                metrics,
                calibrated_faithfulness_min=thresholds["factual_faithfulness_min"],
                calibrated_precision_min=thresholds["noncritical_precision_min"],
                calibrated_recall_min=thresholds["noncritical_recall_min"],
            )
        except (KeyError, ReleaseEvaluationError) as exc:
            raise BaselineMeasurementError(str(exc)) from exc

    usage = measurement.get("usage")
    if not isinstance(usage, dict):
        raise BaselineMeasurementError("usage must be an object.")
    for field in (
        "execution_seconds",
        "source_tokens",
        "input_characters",
        "answer_tokens",
        "thinking_tokens",
        "provider_reported_cost",
    ):
        value = usage.get(field)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0
        ):
            raise BaselineMeasurementError(f"usage.{field} must be null or non-negative.")

    controls_passed = not any(control_failures.values())
    return {
        "schema_version": "pharma_review_baseline_measurement_report.v1",
        "measurement_complete": complete,
        "measured_case_count": len(metric_cases),
        "not_executable_case_count": len(not_executable),
        "not_executable_cases": not_executable,
        "quality_metrics": metrics,
        "quality_gate": gate,
        "control_failures": control_failures,
        "controls_passed": controls_passed if complete else None,
        "usage": usage,
    }
