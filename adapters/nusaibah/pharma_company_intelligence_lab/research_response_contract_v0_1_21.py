"""Version-owned research response contract for pharma adapter 0.1.21.

Only the three search-enabled research roles use this contract:
- portfolio_researcher owns company/profile and portfolio claims.
- market_researcher owns market and commercial claims.
- regulatory_risk_researcher owns regulatory, clinical and safety claims.

The methodology planner, strategic analyst, evidence critic, synthesizer,
benchmark reviewer and one-time response resolver do not own factual citation
references. This helper extends the retained research schema without mutating
historical 0.1.20 validators. It has no provider, storage, approval, publication
or Dynamic Skill mutation authority.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

try:
    from .agent_contract import MAX_CLAIMS
    from .research_diagnostics_v0_1_17 import (
        repair_input_payload as _repair_input_payload_v0_1_17,
        require_repair_preserves_evidence as _require_repair_preserves_v0_1_17,
        research_validation_contract as _research_validation_contract_v0_1_17,
        validate_research_payload as _validate_research_payload_v0_1_17,
    )
except ImportError:  # pragma: no cover - flat intake execution
    from agent_contract import MAX_CLAIMS
    from research_diagnostics_v0_1_17 import (
        repair_input_payload as _repair_input_payload_v0_1_17,
        require_repair_preserves_evidence as _require_repair_preserves_v0_1_17,
        research_validation_contract as _research_validation_contract_v0_1_17,
        validate_research_payload as _validate_research_payload_v0_1_17,
    )


RESEARCH_SCHEMA_VERSION = "pharma_research_agent.v2"
MAX_CITATION_LOCATORS_PER_CLAIM = 24
MAX_CITATION_LOCATOR_CHARS = 2048
MAX_EVIDENCE_QUALIFIERS_PER_CLAIM = 8
MAX_EVIDENCE_QUALIFIER_CHARS = 500

_RESEARCH_FIELDS = {
    "schema_version",
    "company_id",
    "role",
    "status",
    "sections",
    "claims",
    "uncertainties",
}
_CLAIM_FIELDS = {
    "claim_id",
    "section_id",
    "statement",
    "evidence_kind",
    "as_of_date",
    "confidence",
    "inference",
    "citation_locators",
    "evidence_qualifiers",
}
_BASE_CLAIM_FIELDS = (
    "claim_id",
    "section_id",
    "statement",
    "evidence_kind",
    "as_of_date",
    "confidence",
    "inference",
)


class ResearchResponseContractError(ValueError):
    """Value-safe 0.1.21 research response contract rejection."""

    def __init__(self, *, role: str, rule: str, field: str) -> None:
        self.code = "pharma_agent_business_schema_invalid"
        self.proof_failure_detail = {
            "schema_version": "proof_failure_detail.v1",
            "proof_kind": "agent_contract",
            "role": role,
            "stage": "research_payload_v0_1_21",
            "rule": rule,
            "field": field,
        }
        super().__init__("Research response violates the reviewed 0.1.21 contract.")


def validate_research_payload_v0_1_21(
    value: Any,
    *,
    role: str,
    company_id: int,
) -> dict[str, Any]:
    """Validate one exact 0.1.21 research payload and preserve evidence fields.

    The retained 0.1.17 validator remains the authority for historical section,
    claim, identity and uncertainty semantics. This wrapper validates the new
    claim-level locator and qualifier fields, then returns one canonical v2
    payload without changing the input object.
    """

    if not isinstance(value, Mapping) or set(value) != _RESEARCH_FIELDS:
        raise _error(role, "shape", "research_payload")
    if value.get("schema_version") != RESEARCH_SCHEMA_VERSION:
        raise _error(role, "schema_version", "schema_version")
    if value.get("company_id") != company_id:
        raise _error(role, "identity", "company_id")
    if value.get("role") != role:
        raise _error(role, "identity", "role")
    if value.get("status") != "completed":
        raise _error(role, "identity", "status")

    raw_claims = value.get("claims")
    if not isinstance(raw_claims, list) or len(raw_claims) > MAX_CLAIMS:
        raise _error(role, "bounded_list_required", "claims")

    base_claims: list[dict[str, Any]] = []
    evidence_fields: list[tuple[list[str], list[str]]] = []
    for raw in raw_claims:
        if not isinstance(raw, Mapping) or set(raw) != _CLAIM_FIELDS:
            raise _error(role, "shape", "claims")
        base_claims.append({field: raw[field] for field in _BASE_CLAIM_FIELDS})
        locators = _text_list(
            raw.get("citation_locators"),
            role=role,
            field="claims.citation_locators",
            maximum=MAX_CITATION_LOCATORS_PER_CLAIM,
            max_chars=MAX_CITATION_LOCATOR_CHARS,
            minimum=1,
            preserve_internal_whitespace=True,
        )
        qualifiers = _text_list(
            raw.get("evidence_qualifiers"),
            role=role,
            field="claims.evidence_qualifiers",
            maximum=MAX_EVIDENCE_QUALIFIERS_PER_CLAIM,
            max_chars=MAX_EVIDENCE_QUALIFIER_CHARS,
            minimum=0,
            preserve_internal_whitespace=False,
        )
        evidence_fields.append((locators, qualifiers))

    base_payload = {
        "company_id": company_id,
        "role": role,
        "sections": deepcopy(value.get("sections")),
        "claims": base_claims,
        "uncertainties": deepcopy(value.get("uncertainties")),
    }
    try:
        validated = _validate_research_payload_v0_1_17(
            base_payload,
            role=role,
            company_id=company_id,
        )
    except (TypeError, ValueError) as exc:
        proof = getattr(exc, "proof_failure_detail", None)
        if isinstance(proof, Mapping):
            raise ResearchResponseContractError(
                role=str(proof.get("role") or role),
                rule=str(proof.get("rule") or "field_invalid"),
                field=str(proof.get("field") or "research_payload"),
            ) from None
        raise _error(role, "field_invalid", "research_payload") from None

    claims: list[dict[str, Any]] = []
    for claim, (locators, qualifiers) in zip(
        validated["claims"],
        evidence_fields,
    ):
        claims.append(
            {
                **claim,
                "citation_locators": locators,
                "evidence_qualifiers": qualifiers,
            }
        )

    return {
        "schema_version": RESEARCH_SCHEMA_VERSION,
        "company_id": company_id,
        "role": role,
        "status": "completed",
        "sections": validated["sections"],
        "claims": claims,
        "uncertainties": validated["uncertainties"],
    }


def research_validation_contract_v0_1_21(
    *,
    role: str,
    company_id: int,
) -> dict[str, Any]:
    """Expose exact v2 primitive fields and bounds to the research formatter."""

    contract = deepcopy(
        _research_validation_contract_v0_1_17(
            role=role,
            company_id=company_id,
        )
    )
    fields = contract["claims"]["fields"]
    fields["citation_locators"] = {
        "type": "array",
        "min_items": 1,
        "max_items": MAX_CITATION_LOCATORS_PER_CLAIM,
        "item_type": "string",
        "nonempty_items": True,
        "unique": True,
        "max_item_chars": MAX_CITATION_LOCATOR_CHARS,
        "authority": "must_exactly_match_runtime_admitted_citation_locator",
    }
    fields["evidence_qualifiers"] = {
        "type": "array",
        "min_items": 0,
        "max_items": MAX_EVIDENCE_QUALIFIERS_PER_CLAIM,
        "item_type": "string",
        "nonempty_items": True,
        "unique": True,
        "max_item_chars": MAX_EVIDENCE_QUALIFIER_CHARS,
    }
    contract["claim_evidence"] = {
        "schema_version": RESEARCH_SCHEMA_VERSION,
        "unknown_locator_action": "claim_withheld",
        "missing_locator_action": "claim_withheld",
        "model_authored_citation_ids_allowed": False,
    }
    return contract


def project_repair_input_v0_1_21(value: Mapping[str, Any]) -> dict[str, Any]:
    """Project only declared v2 business fields for one bounded resolver call."""

    projected = _repair_input_payload_v0_1_17(dict(value))
    raw_claims = value.get("claims")
    if not isinstance(raw_claims, list):
        return projected

    projected_claims = projected.get("claims")
    if not isinstance(projected_claims, list):
        return projected

    for raw, target in zip(raw_claims, projected_claims):
        if not isinstance(raw, Mapping) or not isinstance(target, dict):
            continue
        target["citation_locators"] = _project_text_list(raw.get("citation_locators"))
        target["evidence_qualifiers"] = _project_text_list(raw.get("evidence_qualifiers"))
    return projected


def require_repair_preserves_claim_evidence_v0_1_21(
    original: Mapping[str, Any],
    repaired: Mapping[str, Any],
    *,
    role: str,
) -> None:
    """Require a resolver to preserve every locator and qualifier exactly."""

    _require_repair_preserves_v0_1_17(
        dict(original),
        dict(repaired),
        role=role,
    )
    before_claims = original.get("claims")
    after_claims = repaired.get("claims")
    if not isinstance(before_claims, list) or not isinstance(after_claims, list):
        raise _error(role, "repair_changed_evidence", "claims")
    if len(before_claims) != len(after_claims):
        raise _error(role, "repair_changed_evidence", "claims")

    for before, after in zip(before_claims, after_claims):
        if not isinstance(before, Mapping) or not isinstance(after, Mapping):
            raise _error(role, "repair_changed_evidence", "claims")
        for field in ("citation_locators", "evidence_qualifiers"):
            if _exact_string_list(before.get(field)) != _exact_string_list(after.get(field)):
                raise _error(role, "repair_changed_evidence", f"claims.{field}")


def _text_list(
    value: Any,
    *,
    role: str,
    field: str,
    maximum: int,
    max_chars: int,
    minimum: int,
    preserve_internal_whitespace: bool,
) -> list[str]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise _error(role, "bounded_list_required", field)
    result: list[str] = []
    for raw in value:
        if not isinstance(raw, str):
            raise _error(role, "field_invalid", field)
        item = raw.strip()
        if not preserve_internal_whitespace:
            item = " ".join(item.split())
        if not item or len(item) > max_chars or _contains_unsafe_text(item):
            raise _error(role, "field_invalid", field)
        if item in result:
            raise _error(role, "duplicate", field)
        result.append(item)
    return result


def _project_text_list(value: Any) -> Any:
    if not isinstance(value, list):
        return None
    return [item if isinstance(item, str) else None for item in value]


def _exact_string_list(value: Any) -> tuple[str, ...] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return None
    return tuple(item.strip() for item in value)


def _contains_unsafe_text(value: str) -> bool:
    return any(
        ord(character) < 0x20
        or ord(character) == 0x7F
        or 0xD800 <= ord(character) <= 0xDFFF
        for character in value
    )


def _error(role: str, rule: str, field: str) -> ResearchResponseContractError:
    return ResearchResponseContractError(role=role, rule=rule, field=field)
