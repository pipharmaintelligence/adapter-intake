"""Version-owned research execution for pharma adapter 0.1.25.

The module owns only the three search-enabled research roles and their bounded
one-time repair path. It validates ``pharma_research_agent.v2``, exact-matches
claim locators against runtime-admitted citations, preserves accepted work, and
withholds unsupported or semantically invalid claims. Planner, analysis,
critique, synthesis, benchmark, storage, publication and Dynamic Skill mutation
remain outside this module.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from devtools.runtime_agent_invocation import RuntimeAgentInvocationError
try:
    from .invocation_recovery_v0_1_25 import invocation_diagnostic
except ImportError:
    from invocation_recovery_v0_1_25 import invocation_diagnostic

try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .research_claim_evidence_v0_1_21 import (
        MergedClaimEvidenceProjection,
        RoleClaimEvidenceProjection,
        merge_role_claim_evidence,
        project_role_claim_evidence,
    )
    from .research_claim_pipeline_v0_1_21 import (
        research_response_contract_for_role_v0_1_21,
    )
    from .research_response_contract_v0_1_21 import (
        RESEARCH_SCHEMA_VERSION,
        ResearchResponseContractError,
        project_repair_input_v0_1_21,
        require_repair_preserves_claim_evidence_v0_1_21,
        validate_research_payload_v0_1_21,
    )
    from .research_section_projection_v0_1_21 import (
        project_research_sections,
    )
    from .methodology_learning_v0_1_21 import reviewed_methodology_addendum
except ImportError:  # pragma: no cover - flat intake execution
    import legacy_preparation_helpers_v0_1_23 as legacy
    from research_claim_evidence_v0_1_21 import (
        MergedClaimEvidenceProjection,
        RoleClaimEvidenceProjection,
        merge_role_claim_evidence,
        project_role_claim_evidence,
    )
    from research_claim_pipeline_v0_1_21 import (
        research_response_contract_for_role_v0_1_21,
    )
    from research_response_contract_v0_1_21 import (
        RESEARCH_SCHEMA_VERSION,
        ResearchResponseContractError,
        project_repair_input_v0_1_21,
        require_repair_preserves_claim_evidence_v0_1_21,
        validate_research_payload_v0_1_21,
    )
    from research_section_projection_v0_1_21 import (
        project_research_sections,
    )
    from methodology_learning_v0_1_21 import reviewed_methodology_addendum


RESEARCH_ROLES = legacy.RESEARCH_ROLES


def run_research_fanout_v0_1_25(
    inputs: Any,
    *,
    company_id: int,
    company_name_value: str,
    baseline: dict[str, Any],
    memory_text: str,
    request: Any,
    methodology_plan: Any,
    methodology: Any,
    learned_methodology_text: str,
    review_passes: int,
) -> dict[str, dict[str, Any]]:
    """Run three bounded research roles and retain claim-level evidence state."""

    results: dict[str, dict[str, Any]] = {}

    def run(role: str) -> dict[str, Any]:
        required_sections = legacy._section_requests(
            legacy.RESEARCH_ROLE_SECTIONS[role]
        )
        learned_sections = [
            legacy._planner_learned_section(
                learned_methodology_text,
                section_id=section_id,
            )
            for section_id in legacy.RESEARCH_ROLE_SECTIONS[role]
        ]
        response_contract = research_response_contract_for_role_v0_1_21(
            role=role,
            company_id=company_id,
        )
        base_input = {
            "company_id": company_id,
            "company_name": company_name_value,
            "objective": request.objective,
            "research_depth": request.research_depth,
            "governed_company_baseline": baseline,
            "existing_company_memory": memory_text,
            "required_sections": required_sections,
            "methodology_plan": methodology_plan.role_focus(role),
            "methodology_packet": {
                "skill_ref": methodology.planner_packet.skill_ref,
                "version": methodology.planner_packet.skill_version,
                "package_digest": methodology.package_digest,
                "evidence_rules": list(
                    methodology.planner_packet.evidence_rules
                ),
                "role_boundaries": list(
                    methodology.planner_packet.role_boundaries
                ),
                "company_isolation_rules": list(
                    methodology.planner_packet.company_isolation_rules
                ),
            },
            "learned_methodology": "\n\n".join(
                text for text in learned_sections if text
            ),
            "learned_methodology_addendum": reviewed_methodology_addendum(
                learned_methodology_text,
            ),
            "response_contract": response_contract,
        }

        passes = review_passes if role == "portfolio_researcher" else 1
        payload: dict[str, Any] | None = None
        projection: RoleClaimEvidenceProjection | None = None
        review_sections: list[dict[str, Any]] | None = None
        withheld_section_ids: list[str] = []
        citations: list[Any] = []
        repairs: list[dict[str, Any]] = []
        trace: list[dict[str, Any]] = []
        resolver_calls = 0
        unresolved: dict[str, Any] | None = None
        issue_entry: dict[str, Any] | None = None
        evidence_incomplete = False

        for pass_number in range(1, passes + 1):
            previous = None
            if payload is not None:
                previous = {
                    key: item
                    for key, item in payload.items()
                    if not key.startswith("_")
                }
                previous["citation_sources"] = legacy._citation_output(citations)

            invocation_failure = None
            try:
                envelope = inputs.invoke_agent(
                    role,
                    input={
                        **base_input,
                        "portfolio_review": {
                            "pass_number": pass_number,
                            "total_passes": passes,
                            "stage": (
                                "initial_review" if pass_number == 1 else "reflection"
                            ),
                            "previous_result": previous,
                        },
                    },
                    on_error="raise",
                )
            except RuntimeAgentInvocationError as error:
                invocation_failure = invocation_diagnostic(error, role=role)
                if invocation_failure is None:
                    raise
                envelope = None
                inputs.record_response_recovery(
                    company_id=company_id, role=role, status="unresolved",
                    diagnostic=invocation_failure,
                )

            admitted: tuple[Any, ...] = ()
            pass_repairs: list[dict[str, Any]] = []
            next_payload: dict[str, Any] | None = None
            next_projection: RoleClaimEvidenceProjection | None = None
            next_review_sections: list[dict[str, Any]] | None = None
            next_withheld_section_ids: list[str] = []
            current_unresolved: dict[str, Any] | None = invocation_failure

            if invocation_failure is None:
                try:
                    normalized, wrappers = legacy.normalize_json_envelope(
                        envelope,
                        role=role,
                    )
                    value, agent_result = legacy.extract_agent_json(
                        normalized,
                        expected_role=role,
                        company_id=company_id,
                        expected_schema_version=RESEARCH_SCHEMA_VERSION,
                    )
                    admitted = legacy._agent_citations(agent_result)
                except (
                    legacy.AgentResponseDiagnosticError,
                    legacy.AgentContractValidationError,
                ) as error:
                    if error.code not in {"pharma_agent_business_schema_invalid", "pharma_agent_status_invalid"}:
                        raise
                    current_unresolved = legacy.safe_diagnostic(error, role=role)
                    inputs.record_response_recovery(
                        company_id=company_id,
                        role=role,
                        status="unresolved",
                        diagnostic=current_unresolved,
                    )
                except ValueError:
                    raise legacy.AgentContractValidationError(
                        "pharma_agent_business_schema_invalid",
                        "Research citation evidence failed its runtime contract.",
                        proof_failure_detail=legacy._agent_contract_proof_detail(
                            role=role,
                            stage="research_citations",
                            rule="invalid_schema",
                            field="citations",
                        ),
                    ) from None
                else:
                    if wrappers:
                        inputs.record_response_recovery(
                            company_id=company_id,
                            role=role,
                            status="json_unwrapped",
                            wrappers=wrappers,
                        )
                    try:
                        validated = validate_research_payload_v0_1_21(
                            value,
                            role=role,
                            company_id=company_id,
                        )
                    except ResearchResponseContractError as initial_error:
                        resolver_calls += 1
                        (
                            validated,
                            pass_repairs,
                            current_unresolved,
                        ) = _repair_research_response_v0_1_25(
                            inputs,
                            value=value,
                            role=role,
                            company_id=company_id,
                            initial_error=initial_error,
                        )
    
                    if validated is not None and current_unresolved is None:
                        next_projection = project_role_claim_evidence(
                            role=role,
                            pass_number=pass_number,
                            payload=validated,
                            citations=admitted,
                        )
                        accepted_local_ids = {
                            claim["local_claim_id"]
                            for claim in next_projection.accepted_claims
                        }
                        section_projection = project_research_sections(
                            sections=validated["sections"],
                            withheld_claims=next_projection.withheld_claims,
                        )
                        next_review_sections = [
                            dict(section)
                            for section in section_projection.review_sections
                        ]
                        next_withheld_section_ids = list(
                            section_projection.withheld_section_ids
                        )
                        next_payload = {
                            **validated,
                            "sections": [
                                dict(section)
                                for section in section_projection.downstream_sections
                            ],
                            "claims": [
                                claim
                                for claim in validated["claims"]
                                if claim["claim_id"] in accepted_local_ids
                            ],
                        }

            repairs.extend(
                {"pass_number": pass_number, **item}
                for item in pass_repairs
            )

            if current_unresolved is not None:
                issue_entry = legacy.research_issue(
                    current_unresolved,
                    category="response_invalid",
                    action=(
                        "previous_validated_pass_retained"
                        if payload is not None
                        else "withheld"
                    ),
                    pass_number=pass_number,
                )
                next_payload = payload
                next_projection = projection
                next_review_sections = review_sections
                next_withheld_section_ids = withheld_section_ids
                evidence_incomplete = True
            elif next_projection is not None and next_projection.withheld_claims:
                evidence_incomplete = True
                semantic_issue = any(
                    issue.get("category") == "semantic_quality"
                    for issue in next_projection.issues
                )
                issue_entry = {
                    "role": role,
                    "stage": "claim_quality_projection",
                    "field": "claims",
                    "rule": "claim_quality_incomplete",
                    "category": (
                        "quality_rejected"
                        if semantic_issue
                        else "evidence_unavailable"
                    ),
                    "action": "claims_and_affected_section_prose_withheld",
                    "section_ids": sorted(
                        {
                            claim["section_id"]
                            for claim in next_projection.withheld_claims
                        }
                    ),
                    "withheld_claim_count": len(
                        next_projection.withheld_claims
                    ),
                    "pass_number": pass_number,
                }

            if next_payload is None:
                next_payload = (
                    payload
                    if payload is not None
                    else _no_evidence_payload_v0_1_23(
                        role=role,
                        company_id=company_id,
                    )
                )
            if next_projection is None:
                next_projection = projection
            if next_review_sections is None:
                next_review_sections = (
                    review_sections
                    if review_sections is not None
                    else [dict(section) for section in next_payload["sections"]]
                )

            if current_unresolved is None:
                if next_payload["claims"]:
                    citations = list(
                        legacy._dedupe_citations(citations + list(admitted))
                    )
                else:
                    next_payload = _no_evidence_payload_v0_1_23(
                        role=role,
                        company_id=company_id,
                    )

            payload = next_payload
            projection = next_projection
            review_sections = next_review_sections
            withheld_section_ids = next_withheld_section_ids
            unresolved = current_unresolved
            trace.append(
                {
                    "pass_number": pass_number,
                    "stage": (
                        "initial_review" if pass_number == 1 else "reflection"
                    ),
                    "status": (
                        "unresolved"
                        if current_unresolved is not None
                        else "validated"
                        if payload["claims"]
                        else "no_evidence"
                    ),
                    "previous_result_sha256": (
                        None
                        if previous is None
                        else legacy._research_digest(previous)
                    ),
                    "result_sha256": legacy._research_digest(
                        {
                            **payload,
                            "citation_sources": legacy._citation_output(citations),
                        }
                    ),
                    "learned_methodology_used": bool(
                        base_input["learned_methodology"]
                        or base_input["learned_methodology_addendum"]
                    ),
                    "claim_count": len(payload["claims"]),
                    "withheld_claim_count": (
                        0
                        if projection is None
                        else len(projection.withheld_claims)
                    ),
                    "withheld_section_count": len(withheld_section_ids),
                    "citation_count": len(citations),
                }
            )

            if current_unresolved is not None or not payload["claims"]:
                break

        assert payload is not None
        if projection is None:
            projection = project_role_claim_evidence(
                role=role,
                pass_number=1,
                payload=payload,
                citations=(),
            )
        if review_sections is None:
            review_sections = [dict(section) for section in payload["sections"]]

        payload["_citations"] = tuple(citations)
        payload["_response_repairs"] = repairs
        payload["_review_trace"] = trace
        payload["_resolver_call_count"] = resolver_calls
        payload["_unresolved_response"] = unresolved
        payload["_issue"] = issue_entry
        payload["_claim_projection"] = projection
        payload["_claim_evidence_incomplete"] = evidence_incomplete
        payload["_review_sections"] = tuple(review_sections)
        payload["_withheld_section_ids"] = tuple(withheld_section_ids)
        return payload

    with ThreadPoolExecutor(
        max_workers=3,
        thread_name_prefix="pharma-research-v023",
    ) as pool:
        futures = {pool.submit(run, role): role for role in RESEARCH_ROLES}
        for future in as_completed(futures):
            role = futures[future]
            results[role] = future.result()

    return {role: results[role] for role in RESEARCH_ROLES}


def join_research_v0_1_25(
    research: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Merge only downstream-safe sections and accepted claim evidence."""

    projections: list[RoleClaimEvidenceProjection] = []
    sections: list[dict[str, Any]] = []
    uncertainties: list[str] = []
    citations: list[Any] = []
    withheld_section_ids: list[str] = []

    for role in RESEARCH_ROLES:
        payload = research[role]
        projection = payload.get("_claim_projection")
        if not isinstance(projection, RoleClaimEvidenceProjection):
            raise legacy.AgentContractValidationError(
                "pharma_agent_business_schema_invalid",
                "Research role is missing its claim evidence projection.",
                proof_failure_detail=legacy._agent_contract_proof_detail(
                    role=role,
                    stage="research_join_v0_1_21",
                    rule="claim_projection_missing",
                    field="claims",
                ),
            )
        projections.append(projection)
        sections.extend(payload["sections"])
        uncertainties.extend(payload["uncertainties"])
        citations.extend(payload["_citations"])
        for section_id in payload.get("_withheld_section_ids", ()):
            if section_id not in withheld_section_ids:
                withheld_section_ids.append(section_id)

    merged: MergedClaimEvidenceProjection = merge_role_claim_evidence(
        projections
    )
    issues = [dict(item) for item in merged.issues]
    deduped = list(legacy._dedupe_citations(citations))
    return {
        "sections": sections,
        "claims": [dict(item) for item in merged.accepted_claims],
        "withheld_claims": [dict(item) for item in merged.withheld_claims],
        "withheld_section_ids": withheld_section_ids,
        "uncertainties": uncertainties,
        "citations": deduped,
        "citation_count_by_role": {
            role: len(research[role]["_citations"])
            for role in RESEARCH_ROLES
        },
        "claim_evidence_index": merged.evidence_index,
        "claim_evidence_issues": issues,
        "claim_quality_issues": issues,
        "claim_evidence_projection_digest": merged.projection_digest,
        "unresolved_research_responses": [
            payload["_unresolved_response"]
            for payload in research.values()
            if payload.get("_unresolved_response")
        ],
    }


def _repair_research_response_v0_1_25(
    inputs: Any,
    *,
    value: dict[str, Any],
    role: str,
    company_id: int,
    initial_error: ResearchResponseContractError,
) -> tuple[
    dict[str, Any] | None,
    list[dict[str, Any]],
    dict[str, Any] | None,
]:
    contract = research_response_contract_for_role_v0_1_21(
        role=role,
        company_id=company_id,
    )
    try:
        repair_envelope = inputs.invoke_response_resolver(
            original_role=role,
            input={
                "company_id": company_id,
                "research_role": role,
                "failed_contract": initial_error.proof_failure_detail,
                "invalid_response": project_repair_input_v0_1_21(value),
                "response_contract": contract,
                "repair_scope": "research_business_json",
            },
        )
    except legacy.UnresolvedAgentResponse as error:
        inputs.record_response_recovery(company_id=company_id, role=role,
            status="unresolved", diagnostic=error.diagnostic)
        return None, [], error.diagnostic

    try:
        repaired, _ = legacy.extract_agent_json(
            repair_envelope,
            expected_role=role,
            company_id=company_id,
            expected_schema_version=RESEARCH_SCHEMA_VERSION,
        )
        validated = validate_research_payload_v0_1_21(
            repaired,
            role=role,
            company_id=company_id,
        )
        require_repair_preserves_claim_evidence_v0_1_21(
            value,
            validated,
            role=role,
        )
    except ResearchResponseContractError as final_error:
        inputs.record_response_recovery(
            company_id=company_id,
            role=role,
            status="unresolved",
            diagnostic=final_error.proof_failure_detail,
        )
        return None, [], final_error.proof_failure_detail
    except legacy.AgentResponseDiagnosticError as final_error:
        inputs.record_response_recovery(
            company_id=company_id,
            role=role,
            status="unresolved",
            diagnostic=final_error.proof_failure_detail,
        )
        return None, [], final_error.proof_failure_detail
    except legacy.AgentContractValidationError as final_error:
        if final_error.code not in {"pharma_agent_business_schema_invalid", "pharma_agent_status_invalid"}:
            raise
        diagnostic = legacy.safe_diagnostic(final_error, role=role)
        inputs.record_response_recovery(
            company_id=company_id,
            role=role,
            status="unresolved",
            diagnostic=diagnostic,
        )
        return None, [], diagnostic

    inputs.record_response_recovery(
        company_id=company_id,
        role=role,
        status="agent_repaired",
        diagnostic=initial_error.proof_failure_detail,
    )
    return (
        validated,
        [
            {
                "field": initial_error.proof_failure_detail["field"],
                "rule": "agent_contract_repaired",
                "count": 1,
            }
        ],
        None,
    )


def _no_evidence_payload_v0_1_23(
    *,
    role: str,
    company_id: int,
) -> dict[str, Any]:
    value = legacy.no_evidence_payload(role=role, company_id=company_id)
    value["schema_version"] = RESEARCH_SCHEMA_VERSION
    return value
