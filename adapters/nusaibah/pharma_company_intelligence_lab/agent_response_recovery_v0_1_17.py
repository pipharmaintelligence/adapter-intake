"""Version-owned JSON diagnostics and evidence-preserving Agent schema repair.

Only complete, explicitly delimited JSON is unwrapped. No substring extraction,
Python evaluation, prose removal, factual rewrite or approval fabrication occurs.
"""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any


class AgentResponseDiagnosticError(ValueError):
    def __init__(self, *, role: str, field: str, rule: str,
                 stage: str = "agent_response_payload") -> None:
        self.code = "pharma_agent_business_schema_invalid"
        self.proof_failure_detail = {
            "schema_version": "proof_failure_detail.v1", "proof_kind": "agent_contract",
            "role": role, "stage": stage, "field": field, "rule": rule,
        }
        super().__init__("Agent response violates its declared JSON contract.")


class UnresolvedAgentResponse(RuntimeError):
    """A business response was withheld after its sole backup attempt."""
    def __init__(self, diagnostic: dict[str, Any]) -> None:
        self.diagnostic = diagnostic
        self.code = "pharma_agent_business_schema_invalid"
        self.proof_failure_detail = diagnostic
        super().__init__("Agent business response remains invalid after one repair.")


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _constant(_: str) -> None:
    raise ValueError("non_finite_json")


def parse_business_json(value: Any, *, role: str) -> tuple[dict[str, Any], int]:
    """Decode one object through at most four whole-response quote/fence layers."""
    if isinstance(value, dict):
        return deepcopy(value), 0
    if not isinstance(value, str):
        raise AgentResponseDiagnosticError(role=role, field="content", rule="json_object_required",
                                           stage="agent_response_json")
    text = value.strip()
    wrappers = 0
    for _ in range(5):
        try:
            parsed = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
        except (ValueError, TypeError, RecursionError):
            parsed = None
        else:
            if isinstance(parsed, dict):
                return parsed, wrappers
            if isinstance(parsed, str) and wrappers < 4:
                text = parsed.strip(); wrappers += 1
                continue
            break
        if wrappers >= 4:
            break
        fence = re.fullmatch(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text, flags=re.IGNORECASE)
        if fence is not None:
            text = fence.group(1).strip(); wrappers += 1
            continue
        delimiter = next((mark for mark in ("'''", '"""', "'")
                          if text.startswith(mark) and text.endswith(mark)
                          and len(text) >= len(mark) * 2), None)
        if delimiter is not None:
            text = text[len(delimiter):-len(delimiter)].strip(); wrappers += 1
            continue
        break
    raise AgentResponseDiagnosticError(role=role, field="content", rule="json_object_invalid",
                                       stage="agent_response_json")


def normalize_json_envelope(envelope: Any, *, role: str) -> tuple[Any, int]:
    """Normalize only canonical completed JSON content, never runtime authority."""
    if (not isinstance(envelope, dict) or envelope.get("status") != "completed"
            or not isinstance(envelope.get("result"), dict)):
        return envelope, 0
    result = envelope["result"]
    content = result.get("content")
    if (result.get("schema_version") != "agent_result.v1" or result.get("kind") != "json"
            or not isinstance(content, list) or len(content) != 1
            or not isinstance(content[0], dict) or content[0].get("type") != "json"):
        return envelope, 0
    if isinstance(content[0].get("value"), dict):
        return envelope, 0  # preserve the normal fast path and citation envelope
    value, wrappers = parse_business_json(content[0].get("value"), role=role)
    normalized = dict(envelope)
    normalized["result"] = {**result, "content": [{**content[0], "value": value}]}
    return normalized, wrappers


LIST_FIELDS = frozenset({
    "implications", "opportunities", "risks", "internal_public_deltas", "uncertainties",
    "questions", "freshness_focus", "evidence_focus", "methodology_steps",
    "unsupported_claim_ids", "contradiction_items", "stale_claim_ids", "missing_section_ids",
    "unmet_plan_requirements", "residual_uncertainties", "results", "sections", "subsections", "fact_ids",
})
ENUMS = {
    "priority": frozenset({"high", "medium", "low"}),
    "recommendation": frozenset({"pass", "fail"}),
    "coverage": frozenset({"covered", "partially_covered", "not_covered"}),
    "disposition": frozenset({"unresolved_evidence", "unsatisfied"}),
}
NESTED_KEYS = {
    "sections": frozenset({"section_id", "content", "subsections"}),
    "subsections": frozenset({"subsection_id", "content"}),
    "results": frozenset({"question_id", "coverage", "evidence_basis"}),
    "unmet_plan_requirements": frozenset({"requirement_id", "disposition", "notes"}),
    "citation_coverage": frozenset({"status", "notes"}),
    "memory_candidate": frozenset({"company_id", "target_section", "markdown", "fact_ids"}),
}


def project_business_payload(value: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    """Forward declared business data only; unknown runtime fields are omitted."""
    def project(item: Any, field: str) -> Any:
        if isinstance(item, list):
            return [project(child, field) for child in item]
        if isinstance(item, dict):
            return {key: project(child, key) for key, child in item.items()
                    if key in NESTED_KEYS.get(field, frozenset())}
        return item if item is None or type(item) in {str, bool, int, float} else None
    return {key: project(item, key) for key, item in value.items()
            if key in contract["required_fields"]}


def formatting_normal_form(value: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    """Represent allowed structural cleanup without changing any business decision."""
    def normalize(item: Any, field: str, parent: str = "") -> Any:
        if field in LIST_FIELDS and not isinstance(item, list) and isinstance(item, (str, dict)):
            item = [item]
        if isinstance(item, list):
            return [normalize(child, "", field) for child in item]
        if isinstance(item, dict):
            return {key: normalize(child, key, field or parent) for key, child in item.items()}
        if isinstance(item, str):
            text = item.strip()
            if field == "status" and parent == "citation_coverage":
                return text.lower() if text.lower() in {"sufficient", "insufficient"} else text
            choices = ENUMS.get(field, frozenset())
            if text.lower() in choices:
                text = text.lower()
            # Planner's retained validator deliberately collapses whitespace.
            if contract.get("schema_version") == "pharma_methodology_chunk.v1":
                text = " ".join(text.split())
            return text
        return item
    normalized = normalize(project_business_payload(value, contract), "")
    def order(rows: Any, field: str, ids: list[str]) -> None:
        if (isinstance(rows, list) and all(isinstance(row, dict) and isinstance(row.get(field), str) for row in rows)
                and len(rows) == len(ids) and len({row.get(field) for row in rows}) == len(ids)
                and {row.get(field) for row in rows} == set(ids)):
            rank = {key: index for index, key in enumerate(ids)}
            rows.sort(key=lambda row: rank[row[field]])
    order(normalized.get("sections"), "section_id", contract.get("section_ids_in_order", []))
    for section in normalized.get("sections", []) if isinstance(normalized.get("sections"), list) else []:
        if isinstance(section, dict) and isinstance(section.get("section_id"), str):
            order(section.get("subsections"), "subsection_id",
                  contract.get("subsection_ids_by_section", {}).get(section.get("section_id"), []))
    order(normalized.get("results"), "question_id", contract.get("question_ids_in_order", []))
    return normalized


def require_preserved_business(original: dict[str, Any], repaired: dict[str, Any],
                               *, contract: dict[str, Any], role: str) -> None:
    if formatting_normal_form(original, contract) != formatting_normal_form(repaired, contract):
        raise AgentResponseDiagnosticError(role=role, field="business_evidence",
                                           rule="repair_changed_business_content")


def safe_diagnostic(error: Exception, *, role: str) -> dict[str, Any]:
    """Use structured proof or static role/stage identifiers; never exception prose."""
    proof = getattr(error, "proof_failure_detail", None)
    if isinstance(proof, dict):
        return dict(proof)
    return AgentResponseDiagnosticError(role=role, field="business_payload",
                                        rule="schema_invalid").proof_failure_detail


def payload_diagnostic(error: Exception, value: dict[str, Any], *,
                       role: str, contract: dict[str, Any]) -> dict[str, Any]:
    """Refine unstructured errors using only declared static field identifiers."""
    if isinstance(getattr(error, "proof_failure_detail", None), dict):
        return safe_diagnostic(error, role=role)
    for field in contract["required_fields"]:
        item = value.get(field)
        if field not in value:
            return AgentResponseDiagnosticError(role=role, field=field, rule="field_missing").proof_failure_detail
        if field in LIST_FIELDS and not isinstance(item, list):
            return AgentResponseDiagnosticError(role=role, field=field, rule="array_required").proof_failure_detail
        if field in {"memory_candidate", "citation_coverage"} and not isinstance(item, dict):
            return AgentResponseDiagnosticError(role=role, field=field, rule="object_required").proof_failure_detail
    return safe_diagnostic(error, role=role)


def nonresearch_validation_contract(role: str) -> dict[str, Any]:
    """Compact provider-visible type/bound guidance; retained validators decide."""
    common = {"company_id_type": "integer", "identity_fields": ["company_id", "role", "schema_version", "status"],
              "text_max_chars": 2000, "text_list_max_items": 64, "uncertainty_max_items": 32,
              "format": "one JSON object; no Markdown, quotes, prose, NaN or Infinity"}
    role_fields = {
        "strategic_analyst": {"string_arrays": ["implications", "opportunities", "risks", "internal_public_deltas", "uncertainties"]},
        "evidence_critic": {"string_arrays": ["unsupported_claim_ids", "contradiction_items", "stale_claim_ids", "missing_section_ids", "residual_uncertainties"],
                            "unsupported_or_stale_max_items": 16, "missing_section_max_items": 32,
                            "unmet_plan_requirements_type": "array of exact requirement_id/disposition/notes objects; max 64",
                            "citation_coverage_type": "object with status and notes strings",
                            "recommendation_type": "string; preserve original pass/fail decision"},
        "intelligence_synthesizer": {"sections_type": "array of section_id/content/subsections objects",
                                    "subsections_type": "array of subsection_id/content objects",
                                    "memory_candidate_types": {"company_id": "integer", "target_section": "string",
                                                                "markdown": "nonempty string; max 24000 chars",
                                                                "fact_ids": "unique nonempty string array; max 256"},
                                    "string_arrays": ["residual_uncertainties"]},
        "memory_benchmark_reviewer": {"results_type": "array of question_id/coverage/evidence_basis objects",
                                      "question_id_max_chars": 128, "coverage_type": "string; preserve original coverage decision"},
    }
    return {**common, **role_fields.get(role, {})}
