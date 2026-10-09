"""Version-owned critic diagnostics; the retained shared contract stays unchanged.

Validation order, normalization, defaults and bounds mirror agent_contract.
Only static identifiers cross the generic runtime failure boundary.
"""
from __future__ import annotations

from typing import Any, Callable

try:
    from .agent_contract import (
        CRITIC_SCHEMA_VERSION, MAX_CLAIMS, MAX_LIST_ITEMS, MAX_TEXT_CHARS,
        MAX_UNCERTAINTIES, MAX_UNMET_PLAN_REQUIREMENTS,
        _text, _token, _text_list, _token_list,
    )
except ImportError:  # pragma: no cover - flat local adapter-root imports
    from agent_contract import (
        CRITIC_SCHEMA_VERSION, MAX_CLAIMS, MAX_LIST_ITEMS, MAX_TEXT_CHARS,
        MAX_UNCERTAINTIES, MAX_UNMET_PLAN_REQUIREMENTS,
        _text, _token, _text_list, _token_list,
    )


class CriticContractValidationError(ValueError):
    """Same rejection semantics, with an existing reviewed runtime failure code."""

    def __init__(self, rule: str, field: str) -> None:
        self.code = "pharma_agent_business_schema_invalid"
        self.proof_failure_detail = {
            "schema_version": "proof_failure_detail.v1",
            "proof_kind": "agent_contract",
            "role": "evidence_critic",
            "stage": "critic_payload",
            "rule": rule,
            "field": field,
        }
        super().__init__("Evidence critic payload violates the reviewed business contract.")


def _error(rule: str, field: str) -> CriticContractValidationError:
    return CriticContractValidationError(rule, field)


def _checked(field: str, validator: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    # Reuse the retained primitive validator. Do not parse exception messages,
    # attach payload values, or infer which hidden provider response was returned.
    try:
        return validator(*args, **kwargs)
    except ValueError:
        raise _error("field_invalid", field) from None


def validate_critic_payload(
    value: dict[str, Any],
    *,
    company_id: int,
    known_claim_ids: set[str],
    known_section_ids: set[str],
    known_plan_requirement_ids: set[str],
) -> dict[str, Any]:
    """Validate critic findings against the already-known same-company evidence."""
    unsupported = _checked(
        "unsupported_claim_ids", _token_list,
        value.get("unsupported_claim_ids", []), "unsupported_claim_ids", MAX_CLAIMS,
    )
    stale = _checked(
        "stale_claim_ids", _token_list,
        value.get("stale_claim_ids", []), "stale_claim_ids", MAX_CLAIMS,
    )
    if any(claim_id not in known_claim_ids for claim_id in unsupported + stale):
        raise _error("unknown_claim_id", "claim_ids")

    missing = _checked(
        "missing_section_ids", _token_list,
        value.get("missing_section_ids", []), "missing_section_ids", 32,
    )
    if any(section_id not in known_section_ids for section_id in missing):
        raise _error("unknown_section_id", "missing_section_ids")

    raw_unmet = value.get("unmet_plan_requirements")
    if not isinstance(raw_unmet, list) or len(raw_unmet) > MAX_UNMET_PLAN_REQUIREMENTS:
        raise _error("bounded_list_required", "unmet_plan_requirements")

    unmet_plan_requirements: list[dict[str, str]] = []
    seen_requirement_ids: set[str] = set()
    for raw in raw_unmet:
        if not isinstance(raw, dict):
            raise _error("object_required", "unmet_plan_requirements")
        if set(raw) != {"requirement_id", "disposition", "notes"}:
            raise _error("entry_shape_invalid", "unmet_plan_requirements")

        requirement_id = _checked("unmet_plan_requirements_requirement_id", _token,
            raw.get("requirement_id"),
            "unmet_plan_requirements.requirement_id",
            max_chars=192,
        )
        if requirement_id not in known_plan_requirement_ids:
            raise _error("unknown_requirement_id", "unmet_plan_requirements_requirement_id")
        if requirement_id in seen_requirement_ids:
            raise _error("duplicate_requirement_id", "unmet_plan_requirements_requirement_id")
        seen_requirement_ids.add(requirement_id)

        disposition = _checked("unmet_plan_requirements_disposition", _token,
            raw.get("disposition"),
            "unmet_plan_requirements.disposition",
            max_chars=32,
        )
        if disposition not in {"unresolved_evidence", "unsatisfied"}:
            raise _error("disposition_invalid", "unmet_plan_requirements_disposition")

        notes = _checked("unmet_plan_requirements_notes", _text,
            raw.get("notes"),
            "unmet_plan_requirements.notes",
            max_chars=MAX_TEXT_CHARS,
        )
        unmet_plan_requirements.append(
            {
                "requirement_id": requirement_id,
                "disposition": disposition,
                "notes": notes,
            }
        )

    recommendation = _checked("recommendation", _token, value.get("recommendation"), "recommendation", max_chars=16)
    if recommendation not in {"pass", "fail"}:
        raise _error("recommendation_invalid", "recommendation")

    coverage = value.get("citation_coverage")
    if not isinstance(coverage, dict):
        raise _error("object_required", "citation_coverage")
    coverage_status = _checked("citation_coverage_status", _token, coverage.get("status"), "citation_coverage.status", max_chars=32)
    if coverage_status not in {"sufficient", "insufficient"}:
        raise _error("coverage_status_invalid", "citation_coverage_status")

    return {
        "schema_version": CRITIC_SCHEMA_VERSION,
        "company_id": company_id,
        "role": "evidence_critic",
        "status": "completed",
        "unsupported_claim_ids": unsupported,
        "contradiction_items": _checked("contradiction_items", _text_list,
            value.get("contradiction_items", []),
            "contradiction_items",
            MAX_LIST_ITEMS,
        ),
        "stale_claim_ids": stale,
        "missing_section_ids": missing,
        "unmet_plan_requirements": unmet_plan_requirements,
        "citation_coverage": {
            "status": coverage_status,
            "notes": _checked("citation_coverage_notes", _text, coverage.get("notes", ""), "citation_coverage.notes", allow_blank=True),
        },
        "residual_uncertainties": _checked("residual_uncertainties", _text_list,
            value.get("residual_uncertainties", []),
            "residual_uncertainties",
            MAX_UNCERTAINTIES,
        ),
        "recommendation": recommendation,
    }
