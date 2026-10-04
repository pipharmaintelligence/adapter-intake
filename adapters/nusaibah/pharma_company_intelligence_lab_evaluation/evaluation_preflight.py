"""No-provider assessment of synthetic replay purpose and projection bounds."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

if __package__:
    from .evaluation_replay import BaselineReplayError, assess_replay_case
    from .nusaibah_pharma_company_intelligence_lab_evaluation_adapter import (
        NusaibahPharmaCompanyIntelligenceLabEvaluationAdapter as _InputContract,
    )
else:
    from evaluation_replay import BaselineReplayError, assess_replay_case
    from nusaibah_pharma_company_intelligence_lab_evaluation_adapter import (
        NusaibahPharmaCompanyIntelligenceLabEvaluationAdapter as _InputContract,
    )

DIAGNOSTIC_PURPOSE = "diagnostic_baseline_replay"
POSITIVE_WEB_PURPOSE = "positive_web_smoke"
MAX_INPUT_BYTES = 128 * 1024
_SAFE_CASE_ID = re.compile(r"^[a-z][a-z0-9_-]{0,95}$")
_SAFE_LOCATOR = re.compile(r"^[a-z][a-z0-9_-]{0,63}:[A-Za-z0-9_.-]{1,96}$")


class EvaluationPreflightError(RuntimeError):
    """Safe purpose/bounds rejection raised before Agent or Skill access."""

    def __init__(self, rule: str) -> None:
        self.failure_code = "pharma_evaluation_preflight_rejected"
        self.code = self.failure_code
        self.proof_stage = "agent_contract"
        self.proof_failure_detail = {
            "schema_version": "proof_failure_detail.v1",
            "proof_kind": "agent_contract",
            "role": "evaluation_preflight",
            "stage": "evaluation_preflight",
            "rule": rule,
        }
        super().__init__(self.failure_code)


def preflight_inputs(inputs: Any, *, purpose: str | None = None) -> dict[str, Any]:
    """Separate projection compatibility from positive-smoke eligibility.

    A diagnostic replay may produce a quality rejection. This contract admits
    only synthetic input; it cannot authorize a positive public-company smoke.
    """
    report: dict[str, Any] = {
        "schema_version": "pharma_evaluation_preflight.v1",
        "status": "blocked",
        "projection_compatible": False,
        "positive_web_smoke_eligible": False,
        "execution_allowed": False,
        "provider_calls": 0,
        "reason_codes": [],
        "safe": True,
        "values_included": False,
    }
    reasons: list[str] = []
    if not isinstance(inputs, dict) or set(inputs) != {"evaluation_case", "variables"}:
        report["reason_codes"] = ["input_roles_invalid"]
        return report
    variables = inputs.get("variables")
    if not isinstance(variables, dict) or set(variables) - {"case_index", "execution_purpose"}:
        report["reason_codes"] = ["variables_invalid"]
        return report
    selected = variables.get("execution_purpose")
    if purpose is not None:
        if selected is not None and selected != purpose:
            reasons.append("execution_purpose_conflict")
        selected = purpose
    if selected not in (DIAGNOSTIC_PURPOSE, POSITIVE_WEB_PURPOSE):
        reasons.append("execution_purpose_required")
    if selected == POSITIVE_WEB_PURPOSE:
        reasons.append("positive_web_smoke_requires_separate_admission")
    try:
        case = _InputContract._evaluation_case(inputs)
        index = _InputContract._case_index({"variables": {"case_index": variables.get("case_index")}})
        if not _SAFE_CASE_ID.fullmatch(case["case_id"]):
            reasons.append("case_id_invalid")
        # A maximum of 48 baseline fields allows at most fourteen source units.
        units = case["source_units"]
        if len(units) > 14:
            reasons.append("source_unit_limit")
        else:
            for unit in units:
                if not isinstance(unit, dict) or set(unit) != {"locator", "text", "quality_flags"}:
                    reasons.append("source_unit_fields_invalid")
                    continue
                flags = unit["quality_flags"]
                if isinstance(flags, list) and any(
                    not isinstance(flag, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", flag) is None
                    for flag in flags
                ):
                    reasons.append("source_quality_flags_invalid")
                if not isinstance(unit["locator"], str) or not _SAFE_LOCATOR.fullmatch(unit["locator"]):
                    reasons.append("synthetic_source_locator_invalid")
            decision = assess_replay_case(case, case_index=index)
            reasons.extend(decision["reason_codes"])
            report["projection_compatible"] = decision["replayable"] and not any(
                reason in reasons for reason in (
                    "case_id_invalid", "source_unit_fields_invalid", "synthetic_source_locator_invalid",
                )
            )
    except (BaselineReplayError, KeyError, TypeError, ValueError):
        reasons.append("evaluation_input_invalid")
    report["reason_codes"] = sorted(set(reasons))
    report["execution_allowed"] = not reasons and report["projection_compatible"] and selected == DIAGNOSTIC_PURPOSE
    report["status"] = "ready" if report["execution_allowed"] else "blocked"
    return report


def require_diagnostic_preflight(inputs: Any) -> dict[str, Any]:
    report = preflight_inputs(inputs)
    if not report["execution_allowed"]:
        raise EvaluationPreflightError(report["reason_codes"][0])
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs-file", type=Path, required=True)
    parser.add_argument("--purpose", choices=(DIAGNOSTIC_PURPOSE, POSITIVE_WEB_PURPOSE))
    args = parser.parse_args(argv)
    try:
        with args.inputs_file.open("rb") as stream:
            content = stream.read(MAX_INPUT_BYTES + 1)
        if len(content) > MAX_INPUT_BYTES:
            raise ValueError("input_file_limit")
        inputs = json.loads(content.decode("utf-8-sig"))
        report = preflight_inputs(inputs, purpose=args.purpose)
    except (OSError, ValueError):
        report = {
            "schema_version": "pharma_evaluation_preflight.v1", "status": "blocked",
            "execution_allowed": False, "provider_calls": 0,
            "reason_codes": ["inputs_file_invalid"], "safe": True, "values_included": False,
        }
    print(json.dumps(report, indent=2))
    return 0 if report["execution_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
