"""Recoverable memory-candidate validation for pharma adapter 0.1.21.

A synthesis defect must not erase validated research or crash the batch. This
helper converts candidate/reference mismatches into bounded review diagnostics.
It does not repair candidate content or grant mutation authority.
"""
from __future__ import annotations

from typing import Iterable


class CandidateContractError(RuntimeError):
    """Recoverable, enum-only candidate contract rejection."""

    code = "pharma_agent_business_schema_invalid"

    def __init__(self, *, rule: str, field: str) -> None:
        self.proof_failure_detail = {
            "schema_version": "proof_failure_detail.v1",
            "proof_kind": "agent_contract",
            "role": "intelligence_synthesizer",
            "stage": "pre_synthesis_quality",
            "rule": rule,
            "field": field,
        }
        super().__init__("Memory candidate violates the reviewed contract.")


def require_candidate_fact_ids(
    *,
    fact_ids: Iterable[str],
    accepted_claim_ids: Iterable[str],
) -> tuple[str, ...]:
    """Require every candidate fact to reference one accepted claim exactly."""

    facts = tuple(fact_ids)
    accepted = set(accepted_claim_ids)
    if any(not isinstance(item, str) or not item for item in facts):
        raise CandidateContractError(
            rule="candidate_fact_id_invalid",
            field="memory_candidate.fact_ids",
        )
    if len(set(facts)) != len(facts):
        raise CandidateContractError(
            rule="candidate_fact_id_duplicate",
            field="memory_candidate.fact_ids",
        )
    if any(item not in accepted for item in facts):
        raise CandidateContractError(
            rule="candidate_fact_id_unknown",
            field="memory_candidate.fact_ids",
        )
    return facts
