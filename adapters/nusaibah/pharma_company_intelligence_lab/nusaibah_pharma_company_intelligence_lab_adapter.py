from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
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
        extract_agent_json,
        validate_benchmark_payload,
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
        resolve_company_records,
        validate_batch_request,
    )
    from .memory_contract import MEMORY_TARGET_SECTION, MemoryCandidate
    from .methodology_contract import MethodologyResources, load_methodology
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
        extract_agent_json,
        validate_benchmark_payload,
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
        resolve_company_records,
        validate_batch_request,
    )
    from memory_contract import MEMORY_TARGET_SECTION, MemoryCandidate
    from methodology_contract import MethodologyResources, load_methodology


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


class NusaibahPharmaCompanyIntelligenceLabAdapter(Adapter):
    """Run a governed multi-company intelligence and memory-improvement pipeline.

    The adapter owns deterministic orchestration, schema validation, section
    rendering, quality gates, and company isolation. Runtime-owned helpers own
    provider execution, fixed/Dynamic Skill materialization, credentials,
    storage, retries, publication and remote authority.
    """

    key: ClassVar[str] = "nusaibah.pharma_company_intelligence_lab"
    version: ClassVar[str] = "0.1.0"

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
                if not state["memory_mutation_eligible"]:
                    state["result"]["memory_update_status"] = "no_change_recommended"
                    continue
                mutation = _apply_company_memory(inputs, state)
                state["result"].update(mutation)
                mutation_count += 1

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
                "logical_agent_invocations": len(company_results) * 8,
                "search_enabled_agent_invocations": len(company_results) * 3,
                "memory_mutations_made": mutation_count,
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

    research = _run_research_fanout(
        inputs,
        company_id=company_id,
        company_name_value=name,
        baseline=baseline,
        memory_text=memory_text,
        request=request,
    )
    joined = _join_research(research)

    strategic = _run_strategic(
        inputs,
        company_id=company_id,
        company_name_value=name,
        baseline=baseline,
        memory_text=memory_text,
        joined_research=joined,
    )
    critic = _run_critic(
        inputs,
        company_id=company_id,
        company_name_value=name,
        joined_research=joined,
        strategic=strategic,
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
        "projected_after_benchmark": after_benchmark,
        "benchmark_questions": methodology.benchmark_questions,
        "memory_candidate": candidate,
        "citations": citations,
        "memory_mutation_eligible": mutation_eligible,
    }


def _run_research_fanout(
    inputs: Any,
    *,
    company_id: int,
    company_name_value: str,
    baseline: dict[str, Any],
    memory_text: str,
    request: BatchRequest,
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}

    def run(role: str) -> dict[str, Any]:
        required_sections = _section_requests(RESEARCH_ROLE_SECTIONS[role])
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
                "response_contract": {
                    "schema_version": RESEARCH_SCHEMA_VERSION,
                    "role": role,
                    "required_section_ids": list(RESEARCH_ROLE_SECTIONS[role]),
                },
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
) -> dict[str, Any]:
    envelope = inputs.invoke_agent(
        STRATEGIC_ROLE,
        input={
            "company_id": company_id,
            "company_name": company_name_value,
            "governed_company_baseline": baseline,
            "existing_company_memory": memory_text,
            "research_evidence": _research_for_downstream(joined_research),
            "response_contract": {
                "schema_version": STRATEGIC_SCHEMA_VERSION,
                "role": STRATEGIC_ROLE,
            },
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
            "research_evidence": _research_for_downstream(joined_research),
            "strategic_analysis": strategic,
            "reviewed_section_ids": sorted(research_section_ids),
            "response_contract": {
                "schema_version": CRITIC_SCHEMA_VERSION,
                "role": CRITIC_ROLE,
            },
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
) -> tuple[dict[str, Any], MemoryCandidate]:
    envelope = inputs.invoke_agent(
        SYNTHESIS_ROLE,
        input={
            "company_id": company_id,
            "company_name": company_name_value,
            "governed_company_baseline": baseline,
            "existing_company_memory": memory_text,
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
                "schema_version": SYNTHESIS_SCHEMA_VERSION,
                "role": SYNTHESIS_ROLE,
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
            "response_contract": {
                "schema_version": BENCHMARK_SCHEMA_VERSION,
                "role": BENCHMARK_ROLE,
                "question_ids": [item["question_id"] for item in questions],
            },
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
