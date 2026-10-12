"""Thin 0.1.21 research-response to claim-evidence pipeline.

The search-enabled researcher roles are portfolio_researcher, market_researcher
and regulatory_risk_researcher. They return bounded research payloads with exact
citation locators. This module validates that versioned response contract and
projects one immutable role-scoped evidence result.

All other Agent roles remain outside this pipeline: methodology_planner plans,
strategic_analyst reasons over accepted evidence, evidence_critic reviews it,
intelligence_synthesizer prepares outputs, memory_benchmark_reviewer scores
supplied memory, and research_response_resolver performs one faithful format
repair. No role in this module receives storage, approval, publication or
Dynamic Skill mutation authority.
"""
from __future__ import annotations

from typing import Any, Iterable

try:
    from .research_claim_evidence_v0_1_26 import (
        RoleClaimEvidenceProjection,
        project_role_claim_evidence,
    )
    from .research_response_contract_v0_1_26 import (
        research_validation_contract_v0_1_26,
        validate_research_payload_v0_1_26,
    )
except ImportError:  # pragma: no cover - flat intake execution
    from research_claim_evidence_v0_1_26 import (
        RoleClaimEvidenceProjection,
        project_role_claim_evidence,
    )
    from research_response_contract_v0_1_26 import (
        research_validation_contract_v0_1_26,
        validate_research_payload_v0_1_26,
    )


def research_response_contract_for_role_v0_1_26(
    *,
    role: str,
    company_id: int,
) -> dict[str, Any]:
    """Return the exact provider-visible validation contract for one role."""

    return research_validation_contract_v0_1_26(
        role=role,
        company_id=company_id,
    )


def validate_and_project_role_claim_evidence_v0_1_26(
    *,
    role: str,
    company_id: int,
    pass_number: int,
    payload: Any,
    admitted_citations: Iterable[Any],
) -> RoleClaimEvidenceProjection:
    """Validate one v2 research payload and project its admitted evidence.

    Args:
        role: One search-enabled research role.
        company_id: Exact governed company identity for this execution unit.
        pass_number: One-based role-pass ordinal.
        payload: Decoded Agent business JSON for the role.
        admitted_citations: Runtime-admitted inert citation objects for this pass.

    Returns:
        One immutable accepted/withheld role projection.

    Raises:
        ResearchResponseContractError: If the v2 payload contract is invalid.
        RoleClaimEvidenceError: If role projection or citation admission fails.
    """

    validated = validate_research_payload_v0_1_26(
        payload,
        role=role,
        company_id=company_id,
    )
    return project_role_claim_evidence(
        role=role,
        pass_number=pass_number,
        payload=validated,
        citations=admitted_citations,
    )
