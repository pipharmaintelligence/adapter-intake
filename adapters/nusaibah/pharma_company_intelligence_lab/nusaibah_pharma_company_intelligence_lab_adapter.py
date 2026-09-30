from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from typing import Any, ClassVar

from adapters.base import Adapter

try:
    from .agent_contract import (
        BENCHMARK_SCHEMA_VERSION,
        CRITIC_SCHEMA_VERSION,
        MAX_CITATIONS_OUTPUT,
        RESEARCH_ROLE_SECTIONS,
        RESEARCH_SCHEMA_VERSION,
        STRATEGIC_SCHEMA_VERSION,
        SYNTHESIS_SCHEMA_VERSION,
        benchmark_counts,
        benchmark_improvement_count,
        _text,
        _token,
        validate_critic_payload,
        validate_research_payload,
        validate_strategic_payload,
        validate_synthesis_payload,
    )
    from .dossier_contract import CANONICAL_SECTIONS, DOSSIER_SCHEMA_VERSION, SECTION_BY_ID
    from .input_contract import (
        BatchRequest,
        company_name,
        order_records_for_request,
        project_company_baseline,
        resolve_company_records as _resolve_company_records_shared,
        validate_batch_request,
    )
    from .memory_contract import MEMORY_TARGET_SECTION, MemoryCandidate
    from .methodology_contract import (
        MANDATORY_RESEARCH_ROLES,
        PLANNER_PRIORITIES,
        PLANNER_ROLE,
        PLANNER_SCHEMA_VERSION,
        _PLANNER_FOCUS_KEYS,
        _PLANNER_TOP_LEVEL_KEYS,
        MethodologyPlan,
        MethodologyResources,
        load_methodology,
        validate_methodology_plan,
    )
except ImportError:  # pragma: no cover - local adapter-root execution path
    from agent_contract import (
        BENCHMARK_SCHEMA_VERSION,
        CRITIC_SCHEMA_VERSION,
        MAX_CITATIONS_OUTPUT,
        RESEARCH_ROLE_SECTIONS,
        RESEARCH_SCHEMA_VERSION,
        STRATEGIC_SCHEMA_VERSION,
        SYNTHESIS_SCHEMA_VERSION,
        benchmark_counts,
        benchmark_improvement_count,
        _text,
        _token,
        validate_critic_payload,
        validate_research_payload,
        validate_strategic_payload,
        validate_synthesis_payload,
    )
    from dossier_contract import CANONICAL_SECTIONS, DOSSIER_SCHEMA_VERSION, SECTION_BY_ID
    from input_contract import (
        BatchRequest,
        company_name,
        order_records_for_request,
        project_company_baseline,
        resolve_company_records as _resolve_company_records_shared,
        validate_batch_request,
    )
    from memory_contract import MEMORY_TARGET_SECTION, MemoryCandidate
    from methodology_contract import (
        MANDATORY_RESEARCH_ROLES,
        PLANNER_PRIORITIES,
        PLANNER_ROLE,
        PLANNER_SCHEMA_VERSION,
        _PLANNER_FOCUS_KEYS,
        _PLANNER_TOP_LEVEL_KEYS,
        MethodologyPlan,
        MethodologyResources,
        load_methodology,
        validate_methodology_plan,
    )


# Exact packaged ownership marker consumed by Assets at execute-time.
# This adapter orchestrates its Agent roles through inputs.invoke_agent(...).
AGENT_ORCHESTRATION_OWNER = "python_adapter"


RESEARCH_ROLES = (
    "portfolio_researcher",
    "market_researcher",
    "regulatory_risk_researcher",
)
STRATEGIC_ROLE = "strategic_analyst"
CRITIC_ROLE = "evidence_critic"
SYNTHESIS_ROLE = "intelligence_synthesizer"
BENCHMARK_ROLE = "memory_benchmark_reviewer"

MAX_MEMORY_CONTEXT_CHARS = 24000
MAX_CITATIONS_PER_COMPANY = 24

# 0.1.6 planner-output target. These are intentionally stricter than the
# shared helper safety ceilings so the provider receives and the adapter
# enforces one compact workload contract without mutating retained helpers.
PLANNER_CHUNK_SCHEMA_VERSION = "pharma_methodology_chunk.v1"
PLANNER_MAX_SECTION_CALLS = 4
PLANNER_MAX_QUESTIONS_PER_SECTION = 1
PLANNER_MAX_FRESHNESS_FOCUS_ITEMS_PER_SECTION = 1
PLANNER_MAX_EVIDENCE_FOCUS_ITEMS_PER_SECTION = 1
PLANNER_MAX_QUESTIONS_PER_ROLE = 3
PLANNER_MAX_FRESHNESS_FOCUS_ITEMS_PER_ROLE = 2
PLANNER_MAX_EVIDENCE_FOCUS_ITEMS_PER_ROLE = 2
PLANNER_MAX_CROSS_CUTTING_QUESTIONS = 4
PLANNER_MAX_KNOWN_MEMORY_GAPS = 4
PLANNER_MAX_EXPECTED_UNCERTAINTIES = 4
PLANNER_MAX_TEXT_CHARS = 280
PLANNER_MAX_TOTAL_JSON_CHARS = 12000

_PLANNER_SECTION_BENCHMARK_QUESTION = {
    "company_profile": "company_identity",
    "product_portfolio_intelligence": "therapeutic_focus",
    "markets_commercial_signals": "market_presence",
    "regulatory_clinical_risk_signals": "regulatory_risk",
}
_PLANNER_GLOBAL_BENCHMARK_QUESTIONS = (
    "recent_developments",
    "uncertainty",
    "novelty",
)
_COVERAGE_PRIORITY = {
    "covered": "low",
    "partially_covered": "medium",
    "not_covered": "high",
}
_PRIORITY_RANK = {"low": 0, "medium": 1, "high": 2}

# Company methodology is procedural memory, separate from factual company_memory.
METHODOLOGY_SKILL_ROLE = "company_methodology"
METHODOLOGY_SKILL_UPDATE_ROLE = "company_methodology_update"
METHODOLOGY_LEARNING_SECTION = "Methodology Learning"
METHODOLOGY_LEARNING_SCHEMA_VERSION = "pharma_methodology_learning.v1"
METHODOLOGY_LEARNING_MAX_SECTION_CHARS = 2400
METHODOLOGY_LEARNING_MAX_TOTAL_CHARS = 12000
PLANNER_MAX_METHODOLOGY_STEPS_PER_SECTION = 2


class AgentContractValidationError(RuntimeError):
    """Bounded 0.1.6 business-contract failure safe for reviewed runtime projection."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def response_contract_for_role(
    role: str,
    *,
    company_id: int,
    required_section_ids: tuple[str, ...] = (),
    question_ids: tuple[str, ...] = (),
    planner_requirement_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Return the canonical 0.1.6 JSON response contract for one Agent role."""
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
            "section_fields": ["section_id", "content", "subsections"],
            "subsection_fields": ["subsection_id", "content"],
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
            "section_fields": ["section_id", "content", "subsections"],
            "subsection_fields": ["subsection_id", "content"],
            "section_ids_in_order": [section.section_id for section in CANONICAL_SECTIONS],
            "subsection_ids_by_section": {
                section.section_id: [item.subsection_id for item in section.subsections]
                for section in CANONICAL_SECTIONS
            },
            "memory_candidate_fields": ["company_id", "target_section", "markdown", "fact_ids"],
            "memory_candidate_target_section": MEMORY_TARGET_SECTION,
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


def planner_response_contract(*, company_id: int) -> dict[str, Any]:
    """Return the compact final-plan contract assembled deterministically from chunks."""

    return {
        "schema_version": PLANNER_SCHEMA_VERSION,
        "company_id": company_id,
        "role": PLANNER_ROLE,
        "status": "completed",
        "required_fields": sorted(_PLANNER_TOP_LEVEL_KEYS),
        "research_focus_count": len(MANDATORY_RESEARCH_ROLES),
        "research_focus_roles_in_order": list(MANDATORY_RESEARCH_ROLES),
        "research_focus_fields": sorted(_PLANNER_FOCUS_KEYS),
        "priority_values": sorted(PLANNER_PRIORITIES),
        "section_ids_by_role": {
            role: list(RESEARCH_ROLE_SECTIONS[role])
            for role in MANDATORY_RESEARCH_ROLES
        },
        "compact_response_required": True,
        "compact_limits": {
            "max_questions_per_role": PLANNER_MAX_QUESTIONS_PER_ROLE,
            "max_freshness_focus_items_per_role": PLANNER_MAX_FRESHNESS_FOCUS_ITEMS_PER_ROLE,
            "max_evidence_focus_items_per_role": PLANNER_MAX_EVIDENCE_FOCUS_ITEMS_PER_ROLE,
            "max_cross_cutting_questions": PLANNER_MAX_CROSS_CUTTING_QUESTIONS,
            "max_known_memory_gaps": PLANNER_MAX_KNOWN_MEMORY_GAPS,
            "max_expected_uncertainties": PLANNER_MAX_EXPECTED_UNCERTAINTIES,
            "max_text_chars": PLANNER_MAX_TEXT_CHARS,
            "max_total_json_chars": PLANNER_MAX_TOTAL_JSON_CHARS,
        },
    }


def planner_section_response_contract(
    *,
    company_id: int,
    planner_chunk: dict[str, Any],
    priority_hint: str | None,
) -> dict[str, Any]:
    """Return one provider-visible contract for a single research section."""

    return {
        "schema_version": PLANNER_CHUNK_SCHEMA_VERSION,
        "company_id": company_id,
        "role": PLANNER_ROLE,
        "status": "completed",
        "required_fields": [
            "schema_version",
            "company_id",
            "role",
            "status",
            "chunk_id",
            "research_role",
            "section_id",
            "priority",
            "questions",
            "freshness_focus",
            "evidence_focus",
            "methodology_steps",
            "priority_rationale",
        ],
        "chunk_id": planner_chunk["chunk_id"],
        "research_role": planner_chunk["research_role"],
        "section_id": planner_chunk["section_id"],
        "priority_values": sorted(PLANNER_PRIORITIES),
        "required_priority": priority_hint,
        "compact_limits": {
            "max_questions": PLANNER_MAX_QUESTIONS_PER_SECTION,
            "max_freshness_focus_items": PLANNER_MAX_FRESHNESS_FOCUS_ITEMS_PER_SECTION,
            "max_evidence_focus_items": PLANNER_MAX_EVIDENCE_FOCUS_ITEMS_PER_SECTION,
            "max_methodology_steps": PLANNER_MAX_METHODOLOGY_STEPS_PER_SECTION,
            "max_text_chars": PLANNER_MAX_TEXT_CHARS,
            "max_priority_rationale_chars": PLANNER_MAX_TEXT_CHARS,
        },
    }


def _planner_section_catalog() -> tuple[dict[str, Any], ...]:
    """Return deterministic section chunks from the canonical dossier table of contents."""

    chunks: list[dict[str, Any]] = []
    for research_role in RESEARCH_ROLES:
        for section_id in RESEARCH_ROLE_SECTIONS[research_role]:
            section = SECTION_BY_ID[section_id]
            chunks.append(
                {
                    "chunk_id": f"{research_role}:{section_id}",
                    "research_role": research_role,
                    "section_id": section_id,
                    "section_title": section.title,
                    "subsections": [
                        {
                            "subsection_id": subsection.subsection_id,
                            "title": subsection.title,
                        }
                        for subsection in section.subsections
                    ],
                }
            )
    if len(chunks) != PLANNER_MAX_SECTION_CALLS:
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Methodology planner section catalog changed outside the reviewed call budget.",
        )
    return tuple(chunks)


def _planner_priority_hint(
    *,
    section_id: str,
    benchmark_results: dict[str, str],
) -> str | None:
    """Map known benchmark coverage to priority; leave unknown mappings to the planner."""

    question_id = _PLANNER_SECTION_BENCHMARK_QUESTION.get(section_id)
    if question_id is None:
        return None
    coverage = benchmark_results.get(question_id)
    return _COVERAGE_PRIORITY.get(coverage)


def _ordered_planner_chunks(before_benchmark: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Prioritize deterministic chunks without using another provider call."""

    benchmark_results = {
        item["question_id"]: item["coverage"]
        for item in before_benchmark.get("results", [])
        if isinstance(item, dict)
        and isinstance(item.get("question_id"), str)
        and isinstance(item.get("coverage"), str)
    }
    indexed: list[tuple[int, dict[str, Any]]] = []
    for index, chunk in enumerate(_planner_section_catalog()):
        priority_hint = _planner_priority_hint(
            section_id=chunk["section_id"],
            benchmark_results=benchmark_results,
        )
        indexed.append(
            (
                index,
                {
                    **chunk,
                    "priority_hint": priority_hint,
                },
            )
        )

    indexed.sort(
        key=lambda item: (
            -_PRIORITY_RANK.get(item[1]["priority_hint"], -1),
            item[0],
        )
    )
    return tuple(chunk for _index, chunk in indexed)


def _load_methodology_learning(inputs: Any, *, company_id: int) -> tuple[Any, str]:
    """Resolve bounded company methodology memory as a read-only planning hint."""

    handle = inputs.dynamic_skill(
        METHODOLOGY_SKILL_ROLE,
        variables={"company_id": str(company_id)},
    )
    if handle.provenance().mutable is not False:
        raise RuntimeError("company_methodology must resolve read-only.")
    if not handle.has_section(METHODOLOGY_LEARNING_SECTION):
        raise RuntimeError("Company methodology Skill is missing its learning section.")
    text = handle.section_text(METHODOLOGY_LEARNING_SECTION).strip()
    if len(text) > METHODOLOGY_LEARNING_MAX_TOTAL_CHARS:
        raise RuntimeError("Company methodology Skill exceeds its context bound.")
    return handle, text


def _planner_learned_section(
    learned_methodology_text: str,
    *,
    section_id: str,
) -> str:
    """Return only the bounded prior methodology for one selected section."""

    if not learned_methodology_text:
        return ""
    marker = f"### {section_id}"
    start = learned_methodology_text.find(marker)
    if start < 0:
        return ""
    end = learned_methodology_text.find("\n### ", start + len(marker))
    if end < 0:
        end = len(learned_methodology_text)
    value = learned_methodology_text[start:end].strip()
    if len(value) > METHODOLOGY_LEARNING_MAX_SECTION_CHARS:
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Stored learned methodology section exceeds its context bound.",
        )
    return value


def _build_methodology_learning_candidate(
    *,
    company_id: int,
    planner_chunks: tuple[dict[str, Any], ...],
    critic: dict[str, Any],
    methodology_plan: MethodologyPlan,
    benchmark_non_regression: bool,
) -> str:
    """Build a bounded procedural-learning snapshot after the critic passes."""

    if not benchmark_non_regression:
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Methodology learning requires benchmark non-regression.",
        )

    if critic.get("recommendation") != "pass":
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Methodology learning requires a passed evidence-critic recommendation.",
        )
    if critic.get("citation_coverage", {}).get("status") != "sufficient":
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Methodology learning requires sufficient citation coverage.",
        )
    if critic.get("unsupported_claim_ids"):
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Methodology learning requires no unsupported claims.",
        )
    if critic.get("missing_section_ids"):
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Methodology learning requires complete section coverage.",
        )

    lines = [
        f"<!-- schema: {METHODOLOGY_LEARNING_SCHEMA_VERSION} -->",
        f"<!-- company_id: {company_id} -->",
        "",
    ]
    for chunk in planner_chunks:
        lines.extend(
            [
                f"### {chunk['section_id']}",
                f"- priority: {chunk['priority']}",
                f"- priority_rationale: {chunk['priority_rationale']}",
                "- methodology_steps:",
            ]
        )
        for step in chunk["methodology_steps"]:
            lines.append(f"  - {step}")
        lines.extend(
            [
                "- useful_questions:",
                f"  - {chunk['questions'][0]}",
                "- evidence_focus:",
            ]
        )
        for item in chunk["evidence_focus"]:
            lines.append(f"  - {item}")
        lines.append("- freshness_focus:")
        for item in chunk["freshness_focus"]:
            lines.append(f"  - {item}")
        lines.extend(
            [
                f"- critic_recommendation: {critic['recommendation']}",
                f"- unresolved_plan_requirements: {len(critic['unmet_plan_requirements'])}",
                "",
            ]
        )

    lines.extend(
        [
            "### Cross Section Learning",
            f"- research_role_count: {len(methodology_plan.research_focus)}",
            f"- cross_cutting_question_count: {len(methodology_plan.cross_cutting_questions)}",
            f"- known_memory_gap_count: {len(methodology_plan.known_memory_gaps)}",
            f"- expected_uncertainty_count: {len(methodology_plan.expected_uncertainties)}",
        ]
    )
    candidate = "\n".join(lines).strip() + "\n"
    if len(candidate) > METHODOLOGY_LEARNING_MAX_TOTAL_CHARS:
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Methodology learning candidate exceeds the bounded snapshot size.",
        )
    return candidate


def _apply_company_methodology(
    inputs: Any,
    *,
    company_id: int,
    handle: Any,
    candidate: str,
) -> dict[str, Any]:
    """Atomically persist one complete company methodology snapshot."""

    before_digest = handle.content_digest()
    update = inputs.dynamic_skill(
        METHODOLOGY_SKILL_UPDATE_ROLE,
        variables={"company_id": str(company_id)},
    )
    if update.provenance().mutable is not True:
        raise RuntimeError("company_methodology_update must resolve mutable.")
    if update.content_digest() != before_digest:
        raise RuntimeError("Company methodology learning baseline digest mismatch.")

    targets = update.find_sections(METHODOLOGY_LEARNING_SECTION)
    if len(targets) != 1:
        raise RuntimeError("Company methodology learning section must resolve exactly once.")

    changes = update.new_changeset().replace_section(targets[0].path, candidate)
    preview = update.preview(changes)
    if preview.diff.old_digest != before_digest:
        raise RuntimeError("Company methodology preview baseline digest mismatch.")
    if preview.diff.new_digest == before_digest:
        raise RuntimeError("Company methodology preview produced no change.")

    receipt = update.apply(changes, expected_digest=before_digest)

    fresh = inputs.dynamic_skill(
        METHODOLOGY_SKILL_ROLE,
        variables={"company_id": str(company_id)},
    )
    if fresh.provenance().mutable is not False:
        raise RuntimeError("Fresh company methodology readback must be read-only.")
    if fresh.content_digest() != receipt.after_content_digest:
        raise RuntimeError("Company methodology readback digest mismatch.")
    if fresh.section_text(METHODOLOGY_LEARNING_SECTION).strip() != candidate.strip():
        raise RuntimeError("Company methodology readback content mismatch.")

    latest = fresh.history(limit=50).latest_change()
    if latest is None or latest.change_id != receipt.change_id:
        raise RuntimeError("Company methodology history change-id mismatch.")

    return {
        "methodology_learning_update_status": "applied",
        "methodology_learning_change_id": receipt.change_id,
        "methodology_learning_before_digest": before_digest,
        "methodology_learning_after_digest": receipt.after_content_digest,
        "methodology_learning_readback_verified": True,
    }


def _planner_methodology_slice(
    methodology: MethodologyResources,
    *,
    planner_chunk: dict[str, Any],
) -> dict[str, Any]:
    """Return only the global methodology needed to plan one selected section."""

    packet = methodology.planner_packet
    question_id = _PLANNER_SECTION_BENCHMARK_QUESTION.get(planner_chunk["section_id"])
    benchmark_questions = [
        dict(item)
        for item in packet.benchmark_questions
        if item.get("question_id") == question_id
    ]
    return {
        "skill_ref": packet.skill_ref,
        "skill_version": packet.skill_version,
        "skill_digest": packet.skill_digest,
        "mission": packet.mission,
        "structural_rules": list(packet.structural_rules),
        "evidence_rules": list(packet.evidence_rules),
        "role_boundaries": list(packet.role_boundaries),
        "company_isolation_rules": list(packet.company_isolation_rules),
        "output_rules": list(packet.output_rules),
        "benchmark_questions": benchmark_questions,
    }


def _benchmark_slice(
    before_benchmark: dict[str, Any],
    *,
    planner_chunk: dict[str, Any],
) -> dict[str, Any]:
    """Return only benchmark evidence directly mapped to the selected section."""

    question_id = _PLANNER_SECTION_BENCHMARK_QUESTION.get(planner_chunk["section_id"])
    results = [
        dict(item)
        for item in before_benchmark.get("results", [])
        if isinstance(item, dict) and item.get("question_id") == question_id
    ]
    return {
        "schema_version": before_benchmark.get("schema_version"),
        "company_id": before_benchmark.get("company_id"),
        "role": before_benchmark.get("role"),
        "status": before_benchmark.get("status"),
        "results": results,
    }


def _validate_planner_section(
    value: Any,
    *,
    company_id: int,
    planner_chunk: dict[str, Any],
) -> dict[str, Any]:
    """Validate one section-sized planner result before deterministic merge."""

    expected_keys = {
        "schema_version",
        "company_id",
        "role",
        "status",
        "chunk_id",
        "research_role",
        "section_id",
        "priority",
        "questions",
        "freshness_focus",
        "evidence_focus",
        "methodology_steps",
        "priority_rationale",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Methodology planner chunk returned an invalid shape.",
        )
    if value.get("schema_version") != PLANNER_CHUNK_SCHEMA_VERSION:
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Methodology planner chunk returned an invalid schema version.",
        )
    if value.get("company_id") != company_id:
        raise AgentContractValidationError(
            "pharma_agent_company_id_invalid",
            "Methodology planner chunk returned the wrong company_id.",
        )
    if value.get("role") != PLANNER_ROLE or value.get("status") != "completed":
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Methodology planner chunk identity or status is invalid.",
        )
    for field in ("chunk_id", "research_role", "section_id"):
        if value.get(field) != planner_chunk[field]:
            raise AgentContractValidationError(
                "pharma_agent_business_schema_invalid",
                f"Methodology planner chunk returned the wrong {field}.",
            )

    priority = value.get("priority")
    if priority not in PLANNER_PRIORITIES:
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Methodology planner chunk priority is unsupported.",
        )
    priority_hint = planner_chunk.get("priority_hint")
    if priority_hint is not None and priority != priority_hint:
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Methodology planner chunk did not preserve the deterministic priority.",
        )

    questions = _planner_chunk_text_list(
        value.get("questions"),
        maximum=PLANNER_MAX_QUESTIONS_PER_SECTION,
        minimum=1,
        field="questions",
    )
    freshness_focus = _planner_chunk_text_list(
        value.get("freshness_focus"),
        maximum=PLANNER_MAX_FRESHNESS_FOCUS_ITEMS_PER_SECTION,
        minimum=0,
        field="freshness_focus",
    )
    evidence_focus = _planner_chunk_text_list(
        value.get("evidence_focus"),
        maximum=PLANNER_MAX_EVIDENCE_FOCUS_ITEMS_PER_SECTION,
        minimum=0,
        field="evidence_focus",
    )
    methodology_steps = _planner_chunk_text_list(
        value.get("methodology_steps"),
        maximum=PLANNER_MAX_METHODOLOGY_STEPS_PER_SECTION,
        minimum=1,
        field="methodology_steps",
    )
    priority_rationale = _planner_chunk_text(
        value.get("priority_rationale"),
        field="priority_rationale",
    )
    return {
        "chunk_id": planner_chunk["chunk_id"],
        "research_role": planner_chunk["research_role"],
        "section_id": planner_chunk["section_id"],
        "priority": priority,
        "questions": questions,
        "freshness_focus": freshness_focus,
        "evidence_focus": evidence_focus,
        "methodology_steps": methodology_steps,
        "priority_rationale": priority_rationale,
    }


def _planner_chunk_text(
    value: Any,
    *,
    field: str,
) -> str:
    """Normalize one bounded planner text field."""

    if not isinstance(value, str):
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            f"Methodology planner chunk {field} must contain text.",
        )
    normalized = " ".join(value.split()).strip()
    if not normalized or len(normalized) > PLANNER_MAX_TEXT_CHARS:
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            f"Methodology planner chunk {field} exceeds the compact text bound.",
        )
    return normalized


def _planner_chunk_text_list(
    value: Any,
    *,
    maximum: int,
    minimum: int,
    field: str,
) -> list[str]:
    """Normalize one compact planner list without using mutable shared helpers."""

    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            f"Methodology planner chunk {field} is outside the compact item bound.",
        )
    normalized: list[str] = []
    for raw in value:
        if not isinstance(raw, str):
            raise AgentContractValidationError(
                "pharma_agent_business_schema_invalid",
                f"Methodology planner chunk {field} must contain text.",
            )
        text = " ".join(raw.split()).strip()
        if not text or len(text) > PLANNER_MAX_TEXT_CHARS:
            raise AgentContractValidationError(
                "pharma_agent_business_schema_invalid",
                f"Methodology planner chunk {field} exceeds the compact text bound.",
            )
        normalized.append(text)
    if len(set(normalized)) != len(normalized):
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            f"Methodology planner chunk {field} contains duplicates.",
        )
    return normalized


def _assemble_methodology_plan(
    *,
    company_id: int,
    methodology: MethodologyResources,
    before_benchmark: dict[str, Any],
    planner_chunks: tuple[dict[str, Any], ...],
) -> MethodologyPlan:
    """Merge section-sized planner outputs into one complete validated plan."""

    by_role: dict[str, list[dict[str, Any]]] = {role: [] for role in RESEARCH_ROLES}
    for chunk in planner_chunks:
        by_role[chunk["research_role"]].append(chunk)

    research_focus: list[dict[str, Any]] = []
    for role in RESEARCH_ROLES:
        expected_sections = RESEARCH_ROLE_SECTIONS[role]
        chunks = by_role[role]
        actual_sections = {chunk["section_id"] for chunk in chunks}
        if actual_sections != set(expected_sections) or len(chunks) != len(expected_sections):
            raise AgentContractValidationError(
                "pharma_agent_business_schema_invalid",
                "Methodology planner chunks do not cover the complete research section set.",
            )

        ordered = sorted(chunks, key=lambda chunk: expected_sections.index(chunk["section_id"]))
        priority = max(
            (chunk["priority"] for chunk in ordered),
            key=lambda value: _PRIORITY_RANK[value],
        )
        research_focus.append(
            {
                "role": role,
                "priority": priority,
                "section_ids": list(expected_sections),
                "questions": _dedupe_text(
                    item
                    for chunk in ordered
                    for item in chunk["questions"]
                ),
                "freshness_focus": _dedupe_text(
                    item
                    for chunk in ordered
                    for item in chunk["freshness_focus"]
                ),
                "evidence_focus": _dedupe_text(
                    item
                    for chunk in ordered
                    for item in chunk["evidence_focus"]
                ),
            }
        )

    benchmark_question_text = {
        item["question_id"]: item["question"]
        for item in methodology.benchmark_questions
    }
    coverage_by_question = {
        item["question_id"]: item["coverage"]
        for item in before_benchmark.get("results", [])
        if isinstance(item, dict)
        and isinstance(item.get("question_id"), str)
        and isinstance(item.get("coverage"), str)
    }
    incomplete_question_ids = [
        question_id
        for question_id, _question in benchmark_question_text.items()
        if coverage_by_question.get(question_id) != "covered"
    ]
    cross_cutting_questions = [
        benchmark_question_text[question_id]
        for question_id in _PLANNER_GLOBAL_BENCHMARK_QUESTIONS
        if question_id in benchmark_question_text
        and coverage_by_question.get(question_id) != "covered"
    ][:PLANNER_MAX_CROSS_CUTTING_QUESTIONS]
    known_memory_gaps = [
        benchmark_question_text[question_id]
        for question_id in incomplete_question_ids
    ][:PLANNER_MAX_KNOWN_MEMORY_GAPS]
    expected_uncertainties = (
        [benchmark_question_text["uncertainty"]]
        if "uncertainty" in benchmark_question_text
        and coverage_by_question.get("uncertainty") != "covered"
        else []
    )

    value = {
        "schema_version": PLANNER_SCHEMA_VERSION,
        "company_id": company_id,
        "role": PLANNER_ROLE,
        "status": "completed",
        "research_focus": research_focus,
        "cross_cutting_questions": cross_cutting_questions,
        "known_memory_gaps": known_memory_gaps,
        "expected_uncertainties": expected_uncertainties,
    }
    return _validate_compact_methodology_plan(value, company_id=company_id)


def _dedupe_text(values: Any) -> list[str]:
    """Preserve first occurrence while merging bounded section planner fragments."""

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _validate_compact_methodology_plan(
    value: Any,
    *,
    company_id: int,
) -> MethodologyPlan:
    """Validate the assembled 0.1.6 plan against strict compact output bounds."""

    try:
        plan = validate_methodology_plan(value, company_id=company_id)
    except ValueError as exc:
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Methodology planner returned an invalid business contract.",
        ) from exc

    serialized = json.dumps(
        plan.to_agent_input(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    if len(serialized) > PLANNER_MAX_TOTAL_JSON_CHARS:
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Methodology planner response exceeds the compact total-size bound.",
        )

    for focus in plan.research_focus:
        if len(focus.questions) > PLANNER_MAX_QUESTIONS_PER_ROLE:
            raise AgentContractValidationError(
                "pharma_agent_business_schema_invalid",
                "Methodology planner returned too many role questions.",
            )
        if len(focus.freshness_focus) > PLANNER_MAX_FRESHNESS_FOCUS_ITEMS_PER_ROLE:
            raise AgentContractValidationError(
                "pharma_agent_business_schema_invalid",
                "Methodology planner returned too many freshness-focus items.",
            )
        if len(focus.evidence_focus) > PLANNER_MAX_EVIDENCE_FOCUS_ITEMS_PER_ROLE:
            raise AgentContractValidationError(
                "pharma_agent_business_schema_invalid",
                "Methodology planner returned too many evidence-focus items.",
            )
        _validate_planner_text_lengths(
            (*focus.questions, *focus.freshness_focus, *focus.evidence_focus)
        )

    if len(plan.cross_cutting_questions) > PLANNER_MAX_CROSS_CUTTING_QUESTIONS:
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Methodology planner returned too many cross-cutting questions.",
        )
    if len(plan.known_memory_gaps) > PLANNER_MAX_KNOWN_MEMORY_GAPS:
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Methodology planner returned too many known-memory gaps.",
        )
    if len(plan.expected_uncertainties) > PLANNER_MAX_EXPECTED_UNCERTAINTIES:
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Methodology planner returned too many expected uncertainties.",
        )
    _validate_planner_text_lengths(
        (
            *plan.cross_cutting_questions,
            *plan.known_memory_gaps,
            *plan.expected_uncertainties,
        )
    )
    return plan


def _validate_planner_text_lengths(values: tuple[str, ...]) -> None:
    """Reject assembled planner prose beyond the 0.1.6 compact character bound."""

    if any(len(value) > PLANNER_MAX_TEXT_CHARS for value in values):
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Methodology planner text exceeds the compact character bound.",
        )

def extract_agent_json(
    envelope: Any,
    *,
    expected_role: str,
    company_id: int,
    expected_schema_version: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return typed Agent JSON while projecting reviewed 0.1.6 failure codes."""
    if not isinstance(envelope, dict) or envelope.get("status") != "completed":
        raise AgentContractValidationError(
            "pharma_agent_runtime_envelope_invalid",
            f"Agent role {expected_role} did not complete.",
        )

    result = envelope.get("result")
    if not isinstance(result, dict):
        raise AgentContractValidationError(
            "pharma_agent_runtime_result_invalid",
            f"Agent role {expected_role} returned an invalid result.",
        )
    if result.get("schema_version") != "agent_result.v1" or result.get("kind") != "json":
        raise AgentContractValidationError(
            "pharma_agent_runtime_result_invalid",
            f"Agent role {expected_role} returned an unexpected runtime result schema.",
        )

    content = result.get("content")
    if (
        not isinstance(content, list)
        or len(content) != 1
        or not isinstance(content[0], dict)
        or content[0].get("type") != "json"
        or not isinstance(content[0].get("value"), dict)
    ):
        raise AgentContractValidationError(
            "pharma_agent_runtime_result_invalid",
            f"Agent role {expected_role} returned invalid typed JSON content.",
        )

    value = dict(content[0]["value"])
    if value.get("schema_version") != expected_schema_version:
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            f"Agent role {expected_role} returned an unexpected business schema.",
        )
    if value.get("company_id") != company_id:
        raise AgentContractValidationError(
            "pharma_agent_company_id_invalid",
            f"Agent role {expected_role} returned the wrong company_id.",
        )
    if value.get("role") != expected_role:
        raise AgentContractValidationError(
            "pharma_agent_role_invalid",
            f"Agent role {expected_role} returned the wrong role identity.",
        )
    if value.get("status") != "completed":
        raise AgentContractValidationError(
            "pharma_agent_status_invalid",
            f"Agent role {expected_role} returned a non-completed business status.",
        )

    return value, result


def validate_benchmark_payload(
    value: dict[str, Any],
    *,
    company_id: int,
    expected_question_ids: tuple[str, ...],
) -> dict[str, Any]:
    """Validate benchmark output with reviewed 0.1.6 failure codes."""
    rows = value.get("results")
    if not isinstance(rows, list) or len(rows) != len(expected_question_ids):
        raise AgentContractValidationError(
            "pharma_benchmark_result_count_invalid",
            "Benchmark results must match the exact question count.",
        )

    normalized: list[dict[str, Any]] = []
    actual_ids: list[str] = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise AgentContractValidationError(
                "pharma_benchmark_result_shape_invalid",
                "Benchmark results must contain objects.",
            )
        question_id = _token(raw.get("question_id"), "question_id", max_chars=128)
        coverage = _token(raw.get("coverage"), "coverage", max_chars=32)
        if coverage not in {"covered", "partially_covered", "not_covered"}:
            raise AgentContractValidationError(
                "pharma_benchmark_coverage_invalid",
                "Benchmark coverage label is unsupported.",
            )
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
        raise AgentContractValidationError(
            "pharma_benchmark_question_order_invalid",
            "Benchmark question order does not match the fixed methodology.",
        )

    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "company_id": company_id,
        "role": BENCHMARK_ROLE,
        "status": "completed",
        "results": normalized,
    }


def resolve_company_records(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize governed company rows for the 0.1.6 database binding contract.

    The shared input_contract.py remains byte-compatible with retained
    published versions. Version-specific database schema normalization belongs
    to this 0.1.6 adapter module so older packaged identities keep their exact
    helper behavior while this version can consume id / company rows.
    """
    records = _resolve_company_records_shared(inputs)
    return [_normalize_governed_company_record(record) for record in records]


def _normalize_governed_company_record(record: dict[str, Any]) -> dict[str, Any]:
    """Map the governed Companies schema onto stable adapter semantics."""
    normalized = dict(record)

    database_id = normalized.get("id")
    semantic_id = normalized.get("company_id")
    if database_id is not None:
        if isinstance(database_id, bool) or not isinstance(database_id, int) or database_id <= 0:
            raise ValueError("Governed company record id must be a positive integer.")
        if semantic_id is not None and semantic_id != database_id:
            raise ValueError("Governed company record id and company_id must match.")
        normalized["company_id"] = database_id

    company_value = normalized.get("company")
    semantic_name = normalized.get("company_name")
    if semantic_name is None and isinstance(company_value, str) and company_value.strip():
        normalized["company_name"] = company_value.strip()

    return normalized


class NusaibahPharmaCompanyIntelligenceLabAdapter(Adapter):
    """Run a governed multi-company intelligence and memory-improvement pipeline.

    The adapter owns deterministic orchestration, schema validation, section
    rendering, quality gates, and company isolation. Runtime-owned helpers own
    provider execution, fixed/Dynamic Skill materialization, credentials,
    storage, retries, publication and remote authority.
    """

    key: ClassVar[str] = "nusaibah.pharma_company_intelligence_lab"
    version: ClassVar[str] = "0.1.6"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        """Execute one bounded company batch with two-phase memory mutation."""
        del context

        request = validate_batch_request(inputs)
        records = order_records_for_request(resolve_company_records(inputs), request)
        methodology = load_methodology(inputs)
        _require_runtime_helpers(inputs)

        prepared: list[dict[str, Any]] = []
        for record in records:
            prepared.append(
                _prepare_company(
                    inputs,
                    request=request,
                    record=record,
                    methodology=methodology,
                )
            )

        mutation_count = 0
        if request.memory_mode == "apply":
            for state in prepared:
                if state["memory_mutation_eligible"]:
                    mutation = _apply_company_memory(inputs, state)
                    state["result"].update(mutation)
                    mutation_count += 1

                # Methodology learning is committed only after the company
                # research/memory quality gate has completed successfully.
                learning_mutation = _apply_company_methodology(
                    inputs,
                    company_id=state["company_id"],
                    handle=state["methodology_learning_handle"],
                    candidate=state["methodology_learning_candidate"],
                )
                state["result"].update(learning_mutation)

        company_results = [state["result"] for state in prepared]
        dossier = {
            "schema_version": DOSSIER_SCHEMA_VERSION,
            "status": "completed",
            "requested_company_count": len(request.company_ids),
            "completed_company_count": len(company_results),
            "failed_company_count": 0,
            "publication_requested": request.publish_dossier,
            "publication_state": (
                "runtime_output_ready_for_output_policy"
                if request.publish_dossier
                else "runtime_output_only"
            ),
            "company_results": company_results,
        }

        return {
            "response_version": "1",
            "status": "success",
            "outputs": {"intelligence_dossier": dossier},
            "logs": [
                {
                    "level": "info",
                    "message": (
                        "Completed governed pharma intelligence batch for "
                        f"{len(company_results)} company contexts."
                    ),
                }
            ],
            "metrics": {
                "requested_company_count": len(request.company_ids),
                "completed_company_count": len(company_results),
                "logical_agent_invocations": (
                    sum(
                        8 + item["methodology_planner_call_count"]
                        for item in company_results
                    )
                    + mutation_count
                ),
                "search_enabled_agent_invocations": len(company_results) * 3,
                "methodology_planner_call_count": sum(
                    item["methodology_planner_call_count"] for item in company_results
                ),
                "planner_required_question_count": sum(
                    item["planner_required_question_count"] for item in company_results
                ),
                "planner_focus_item_count": sum(
                    item["planner_focus_item_count"] for item in company_results
                ),
                "planner_unmet_requirement_count": sum(
                    item["planner_unmet_requirement_count"] for item in company_results
                ),
                "research_role_count": sum(
                    item["research_role_count"] for item in company_results
                ),
                "research_claim_count": sum(
                    item["research_claim_count"] for item in company_results
                ),
                "citation_count": sum(item["citation_count"] for item in company_results),
                "quality_gate_passed_company_count": sum(
                    1 for item in company_results if item["quality_gate_passed"]
                ),
                "benchmark_improvement_count": sum(
                    item["benchmark_improvement_count"] for item in company_results
                ),
                "memory_mutations_made": mutation_count,
        "methodology_learning_mutations_made": sum(
            1 for item in company_results
            if item["methodology_learning_update_status"] == "applied"
        ),
            },
        }


def _require_runtime_helpers(inputs: Any) -> None:
    for name in ("invoke_agent", "skill", "dynamic_skill"):
        if not callable(getattr(inputs, name, None)):
            raise RuntimeError(f"Trusted runtime helper is unavailable: {name}.")


def _prepare_company(
    inputs: Any,
    *,
    request: BatchRequest,
    record: dict[str, Any],
    methodology: MethodologyResources,
) -> dict[str, Any]:
    company_id = int(record["company_id"])
    name = company_name(record)
    baseline = project_company_baseline(record)

    memory_handle = inputs.dynamic_skill(
        "company_memory",
        variables={"company_id": str(company_id)},
    )
    provenance = memory_handle.provenance()
    if provenance.mutable is not False:
        raise RuntimeError("company_memory must resolve read-only.")

    memory_text = memory_handle.read()
    if not isinstance(memory_text, str) or not memory_text.strip():
        raise RuntimeError("Existing company memory is empty.")
    if len(memory_text) > MAX_MEMORY_CONTEXT_CHARS:
        raise RuntimeError("Existing company memory exceeds the adapter context bound.")
    if not memory_handle.has_section(MEMORY_TARGET_SECTION):
        raise RuntimeError("Existing company memory is missing the approved update section.")

    before_digest = memory_handle.content_digest()
    before_target_text = memory_handle.section_text(MEMORY_TARGET_SECTION).strip()

    before_benchmark = _run_benchmark(
        inputs,
        company_id=company_id,
        company_name_value=name,
        memory_text=memory_text,
        questions=methodology.benchmark_questions,
        stage="before",
    )

    methodology_handle, methodology_learning_text = _load_methodology_learning(
        inputs,
        company_id=company_id,
    )

    methodology_plan, planner_call_count, planner_chunks = _run_methodology_planner(
        inputs,
        company_id=company_id,
        company_name_value=name,
        baseline=baseline,
        request=request,
        methodology=methodology,
        before_benchmark=before_benchmark,
        learned_methodology_text=methodology_learning_text,
    )

    research = _run_research_fanout(
        inputs,
        company_id=company_id,
        company_name_value=name,
        baseline=baseline,
        memory_text=memory_text,
        request=request,
        methodology_plan=methodology_plan,
    )
    joined = _join_research(research)

    strategic = _run_strategic(
        inputs,
        company_id=company_id,
        company_name_value=name,
        baseline=baseline,
        memory_text=memory_text,
        joined_research=joined,
        methodology_plan=methodology_plan,
    )
    critic = _run_critic(
        inputs,
        company_id=company_id,
        company_name_value=name,
        joined_research=joined,
        strategic=strategic,
        methodology=methodology,
        methodology_plan=methodology_plan,
    )
    _require_pre_synthesis_quality(research, critic)

    synthesis, candidate = _run_synthesis(
        inputs,
        company_id=company_id,
        company_name_value=name,
        baseline=baseline,
        memory_text=memory_text,
        joined_research=joined,
        strategic=strategic,
        critic=critic,
        methodology=methodology,
        methodology_plan=methodology_plan,
    )

    claim_ids = {claim["claim_id"] for claim in joined["claims"]}
    if any(fact_id not in claim_ids for fact_id in candidate.fact_ids):
        raise RuntimeError("Memory candidate referenced a fact_id not present in grounded research.")

    after_benchmark = _run_benchmark(
        inputs,
        company_id=company_id,
        company_name_value=name,
        memory_text=candidate.markdown,
        questions=methodology.benchmark_questions,
        stage="proposed",
    )

    before_counts = benchmark_counts(before_benchmark)
    after_counts = benchmark_counts(after_benchmark)
    improvement_count = benchmark_improvement_count(before_benchmark, after_benchmark)
    before_score = before_counts["covered"] * 2 + before_counts["partially_covered"]
    after_score = after_counts["covered"] * 2 + after_counts["partially_covered"]
    benchmark_non_regression = after_score >= before_score

    citations = joined["citations"]
    candidate_changed = candidate.markdown.strip() != before_target_text
    mutation_eligible = (
        bool(candidate.fact_ids)
        and candidate_changed
        and benchmark_non_regression
    )

    methodology_learning_candidate = _build_methodology_learning_candidate(
        company_id=company_id,
        planner_chunks=planner_chunks,
        critic=critic,
        methodology_plan=methodology_plan,
        benchmark_non_regression=benchmark_non_regression,
    )

    result = {
        "company_id": company_id,
        "company_name": name,
        "status": "completed",
        "sections": synthesis["sections"],
        "citation_count": len(citations),
        "citation_sources": _citation_output(citations),
        "verified_reference_count": 0,
        "unsupported_claim_count": len(critic["unsupported_claim_ids"]),
        "contradiction_count": len(critic["contradiction_items"]),
        "stale_claim_count": len(critic["stale_claim_ids"]),
        "novel_fact_count": len(candidate.fact_ids),
        "duplicate_memory_fact_count": 0,
        "methodology_planner_call_count": planner_call_count,
        "planner_required_question_count": (
            sum(len(focus.questions) for focus in methodology_plan.research_focus)
            + len(methodology_plan.cross_cutting_questions)
        ),
        "planner_focus_item_count": len(methodology_plan.research_focus),
        "planner_unmet_requirement_count": len(critic["unmet_plan_requirements"]),
        "research_role_count": len(RESEARCH_ROLES),
        "research_claim_count": len(joined["claims"]),
        "specialist_agent_call_count": 3,
        "search_enabled_agent_call_count": 3,
        "required_section_coverage_count": len(synthesis["sections"]),
        "quality_gate_passed": True,
        "benchmark_question_count": len(methodology.benchmark_questions),
        "benchmark_before_covered_count": before_counts["covered"],
        "benchmark_before_partially_covered_count": before_counts["partially_covered"],
        "benchmark_after_covered_count": after_counts["covered"],
        "benchmark_after_partially_covered_count": after_counts["partially_covered"],
        "benchmark_improvement_count": improvement_count,
        "benchmark_non_regression": benchmark_non_regression,
        "benchmark_result_basis": "projected_memory_candidate",
        "memory_mutation_eligible": mutation_eligible,
        "methodology_learning_update_status": (
            "preview_ready"
            if benchmark_non_regression and request.memory_mode in {"preview", "apply"}
            else "no_change_recommended"
        ),
        "methodology_learning_change_id": None,
        "methodology_learning_before_digest": methodology_handle.content_digest(),
        "methodology_learning_after_digest": None,
        "methodology_learning_readback_verified": False,
        "memory_update_status": (
            "preview_ready" if mutation_eligible else "no_change_recommended"
        ),
        "memory_change_id": None,
        "memory_before_digest": before_digest,
        "memory_after_digest": None,
        "memory_readback_verified": False,
        "residual_uncertainty_count": len(synthesis["residual_uncertainties"]),
    }

    return {
        "company_id": company_id,
        "company_name": name,
        "result": result,
        "before_digest": before_digest,
        "before_benchmark": before_benchmark,
        "methodology_plan": methodology_plan,
        "planner_chunks": planner_chunks,
        "methodology_learning_handle": methodology_handle,
        "methodology_learning_candidate": methodology_learning_candidate,
        "projected_after_benchmark": after_benchmark,
        "benchmark_questions": methodology.benchmark_questions,
        "memory_candidate": candidate,
        "citations": citations,
        "memory_mutation_eligible": mutation_eligible,
    }



def _run_methodology_planner(
    inputs: Any,
    *,
    company_id: int,
    company_name_value: str,
    baseline: dict[str, Any],
    request: BatchRequest,
    methodology: MethodologyResources,
    before_benchmark: dict[str, Any],
    learned_methodology_text: str,
) -> tuple[MethodologyPlan, int, tuple[dict[str, Any], ...]]:
    """Plan the full methodology through prioritized section-sized Agent calls."""

    validated_chunks: list[dict[str, Any]] = []
    ordered_chunks = _ordered_planner_chunks(before_benchmark)

    for planner_chunk in ordered_chunks:
        priority_hint = planner_chunk.get("priority_hint")
        envelope = inputs.invoke_agent(
            PLANNER_ROLE,
            input={
                "planning_stage": "section_chunk",
                "company_id": company_id,
                "company_name": company_name_value,
                "objective": request.objective,
                "research_depth": request.research_depth,
                "methodology_slice": _planner_methodology_slice(
                    methodology,
                    planner_chunk=planner_chunk,
                ),
                "governed_company_baseline": baseline,
                "memory_benchmark": _benchmark_slice(
                    before_benchmark,
                    planner_chunk=planner_chunk,
                ),
                "planner_chunk": {
                    key: value
                    for key, value in planner_chunk.items()
                    if key != "priority_hint"
                },
                "priority_hint": priority_hint,
                "learned_methodology": _planner_learned_section(
                    learned_methodology_text,
                    section_id=planner_chunk["section_id"],
                ),
                "response_contract": planner_section_response_contract(
                    company_id=company_id,
                    planner_chunk=planner_chunk,
                    priority_hint=priority_hint,
                ),
            },
            on_error="raise",
        )
        value, _ = extract_agent_json(
            envelope,
            expected_role=PLANNER_ROLE,
            company_id=company_id,
            expected_schema_version=PLANNER_CHUNK_SCHEMA_VERSION,
        )
        validated_chunks.append(
            _validate_planner_section(
                value,
                company_id=company_id,
                planner_chunk=planner_chunk,
            )
        )

    plan = _assemble_methodology_plan(
        company_id=company_id,
        methodology=methodology,
        before_benchmark=before_benchmark,
        planner_chunks=tuple(validated_chunks),
    )
    return plan, len(validated_chunks), tuple(validated_chunks)

def _run_research_fanout(
    inputs: Any,
    *,
    company_id: int,
    company_name_value: str,
    baseline: dict[str, Any],
    memory_text: str,
    request: BatchRequest,
    methodology_plan: MethodologyPlan,
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}

    def run(role: str) -> dict[str, Any]:
        required_sections = _section_requests(RESEARCH_ROLE_SECTIONS[role])
        methodology_focus = methodology_plan.role_focus(role)
        envelope = inputs.invoke_agent(
            role,
            input={
                "company_id": company_id,
                "company_name": company_name_value,
                "objective": request.objective,
                "research_depth": request.research_depth,
                "governed_company_baseline": baseline,
                "existing_company_memory": memory_text,
                "required_sections": required_sections,
                "methodology_plan": methodology_focus,
                "response_contract": response_contract_for_role(
                    role,
                    company_id=company_id,
                    required_section_ids=RESEARCH_ROLE_SECTIONS[role],
                ),
            },
            on_error="raise",
        )
        value, agent_result = extract_agent_json(
            envelope,
            expected_role=role,
            company_id=company_id,
            expected_schema_version=RESEARCH_SCHEMA_VERSION,
        )
        payload = validate_research_payload(value, role=role, company_id=company_id)
        payload["_citations"] = _agent_citations(agent_result)
        return payload

    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="pharma-research") as pool:
        futures = {pool.submit(run, role): role for role in RESEARCH_ROLES}
        for future in as_completed(futures):
            role = futures[future]
            results[role] = future.result()

    return {role: results[role] for role in RESEARCH_ROLES}


def _join_research(research: dict[str, dict[str, Any]]) -> dict[str, Any]:
    claims: list[dict[str, Any]] = []
    uncertainties: list[str] = []
    sections: list[dict[str, Any]] = []
    citations: list[Any] = []
    seen_claim_ids: set[str] = set()

    for role in RESEARCH_ROLES:
        payload = research[role]
        if not payload["claims"]:
            raise RuntimeError(f"Research role {role} returned no claims.")
        for claim in payload["claims"]:
            if claim["claim_id"] in seen_claim_ids:
                raise RuntimeError("Research claim_id values must be unique across roles.")
            seen_claim_ids.add(claim["claim_id"])
            claims.append(claim)
        sections.extend(payload["sections"])
        uncertainties.extend(payload["uncertainties"])
        citations.extend(payload["_citations"])

    citations = list(_dedupe_citations(citations))
    return {
        "sections": sections,
        "claims": claims,
        "uncertainties": uncertainties,
        "citations": citations,
        "citation_count_by_role": {
            role: len(research[role]["_citations"])
            for role in RESEARCH_ROLES
        },
    }


def _run_strategic(
    inputs: Any,
    *,
    company_id: int,
    company_name_value: str,
    baseline: dict[str, Any],
    memory_text: str,
    joined_research: dict[str, Any],
    methodology_plan: MethodologyPlan,
) -> dict[str, Any]:
    envelope = inputs.invoke_agent(
        STRATEGIC_ROLE,
        input={
            "company_id": company_id,
            "company_name": company_name_value,
            "governed_company_baseline": baseline,
            "existing_company_memory": memory_text,
            "methodology_plan": {
                "cross_cutting_questions": list(methodology_plan.cross_cutting_questions),
            },
            "research_evidence": _research_for_downstream(joined_research),
            "response_contract": response_contract_for_role(
                STRATEGIC_ROLE,
                company_id=company_id,
            ),
        },
        on_error="raise",
    )
    value, _ = extract_agent_json(
        envelope,
        expected_role=STRATEGIC_ROLE,
        company_id=company_id,
        expected_schema_version=STRATEGIC_SCHEMA_VERSION,
    )
    return validate_strategic_payload(value, company_id=company_id)


def _run_critic(
    inputs: Any,
    *,
    company_id: int,
    company_name_value: str,
    joined_research: dict[str, Any],
    strategic: dict[str, Any],
    methodology: MethodologyResources,
    methodology_plan: MethodologyPlan,
) -> dict[str, Any]:
    research_section_ids = {
        section_id
        for role in RESEARCH_ROLES
        for section_id in RESEARCH_ROLE_SECTIONS[role]
    }
    envelope = inputs.invoke_agent(
        CRITIC_ROLE,
        input={
            "company_id": company_id,
            "company_name": company_name_value,
            "methodology_packet": {
                "evidence_rules": list(methodology.planner_packet.evidence_rules),
            },
            "methodology_plan": methodology_plan.to_agent_input(),
            "planner_requirements": list(methodology_plan.requirement_catalog()),
            "research_evidence": _research_for_downstream(joined_research),
            "strategic_analysis": strategic,
            "reviewed_section_ids": sorted(research_section_ids),
            "response_contract": response_contract_for_role(
                CRITIC_ROLE,
                company_id=company_id,
                planner_requirement_ids=methodology_plan.requirement_ids(),
            ),
        },
        on_error="raise",
    )
    value, _ = extract_agent_json(
        envelope,
        expected_role=CRITIC_ROLE,
        company_id=company_id,
        expected_schema_version=CRITIC_SCHEMA_VERSION,
    )
    return validate_critic_payload(
        value,
        company_id=company_id,
        known_claim_ids={claim["claim_id"] for claim in joined_research["claims"]},
        known_section_ids=research_section_ids,
        known_plan_requirement_ids=set(methodology_plan.requirement_ids()),
    )


def _require_pre_synthesis_quality(
    research: dict[str, dict[str, Any]],
    critic: dict[str, Any],
) -> None:
    if any(len(research[role]["_citations"]) == 0 for role in RESEARCH_ROLES):
        raise RuntimeError("Every search-enabled research role must return admitted citations.")
    if critic["recommendation"] != "pass":
        raise RuntimeError("Evidence critic rejected the company evidence package.")
    if critic["citation_coverage"]["status"] != "sufficient":
        raise RuntimeError("Evidence critic reported insufficient citation coverage.")
    if critic["unsupported_claim_ids"]:
        raise RuntimeError("Unsupported research claims remain after critique.")
    if critic["missing_section_ids"]:
        raise RuntimeError("Mandatory research sections are missing after critique.")
    if any(
        item["disposition"] == "unsatisfied"
        for item in critic["unmet_plan_requirements"]
    ):
        raise RuntimeError("Mandatory methodology plan requirements remain unsatisfied.")


def _run_synthesis(
    inputs: Any,
    *,
    company_id: int,
    company_name_value: str,
    baseline: dict[str, Any],
    memory_text: str,
    joined_research: dict[str, Any],
    strategic: dict[str, Any],
    critic: dict[str, Any],
    methodology: MethodologyResources,
    methodology_plan: MethodologyPlan,
) -> tuple[dict[str, Any], MemoryCandidate]:
    envelope = inputs.invoke_agent(
        SYNTHESIS_ROLE,
        input={
            "company_id": company_id,
            "company_name": company_name_value,
            "governed_company_baseline": baseline,
            "existing_company_memory": memory_text,
            "methodology_packet": {
                "memory_rules": list(methodology.planner_packet.memory_rules),
            },
            "methodology_plan": methodology_plan.to_agent_input(),
            "research_evidence": _research_for_downstream(joined_research),
            "strategic_analysis": strategic,
            "critic_findings": critic,
            "canonical_sections": _section_requests(
                tuple(section.section_id for section in CANONICAL_SECTIONS)
            ),
            "allowed_memory_fact_ids": [
                claim["claim_id"] for claim in joined_research["claims"]
            ],
            "response_contract": {
                **response_contract_for_role(
                    SYNTHESIS_ROLE,
                    company_id=company_id,
                ),
                "dossier_schema_version": DOSSIER_SCHEMA_VERSION,
            },
        },
        on_error="raise",
    )
    value, _ = extract_agent_json(
        envelope,
        expected_role=SYNTHESIS_ROLE,
        company_id=company_id,
        expected_schema_version=SYNTHESIS_SCHEMA_VERSION,
    )
    return validate_synthesis_payload(value, company_id=company_id)


def _run_benchmark(
    inputs: Any,
    *,
    company_id: int,
    company_name_value: str,
    memory_text: str,
    questions: tuple[dict[str, str], ...],
    stage: str,
) -> dict[str, Any]:
    envelope = inputs.invoke_agent(
        BENCHMARK_ROLE,
        input={
            "company_id": company_id,
            "company_name": company_name_value,
            "memory_stage": stage,
            "memory_text": memory_text,
            "benchmark_questions": list(questions),
            "response_contract": response_contract_for_role(
                BENCHMARK_ROLE,
                company_id=company_id,
                question_ids=tuple(item["question_id"] for item in questions),
            ),
        },
        on_error="raise",
    )
    value, _ = extract_agent_json(
        envelope,
        expected_role=BENCHMARK_ROLE,
        company_id=company_id,
        expected_schema_version=BENCHMARK_SCHEMA_VERSION,
    )
    return validate_benchmark_payload(
        value,
        company_id=company_id,
        expected_question_ids=tuple(item["question_id"] for item in questions),
    )


def _apply_company_memory(inputs: Any, state: dict[str, Any]) -> dict[str, Any]:
    company_id = state["company_id"]
    before_digest = state["before_digest"]
    candidate: MemoryCandidate = state["memory_candidate"]

    handle = inputs.dynamic_skill(
        "company_memory_update",
        variables={"company_id": str(company_id)},
    )
    if handle.provenance().mutable is not True:
        raise RuntimeError("company_memory_update must resolve mutable.")
    if handle.content_digest() != before_digest:
        raise RuntimeError("Mutable company memory digest differs from the Phase-1 baseline.")

    targets = handle.find_sections(MEMORY_TARGET_SECTION)
    if len(targets) != 1:
        raise RuntimeError("Company memory update section must resolve exactly once.")
    target_path = targets[0].path

    changes = handle.new_changeset().replace_section(
        target_path,
        candidate.markdown.rstrip() + "\n",
    )
    for citation in state["citations"][:MAX_CITATIONS_PER_COMPANY]:
        changes = changes.add_citation(target_path, citation)

    preview = handle.preview(changes)
    if preview.diff.old_digest != before_digest:
        raise RuntimeError("Dynamic Skill preview baseline digest mismatch.")
    if preview.diff.new_digest == before_digest:
        raise RuntimeError("Dynamic Skill preview produced no change.")

    receipt = handle.apply(changes, expected_digest=before_digest)

    fresh = inputs.dynamic_skill(
        "company_memory",
        variables={"company_id": str(company_id)},
    )
    if fresh.provenance().mutable is not False:
        raise RuntimeError("Fresh company memory readback must be read-only.")
    if fresh.content_digest() != receipt.after_content_digest:
        raise RuntimeError("Fresh company memory readback digest mismatch.")
    if fresh.section_text(MEMORY_TARGET_SECTION).strip() != candidate.markdown.strip():
        raise RuntimeError("Fresh company memory section content mismatch.")

    final_benchmark = _run_benchmark(
        inputs,
        company_id=company_id,
        company_name_value=state["company_name"],
        memory_text=fresh.read(),
        questions=state["benchmark_questions"],
        stage="committed",
    )
    final_counts = benchmark_counts(final_benchmark)
    final_improvement_count = benchmark_improvement_count(
        state["before_benchmark"],
        final_benchmark,
    )

    history = fresh.history(limit=50)
    latest = history.latest_change()
    if latest is None or latest.change_id != receipt.change_id:
        raise RuntimeError("Fresh company memory history change-id mismatch.")
    if latest.after_content_digest != receipt.after_content_digest:
        raise RuntimeError("Fresh company memory history digest mismatch.")
    if history.latest().content_digest != receipt.after_content_digest:
        raise RuntimeError("Fresh company memory latest snapshot digest mismatch.")

    return {
        "memory_update_status": "applied",
        "memory_change_id": receipt.change_id,
        "memory_after_digest": receipt.after_content_digest,
        "memory_readback_verified": True,
        "benchmark_after_covered_count": final_counts["covered"],
        "benchmark_after_partially_covered_count": final_counts["partially_covered"],
        "benchmark_improvement_count": final_improvement_count,
        "benchmark_result_basis": "committed_memory",
    }


def _research_for_downstream(joined: dict[str, Any]) -> dict[str, Any]:
    return {
        "sections": joined["sections"],
        "claims": joined["claims"],
        "uncertainties": joined["uncertainties"],
        "citation_count_by_role": joined["citation_count_by_role"],
        "citation_sources": _citation_output(joined["citations"]),
    }


def _section_requests(section_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for section_id in section_ids:
        spec = SECTION_BY_ID[section_id]
        result.append(
            {
                "section_id": spec.section_id,
                "title": spec.title,
                "subsection_ids": [item.subsection_id for item in spec.subsections],
            }
        )
    return result


def _agent_citations(agent_result: dict[str, Any]) -> tuple[Any, ...]:
    from devtools.agent_citation_view import AgentCitationView

    return AgentCitationView.from_agent_result(agent_result).deduped_citations()


def _dedupe_citations(citations: list[Any]) -> tuple[Any, ...]:
    from devtools.skill_citation import dedupe_citations

    return dedupe_citations(citations)


def _citation_output(citations: list[Any] | tuple[Any, ...]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for citation in list(citations)[:MAX_CITATIONS_OUTPUT]:
        output.append(
            {
                "locator": citation.locator,
                "title": citation.title,
                "source_kind": citation.source_kind,
                "provider_family": citation.provider_family,
            }
        )
    return output
