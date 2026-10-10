from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from hashlib import sha256
from threading import Lock
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
        validate_strategic_payload,
        validate_synthesis_payload,
    )
    from .company_context_contract_v0_1_15 import resolve_company_context
    from .review_packet_v0_1_16 import (
        build_review_packet as _build_complete_review_packet,
        review_packet_requested, require_output_bound, canonical_bytes,
    )
    from .critic_diagnostics_v0_1_13 import validate_critic_payload
    from .research_diagnostics_v0_1_17 import (
        extract_research_json, resolve_research_payload, research_validation_contract,
        ResearchContractValidationError, repair_input_payload,
        require_repair_preserves_evidence, unresolved_research_payload,
    )
    from .portfolio_review_v0_1_17 import portfolio_review_passes
    from .evidence_recovery_v0_1_20 import (
        annex as issues_annex, issue as research_issue, diagnostic as evidence_diagnostic,
        recoverable_quality, no_evidence_payload, retained_research, partial_sections,
    )
    from .agent_response_recovery_v0_1_17 import (
        normalize_json_envelope, formatting_normal_form, project_business_payload,
        require_preserved_business, safe_diagnostic, payload_diagnostic, UnresolvedAgentResponse,
        AgentResponseDiagnosticError, nonresearch_validation_contract,
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
        validate_strategic_payload,
        validate_synthesis_payload,
    )
    from company_context_contract_v0_1_15 import resolve_company_context
    from review_packet_v0_1_16 import (
        build_review_packet as _build_complete_review_packet,
        review_packet_requested, require_output_bound, canonical_bytes,
    )
    from critic_diagnostics_v0_1_13 import validate_critic_payload
    from research_diagnostics_v0_1_17 import (
        extract_research_json, resolve_research_payload, research_validation_contract,
        ResearchContractValidationError, repair_input_payload,
        require_repair_preserves_evidence, unresolved_research_payload,
    )
    from portfolio_review_v0_1_17 import portfolio_review_passes
    from evidence_recovery_v0_1_20 import (
        annex as issues_annex, issue as research_issue, diagnostic as evidence_diagnostic,
        recoverable_quality, no_evidence_payload, retained_research, partial_sections,
    )
    from agent_response_recovery_v0_1_17 import (
        normalize_json_envelope, formatting_normal_form, project_business_payload,
        require_preserved_business, safe_diagnostic, payload_diagnostic, UnresolvedAgentResponse,
        AgentResponseDiagnosticError, nonresearch_validation_contract,
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
RESEARCH_RESOLVER_ROLE = "research_response_resolver"

MAX_MEMORY_CONTEXT_CHARS = 24000
MAX_CITATIONS_PER_COMPANY = 24
MAX_COMPANY_ITERATIONS = 5
MAX_AGENT_CALLS_PER_COMPANY_PREVIEW = 12
MAX_AGENT_CALLS_PER_COMPANY_APPLY = 13

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
    """Bounded business-contract failure with optional enum-only proof detail."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        proof_failure_detail: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.proof_failure_detail = proof_failure_detail
        super().__init__(message)


def _agent_contract_proof_detail(
    *,
    role: str,
    stage: str,
    rule: str,
    field: str | None = None,
) -> dict[str, Any]:
    """Return enum-only proof metadata; never include Agent response values."""

    detail: dict[str, Any] = {
        "schema_version": "proof_failure_detail.v1",
        "proof_kind": "agent_contract",
        "role": role,
        "stage": stage,
        "rule": rule,
    }
    if field is not None:
        detail["field"] = field
    return detail


def _planner_contract_error(
    message: str,
    *,
    rule: str,
    field: str | None = None,
) -> None:
    """Raise one planner validation failure with bounded diagnostic metadata."""

    raise AgentContractValidationError(
        "pharma_agent_business_schema_invalid",
        message,
        proof_failure_detail=_agent_contract_proof_detail(
            role=PLANNER_ROLE,
            stage="planner_section",
            rule=rule,
            field=field,
        ),
    )


def _iteration_limit_exceeded() -> None:
    raise AgentContractValidationError(
        "pharma_agent_business_schema_invalid",
        "Agent iteration limit exceeded for this bounded company run.",
        proof_failure_detail=_agent_contract_proof_detail(
            role="orchestration",
            stage="logical_agent_budget",
            rule="iteration_limit",
        ),
    )


class _BoundedAgentInputs:
    """Enforce a run-local business call budget around trusted runtime helpers.

    Counting occurs before dispatch and is never refunded after failure. The
    lock protects parallel research reservations, not provider execution.
    Provider attempts, retries and wall-clock deadlines remain runtime-owned.
    """

    def __init__(self, inputs: Any, request: BatchRequest, *, review_passes: int = 1) -> None:
        if not 1 <= len(request.company_ids) <= MAX_COMPANY_ITERATIONS:
            _iteration_limit_exceeded()
        self._inputs = inputs
        self._lock = Lock()
        self._company_calls = {company_id: 0 for company_id in request.company_ids}
        self._role_calls: dict[tuple[int, str], int] = {}
        if type(review_passes) is not int or not 1 <= review_passes <= 3:
            _iteration_limit_exceeded()
        self._ordinary_company_limit = (
            MAX_AGENT_CALLS_PER_COMPANY_APPLY
            if request.memory_mode == "apply"
            else MAX_AGENT_CALLS_PER_COMPANY_PREVIEW
        ) + review_passes - 1
        self._per_company_limit = self._ordinary_company_limit * 2
        self._role_limits = {
            PLANNER_ROLE: PLANNER_MAX_SECTION_CALLS,
            BENCHMARK_ROLE: 3 if request.memory_mode == "apply" else 2,
            "portfolio_researcher": review_passes,
            "market_researcher": 1,
            "regulatory_risk_researcher": 1,
            STRATEGIC_ROLE: 1,
            CRITIC_ROLE: 1,
            SYNTHESIS_ROLE: 1,
            RESEARCH_RESOLVER_ROLE: self._ordinary_company_limit,
        }
        self._repair_reservations: set[tuple[int, str, int]] = set()
        self._repair_dispatches: set[tuple[int, str, int]] = set()
        self.response_recovery_trace: list[dict[str, Any]] = []
        self.agent_call_limit = len(request.company_ids) * self._per_company_limit
        self.agent_call_count = 0

    def _check_available(self, company_id: Any, role: str) -> None:
        if (
            type(company_id) is not int
            or company_id not in self._company_calls
            or role not in self._role_limits
            or self.agent_call_count >= self.agent_call_limit
            or self._company_calls[company_id] >= self._per_company_limit
            or (role != RESEARCH_RESOLVER_ROLE
                and self._company_calls[company_id] - self._role_calls.get((company_id, RESEARCH_RESOLVER_ROLE), 0)
                >= self._ordinary_company_limit)
            or self._role_calls.get((company_id, role), 0) >= self._role_limits[role]
        ):
            _iteration_limit_exceeded()

    def invoke_agent(self, role: str, *, input: dict[str, Any], on_error: str = "raise") -> Any:
        company_id = input.get("company_id")
        with self._lock:
            if role == RESEARCH_RESOLVER_ROLE:
                reservation = (company_id, input.get("original_role"), input.get("original_invocation_ordinal"))
                if reservation not in self._repair_reservations or reservation in self._repair_dispatches:
                    _iteration_limit_exceeded()
                self._repair_dispatches.add(reservation)
            self._check_available(company_id, role)
            self.agent_call_count += 1
            self._company_calls[company_id] += 1
            key = (company_id, role)
            self._role_calls[key] = self._role_calls.get(key, 0) + 1
        return self._inputs.invoke_agent(role, input=input, on_error=on_error)

    def invoke_response_resolver(self, *, original_role: str, input: dict[str, Any]) -> Any:
        company_id = input["company_id"]
        with self._lock:
            ordinal = self._role_calls.get((company_id, original_role), 0)
            reservation = (company_id, original_role, ordinal)
            if (original_role == RESEARCH_RESOLVER_ROLE or ordinal < 1
                    or reservation in self._repair_reservations):
                _iteration_limit_exceeded()
            self._repair_reservations.add(reservation)
        # The backup is never processed through another backup. A failed call
        # consumes its one reservation; it cannot recurse or be refunded.
        return self.invoke_agent(RESEARCH_RESOLVER_ROLE, input={
            **input, "original_role": original_role,
            "original_invocation_ordinal": ordinal,
        }, on_error="raise")

    def record_response_recovery(self, *, company_id: int, role: str,
                                 status: str, wrappers: int = 0,
                                 diagnostic: dict[str, Any] | None = None) -> None:
        with self._lock:
            self.response_recovery_trace.append({
                "company_id": company_id, "role": role, "status": status,
                "json_wrapper_count": wrappers,
                "diagnostic": diagnostic,
            })

    def company_recovery_trace(self, company_id: int) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self.response_recovery_trace
                    if item["company_id"] == company_id]

    def company_agent_counts(self, company_id: int) -> dict[str, int]:
        with self._lock:
            return {role: count for (scope, role), count in self._role_calls.items()
                    if scope == company_id}

    def require_commit_benchmark_capacity(self, company_ids: list[int]) -> None:
        # Phase one has joined all research futures. Check the complete apply
        # phase before any company mutation; committed readback needs one call.
        with self._lock:
            if (
                len(company_ids) != len(set(company_ids))
                or self.agent_call_count + len(company_ids) > self.agent_call_limit
            ):
                _iteration_limit_exceeded()
            for company_id in company_ids:
                self._check_available(company_id, BENCHMARK_ROLE)

    def skill(self, *args: Any, **kwargs: Any) -> Any:
        return self._inputs.skill(*args, **kwargs)

    def dynamic_skill(self, *args: Any, **kwargs: Any) -> Any:
        return self._inputs.dynamic_skill(*args, **kwargs)


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
        "validation_contract": nonresearch_validation_contract(role),
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
            "validation_contract": research_validation_contract(role=role, company_id=company_id),
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
        "validation_contract": {
            "exact_fields": True,
            "text_normalization": "collapse_whitespace_and_trim",
            "fields": {
                "schema_version": {
                    "type": "string",
                    "required_value": PLANNER_CHUNK_SCHEMA_VERSION,
                },
                "company_id": {"type": "integer", "required_value": company_id},
                "role": {"type": "string", "required_value": PLANNER_ROLE},
                "status": {"type": "string", "required_value": "completed"},
                "chunk_id": {
                    "type": "string",
                    "required_value": planner_chunk["chunk_id"],
                },
                "research_role": {
                    "type": "string",
                    "required_value": planner_chunk["research_role"],
                },
                "section_id": {
                    "type": "string",
                    "required_value": planner_chunk["section_id"],
                },
                "priority": {
                    "type": "string",
                    "allowed_values": sorted(PLANNER_PRIORITIES),
                    "required_value": priority_hint,
                },
                "questions": {
                    "type": "array",
                    "min_items": 1,
                    "max_items": PLANNER_MAX_QUESTIONS_PER_SECTION,
                    "items": {
                        "type": "string",
                        "nonempty": True,
                        "max_chars": PLANNER_MAX_TEXT_CHARS,
                    },
                    "unique_after_normalization": True,
                },
                "freshness_focus": {
                    "type": "array",
                    "min_items": 0,
                    "max_items": PLANNER_MAX_FRESHNESS_FOCUS_ITEMS_PER_SECTION,
                    "items": {
                        "type": "string",
                        "nonempty": True,
                        "max_chars": PLANNER_MAX_TEXT_CHARS,
                    },
                    "unique_after_normalization": True,
                },
                "evidence_focus": {
                    "type": "array",
                    "min_items": 0,
                    "max_items": PLANNER_MAX_EVIDENCE_FOCUS_ITEMS_PER_SECTION,
                    "items": {
                        "type": "string",
                        "nonempty": True,
                        "max_chars": PLANNER_MAX_TEXT_CHARS,
                    },
                    "unique_after_normalization": True,
                },
                "methodology_steps": {
                    "type": "array",
                    "min_items": 1,
                    "max_items": PLANNER_MAX_METHODOLOGY_STEPS_PER_SECTION,
                    "items": {
                        "type": "string",
                        "nonempty": True,
                        "max_chars": PLANNER_MAX_TEXT_CHARS,
                    },
                    "unique_after_normalization": True,
                },
                "priority_rationale": {
                    "type": "string",
                    "nonempty": True,
                    "max_chars": PLANNER_MAX_TEXT_CHARS,
                },
            },
        },
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


def _load_methodology_learning(
    inputs: Any,
    *,
    company_id: int,
) -> tuple[Any | None, str]:
    """Resolve optional prior company methodology as a bounded planning hint."""

    from devtools.dynamic_skill_runtime import DynamicSkillRuntimeError

    try:
        handle = inputs.dynamic_skill(
            METHODOLOGY_SKILL_ROLE,
            variables={"company_id": str(company_id)},
        )
    except DynamicSkillRuntimeError as exc:
        if exc.code == "dynamic_skill_not_initialized":
            return None, ""
        raise

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
    handle: Any | None,
    candidate: str,
) -> dict[str, Any]:
    """Atomically persist one complete initialized company methodology snapshot."""

    if handle is None:
        raise RuntimeError(
            "Company methodology is not initialized; governed create-if-absent "
            "is required before apply."
        )

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
        return {
            "methodology_learning_update_status": "no_change_recommended",
            "methodology_learning_change_id": None,
            "methodology_learning_before_digest": before_digest,
            "methodology_learning_after_digest": before_digest,
            "methodology_learning_readback_verified": False,
        }

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

    committed_update = inputs.dynamic_skill(
        METHODOLOGY_SKILL_UPDATE_ROLE,
        variables={"company_id": str(company_id)},
    )
    if committed_update.provenance().mutable is not True:
        raise RuntimeError("Fresh company methodology update handle must remain mutable.")
    if committed_update.content_digest() != receipt.after_content_digest:
        raise RuntimeError("Fresh company methodology update digest mismatch.")

    latest = committed_update.history(limit=50).latest_change()
    if latest is None or latest.change_id != receipt.change_id:
        raise RuntimeError("Company methodology history change-id mismatch.")
    if latest.after_content_digest != receipt.after_content_digest:
        raise RuntimeError("Company methodology history digest mismatch.")

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
        _planner_contract_error(
            "Methodology planner chunk returned an invalid shape.",
            rule="shape",
        )
    if value.get("schema_version") != PLANNER_CHUNK_SCHEMA_VERSION:
        _planner_contract_error(
            "Methodology planner chunk returned an invalid schema version.",
            rule="schema_version",
            field="schema_version",
        )
    if value.get("company_id") != company_id:
        raise AgentContractValidationError(
            "pharma_agent_company_id_invalid",
            "Methodology planner chunk returned the wrong company_id.",
        )
    if value.get("role") != PLANNER_ROLE:
        _planner_contract_error(
            "Methodology planner chunk role is invalid.",
            rule="identity",
            field="role",
        )
    if value.get("status") != "completed":
        _planner_contract_error(
            "Methodology planner chunk status is invalid.",
            rule="identity",
            field="status",
        )
    for field in ("chunk_id", "research_role", "section_id"):
        if value.get(field) != planner_chunk[field]:
            _planner_contract_error(
                f"Methodology planner chunk returned the wrong {field}.",
                rule="identity",
                field=field,
            )

    priority = value.get("priority")
    if priority not in PLANNER_PRIORITIES:
        _planner_contract_error(
            "Methodology planner chunk priority is unsupported.",
            rule="enum",
            field="priority",
        )
    priority_hint = planner_chunk.get("priority_hint")
    if priority_hint is not None and priority != priority_hint:
        _planner_contract_error(
            "Methodology planner chunk did not preserve the deterministic priority.",
            rule="deterministic_value",
            field="priority",
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
        _planner_contract_error(
            f"Methodology planner chunk {field} must contain text.",
            rule="field_type",
            field=field,
        )
    normalized = " ".join(value.split()).strip()
    if not normalized:
        _planner_contract_error(
            f"Methodology planner chunk {field} must be non-empty.",
            rule="nonempty_text",
            field=field,
        )
    if len(normalized) > PLANNER_MAX_TEXT_CHARS:
        _planner_contract_error(
            f"Methodology planner chunk {field} exceeds the compact text bound.",
            rule="text_bound",
            field=field,
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

    if not isinstance(value, list):
        _planner_contract_error(
            f"Methodology planner chunk {field} must be a list.",
            rule="field_type",
            field=field,
        )
    if not minimum <= len(value) <= maximum:
        _planner_contract_error(
            f"Methodology planner chunk {field} is outside the compact item bound.",
            rule="item_count",
            field=field,
        )
    normalized: list[str] = []
    for raw in value:
        if not isinstance(raw, str):
            _planner_contract_error(
                f"Methodology planner chunk {field} must contain text.",
                rule="field_type",
                field=field,
            )
        text = " ".join(raw.split()).strip()
        if not text:
            _planner_contract_error(
                f"Methodology planner chunk {field} must contain non-empty text.",
                rule="nonempty_text",
                field=field,
            )
        if len(text) > PLANNER_MAX_TEXT_CHARS:
            _planner_contract_error(
                f"Methodology planner chunk {field} exceeds the compact text bound.",
                rule="text_bound",
                field=field,
            )
        normalized.append(text)
    if len(set(normalized)) != len(normalized):
        _planner_contract_error(
            f"Methodology planner chunk {field} contains duplicates.",
            rule="duplicate",
            field=field,
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
    envelope, _ = normalize_json_envelope(envelope, role=expected_role)
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
    if type(value.get("company_id")) is not int or value.get("company_id") != company_id:
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
    if value.get("schema_version") != expected_schema_version:
        raise AgentContractValidationError(
            "pharma_agent_business_schema_invalid",
            "Agent returned an unexpected business schema.",
            proof_failure_detail=_agent_contract_proof_detail(
                role=expected_role, stage="agent_business_schema",
                rule="schema_version", field="schema_version",
            ),
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


def _validated_agent_response(inputs: Any, envelope: Any, *, role: str,
                              company_id: int, contract: dict[str, Any],
                              validator: Any) -> Any:
    """One original call, deterministic diagnostics, at most one backup call."""
    try:
        envelope, wrappers = normalize_json_envelope(envelope, role=role)
        value, _ = extract_agent_json(envelope, expected_role=role, company_id=company_id,
                                      expected_schema_version=contract["schema_version"])
    except (AgentResponseDiagnosticError, AgentContractValidationError) as error:
        if error.code != "pharma_agent_business_schema_invalid":
            raise  # runtime envelope, status and company/role authority remain strict
        diagnostic = safe_diagnostic(error, role=role)
        inputs.record_response_recovery(company_id=company_id, role=role,
                                         status="unresolved", diagnostic=diagnostic)
        # With no faithful typed business object, a backup cannot prove that it
        # preserved content. Retain the issue, never send arbitrary raw prose.
        raise UnresolvedAgentResponse(diagnostic) from None
    try:
        validated = validator(value)
    except (ValueError, TypeError, AgentContractValidationError) as initial_error:
        diagnostic = payload_diagnostic(initial_error, value, role=role, contract=contract)
    else:
        if wrappers:
            inputs.record_response_recovery(company_id=company_id, role=role,
                                             status="json_unwrapped", wrappers=wrappers)
        return validated
    cleaned = formatting_normal_form(value, contract)
    try:
        validated = validator(cleaned)
        require_preserved_business(value, cleaned, contract=contract, role=role)
    except (ValueError, TypeError, AgentContractValidationError):
        pass
    else:
        inputs.record_response_recovery(company_id=company_id, role=role,
                                         status="deterministic_cleanup", wrappers=wrappers,
                                         diagnostic=diagnostic)
        return validated
    repaired_envelope = inputs.invoke_response_resolver(original_role=role, input={
        "company_id": company_id, "research_role": role,
        "failed_contract": diagnostic,
        "invalid_response": project_business_payload(value, contract),
        "response_contract": contract,
        "repair_scope": "business_json_format_only",
    })
    try:
        repaired_envelope, repaired_wrappers = normalize_json_envelope(repaired_envelope, role=role)
        repaired, _ = extract_agent_json(repaired_envelope, expected_role=role,
                                         company_id=company_id,
                                         expected_schema_version=contract["schema_version"])
        repaired = formatting_normal_form(repaired, contract)
        validated = validator(repaired)
        require_preserved_business(value, repaired, contract=contract, role=role)
    except AgentContractValidationError as final_error:
        if final_error.code in {"pharma_agent_company_id_invalid", "pharma_agent_role_invalid",
                                "pharma_agent_status_invalid", "pharma_agent_runtime_envelope_invalid",
                                "pharma_agent_runtime_result_invalid"}:
            raise
        final_diagnostic = safe_diagnostic(final_error, role=role)
    except (ValueError, TypeError) as final_error:
        final_diagnostic = safe_diagnostic(final_error, role=role)
    else:
        inputs.record_response_recovery(company_id=company_id, role=role, status="agent_repaired",
                                         wrappers=wrappers + repaired_wrappers,
                                         diagnostic=diagnostic)
        return validated
    inputs.record_response_recovery(company_id=company_id, role=role, status="unresolved",
                                     wrappers=wrappers, diagnostic=final_diagnostic)
    raise UnresolvedAgentResponse(final_diagnostic)


def resolve_company_records(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize governed company rows for the 0.1.6 database binding contract.

    The shared input_contract.py remains byte-compatible with retained
    published versions. Version-specific database schema normalization belongs
    to this 0.1.6 adapter module so older packaged identities keep their exact
    helper behavior while this version can consume id / company rows.
    """
    records = _resolve_company_records_shared(inputs)
    if len(records) > MAX_COMPANY_ITERATIONS:
        _iteration_limit_exceeded()
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
    version: ClassVar[str] = "0.1.20"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        """Execute one bounded company batch with two-phase memory mutation."""
        del context

        request = validate_batch_request(inputs)
        review_passes = portfolio_review_passes(inputs)
        retain_review_packet = review_packet_requested(inputs)
        records = order_records_for_request(resolve_company_context(inputs, company_ids=request.company_ids), request)
        methodology = load_methodology(inputs)
        _require_runtime_helpers(inputs)
        inputs = _BoundedAgentInputs(inputs, request, review_passes=review_passes)

        # Check every company's read prerequisites before the first paid call.
        # Runtime mutation authority and CAS are still rechecked at commit time.
        preflight = {}
        if request.memory_mode == "apply":
            inputs.require_commit_benchmark_capacity(list(request.company_ids))
            for record in records:
                company_id = int(record["company_id"])
                memory_state = _read_company_memory(inputs, company_id=company_id)
                learning = _load_methodology_learning(inputs, company_id=company_id)
                if learning[0] is None:
                    raise RuntimeError(
                        "Company methodology is not initialized; governed "
                        "create-if-absent is required before apply."
                    )
                preflight[company_id] = (memory_state, learning)

        prepared: list[dict[str, Any]] = []
        for company_iteration, record in enumerate(records, start=1):
            if company_iteration > MAX_COMPANY_ITERATIONS:
                _iteration_limit_exceeded()
            progress: dict[str, Any] = {}
            try:
                state = _prepare_company(
                    inputs,
                    request=request,
                    record=record,
                    methodology=methodology,
                    review_passes=review_passes,
                    preflight=preflight.get(int(record["company_id"])),
                    progress=progress,
                )
            except UnresolvedAgentResponse as error:
                state = _incomplete_company_state(inputs, record=record, diagnostic=error.diagnostic,
                                                  progress=progress)
            except AgentContractValidationError as error:
                if not recoverable_quality(error):
                    raise
                state = _incomplete_company_state(inputs, record=record,
                                                  diagnostic=error.proof_failure_detail, progress=progress)
            prepared.append(state)

        review_packet = None
        if retain_review_packet:
            review_packet = build_review_packet(
                prepared, asset_identity=f"{self.key}:{self.version}",
                methodology_digest=methodology.package_digest,
                memory_mode=request.memory_mode,
            )
            require_output_bound({"company_results": [state["result"] for state in prepared],
                                  "review_packet": review_packet})

        mutation_count = 0
        if request.memory_mode == "apply":
            inputs.require_commit_benchmark_capacity([
                state["company_id"] for state in prepared if state["memory_mutation_eligible"]
            ])
            # Fail before any mutation if methodology learning would need a first
            # governed package creation. Current mutation handles only update an
            # already initialized package and must not emulate create-if-absent.
            for state in prepared:
                if (
                    state["methodology_learning_candidate"] is not None
                    and state["methodology_learning_handle"] is None
                ):
                    raise RuntimeError(
                        "Company methodology is not initialized; governed "
                        "create-if-absent is required before apply."
                    )

            for state in prepared:
                if state["memory_mutation_eligible"]:
                    mutation = _apply_company_memory(inputs, state)
                    state["result"].update(mutation)
                    mutation_count += 1

                # Methodology learning is committed only after the company
                # research/memory quality gate and benchmark non-regression gate.
                methodology_candidate = state["methodology_learning_candidate"]
                if methodology_candidate is not None:
                    learning_mutation = _apply_company_methodology(
                        inputs,
                        company_id=state["company_id"],
                        handle=state["methodology_learning_handle"],
                        candidate=methodology_candidate,
                    )
                    state["result"].update(learning_mutation)

        for state in prepared:
            company_id = state["company_id"]
            state["result"]["agent_response_recovery_trace"] = inputs.company_recovery_trace(company_id)
            state["result"]["agent_response_resolver_call_count"] = inputs.company_agent_counts(company_id).get(RESEARCH_RESOLVER_ROLE, 0)
        company_results = [state["result"] for state in prepared]
        dossier = {
            "schema_version": DOSSIER_SCHEMA_VERSION,
            "status": "completed",
            "requested_company_count": len(request.company_ids),
            "completed_company_count": len(company_results),
            "failed_company_count": 0,
            "research_incomplete_company_count": sum(item["research_incomplete"] for item in company_results),
            "agent_schema_incomplete_company_count": sum(item["agent_schema_incomplete"] for item in company_results),
            "business_result_state": "incomplete" if any(item["research_incomplete"] for item in company_results) else "reviewed",
            "publication_requested": request.publish_dossier,
            "publication_state": (
                "runtime_output_ready_for_output_policy"
                if request.publish_dossier
                else "runtime_output_only"
            ),
            "company_results": company_results,
        }

        if review_packet is not None:
            dossier["review_packet"] = review_packet

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
                "logical_agent_invocations": inputs.agent_call_count,
                "search_enabled_agent_invocations": sum(item["search_enabled_agent_call_count"] for item in company_results),
                "portfolio_review_pass_count": sum(item["portfolio_review_pass_count"] for item in company_results),
                "research_response_repair_count": sum(item["research_response_repair_count"] for item in company_results),
                "research_resolver_agent_call_count": sum(item["research_resolver_agent_call_count"] for item in company_results),
                "agent_response_resolver_call_count": sum(item["agent_response_resolver_call_count"] for item in company_results),
                "agent_schema_incomplete_company_count": sum(item["agent_schema_incomplete"] for item in company_results),
                "incomplete_research_company_count": sum(item["research_incomplete"] for item in company_results),
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
                    item["benchmark_improvement_count"] or 0 for item in company_results
                ),
                "memory_mutations_made": mutation_count,
                "methodology_learning_mutations_made": sum(
                    1
                    for item in company_results
                    if item["methodology_learning_update_status"] == "applied"
                ),
            },
        }


def build_review_packet(prepared: list[dict[str, Any]], *, asset_identity: str,
                         methodology_digest: str, memory_mode: str) -> dict[str, Any]:
    """Keep historical complete packets; explicitly withhold incomplete proposals."""
    complete = [state for state in prepared if not state.get("incomplete_schema_preview")]
    packet = _build_complete_review_packet(complete, asset_identity=asset_identity,
                                           methodology_digest=methodology_digest,
                                           memory_mode=memory_mode)
    absent = {state["company_id"] for state in complete
              if state["result"].get("memory_initialized") is False}
    companies = {row["company_id"]: row for row in packet["companies"]}
    for company_id in absent:
        row = companies[company_id]
        row["memory_proposal"].update(initialized=False, initialization_required=True)
        row["benchmark"]["before_basis"] = "deterministic_absent_memory"
    for state in prepared:
        if not state.get("incomplete_schema_preview"):
            continue
        withheld = {"baseline_content_digest": None, "baseline_section_text": None,
                    "replacement_text": None, "replacement_sha256": None}
        companies[state["company_id"]] = {
            "company_id": state["company_id"], "company_name": state["company_name"],
            "preparation_status": "incomplete", "quality_gate_passed": False,
            "memory_proposal": {**withheld, "role": "company_memory",
                                "target_section": MEMORY_TARGET_SECTION,
                                "fact_ids": [], "mutation_eligible": False},
            "methodology_proposal": {**withheld, "role": "company_methodology",
                                     "target_section": "Methodology Learning", "initialized": None},
            "claims": state["retained_claims"],
            "research_role_evidence": [
                {"role": role, "sections": payload["sections"],
                 "uncertainties": payload["uncertainties"],
                 "citations": _citation_output(payload["_citations"])}
                for role, payload in state["retained_research"].items()
            ],
            "memory_apply_citations": [],
            "evidence_granularity": "research_role; retained work is not an approved candidate",
            "methodology_plan": (state["progress"]["methodology_plan"].to_agent_input()
                                 if state["progress"].get("methodology_plan") else None),
            "planner_requirements": state["progress"].get("planner_requirements", []),
            "planner_chunks": state["progress"].get("planner_chunks", []),
            "critic": state["progress"].get("critic"),
            "strategic": (None if any(item["category"] == "quality_rejected"
                                      for item in state["result"]["issues_annex"]["items"])
                          else state["progress"].get("strategic")),
            "benchmark": {"questions": [], "before": None, "projected": None,
                          "basis": "not_evaluated", "committed": None},
            "unresolved_agent_responses": state["result"]["unresolved_agent_responses"],
            "residual_uncertainties": ["Preparation is incomplete; inspect issues_annex. No canonical candidate is approved."],
        }
    for state in prepared:
        companies[state["company_id"]]["issues_annex"] = state["result"]["issues_annex"]
    packet["companies"] = [companies[state["company_id"]] for state in prepared]
    packet.pop("packet_sha256")
    packet["packet_sha256"] = "sha256:" + sha256(canonical_bytes(packet)).hexdigest()
    require_output_bound(packet)
    return packet


def _incomplete_company_state(inputs: Any, *, record: dict[str, Any],
                              diagnostic: dict[str, Any], progress: dict[str, Any] | None = None) -> dict[str, Any]:
    """Retain a truthful preview without synthesizing a plan, verdict or candidate."""
    company_id = int(record["company_id"])
    counts = inputs.company_agent_counts(company_id)
    progress = progress or {}
    research = progress.get("research", {})
    retained = retained_research(research, progress.get("critic"))
    retained_claims = [claim for claim in progress.get("joined_research", {}).get("claims", [])
                       if claim["claim_id"].split(":", 1)[0] in retained]
    citations = _dedupe_citations([item for payload in retained.values() for item in payload["_citations"]])
    critic = progress.get("critic") or {}
    issue_report = issues_annex(research, diagnostic)
    schema_incomplete = any(item["category"] == "response_invalid" for item in issue_report["items"])
    result = {key: 0 for key in (
        "citation_count", "verified_reference_count", "unsupported_claim_count", "contradiction_count",
        "stale_claim_count", "novel_fact_count", "duplicate_memory_fact_count",
        "planner_required_question_count", "planner_focus_item_count", "planner_unmet_requirement_count",
        "research_role_count", "research_claim_count", "portfolio_review_pass_count",
        "portfolio_reflection_pass_count", "research_resolver_agent_call_count",
        "research_response_repair_count", "required_section_coverage_count",
        "benchmark_question_count", "benchmark_before_covered_count", "benchmark_before_partially_covered_count",
        "benchmark_after_covered_count", "benchmark_after_partially_covered_count", "benchmark_improvement_count",
    )}
    result.update({
        "company_id": company_id, "company_name": company_name(record), "status": "completed",
        "business_result_state": "incomplete", "agent_schema_incomplete": schema_incomplete,
        "research_incomplete": True,
        "unresolved_agent_responses": [diagnostic] if schema_incomplete else [],
        "unresolved_research_responses": [payload["_unresolved_response"] for payload in research.values()
                                           if payload.get("_unresolved_response")],
        "quality_gate_passed": False, "issues_annex": issue_report,
        "unsupported_claim_count": len(critic.get("unsupported_claim_ids", [])),
        "contradiction_count": len(critic.get("contradiction_items", [])),
        "stale_claim_count": len(critic.get("stale_claim_ids", [])),
        "planner_unmet_requirement_count": len(critic.get("unmet_plan_requirements", [])),
        "planner_required_question_count": len(progress.get("planner_requirements", [])),
        "planner_focus_item_count": (len(progress["methodology_plan"].research_focus)
                                     if progress.get("methodology_plan") else 0),
        "benchmark_non_regression": None, "benchmark_result_basis": "not_evaluated",
        "sections": partial_sections(retained), "research_evidence_state": "retained_pending_final_review",
        "citation_sources": _citation_output(citations), "citation_count": len(citations),
        "research_claim_count": len(retained_claims), "research_role_count": len(research),
        "portfolio_review_trace": research.get("portfolio_researcher", {}).get("_review_trace", []),
        "portfolio_review_pass_count": counts.get("portfolio_researcher", 0),
        "portfolio_reflection_pass_count": max(0, counts.get("portfolio_researcher", 0) - 1),
        "research_response_repairs": [{"role": role, **repair} for role, payload in research.items()
                                       for repair in payload["_response_repairs"]],
        "research_response_repair_count": sum(repair["count"] for payload in research.values()
                                              for repair in payload["_response_repairs"]),
        "research_resolver_agent_call_count": sum(payload["_resolver_call_count"] for payload in research.values()),
        "no_evidence_research_roles": [role for role in RESEARCH_ROLES if not retained.get(role, {}).get("claims")],
        "methodology_planner_call_count": counts.get(PLANNER_ROLE, 0),
        "specialist_agent_call_count": sum(counts.get(role, 0) for role in RESEARCH_ROLES),
        "search_enabled_agent_call_count": sum(counts.get(role, 0) for role in RESEARCH_ROLES),
        "portfolio_review_passes_requested": inputs._role_limits["portfolio_researcher"],
        "agent_response_resolver_call_count": counts.get(RESEARCH_RESOLVER_ROLE, 0),
        "agent_response_recovery_trace": inputs.company_recovery_trace(company_id),
        "memory_mutation_eligible": False, "memory_update_status": "withheld_incomplete",
        "methodology_learning_update_status": "withheld_incomplete",
        "memory_change_id": None, "memory_before_digest": None, "memory_after_digest": None,
        "memory_readback_verified": False, "methodology_learning_change_id": None,
        "methodology_learning_before_digest": None, "methodology_learning_after_digest": None,
        "methodology_learning_readback_verified": False, "residual_uncertainty_count": 1,
    })
    for field in ("benchmark_before_covered_count", "benchmark_before_partially_covered_count",
                  "benchmark_after_covered_count", "benchmark_after_partially_covered_count",
                  "benchmark_improvement_count"):
        result[field] = None  # unknown/unscored is not a fabricated zero benchmark
    return {"company_id": company_id, "company_name": company_name(record), "result": result,
            "incomplete_schema_preview": True, "memory_mutation_eligible": False,
            "progress": progress, "retained_research": retained, "retained_claims": retained_claims,
            "methodology_learning_candidate": None, "methodology_learning_handle": None}


def _require_runtime_helpers(inputs: Any) -> None:
    for name in ("invoke_agent", "skill", "dynamic_skill"):
        if not callable(getattr(inputs, name, None)):
            raise RuntimeError(f"Trusted runtime helper is unavailable: {name}.")


def _read_company_memory(inputs: Any, *, company_id: int,
                         allow_absent: bool = False) -> dict[str, Any]:
    from devtools.dynamic_skill_runtime import DynamicSkillRuntimeError

    try:
        memory_handle = inputs.dynamic_skill(
            "company_memory", variables={"company_id": str(company_id)},
        )
    except DynamicSkillRuntimeError as exc:
        if allow_absent and exc.code == "dynamic_skill_not_initialized":
            # An absent package is not an empty initialized package or a write handle.
            return {"handle": None, "text": "", "digest": None, "target_text": None}
        raise
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

    return {
        "handle": memory_handle, "text": memory_text, "digest": before_digest,
        "target_text": before_target_text,
    }


def _prepare_company(
    inputs: Any,
    *,
    request: BatchRequest,
    record: dict[str, Any],
    methodology: MethodologyResources,
    preflight: tuple[Any, Any] | None = None,
    review_passes: int = 1,
    progress: dict[str, Any] | None = None,
) -> dict[str, Any]:
    progress = progress if progress is not None else {}
    company_id = int(record["company_id"])
    name = company_name(record)
    baseline = project_company_baseline(record)

    memory_state = (preflight[0] if preflight is not None
                    else _read_company_memory(inputs, company_id=company_id,
                                              allow_absent=request.memory_mode == "preview"))
    memory_text = memory_state["text"]
    before_digest = memory_state["digest"]
    before_target_text = memory_state["target_text"]
    memory_initialized = memory_state["handle"] is not None

    methodology_handle, methodology_learning_text = (
        preflight[1] if preflight is not None
        else _load_methodology_learning(inputs, company_id=company_id)
    )

    if memory_initialized:
        before_benchmark = _run_benchmark(
            inputs, company_id=company_id, company_name_value=name,
            memory_text=memory_text, questions=methodology.benchmark_questions,
            stage="before",
        )
    else:
        # No memory can cover a question. This is deterministic source-absence
        # accounting, not an Agent judgement or fabricated existing content.
        before_benchmark = {
            "schema_version": BENCHMARK_SCHEMA_VERSION, "company_id": company_id,
            "role": BENCHMARK_ROLE, "status": "completed",
            "results": [{"question_id": question["question_id"], "coverage": "not_covered",
                         "evidence_basis": "No company memory package is initialized."}
                        for question in methodology.benchmark_questions],
        }

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
    progress.update(methodology_plan=methodology_plan, planner_chunks=planner_chunks,
                    planner_requirements=list(methodology_plan.requirement_catalog()))

    research = _run_research_fanout(
        inputs,
        company_id=company_id,
        company_name_value=name,
        baseline=baseline,
        memory_text=memory_text,
        request=request,
        methodology_plan=methodology_plan,
        methodology=methodology,
        learned_methodology_text=methodology_learning_text,
        review_passes=review_passes,
    )
    joined = _join_research(research)
    progress.update(research=research, joined_research=joined)
    research_incomplete = any(payload.get("_unresolved_response") for payload in research.values())
    if not joined["claims"]:
        # Do not pay for a reflection/critic/synthesis without usable evidence,
        # or invent a memory candidate merely to satisfy its nonempty contract.
        raise UnresolvedAgentResponse(evidence_diagnostic(
            role="orchestration", stage="pre_synthesis_quality",
            rule="no_usable_research_evidence", field="claims",
        ))

    strategic = _run_strategic(
        inputs,
        company_id=company_id,
        company_name_value=name,
        baseline=baseline,
        memory_text=memory_text,
        joined_research=joined,
        methodology_plan=methodology_plan,
    )
    progress["strategic"] = strategic
    critic = _run_critic(
        inputs,
        company_id=company_id,
        company_name_value=name,
        joined_research=joined,
        strategic=strategic,
        methodology=methodology,
        methodology_plan=methodology_plan,
    )
    progress["critic"] = critic
    _require_pre_synthesis_quality(research, critic, methodology_plan=methodology_plan)

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
    candidate_eligible = (
        bool(candidate.fact_ids)
        and candidate_changed
        and benchmark_non_regression
        and not research_incomplete
    )

    mutation_eligible = memory_initialized and candidate_eligible

    methodology_learning_candidate = (
        _build_methodology_learning_candidate(
            company_id=company_id,
            planner_chunks=planner_chunks,
            critic=critic,
            methodology_plan=methodology_plan,
            benchmark_non_regression=True,
        )
        if benchmark_non_regression and not research_incomplete
        else None
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
        "specialist_agent_call_count": 2 + len(research["portfolio_researcher"]["_review_trace"]),
        "search_enabled_agent_call_count": 2 + len(research["portfolio_researcher"]["_review_trace"]),
        "portfolio_review_passes_requested": review_passes,
        "portfolio_review_pass_count": len(research["portfolio_researcher"]["_review_trace"]),
        "portfolio_reflection_pass_count": max(0, len(research["portfolio_researcher"]["_review_trace"]) - 1),
        "portfolio_review_trace": research["portfolio_researcher"]["_review_trace"],
        "research_resolver_agent_call_count": sum(payload["_resolver_call_count"] for payload in research.values()),
        "research_incomplete": research_incomplete,
        "business_result_state": "incomplete" if research_incomplete else "reviewed",
        "issues_annex": issues_annex(research),
        "agent_schema_incomplete": False,
        "unresolved_agent_responses": [],
        "agent_response_resolver_call_count": inputs.company_agent_counts(company_id).get(RESEARCH_RESOLVER_ROLE, 0),
        "agent_response_recovery_trace": inputs.company_recovery_trace(company_id),
        "unresolved_research_responses": [
            payload["_unresolved_response"] for payload in research.values() if payload.get("_unresolved_response")
        ],
        "research_response_repair_count": sum(
            repair["count"] for payload in research.values() for repair in payload["_response_repairs"]
        ),
        "research_response_repairs": [
            {"role": role, **repair} for role, payload in research.items() for repair in payload["_response_repairs"]
        ],
        "no_evidence_research_roles": [role for role in RESEARCH_ROLES if not research[role]["claims"]],
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
        "memory_initialized": memory_initialized,
        "memory_initialization_required": not memory_initialized,
        "benchmark_before_basis": (
            "existing_memory_agent_review" if memory_initialized else "deterministic_absent_memory"
        ),
        "methodology_learning_update_status": (
            "withheld_incomplete" if research_incomplete
            else "preview_ready" if methodology_learning_candidate is not None
            else "no_change_recommended"
        ),
        "methodology_learning_change_id": None,
        "methodology_learning_before_digest": (
            methodology_handle.content_digest()
            if methodology_handle is not None
            else None
        ),
        "methodology_learning_after_digest": None,
        "methodology_learning_readback_verified": False,
        "memory_update_status": (
            "withheld_incomplete" if research_incomplete else "preview_ready" if candidate_eligible else "no_change_recommended"
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
        "before_target_text": before_target_text,
        "methodology_learning_before_text": methodology_learning_text,
        "research": research,
        "joined_research": joined,
        "critic": critic,
        "strategic": strategic,
        "residual_uncertainties": synthesis["residual_uncertainties"],
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

    for planner_iteration, planner_chunk in enumerate(ordered_chunks, start=1):
        if planner_iteration > PLANNER_MAX_SECTION_CALLS:
            _iteration_limit_exceeded()
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
        validated_chunks.append(_validated_agent_response(
            inputs, envelope, role=PLANNER_ROLE, company_id=company_id,
            contract=planner_section_response_contract(
                company_id=company_id, planner_chunk=planner_chunk, priority_hint=priority_hint),
            validator=lambda value: _validate_planner_section(
                value, company_id=company_id, planner_chunk=planner_chunk),
        ))

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
    methodology: MethodologyResources,
    learned_methodology_text: str,
    review_passes: int,
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}

    def run(role: str) -> dict[str, Any]:
        required_sections = _section_requests(RESEARCH_ROLE_SECTIONS[role])
        methodology_focus = methodology_plan.role_focus(role)
        learned_sections = [
            _planner_learned_section(learned_methodology_text, section_id=section_id)
            for section_id in RESEARCH_ROLE_SECTIONS[role]
        ]
        base_input = {
                "company_id": company_id,
                "company_name": company_name_value,
                "objective": request.objective,
                "research_depth": request.research_depth,
                "governed_company_baseline": baseline,
                "existing_company_memory": memory_text,
                "required_sections": required_sections,
                "methodology_plan": methodology_focus,
                "methodology_packet": {
                    "skill_ref": methodology.planner_packet.skill_ref,
                    "version": methodology.planner_packet.skill_version,
                    "package_digest": methodology.package_digest,
                    "evidence_rules": list(methodology.planner_packet.evidence_rules),
                    "role_boundaries": list(methodology.planner_packet.role_boundaries),
                    "company_isolation_rules": list(methodology.planner_packet.company_isolation_rules),
                },
                "learned_methodology": "\n\n".join(text for text in learned_sections if text),
                "response_contract": response_contract_for_role(
                    role,
                    company_id=company_id,
                    required_section_ids=RESEARCH_ROLE_SECTIONS[role],
                ),
        }
        passes = review_passes if role == "portfolio_researcher" else 1
        payload: dict[str, Any] | None = None
        citations: list[Any] = []
        repairs: list[dict[str, Any]] = []
        trace: list[dict[str, Any]] = []
        resolver_calls = 0
        unresolved = None
        issue_entry = None
        for pass_number in range(1, passes + 1):
            previous = None if payload is None else {
                key: item for key, item in payload.items() if not key.startswith("_")
            }
            if previous is not None:
                previous["citation_sources"] = _citation_output(citations)
            envelope = inputs.invoke_agent(role, input={
                **base_input,
                "portfolio_review": {
                    "pass_number": pass_number, "total_passes": passes,
                    "stage": "initial_review" if pass_number == 1 else "reflection",
                    "previous_result": previous,
                },
            }, on_error="raise")
            try:
                envelope, wrappers = normalize_json_envelope(envelope, role=role)
                value, agent_result = extract_agent_json(
                    envelope, expected_role=role, company_id=company_id,
                    expected_schema_version=RESEARCH_SCHEMA_VERSION,
                )
            except (AgentResponseDiagnosticError, AgentContractValidationError) as error:
                if error.code != "pharma_agent_business_schema_invalid":
                    raise
                unresolved = safe_diagnostic(error, role=role)
                next_payload, pass_repairs, agent_result = None, [], None
                inputs.record_response_recovery(company_id=company_id, role=role,
                                                 status="unresolved", diagnostic=unresolved)
            else:
                if wrappers:
                    inputs.record_response_recovery(company_id=company_id, role=role,
                                                     status="json_unwrapped", wrappers=wrappers)
                try:
                    next_payload, pass_repairs = resolve_research_payload(value, role=role, company_id=company_id)
                except ResearchContractValidationError as initial_error:
                    if initial_error.proof_failure_detail["rule"] == "explicit_evidence_gap_required":
                        unresolved = initial_error.proof_failure_detail
                        next_payload, pass_repairs = None, []
                        inputs.record_response_recovery(company_id=company_id, role=role,
                                                         status="evidence_withheld", diagnostic=unresolved)
                    else:
                        resolver_calls += 1
                        next_payload, pass_repairs, unresolved = _repair_research_response(
                            inputs, value=value, role=role, company_id=company_id,
                            initial_error=initial_error,
                        )
            repairs.extend({"pass_number": pass_number, **item} for item in pass_repairs)
            try:
                admitted = () if unresolved is not None else _agent_citations(agent_result)
            except ValueError:
                raise AgentContractValidationError(
                    "pharma_agent_business_schema_invalid",
                    "Research citation evidence failed its runtime contract.",
                    proof_failure_detail=_agent_contract_proof_detail(
                        role=role, stage="research_citations", rule="invalid_schema", field="citations",
                    ),
                ) from None
            withheld_count = 0
            if unresolved is None and not admitted and (next_payload["claims"] or payload is not None):
                # Every new pass needs its own admitted evidence. Earlier citations
                # cannot confer blanket authority on uncited reflection claims.
                withheld_count = len(next_payload["claims"])
                unresolved = evidence_diagnostic(role=role, stage="pre_synthesis_quality",
                                                 rule="research_citations_missing", field="citations")
                inputs.record_response_recovery(company_id=company_id, role=role,
                                                 status="evidence_withheld", diagnostic=unresolved)
            if unresolved is not None:
                issue_entry = research_issue(
                    unresolved,
                    category="evidence_unavailable" if unresolved["rule"] in {"research_citations_missing", "explicit_evidence_gap_required"} else "response_invalid",
                    action="previous_validated_pass_retained" if payload is not None else "withheld",
                    withheld_claim_count=withheld_count, pass_number=pass_number,
                )
                next_payload = payload if payload is not None else no_evidence_payload(role=role, company_id=company_id)
            else:
                if not admitted:
                    # A claimless role must not leak uncited facts through prose.
                    next_payload = no_evidence_payload(role=role, company_id=company_id)
                citations = list(_dedupe_citations(citations + list(admitted)))
            payload = next_payload
            trace.append({
                "pass_number": pass_number,
                "stage": "initial_review" if pass_number == 1 else "reflection",
                "status": "unresolved" if unresolved is not None else "validated" if admitted else "no_evidence",
                "previous_result_sha256": None if previous is None else _research_digest(previous),
                "result_sha256": _research_digest({**payload, "citation_sources": _citation_output(citations)}),
                "learned_methodology_used": bool(base_input["learned_methodology"]),
                "claim_count": len(payload["claims"]), "citation_count": len(citations),
            })
            if unresolved is not None or not payload["claims"]:
                break  # no reflection on withheld evidence and no repair loop
        assert payload is not None  # bounded configuration was checked before dispatch
        payload["_citations"] = tuple(citations)
        payload["_response_repairs"] = repairs
        payload["_review_trace"] = trace
        payload["_resolver_call_count"] = resolver_calls
        payload["_unresolved_response"] = unresolved
        payload["_issue"] = issue_entry
        return payload

    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="pharma-research") as pool:
        futures = {pool.submit(run, role): role for role in RESEARCH_ROLES}
        for future in as_completed(futures):
            role = futures[future]
            results[role] = future.result()

    return {role: results[role] for role in RESEARCH_ROLES}


def _research_digest(value: dict[str, Any]) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                        separators=(",", ":")).encode("utf-8")).hexdigest()


def _repair_research_response(
    inputs: Any, *, value: dict[str, Any], role: str, company_id: int,
    initial_error: ResearchContractValidationError,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], dict[str, Any] | None]:
    repair_envelope = inputs.invoke_response_resolver(original_role=role, input={
        "company_id": company_id, "research_role": role,
        "failed_contract": initial_error.proof_failure_detail,
        "invalid_response": repair_input_payload(value),
        "response_contract": response_contract_for_role(role, company_id=company_id),
        "repair_scope": "research_business_json",
    })
    try:
        # Invalid backup syntax is withheld; identity/runtime authority still rejects.
        repaired, _ = extract_agent_json(repair_envelope, expected_role=role, company_id=company_id,
                                         expected_schema_version=RESEARCH_SCHEMA_VERSION)
        payload, repairs = resolve_research_payload(repaired, role=role, company_id=company_id)
        require_repair_preserves_evidence(value, payload, role=role)
    except ResearchContractValidationError as final_error:
        if final_error.proof_failure_detail["stage"] == "research_envelope":
            raise
        inputs.record_response_recovery(company_id=company_id, role=role, status="unresolved",
                                         diagnostic=final_error.proof_failure_detail)
        return None, [], final_error.proof_failure_detail
    except AgentResponseDiagnosticError as final_error:
        inputs.record_response_recovery(company_id=company_id, role=role, status="unresolved",
                                         diagnostic=final_error.proof_failure_detail)
        return None, [], final_error.proof_failure_detail
    except AgentContractValidationError as final_error:
        if final_error.code != "pharma_agent_business_schema_invalid":
            raise
        diagnostic = safe_diagnostic(final_error, role=role)
        inputs.record_response_recovery(company_id=company_id, role=role, status="unresolved",
                                         diagnostic=diagnostic)
        return None, [], diagnostic
    inputs.record_response_recovery(company_id=company_id, role=role, status="agent_repaired",
                                     diagnostic=initial_error.proof_failure_detail)
    return payload, [*repairs, {"field": initial_error.proof_failure_detail["field"],
                               "rule": "agent_contract_repaired", "count": 1}], None


def _join_research(research: dict[str, dict[str, Any]]) -> dict[str, Any]:
    claims: list[dict[str, Any]] = []
    uncertainties: list[str] = []
    sections: list[dict[str, Any]] = []
    citations: list[Any] = []
    seen_claim_ids: set[str] = set()

    for role in RESEARCH_ROLES:
        payload = research[role]
        if not payload["claims"] and not payload["uncertainties"]:
            raise AgentContractValidationError(
                "pharma_agent_business_schema_invalid",
                "Research role returned neither claims nor explicit evidence gaps.",
                proof_failure_detail=_agent_contract_proof_detail(
                    role=role, stage="research_join", rule="missing_claims", field="claims",
                ),
            )
        for claim in payload["claims"]:
            # Independent research roles own local identifiers. Freeze a bounded
            # role-qualified identity before any downstream claim references exist.
            claim_id = f"{role}:{sha256(claim['claim_id'].encode('utf-8')).hexdigest()}"
            if claim_id in seen_claim_ids:
                raise AgentContractValidationError(
                    "pharma_agent_business_schema_invalid",
                    "Research claim_id values must be unique within one role.",
                    proof_failure_detail=_agent_contract_proof_detail(
                        role=role, stage="research_join", rule="duplicate_claim_id", field="claim_id",
                    ),
                )
            seen_claim_ids.add(claim_id)
            claims.append({**claim, "claim_id": claim_id})
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
        "unresolved_research_responses": [
            payload["_unresolved_response"] for payload in research.values() if payload.get("_unresolved_response")
        ],
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
    return _validated_agent_response(
        inputs, envelope, role=STRATEGIC_ROLE, company_id=company_id,
        contract=response_contract_for_role(STRATEGIC_ROLE, company_id=company_id),
        validator=lambda value: validate_strategic_payload(value, company_id=company_id),
    )


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
    return _validated_agent_response(
        inputs, envelope, role=CRITIC_ROLE, company_id=company_id,
        contract=response_contract_for_role(CRITIC_ROLE, company_id=company_id,
                                            planner_requirement_ids=methodology_plan.requirement_ids()),
        validator=lambda value: validate_critic_payload(
            value, company_id=company_id,
            known_claim_ids={claim["claim_id"] for claim in joined_research["claims"]},
            known_section_ids=research_section_ids,
            known_plan_requirement_ids=set(methodology_plan.requirement_ids())),
    )


def _quality_contract_error(message: str, *, role: str, rule: str, field: str) -> None:
    # Existing reviewed code is compatible with the installed generic runtime.
    # The proof stage distinguishes a quality stop from a malformed payload.
    raise AgentContractValidationError(
        "pharma_agent_business_schema_invalid",
        message,
        proof_failure_detail=_agent_contract_proof_detail(
            role=role, stage="pre_synthesis_quality", rule=rule, field=field,
        ),
    )


def _require_pre_synthesis_quality(
    research: dict[str, dict[str, Any]],
    critic: dict[str, Any],
    *, methodology_plan: MethodologyPlan | None = None,
) -> None:
    for role in RESEARCH_ROLES:
        payload = research[role]
        if payload.get("claims") == []:
            required = [] if methodology_plan is None else [
                item["requirement_id"] for item in methodology_plan.requirement_catalog()
                if item.get("role") == role
            ]
            unresolved = {item["requirement_id"] for item in critic["unmet_plan_requirements"]
                          if item["disposition"] == "unresolved_evidence"}
            if not payload.get("uncertainties") or not required or not set(required).issubset(unresolved):
                _quality_contract_error(
                    "Claimless research requires explicit critic evidence-gap dispositions.",
                    role=role, rule="no_evidence_not_disposed", field="unmet_plan_requirements",
                )
        elif len(payload["_citations"]) == 0:
            _quality_contract_error(
                "Every search-enabled research role must return admitted citations.",
                role=role, rule="research_citations_missing", field="citations",
            )
    if critic["recommendation"] != "pass":
        _quality_contract_error(
            "Evidence critic rejected the company evidence package.",
            role=CRITIC_ROLE, rule="critic_rejected", field="recommendation",
        )
    if critic["citation_coverage"]["status"] != "sufficient":
        _quality_contract_error(
            "Evidence critic reported insufficient citation coverage.",
            role=CRITIC_ROLE, rule="citation_coverage_insufficient", field="citation_coverage_status",
        )
    if critic["unsupported_claim_ids"]:
        _quality_contract_error(
            "Unsupported research claims remain after critique.",
            role=CRITIC_ROLE, rule="unsupported_claims_remaining", field="unsupported_claim_ids",
        )
    if critic["missing_section_ids"]:
        _quality_contract_error(
            "Mandatory research sections are missing after critique.",
            role=CRITIC_ROLE, rule="required_sections_missing", field="missing_section_ids",
        )
    if any(
        item["disposition"] == "unsatisfied"
        for item in critic["unmet_plan_requirements"]
    ):
        _quality_contract_error(
            "Mandatory methodology plan requirements remain unsatisfied.",
            role=CRITIC_ROLE, rule="planner_requirements_unsatisfied", field="unmet_plan_requirements",
        )


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
    return _validated_agent_response(
        inputs, envelope, role=SYNTHESIS_ROLE, company_id=company_id,
        contract=response_contract_for_role(SYNTHESIS_ROLE, company_id=company_id),
        validator=lambda value: validate_synthesis_payload(value, company_id=company_id),
    )


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
    return _validated_agent_response(
        inputs, envelope, role=BENCHMARK_ROLE, company_id=company_id,
        contract=response_contract_for_role(BENCHMARK_ROLE, company_id=company_id,
                                            question_ids=tuple(item["question_id"] for item in questions)),
        validator=lambda value: validate_benchmark_payload(
            value, company_id=company_id,
            expected_question_ids=tuple(item["question_id"] for item in questions)),
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

    committed_update = inputs.dynamic_skill(
        "company_memory_update",
        variables={"company_id": str(company_id)},
    )
    if committed_update.provenance().mutable is not True:
        raise RuntimeError("Fresh company memory update handle must remain mutable.")
    if committed_update.content_digest() != receipt.after_content_digest:
        raise RuntimeError("Fresh company memory update digest mismatch.")

    history = committed_update.history(limit=50)
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
        "unresolved_research_responses": joined.get("unresolved_research_responses", []),
        "no_evidence_research_roles": [
            role for role in RESEARCH_ROLES
            if not any(claim["claim_id"].startswith(role + ":") for claim in joined["claims"])
        ],
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
