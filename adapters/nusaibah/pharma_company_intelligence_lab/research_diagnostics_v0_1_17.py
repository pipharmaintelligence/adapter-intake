"""Version-owned research validation and conservative, deterministic cleanup.

The validator mirrors the retained agent_contract without changing its bytes.
The resolver runs before validation and never invents identity or evidence.
Only static field/rule identifiers cross the runtime failure boundary.
"""
from __future__ import annotations

from typing import Any, Callable

try:
    from .agent_contract import (
        RESEARCH_SCHEMA_VERSION, RESEARCH_ROLE_SECTIONS, MAX_CLAIMS,
        MAX_TEXT_CHARS, MAX_UNCERTAINTIES, _text, _token, _text_list,
    )
    from .dossier_contract import normalize_sections, SECTION_BY_ID
except ImportError:  # pragma: no cover - flat adapter-root imports
    from agent_contract import (
        RESEARCH_SCHEMA_VERSION, RESEARCH_ROLE_SECTIONS, MAX_CLAIMS,
        MAX_TEXT_CHARS, MAX_UNCERTAINTIES, _text, _token, _text_list,
    )
    from dossier_contract import normalize_sections, SECTION_BY_ID


class ResearchContractValidationError(ValueError):
    def __init__(self, *, role: str, stage: str, rule: str, field: str) -> None:
        self.code = "pharma_agent_business_schema_invalid"
        self.proof_failure_detail = {
            "schema_version": "proof_failure_detail.v1",
            "proof_kind": "agent_contract", "role": role, "stage": stage,
            "rule": rule, "field": field,
        }
        super().__init__("Research response violates the reviewed business contract.")


def _error(role: str, rule: str, field: str, stage: str = "research_payload") -> ResearchContractValidationError:
    return ResearchContractValidationError(role=role, stage=stage, rule=rule, field=field)


def _checked(role: str, field: str, validator: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    try:
        return validator(*args, **kwargs)
    except (ValueError, TypeError):
        raise _error(role, "field_invalid", field) from None


def extract_research_json(envelope: Any, *, role: str, company_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
    """Mirror extract_agent_json's research envelope checks with safe diagnostics."""
    if not isinstance(envelope, dict) or envelope.get("status") != "completed":
        raise _error(role, "not_completed", "status", "research_envelope")
    result = envelope.get("result")
    if not isinstance(result, dict):
        raise _error(role, "object_required", "result", "research_envelope")
    if result.get("schema_version") != "agent_result.v1" or result.get("kind") != "json":
        raise _error(role, "schema_mismatch", "result_schema", "research_envelope")
    content = result.get("content")
    if (not isinstance(content, list) or len(content) != 1
            or not isinstance(content[0], dict) or content[0].get("type") != "json"
            or not isinstance(content[0].get("value"), dict)):
        raise _error(role, "typed_json_required", "content", "research_envelope")
    value = dict(content[0]["value"])
    for field, expected in (("schema_version", RESEARCH_SCHEMA_VERSION),
                            ("company_id", company_id), ("role", role), ("status", "completed")):
        if value.get(field) != expected:
            raise _error(role, "identity_mismatch" if field in {"company_id", "role"} else "value_mismatch",
                         field, "research_envelope")
    return value, result


def validate_research_payload(value: dict[str, Any], *, role: str, company_id: int) -> dict[str, Any]:
    """Preserve validation order, normalization, defaults and safety bounds."""
    allowed = RESEARCH_ROLE_SECTIONS.get(role)
    if allowed is None:
        raise _error("orchestration", "unknown_role", "role")
    sections = _checked(role, "sections", normalize_sections, value.get("sections"),
                        require_all=True, allowed_section_ids=allowed)
    for section in sections:
        if section["subsections"]:
            if any(not item["content"] for item in section["subsections"]):
                raise _error(role, "explicit_content_required", "subsections_content")
            if any(len(item["content"]) > MAX_TEXT_CHARS for item in section["subsections"]):
                raise _error(role, "text_bound_exceeded", "subsections_content")
        else:
            if not section["content"]:
                raise _error(role, "explicit_content_required", "sections_content")
            if len(section["content"]) > MAX_TEXT_CHARS:
                raise _error(role, "text_bound_exceeded", "sections_content")
    claims = value.get("claims")
    if not isinstance(claims, list) or len(claims) > MAX_CLAIMS:
        raise _error(role, "bounded_list_required", "claims")
    normalized = []
    seen = set()
    for raw in claims:
        if not isinstance(raw, dict):
            raise _error(role, "object_required", "claims")
        claim_id = _checked(role, "claims_claim_id", _token, raw.get("claim_id"), "claim_id", max_chars=128)
        if claim_id in seen:
            raise _error(role, "duplicate_claim_id", "claims_claim_id")
        seen.add(claim_id)
        section_id = _checked(role, "claims_section_id", _token, raw.get("section_id"), "section_id", max_chars=128)
        if section_id not in allowed:
            raise _error(role, "outside_role_scope", "claims_section_id")
        kind = _checked(role, "claims_evidence_kind", _token, raw.get("evidence_kind"), "evidence_kind", max_chars=64)
        if kind not in {"grounded_external", "inference"}:
            raise _error(role, "enum_invalid", "claims_evidence_kind")
        confidence = _checked(role, "claims_confidence", _token, raw.get("confidence"), "confidence", max_chars=32)
        if confidence not in {"low", "medium", "high"}:
            raise _error(role, "enum_invalid", "claims_confidence")
        inference = raw.get("inference")
        if not isinstance(inference, bool):
            raise _error(role, "boolean_required", "claims_inference")
        if kind == "inference" and inference is not True:
            raise _error(role, "inference_flag_required", "claims_inference")
        date = raw.get("as_of_date")
        if date is not None:
            date = _checked(role, "claims_as_of_date", _text, date, "as_of_date", max_chars=64)
        normalized.append({"claim_id": claim_id, "section_id": section_id,
                           "statement": _checked(role, "claims_statement", _text, raw.get("statement"), "statement"),
                           "evidence_kind": kind, "as_of_date": date,
                           "confidence": confidence, "inference": inference})
    uncertainties = _checked(role, "uncertainties", _text_list,
                             value.get("uncertainties", []), "uncertainties", MAX_UNCERTAINTIES)
    if value.get("company_id") != company_id or value.get("role") != role:
        raise _error(role, "identity_mismatch", "identity")
    return {"schema_version": RESEARCH_SCHEMA_VERSION, "company_id": company_id,
            "role": role, "status": "completed", "sections": sections,
            "claims": normalized, "uncertainties": uncertainties}


def resolve_research_payload(value: dict[str, Any], *, role: str, company_id: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Resolve only lossless representation differences, then validate exactly.

    No dropped claims, truncation, guessed dates, missing sections, identity
    coercions or boolean coercions. A rejected response cannot receive a new
    paid call here. Repair receipts contain static fields/rules and counts.
    """
    cleaned = dict(value)
    repairs: dict[tuple[str, str], int] = {}

    def record(field: str, rule: str) -> None:
        key = (field, rule)
        repairs[key] = repairs.get(key, 0) + 1

    def ordered(items: Any, key: str, expected: tuple[str, ...], field: str) -> Any:
        if not isinstance(items, list) or len(items) != len(expected):
            return items
        ids = [item.get(key) for item in items if isinstance(item, dict)]
        if len(ids) != len(items) or any(not isinstance(item, str) for item in ids):
            return items
        if len(set(ids)) != len(ids) or set(ids) != set(expected):
            return items
        if tuple(ids) != expected:
            record(field, "canonical_order_restored")
        by_id = dict(zip(ids, items))
        return [by_id[item] for item in expected]

    sections = ordered(cleaned.get("sections"), "section_id", RESEARCH_ROLE_SECTIONS.get(role, ()), "sections")
    if isinstance(sections, list):
        result = []
        for raw in sections:
            if not isinstance(raw, dict):
                result.append(raw)
                continue
            section = dict(raw)
            spec = SECTION_BY_ID.get(section.get("section_id")) if isinstance(section.get("section_id"), str) else None
            if spec is not None:
                section["subsections"] = ordered(section.get("subsections", []), "subsection_id",
                                                tuple(s.subsection_id for s in spec.subsections), "subsections")
            result.append(section)
        cleaned["sections"] = result
    if isinstance(cleaned.get("claims"), list):
        claims = []
        for raw in cleaned["claims"]:
            if not isinstance(raw, dict):
                claims.append(raw)
                continue
            claim = dict(raw)
            for field, enums in (("confidence", {"low", "medium", "high"}),
                                 ("evidence_kind", {"grounded_external", "inference"})):
                item = claim.get(field)
                if isinstance(item, str) and item.strip().lower() in enums:
                    normalized = item.strip().lower()
                    if normalized != item:
                        claim[field] = normalized
                        record("claims_" + field, "known_enum_normalized")
            claims.append(claim)
        cleaned["claims"] = claims
    payload = validate_research_payload(cleaned, role=role, company_id=company_id)
    if not payload["claims"] and not payload["uncertainties"]:
        raise _error(role, "explicit_evidence_gap_required", "uncertainties")
    return payload, [{"field": field, "rule": rule, "count": count}
                     for (field, rule), count in sorted(repairs.items())]


EVIDENCE_GAP_TEXT = "No verified evidence was supplied for this item."


def repair_input_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Project declared business fields; omit undeclared runtime material."""
    def scalar(item: Any) -> Any:
        return item if item is None or isinstance(item, (str, bool, int, float)) else None
    result = {key: scalar(value[key]) for key in
              ("schema_version", "company_id", "role", "status", "uncertainties") if key in value}
    if isinstance(value.get("uncertainties"), list):
        result["uncertainties"] = [item if isinstance(item, str) else None for item in value["uncertainties"]]
    raw_sections = value.get("sections")
    if isinstance(raw_sections, list):
        result["sections"] = []
        for raw in raw_sections:
            if not isinstance(raw, dict):
                result["sections"].append(None)
                continue
            section = {key: scalar(raw[key]) for key in ("section_id", "content") if key in raw}
            subs = raw.get("subsections")
            if isinstance(subs, list):
                section["subsections"] = [
                    {key: scalar(sub[key]) for key in ("subsection_id", "content") if key in sub}
                    if isinstance(sub, dict) else None for sub in subs
                ]
            result["sections"].append(section)
    raw_claims = value.get("claims")
    if isinstance(raw_claims, list):
        result["claims"] = [
            {key: scalar(claim[key]) for key in ("claim_id", "section_id", "statement", "evidence_kind",
                                        "as_of_date", "confidence", "inference") if key in claim}
            if isinstance(claim, dict) else None for claim in raw_claims
        ]
    # Values still have to pass the generic input-size/forbidden-material guard.
    return result


def require_repair_preserves_evidence(original: dict[str, Any], repaired: dict[str, Any], *, role: str) -> None:
    """An Agent may repair formatting, never author replacement research facts."""
    def rejected(field: str) -> None:
        raise _error(role, "repair_changed_evidence", field, "research_repair")

    raw_claims = original.get("claims")
    if not isinstance(raw_claims, list) or len(raw_claims) != len(repaired["claims"]):
        rejected("claims")
    for before, after in zip(raw_claims, repaired["claims"]):
        if not isinstance(before, dict):
            rejected("claims")
        for field in ("statement", "section_id"):
            raw = before.get(field)
            if not isinstance(raw, str) or raw.strip() != after[field]:
                rejected("claims_" + field)
        kind = before.get("evidence_kind")
        kind = kind.strip().lower() if isinstance(kind, str) else None
        if kind in {"grounded_external", "inference"}:
            if kind != after["evidence_kind"]:
                rejected("claims_evidence_kind")
        elif after["evidence_kind"] != "inference" or after["inference"] is not True:
            rejected("claims_evidence_kind")
        flag = before.get("inference")
        if type(flag) is bool:
            if flag != after["inference"]:
                rejected("claims_inference")
        elif isinstance(flag, str) and flag.strip().lower() in {"true", "false"}:
            if (flag.strip().lower() == "true") != after["inference"]:
                rejected("claims_inference")
        else:
            rejected("claims_inference")
        confidence = before.get("confidence")
        confidence = confidence.strip().lower() if isinstance(confidence, str) else None
        if after["confidence"] != (confidence if confidence in {"low", "medium", "high"} else "low"):
            rejected("claims_confidence")
        date = before.get("as_of_date")
        expected_date = date.strip() if isinstance(date, str) and date.strip() and len(date.strip()) <= 64 else None
        if after["as_of_date"] != expected_date:
            rejected("claims_as_of_date")
    original_content: dict[tuple[str, str | None], str] = {}
    sections = original.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            sid = section.get("section_id")
            if not isinstance(sid, str):
                rejected("sections")
            text = section.get("content")
            if isinstance(text, str) and text.strip():
                if (sid, None) in original_content and original_content[(sid, None)] != text.strip():
                    rejected("sections_content")
                original_content[(sid, None)] = text.strip()
            subs = section.get("subsections")
            if isinstance(subs, list):
                for sub in subs:
                    if isinstance(sub, dict) and isinstance(sub.get("content"), str) and sub["content"].strip():
                        sub_id = sub.get("subsection_id")
                        if not isinstance(sub_id, str):
                            rejected("subsections")
                        if (sid, sub_id) in original_content and original_content[(sid, sub_id)] != sub["content"].strip():
                            rejected("subsections_content")
                        original_content[(sid, sub_id)] = sub["content"].strip()
    repaired_content = {}
    for section in repaired["sections"]:
        sid = section["section_id"]
        if section["content"]:
            repaired_content[(sid, None)] = section["content"]
        for sub in section["subsections"]:
            if sub["content"]:
                repaired_content[(sid, sub["subsection_id"])] = sub["content"]
    if any(repaired_content.get(key) != text for key, text in original_content.items()):
        rejected("sections_content")
    if any(text != original_content.get(key, EVIDENCE_GAP_TEXT) for key, text in repaired_content.items()):
        rejected("sections_content")
    original_uncertainties = original.get("uncertainties", [])
    if not isinstance(original_uncertainties, list) or any(not isinstance(item, str) for item in original_uncertainties):
        rejected("uncertainties")
    before_uncertainties = {item.strip() for item in original_uncertainties if item.strip()}
    after_uncertainties = set(repaired["uncertainties"])
    if not before_uncertainties.issubset(after_uncertainties) or not after_uncertainties.issubset(before_uncertainties | {EVIDENCE_GAP_TEXT}):
        rejected("uncertainties")


def unresolved_research_payload(*, role: str, company_id: int) -> dict[str, Any]:
    """Withhold an unrepaired response, preserving the canonical no-evidence shape."""
    sections = []
    for section_id in RESEARCH_ROLE_SECTIONS[role]:
        spec = SECTION_BY_ID[section_id]
        sections.append({"section_id": section_id,
                         "content": "" if spec.subsections else EVIDENCE_GAP_TEXT,
                         "subsections": [{"subsection_id": sub.subsection_id, "content": EVIDENCE_GAP_TEXT}
                                         for sub in spec.subsections]})
    return validate_research_payload({"company_id": company_id, "role": role,
                                     "sections": sections, "claims": [],
                                     "uncertainties": ["Research response remained invalid after one bounded contract repair; its findings were withheld."]},
                                    role=role, company_id=company_id)


def research_validation_contract(*, role: str, company_id: int) -> dict[str, Any]:
    """Expose the actual primitive types and bounds to the existing formatter."""
    return {
        "company_id": {"type": "integer", "required_value": company_id},
        "role": {"type": "string", "required_value": role},
        "sections": {"type": "array", "ids_in_order": list(RESEARCH_ROLE_SECTIONS[role]),
                     "required_subsection_ids": {
                         sid: [sub.subsection_id for sub in SECTION_BY_ID[sid].subsections]
                         for sid in RESEARCH_ROLE_SECTIONS[role]},
                     "content_type": "string", "subsection_content_nonempty": True,
                     "max_content_chars": MAX_TEXT_CHARS,
                     "unavailable_evidence": "Use explicit evidence-gap text; never invent a finding."},
        "claims": {"type": "array", "min_items": 0, "max_items": MAX_CLAIMS,
                   "fields": {"claim_id": {"type": "string", "compact": True, "unique": True, "max_chars": 128},
                              "section_id": {"type": "string", "allowed_values": list(RESEARCH_ROLE_SECTIONS[role])},
                              "statement": {"type": "string", "nonempty": True, "max_chars": MAX_TEXT_CHARS},
                              "evidence_kind": {"type": "string", "allowed_values": ["grounded_external", "inference"]},
                              "as_of_date": {"type": ["string", "null"], "max_chars": 64},
                              "confidence": {"type": "string", "allowed_values": ["low", "medium", "high"]},
                              "inference": {"type": "boolean", "required_true_for": "inference"}}},
        "uncertainties": {"type": "array", "max_items": MAX_UNCERTAINTIES,
                          "item_type": "string", "nonempty_items": True, "max_item_chars": MAX_TEXT_CHARS},
        "no_evidence": "Empty claims require explicit uncertainties and critic disposition of all role requirements.",
    }
