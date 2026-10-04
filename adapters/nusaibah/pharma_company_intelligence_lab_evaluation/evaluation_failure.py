"""Safe diagnostics around unchanged, pinned baseline validation decisions."""

from __future__ import annotations

import traceback
from typing import Any

if __package__:
    from . import agent_contract, frozen_pharma_company_intelligence_lab as frozen
else:
    import agent_contract
    import frozen_pharma_company_intelligence_lab as frozen


class EvaluationFailure(RuntimeError):
    """A reviewed evaluation stop code; never includes provider or exception text."""

    def __init__(self, code: str, *, stage: str, rule: str, field: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.proof_stage = "agent_contract"
        self.proof_failure_detail = {
            "schema_version": "proof_failure_detail.v1",
            "proof_kind": "agent_contract",
            "role": "evidence_critic",
            "stage": stage,
            "rule": rule,
        }
        if field is not None:
            self.proof_failure_detail["field"] = field


_QUALITY_RULES = {
    "Every search-enabled research role must return admitted citations.": "research_citations_missing",
    "Evidence critic rejected the company evidence package.": "critic_rejected",
    "Evidence critic reported insufficient citation coverage.": "citation_coverage_insufficient",
    "Unsupported research claims remain after critique.": "unsupported_claims",
    "Mandatory research sections are missing after critique.": "mandatory_sections_missing",
    "Mandatory methodology plan requirements remain unsatisfied.": "methodology_requirements_unsatisfied",
}

_CRITIC_RULES: dict[str, tuple[str, str | None]] = {
    "Critic referenced an unknown claim_id.": ("unknown_claim_id", None),
    "Critic referenced an unknown section_id.": ("unknown_section_id", None),
    "unmet_plan_requirements must be a bounded list.": ("list_bound", "unmet_plan_requirements"),
    "unmet_plan_requirements must contain objects.": ("object_required", "unmet_plan_requirements"),
    "unmet_plan_requirements entries have an invalid shape.": ("object_shape", "unmet_plan_requirements"),
    "Critic referenced an unknown planner requirement_id.": ("unknown_requirement_id", None),
    "Critic planner requirement_id values must be unique.": ("duplicate_requirement_id", None),
    "Critic planner requirement disposition is unsupported.": ("disposition_invalid", None),
    "Critic recommendation must be pass or fail.": ("recommendation_invalid", None),
    "citation_coverage must be an object.": ("object_required", "citation_coverage"),
    "citation_coverage.status is unsupported.": ("coverage_status_invalid", None),
}
# These are the exact field/signature combinations used by the pinned validator.
# No pattern derived from model text is accepted or returned.
_CRITIC_FIELDS = (
    "unsupported_claim_ids", "stale_claim_ids", "missing_section_ids",
    "unmet_plan_requirements.requirement_id", "unmet_plan_requirements.disposition",
    "unmet_plan_requirements.notes", "recommendation", "citation_coverage.status",
    "citation_coverage.notes", "contradiction_items", "residual_uncertainties",
)
for _field in _CRITIC_FIELDS:
    for _suffix, _rule in (
        ("must be a string.", "string_required"),
        ("must not be blank.", "text_required"),
        ("exceeds the allowed character bound.", "text_bound"),
        ("must be a compact token.", "token_shape"),
        ("must be a bounded list.", "list_bound"),
        ("must not contain duplicates.", "duplicate_values"),
    ):
        _CRITIC_RULES[f"{_field} {_suffix}"] = (_rule, _field.replace(".", "_"))


def project_baseline_failure(exc: Exception) -> EvaluationFailure | None:
    """Classify only known failures originating in the pinned business functions.

    Frozen source and helper parity tests guard these mappings. Unknown errors,
    existing typed errors, and matching prose from a delegate remain untouched.
    The exception message is matched internally and is never emitted.
    """
    frames = {frame.f_code for frame, _ in traceback.walk_tb(exc.__traceback__)}
    if type(exc) is RuntimeError and frozen._require_pre_synthesis_quality.__code__ in frames:
        rule = _QUALITY_RULES.get(str(exc))
        if rule is not None:
            return EvaluationFailure(
                "pharma_evaluation_quality_rejected",
                stage="pre_synthesis_quality", rule=rule,
            )
    if type(exc) is ValueError and agent_contract.validate_critic_payload.__code__ in frames:
        detail = _CRITIC_RULES.get(str(exc))
        if detail is not None:
            rule, field = detail
            return EvaluationFailure(
                "pharma_evaluation_critic_schema_invalid",
                stage="critic_validation", rule=rule, field=field,
            )
    return None
