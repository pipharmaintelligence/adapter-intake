from __future__ import annotations

from typing import Any

try:
    from .dossier_contract import normalize_sections
    from .memory_contract import MemoryCandidate, validate_memory_candidate
except ImportError:  # pragma: no cover - local adapter-root execution path
    from dossier_contract import normalize_sections
    from memory_contract import MemoryCandidate, validate_memory_candidate

RESEARCH_SCHEMA_VERSION = "pharma_research_agent.v1"
STRATEGIC_SCHEMA_VERSION = "pharma_strategic_agent.v1"
CRITIC_SCHEMA_VERSION = "pharma_evidence_critic.v1"
SYNTHESIS_SCHEMA_VERSION = "pharma_synthesis_agent.v1"
BENCHMARK_SCHEMA_VERSION = "pharma_memory_benchmark.v1"

MAX_CLAIMS = 16
MAX_UNCERTAINTIES = 32
MAX_LIST_ITEMS = 64
MAX_TEXT_CHARS = 2000
MAX_CITATIONS_OUTPUT = 24
MAX_UNMET_PLAN_REQUIREMENTS = 64

RESEARCH_ROLE_SECTIONS: dict[str, tuple[str, ...]] = {
    "portfolio_researcher": (
        "company_profile",
        "product_portfolio_intelligence",
    ),
    "market_researcher": (
        "markets_commercial_signals",
    ),
    "regulatory_risk_researcher": (
        "regulatory_clinical_risk_signals",
    ),
}

def response_contract_for_role(
    role: str,
    *,
    company_id: int,
    required_section_ids: tuple[str, ...] = (),
    question_ids: tuple[str, ...] = (),
    planner_requirement_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Return the compact canonical JSON response contract for one Agent role."""
    base: dict[str, Any] = {
        "company_id": company_id,
        "role": role,
        "status": "completed",
    }

    if role in RESEARCH_ROLE_SECTIONS:
        return {
            **base,
            "schema_version": RESEARCH_SCHEMA_VERSION,
            "required_fields": [
                "schema_version",
                "company_id",
                "role",
                "status",
                "sections",
                "claims",
                "uncertainties",
            ],
            "section_ids_in_order": list(required_section_ids or RESEARCH_ROLE_SECTIONS[role]),
            "claim_fields": [
                "claim_id",
                "section_id",
                "statement",
                "evidence_kind",
                "as_of_date",
                "confidence",
                "inference",
            ],
            "evidence_kind_values": ["grounded_external", "inference"],
            "confidence_values": ["low", "medium", "high"],
        }

    if role == "strategic_analyst":
        return {
            **base,
            "schema_version": STRATEGIC_SCHEMA_VERSION,
            "required_fields": [
                "schema_version",
                "company_id",
                "role",
                "status",
                "implications",
                "opportunities",
                "risks",
                "internal_public_deltas",
                "uncertainties",
            ],
        }

    if role == "evidence_critic":
        return {
            **base,
            "schema_version": CRITIC_SCHEMA_VERSION,
            "required_fields": [
                "schema_version",
                "company_id",
                "role",
                "status",
                "unsupported_claim_ids",
                "contradiction_items",
                "stale_claim_ids",
                "missing_section_ids",
                "unmet_plan_requirements",
                "citation_coverage",
                "residual_uncertainties",
                "recommendation",
            ],
            "unmet_plan_requirement_ids": list(planner_requirement_ids),
            "unmet_plan_requirement_fields": ["requirement_id", "disposition", "notes"],
            "unmet_plan_requirement_dispositions": ["unresolved_evidence", "unsatisfied"],
            "citation_coverage_fields": ["status", "notes"],
            "citation_coverage_status_values": ["sufficient", "insufficient"],
            "recommendation_values": ["pass", "fail"],
        }

    if role == "intelligence_synthesizer":
        return {
            **base,
            "schema_version": SYNTHESIS_SCHEMA_VERSION,
            "required_fields": [
                "schema_version",
                "company_id",
                "role",
                "status",
                "sections",
                "memory_candidate",
                "residual_uncertainties",
            ],
            "memory_candidate_fields": ["company_id", "target_section", "markdown", "fact_ids"],
        }

    if role == "memory_benchmark_reviewer":
        return {
            **base,
            "schema_version": BENCHMARK_SCHEMA_VERSION,
            "required_fields": [
                "schema_version",
                "company_id",
                "role",
                "status",
                "results",
            ],
            "question_ids_in_order": list(question_ids),
            "result_fields": ["question_id", "coverage", "evidence_basis"],
            "coverage_values": ["covered", "partially_covered", "not_covered"],
        }

    raise ValueError("Unknown Agent role for response contract.")



def extract_agent_json(
    envelope: Any,
    *,
    expected_role: str,
    company_id: int,
    expected_schema_version: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return one typed JSON object from a completed agent_result.v1 envelope."""
    if not isinstance(envelope, dict) or envelope.get("status") != "completed":
        raise RuntimeError(f"Agent role {expected_role} did not complete.")

    result = envelope.get("result")
    if not isinstance(result, dict):
        raise RuntimeError(f"Agent role {expected_role} returned an invalid result.")
    if result.get("schema_version") != "agent_result.v1" or result.get("kind") != "json":
        raise RuntimeError(f"Agent role {expected_role} returned an unexpected runtime result schema.")

    content = result.get("content")
    if (
        not isinstance(content, list)
        or len(content) != 1
        or not isinstance(content[0], dict)
        or content[0].get("type") != "json"
        or not isinstance(content[0].get("value"), dict)
    ):
        raise RuntimeError(f"Agent role {expected_role} returned invalid typed JSON content.")

    value = dict(content[0]["value"])
    if value.get("schema_version") != expected_schema_version:
        raise RuntimeError(f"Agent role {expected_role} returned an unexpected business schema.")
    if value.get("company_id") != company_id:
        raise RuntimeError(f"Agent role {expected_role} returned the wrong company_id.")
    if value.get("role") != expected_role:
        raise RuntimeError(f"Agent role {expected_role} returned the wrong role identity.")
    if value.get("status") != "completed":
        raise RuntimeError(f"Agent role {expected_role} returned a non-completed business status.")

    return value, result


def validate_research_payload(
    value: dict[str, Any],
    *,
    role: str,
    company_id: int,
) -> dict[str, Any]:
    """Validate one search-enabled specialist result and canonicalize its sections."""
    allowed_sections = RESEARCH_ROLE_SECTIONS.get(role)
    if allowed_sections is None:
        raise ValueError("Unknown research role.")

    sections = normalize_sections(
        value.get("sections"),
        require_all=True,
        allowed_section_ids=allowed_sections,
    )
    _require_section_content(sections)

    claims = value.get("claims")
    if not isinstance(claims, list) or len(claims) > MAX_CLAIMS:
        raise ValueError("Research claims must be a bounded list.")

    normalized_claims: list[dict[str, Any]] = []
    seen_claim_ids: set[str] = set()
    for raw in claims:
        if not isinstance(raw, dict):
            raise ValueError("Research claims must contain objects.")
        claim_id = _token(raw.get("claim_id"), "claim_id", max_chars=128)
        if claim_id in seen_claim_ids:
            raise ValueError("Research claim_id values must be unique within one role.")
        seen_claim_ids.add(claim_id)

        section_id = _token(raw.get("section_id"), "section_id", max_chars=128)
        if section_id not in allowed_sections:
            raise ValueError("Research claim section_id is outside the role scope.")

        evidence_kind = _token(raw.get("evidence_kind"), "evidence_kind", max_chars=64)
        if evidence_kind not in {"grounded_external", "inference"}:
            raise ValueError("Research claim evidence_kind is not supported.")

        confidence = _token(raw.get("confidence"), "confidence", max_chars=32)
        if confidence not in {"low", "medium", "high"}:
            raise ValueError("Research claim confidence is not supported.")

        inference = raw.get("inference")
        if not isinstance(inference, bool):
            raise ValueError("Research claim inference must be boolean.")
        if evidence_kind == "inference" and inference is not True:
            raise ValueError("Inference claims must be explicitly marked as inference.")

        as_of_date = raw.get("as_of_date")
        if as_of_date is not None:
            as_of_date = _text(as_of_date, "as_of_date", max_chars=64)

        normalized_claims.append(
            {
                "claim_id": claim_id,
                "section_id": section_id,
                "statement": _text(raw.get("statement"), "statement"),
                "evidence_kind": evidence_kind,
                "as_of_date": as_of_date,
                "confidence": confidence,
                "inference": inference,
            }
        )

    uncertainties = _text_list(value.get("uncertainties", []), "uncertainties", MAX_UNCERTAINTIES)
    if value.get("company_id") != company_id or value.get("role") != role:
        raise ValueError("Research payload identity mismatch.")

    return {
        "schema_version": RESEARCH_SCHEMA_VERSION,
        "company_id": company_id,
        "role": role,
        "status": "completed",
        "sections": sections,
        "claims": normalized_claims,
        "uncertainties": uncertainties,
    }


def validate_strategic_payload(
    value: dict[str, Any],
    *,
    company_id: int,
) -> dict[str, Any]:
    """Validate same-company strategic reasoning produced without search authority."""
    return {
        "schema_version": STRATEGIC_SCHEMA_VERSION,
        "company_id": company_id,
        "role": "strategic_analyst",
        "status": "completed",
        "implications": _text_list(value.get("implications"), "implications", MAX_LIST_ITEMS),
        "opportunities": _text_list(value.get("opportunities"), "opportunities", MAX_LIST_ITEMS),
        "risks": _text_list(value.get("risks"), "risks", MAX_LIST_ITEMS),
        "internal_public_deltas": _text_list(
            value.get("internal_public_deltas"),
            "internal_public_deltas",
            MAX_LIST_ITEMS,
        ),
        "uncertainties": _text_list(value.get("uncertainties", []), "uncertainties", MAX_UNCERTAINTIES),
    }


def validate_critic_payload(
    value: dict[str, Any],
    *,
    company_id: int,
    known_claim_ids: set[str],
    known_section_ids: set[str],
    known_plan_requirement_ids: set[str],
) -> dict[str, Any]:
    """Validate critic findings against the already-known same-company evidence."""
    unsupported = _token_list(value.get("unsupported_claim_ids", []), "unsupported_claim_ids", MAX_CLAIMS)
    stale = _token_list(value.get("stale_claim_ids", []), "stale_claim_ids", MAX_CLAIMS)
    if any(claim_id not in known_claim_ids for claim_id in unsupported + stale):
        raise ValueError("Critic referenced an unknown claim_id.")

    missing = _token_list(value.get("missing_section_ids", []), "missing_section_ids", 32)
    if any(section_id not in known_section_ids for section_id in missing):
        raise ValueError("Critic referenced an unknown section_id.")

    raw_unmet = value.get("unmet_plan_requirements")
    if not isinstance(raw_unmet, list) or len(raw_unmet) > MAX_UNMET_PLAN_REQUIREMENTS:
        raise ValueError("unmet_plan_requirements must be a bounded list.")

    unmet_plan_requirements: list[dict[str, str]] = []
    seen_requirement_ids: set[str] = set()
    for raw in raw_unmet:
        if not isinstance(raw, dict):
            raise ValueError("unmet_plan_requirements must contain objects.")
        if set(raw) != {"requirement_id", "disposition", "notes"}:
            raise ValueError("unmet_plan_requirements entries have an invalid shape.")

        requirement_id = _token(
            raw.get("requirement_id"),
            "unmet_plan_requirements.requirement_id",
            max_chars=192,
        )
        if requirement_id not in known_plan_requirement_ids:
            raise ValueError("Critic referenced an unknown planner requirement_id.")
        if requirement_id in seen_requirement_ids:
            raise ValueError("Critic planner requirement_id values must be unique.")
        seen_requirement_ids.add(requirement_id)

        disposition = _token(
            raw.get("disposition"),
            "unmet_plan_requirements.disposition",
            max_chars=32,
        )
        if disposition not in {"unresolved_evidence", "unsatisfied"}:
            raise ValueError("Critic planner requirement disposition is unsupported.")

        notes = _text(
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

    recommendation = _token(value.get("recommendation"), "recommendation", max_chars=16)
    if recommendation not in {"pass", "fail"}:
        raise ValueError("Critic recommendation must be pass or fail.")

    coverage = value.get("citation_coverage")
    if not isinstance(coverage, dict):
        raise ValueError("citation_coverage must be an object.")
    coverage_status = _token(coverage.get("status"), "citation_coverage.status", max_chars=32)
    if coverage_status not in {"sufficient", "insufficient"}:
        raise ValueError("citation_coverage.status is unsupported.")

    return {
        "schema_version": CRITIC_SCHEMA_VERSION,
        "company_id": company_id,
        "role": "evidence_critic",
        "status": "completed",
        "unsupported_claim_ids": unsupported,
        "contradiction_items": _text_list(
            value.get("contradiction_items", []),
            "contradiction_items",
            MAX_LIST_ITEMS,
        ),
        "stale_claim_ids": stale,
        "missing_section_ids": missing,
        "unmet_plan_requirements": unmet_plan_requirements,
        "citation_coverage": {
            "status": coverage_status,
            "notes": _text(coverage.get("notes", ""), "citation_coverage.notes", allow_blank=True),
        },
        "residual_uncertainties": _text_list(
            value.get("residual_uncertainties", []),
            "residual_uncertainties",
            MAX_UNCERTAINTIES,
        ),
        "recommendation": recommendation,
    }


def validate_synthesis_payload(
    value: dict[str, Any],
    *,
    company_id: int,
) -> tuple[dict[str, Any], MemoryCandidate]:
    """Validate the full canonical dossier plus the bounded memory candidate."""
    sections = normalize_sections(value.get("sections"), require_all=True)
    _require_section_content(sections)
    candidate_raw = value.get("memory_candidate")
    if not isinstance(candidate_raw, dict):
        raise ValueError("memory_candidate must be an object.")
    candidate = validate_memory_candidate(candidate_raw, company_id=company_id)
    return (
        {
            "schema_version": SYNTHESIS_SCHEMA_VERSION,
            "company_id": company_id,
            "role": "intelligence_synthesizer",
            "status": "completed",
            "sections": sections,
            "memory_candidate": {
                "company_id": candidate.company_id,
                "target_section": candidate.target_section,
                "markdown": candidate.markdown,
                "fact_ids": list(candidate.fact_ids),
            },
            "residual_uncertainties": _text_list(
                value.get("residual_uncertainties", []),
                "residual_uncertainties",
                MAX_UNCERTAINTIES,
            ),
        },
        candidate,
    )


def validate_benchmark_payload(
    value: dict[str, Any],
    *,
    company_id: int,
    expected_question_ids: tuple[str, ...],
) -> dict[str, Any]:
    """Validate deterministic question order and coverage labels."""
    rows = value.get("results")
    if not isinstance(rows, list) or len(rows) != len(expected_question_ids):
        raise ValueError("Benchmark results must match the exact question count.")

    normalized: list[dict[str, Any]] = []
    actual_ids: list[str] = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError("Benchmark results must contain objects.")
        question_id = _token(raw.get("question_id"), "question_id", max_chars=128)
        coverage = _token(raw.get("coverage"), "coverage", max_chars=32)
        if coverage not in {"covered", "partially_covered", "not_covered"}:
            raise ValueError("Benchmark coverage label is unsupported.")
        actual_ids.append(question_id)
        normalized.append(
            {
                "question_id": question_id,
                "coverage": coverage,
                "evidence_basis": _text(
                    raw.get("evidence_basis", ""),
                    "evidence_basis",
                    allow_blank=coverage == "not_covered",
                ),
            }
        )

    if tuple(actual_ids) != expected_question_ids:
        raise ValueError("Benchmark question order does not match the fixed methodology.")

    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "company_id": company_id,
        "role": "memory_benchmark_reviewer",
        "status": "completed",
        "results": normalized,
    }


def benchmark_counts(payload: dict[str, Any]) -> dict[str, int]:
    """Return deterministic coverage counts from one validated benchmark."""
    rows = payload["results"]
    return {
        "covered": sum(1 for row in rows if row["coverage"] == "covered"),
        "partially_covered": sum(1 for row in rows if row["coverage"] == "partially_covered"),
        "not_covered": sum(1 for row in rows if row["coverage"] == "not_covered"),
    }


def benchmark_improvement_count(
    before: dict[str, Any],
    after: dict[str, Any],
) -> int:
    """Count benchmark questions whose coverage rank improved."""
    ranks = {"not_covered": 0, "partially_covered": 1, "covered": 2}
    return sum(
        1
        for before_row, after_row in zip(before["results"], after["results"], strict=True)
        if ranks[after_row["coverage"]] > ranks[before_row["coverage"]]
    )


def _require_section_content(sections: list[dict[str, Any]]) -> None:
    for section in sections:
        subsections = section["subsections"]
        if subsections:
            if any(not item["content"] for item in subsections):
                raise ValueError("Every required subsection must contain explicit content.")
            if any(len(item["content"]) > MAX_TEXT_CHARS for item in subsections):
                raise ValueError("Required subsection content exceeds the downstream input bound.")
        else:
            if not section["content"]:
                raise ValueError("Every required section without subsections must contain explicit content.")
            if len(section["content"]) > MAX_TEXT_CHARS:
                raise ValueError("Required section content exceeds the downstream input bound.")


def _text(value: Any, field: str, *, max_chars: int = MAX_TEXT_CHARS, allow_blank: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string.")
    text = value.strip()
    if not allow_blank and not text:
        raise ValueError(f"{field} must not be blank.")
    if len(text) > max_chars:
        raise ValueError(f"{field} exceeds the allowed character bound.")
    return text


def _token(value: Any, field: str, *, max_chars: int) -> str:
    text = _text(value, field, max_chars=max_chars)
    if any(character.isspace() for character in text):
        raise ValueError(f"{field} must be a compact token.")
    return text


def _text_list(value: Any, field: str, maximum: int) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"{field} must be a bounded list.")
    return [_text(item, field) for item in value]


def _token_list(value: Any, field: str, maximum: int) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"{field} must be a bounded list.")
    result = [_token(item, field, max_chars=128) for item in value]
    if len(set(result)) != len(result):
        raise ValueError(f"{field} must not contain duplicates.")
    return result
