from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ASSET_ROOT = Path(__file__).resolve().parents[2]
if str(ASSET_ROOT) not in sys.path:
    sys.path.insert(0, str(ASSET_ROOT))

from devtools.dynamic_skill_runtime import DynamicSkillRuntimeError
from nusaibah_pharma_company_intelligence_lab_adapter import (
    NusaibahPharmaCompanyIntelligenceLabAdapter,
)


class BaselineReplayError(ValueError):
    """Raised when an evaluation-only replay violates the pinned baseline contract."""


BASELINE_ASSET_KEY = "nusaibah.pharma_company_intelligence_lab"
BASELINE_ASSET_VERSION = "0.1.12"
BASELINE_RUNTIME_VERSION = "0.1.97"
BASELINE_INTAKE_COMMIT = "21cc6b39492cbd3c090de537a2ee27c599f0f0ec"
PINNED_METHODOLOGY_REF = "nusaibah.pharma-intelligence-methodology"
PINNED_METHODOLOGY_VERSION = "1.0.0"
PINNED_METHODOLOGY_DIGEST = (
    "sha256:2fa082aca1c100abb60a4bf77aa4cf796da2707bb951a3b51f11948efd2dd564"
)

COMPANY_CASE_MODE = "company_research"
DOCUMENT_CASE_MODE = "document_review"

MAX_BASELINE_FIELDS = 48
MAX_BASELINE_STRING_CHARS = 4000
MAX_BASELINE_LIST_ITEMS = 20

# Evaluation-only synthetic IDs are deliberately outside known business IDs.
SYNTHETIC_COMPANY_ID_BASE = 900_000


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _case_source_digest(case: dict[str, Any]) -> str:
    canonical = json.dumps(
        case["source_units"],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _sha256_text(canonical)


def _synthetic_company_id(case_index: int) -> int:
    if isinstance(case_index, bool) or not isinstance(case_index, int) or case_index < 0:
        raise BaselineReplayError("case_index must be a non-negative integer.")
    return SYNTHETIC_COMPANY_ID_BASE + case_index + 1


def assess_replay_case(case: dict[str, Any], *, case_index: int) -> dict[str, Any]:
    """Return an honest replay-compatibility decision for one adjudicated case."""

    if not isinstance(case, dict):
        raise BaselineReplayError("case must be an object.")
    case_id = case.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise BaselineReplayError("case_id is required.")

    mode = case.get("mode")
    reasons: list[str] = []
    if mode == DOCUMENT_CASE_MODE:
        reasons.append("document_review_input_contract_absent")
    elif mode != COMPANY_CASE_MODE:
        reasons.append("unsupported_evaluation_mode")

    source_units = case.get("source_units")
    if not isinstance(source_units, list) or not source_units:
        reasons.append("source_units_missing")
        source_units = []

    required_fields = 4
    for unit in source_units:
        if not isinstance(unit, dict):
            reasons.append("source_unit_invalid")
            continue
        locator = unit.get("locator")
        text = unit.get("text")
        quality_flags = unit.get("quality_flags")
        if not isinstance(locator, str) or not locator:
            reasons.append("source_locator_invalid")
        elif len(locator) > MAX_BASELINE_STRING_CHARS:
            reasons.append("source_locator_too_large")
        if not isinstance(text, str) or not text:
            reasons.append("source_text_invalid")
        elif len(text) > MAX_BASELINE_STRING_CHARS:
            reasons.append("source_text_too_large")
        if (
            not isinstance(quality_flags, list)
            or len(quality_flags) > MAX_BASELINE_LIST_ITEMS
            or not all(isinstance(item, str) for item in quality_flags)
        ):
            reasons.append("source_quality_flags_invalid")
        required_fields += 3

    if required_fields > MAX_BASELINE_FIELDS:
        reasons.append("baseline_projection_field_limit")

    # The production binding is intentionally bypassed for synthetic evaluation.
    # That changes authority plumbing, not the unchanged adapter/Agent definitions.
    replayable = not reasons
    return {
        "case_id": case_id,
        "mode": mode,
        "case_index": case_index,
        "synthetic_company_id": _synthetic_company_id(case_index),
        "source_digest": _case_source_digest(case) if source_units else None,
        "replayable": replayable,
        "reason_codes": sorted(set(reasons)),
        "comparability": {
            "production_binding_used": False,
            "production_adapter_code_changed": False,
            "production_agent_definitions_changed": False,
            "production_model_provider_policy_changed": False,
            "production_budgets_changed": False,
            "synthetic_company_memory_used": replayable,
            "company_methodology_first_run_state_used": replayable,
            "document_input_contract_used": False,
        },
    }


def build_replay_company_record(
    case: dict[str, Any],
    *,
    case_index: int,
) -> dict[str, Any]:
    """Project one company-mode case into bounded scalar baseline fields."""

    decision = assess_replay_case(case, case_index=case_index)
    if not decision["replayable"]:
        raise BaselineReplayError(
            f"{case['case_id']} is not replayable: "
            + ",".join(decision["reason_codes"])
        )

    company_id = decision["synthetic_company_id"]
    record: dict[str, Any] = {
        "company_id": company_id,
        "company_name": f"WP1 Synthetic Evaluation {case['case_id']}",
        "evaluation_case_id": case["case_id"],
        "evaluation_source_digest": decision["source_digest"],
    }

    for index, unit in enumerate(case["source_units"], start=1):
        prefix = f"evaluation_source_{index:02d}"
        record[f"{prefix}_locator"] = unit["locator"]
        record[f"{prefix}_text"] = unit["text"]
        record[f"{prefix}_quality_flags"] = list(unit["quality_flags"])

    if len(record) > MAX_BASELINE_FIELDS:
        raise BaselineReplayError("Synthetic company record exceeds baseline field limit.")
    return record


def build_replay_inputs(
    case: dict[str, Any],
    *,
    case_index: int,
) -> dict[str, Any]:
    """Build the exact input mapping consumed by the unchanged preview adapter."""

    record = build_replay_company_record(case, case_index=case_index)
    company_id = record["company_id"]
    return {
        "variables": {
            "execution_scope": "batch",
            "company_ids": [company_id],
            "objective": "company_intelligence_memory",
            "research_depth": "deep",
            "memory_mode": "preview",
            "publish_dossier": False,
        },
        "companies": {"records": [record]},
    }


class SyntheticCompanyMemory:
    """Minimal read-only prior memory for a synthetic evaluation company."""

    def __init__(self, *, case_id: str, company_id: int) -> None:
        self._text = (
            "---\n"
            "name: wp1-evaluation-company-memory\n"
            "description: Evaluation-only neutral prior memory.\n"
            "---\n"
            "# Company Memory\n\n"
            "## Current Public Research\n\n"
            f"No prior company-specific public research is supplied for {case_id} "
            f"(synthetic company {company_id}).\n"
        )
        self._digest = _sha256_text(self._text)

    def provenance(self) -> Any:
        return type("ReplayProvenance", (), {"mutable": False, "role": "company_memory"})()

    def read(self) -> str:
        return self._text

    def has_section(self, section: str) -> bool:
        return section == "Current Public Research"

    def section_text(self, section: str) -> str:
        if not self.has_section(section):
            raise KeyError(section)
        return self._text.split("## Current Public Research", 1)[1].strip()

    def content_digest(self) -> str:
        return self._digest


class EvaluationReplayInputs(dict):
    """Evaluation-only RuntimeInputs wrapper around an approved Agent-call delegate.

    The wrapper supplies synthetic company/memory context only. Agent execution and
    the immutable Fixed Skill remain delegated to the caller's runtime authority.
    Mutable Dynamic Skill roles are prohibited.
    """

    def __init__(
        self,
        *,
        case: dict[str, Any],
        case_index: int,
        runtime_delegate: Any,
    ) -> None:
        super().__init__(build_replay_inputs(case, case_index=case_index))
        self.case = case
        self.case_index = case_index
        self.runtime_delegate = runtime_delegate
        self.agent_calls: list[dict[str, Any]] = []
        self.dynamic_skill_calls: list[str] = []

    def invoke_agent(
        self,
        role: str,
        *,
        input: dict[str, Any],
        on_error: str = "raise",
    ) -> Any:
        if not callable(getattr(self.runtime_delegate, "invoke_agent", None)):
            raise BaselineReplayError("runtime_delegate.invoke_agent is unavailable.")
        self.agent_calls.append(
            {
                "role": role,
                "company_id": input.get("company_id"),
                "input_digest": _sha256_text(
                    json.dumps(
                        input,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                ),
            }
        )
        return self.runtime_delegate.invoke_agent(role, input=input, on_error=on_error)

    def skill(self, selector: str) -> Any:
        if selector != PINNED_METHODOLOGY_REF:
            raise BaselineReplayError("Unexpected Fixed Skill selector.")
        if not callable(getattr(self.runtime_delegate, "skill", None)):
            raise BaselineReplayError("runtime_delegate.skill is unavailable.")

        handle = self.runtime_delegate.skill(selector)
        report = handle.validate()
        if getattr(report, "skill_ref", None) != PINNED_METHODOLOGY_REF:
            raise BaselineReplayError("Fixed Skill reference mismatch.")
        if getattr(report, "version", None) != PINNED_METHODOLOGY_VERSION:
            raise BaselineReplayError("Fixed Skill version mismatch.")
        if getattr(report, "package_digest", None) != PINNED_METHODOLOGY_DIGEST:
            raise BaselineReplayError("Fixed Skill digest mismatch.")
        return handle

    def dynamic_skill(self, role: str, *, variables: dict[str, str] | None = None) -> Any:
        self.dynamic_skill_calls.append(role)
        company_id = int((variables or {}).get("company_id", "0"))
        if role == "company_memory":
            return SyntheticCompanyMemory(
                case_id=self.case["case_id"],
                company_id=company_id,
            )
        if role == "company_methodology":
            # This is a production-supported preview state in 0.1.12.
            raise DynamicSkillRuntimeError("dynamic_skill_not_initialized")
        raise BaselineReplayError(
            f"Mutable or unexpected Dynamic Skill role is forbidden in replay: {role}."
        )


def run_company_replay_case(
    case: dict[str, Any],
    *,
    case_index: int,
    runtime_delegate: Any,
) -> dict[str, Any]:
    """Run one company-mode case through the unchanged 0.1.12 adapter in preview."""

    decision = assess_replay_case(case, case_index=case_index)
    if not decision["replayable"]:
        return {
            "schema_version": "pharma_review_baseline_replay_result.v1",
            **decision,
            "executed": False,
            "adapter_result": None,
            "agent_calls": [],
        }

    inputs = EvaluationReplayInputs(
        case=case,
        case_index=case_index,
        runtime_delegate=runtime_delegate,
    )
    result = NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(inputs, {})
    if any(role.endswith("_update") for role in inputs.dynamic_skill_calls):
        raise BaselineReplayError("Replay attempted a mutable Dynamic Skill role.")

    return {
        "schema_version": "pharma_review_baseline_replay_result.v1",
        **decision,
        "executed": True,
        "adapter_result": result,
        "agent_calls": list(inputs.agent_calls),
        "dynamic_skill_calls": list(inputs.dynamic_skill_calls),
    }


def replay_plan(suite: dict[str, Any]) -> dict[str, Any]:
    """Describe replayability of the complete adjudicated suite without executing it."""

    cases = suite.get("cases")
    if not isinstance(cases, list) or not cases:
        raise BaselineReplayError("Evaluation suite cases are required.")

    decisions = [
        assess_replay_case(case, case_index=index)
        for index, case in enumerate(cases)
    ]
    replayable = [item for item in decisions if item["replayable"]]
    return {
        "schema_version": "pharma_review_baseline_replay_plan.v1",
        "baseline": {
            "asset_key": BASELINE_ASSET_KEY,
            "asset_version": BASELINE_ASSET_VERSION,
            "runtime_version": BASELINE_RUNTIME_VERSION,
            "intake_commit": BASELINE_INTAKE_COMMIT,
            "methodology_ref": PINNED_METHODOLOGY_REF,
            "methodology_version": PINNED_METHODOLOGY_VERSION,
            "methodology_digest": PINNED_METHODOLOGY_DIGEST,
        },
        "case_count": len(decisions),
        "replayable_case_count": len(replayable),
        "not_replayable_case_count": len(decisions) - len(replayable),
        "cases": decisions,
        "production_manifest_changed": False,
        "production_adapter_changed": False,
        "purpose": "evaluation_only",
    }
