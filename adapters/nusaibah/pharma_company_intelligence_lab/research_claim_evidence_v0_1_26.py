"""Modular role-scoped claim evidence projection for pharma 0.1.21.

Role boundaries:
- methodology_planner plans bounded work and owns no factual evidence.
- portfolio_researcher owns company/profile and portfolio research claims.
- market_researcher owns market and commercial research claims.
- regulatory_risk_researcher owns regulatory, clinical and safety claims.
- strategic_analyst reasons only over accepted same-company evidence.
- evidence_critic assigns bounded quality dispositions without mutation authority.
- intelligence_synthesizer uses accepted claims to prepare a dossier/candidate.
- memory_benchmark_reviewer evaluates supplied memory without adding facts.
- research_response_resolver performs one faithful format repair only.

This helper keeps role projection, claim-ID qualification, semantic validation
and issue construction outside the main adapter module. It has no provider,
storage, publication, approval or Dynamic Skill mutation authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

try:
    from .claim_evidence_contract_v0_1_21 import (
        ClaimEvidenceIndex,
        build_claim_evidence_index,
        merge_claim_evidence_indexes,
    )
    from .claim_semantics_v0_1_26 import (
        ClaimSemanticContractError,
        validate_claim_semantic_context,
    )
except ImportError:  # pragma: no cover - flat intake execution
    from claim_evidence_contract_v0_1_21 import (
        ClaimEvidenceIndex,
        build_claim_evidence_index,
        merge_claim_evidence_indexes,
    )
    from claim_semantics_v0_1_26 import (
        ClaimSemanticContractError,
        validate_claim_semantic_context,
    )


RESEARCH_ROLES = (
    "portfolio_researcher",
    "market_researcher",
    "regulatory_risk_researcher",
)
ISSUE_SCHEMA_VERSION = "pharma_claim_evidence_issue.v1"
PROJECTION_SCHEMA_VERSION = "pharma_role_claim_evidence_projection.v1"
MERGED_SCHEMA_VERSION = "pharma_merged_claim_evidence_projection.v1"


class RoleClaimEvidenceError(ValueError):
    """Value-safe rejection for invalid role-scoped claim evidence input."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class RoleClaimEvidenceProjection:
    """Accepted and withheld claims for one research role and pass."""

    schema_version: str
    role: str
    pass_number: int
    accepted_claims: tuple[dict[str, Any], ...]
    withheld_claims: tuple[dict[str, Any], ...]
    evidence_index: ClaimEvidenceIndex
    issues: tuple[dict[str, Any], ...]
    projection_digest: str


@dataclass(frozen=True)
class MergedClaimEvidenceProjection:
    """Canonical research-role merge used by downstream quality stages."""

    schema_version: str
    accepted_claims: tuple[dict[str, Any], ...]
    withheld_claims: tuple[dict[str, Any], ...]
    evidence_index: ClaimEvidenceIndex
    issues: tuple[dict[str, Any], ...]
    projection_digest: str


def qualified_claim_id(role: str, local_claim_id: str) -> str:
    """Return the existing role-qualified claim identity used downstream."""

    role = _research_role(role)
    local = _token(local_claim_id, "role_claim_local_id_invalid")
    return f"{role}:{sha256(local.encode('utf-8')).hexdigest()}"


def project_role_claim_evidence(
    *,
    role: str,
    pass_number: int,
    payload: Mapping[str, Any],
    citations: Iterable[Any],
) -> RoleClaimEvidenceProjection:
    """Qualify claims and withhold evidence or semantic defects individually."""

    role = _research_role(role)
    if type(pass_number) is not int or pass_number < 1:
        raise RoleClaimEvidenceError("role_claim_pass_number_invalid")
    if not isinstance(payload, Mapping):
        raise RoleClaimEvidenceError("role_claim_payload_invalid")
    if payload.get("role") != role:
        raise RoleClaimEvidenceError("role_claim_payload_role_invalid")

    raw_claims = payload.get("claims")
    if not isinstance(raw_claims, list):
        raise RoleClaimEvidenceError("role_claim_list_invalid")

    qualified: list[dict[str, Any]] = []
    forced_withheld: dict[str, str] = {}
    for raw in raw_claims:
        claim, semantic_issue = _qualified_claim(role, raw)
        qualified.append(claim)
        source_issue = raw.get("_source_issue")
        if semantic_issue is not None or source_issue is not None:
            forced_withheld[claim["claim_id"]] = semantic_issue or source_issue

    index = build_claim_evidence_index(
        role=role,
        pass_number=pass_number,
        claims=qualified,
        citations=citations,
        forced_withheld=forced_withheld,
    )

    by_id = {claim["claim_id"]: claim for claim in qualified}
    accepted = tuple(
        dict(by_id[claim_id]) for claim_id in index.accepted_claim_ids
    )
    withheld = tuple(
        dict(by_id[claim_id]) for claim_id in index.withheld_claim_ids
    )
    issues = tuple(
        _claim_issue(
            role=role,
            pass_number=pass_number,
            claim_id=record.claim_id,
            rule=record.issue_code,
        )
        for record in index.records
        if record.issue_code is not None
    )
    digest = _digest(
        {
            "schema_version": PROJECTION_SCHEMA_VERSION,
            "role": role,
            "pass_number": pass_number,
            "accepted_claim_ids": [item["claim_id"] for item in accepted],
            "withheld_claim_ids": [item["claim_id"] for item in withheld],
            "evidence_index_digest": index.index_digest,
            "issues": list(issues),
        }
    )
    return RoleClaimEvidenceProjection(
        schema_version=PROJECTION_SCHEMA_VERSION,
        role=role,
        pass_number=pass_number,
        accepted_claims=accepted,
        withheld_claims=withheld,
        evidence_index=index,
        issues=issues,
        projection_digest=digest,
    )


def merge_role_claim_evidence(
    projections: Iterable[RoleClaimEvidenceProjection],
) -> MergedClaimEvidenceProjection:
    """Merge role projections in canonical role order without losing issues."""

    by_role: dict[str, RoleClaimEvidenceProjection] = {}
    for projection in projections:
        if not isinstance(projection, RoleClaimEvidenceProjection):
            raise RoleClaimEvidenceError("role_claim_projection_invalid")
        if projection.role in by_role:
            raise RoleClaimEvidenceError("role_claim_projection_duplicate")
        by_role[projection.role] = projection

    missing = [role for role in RESEARCH_ROLES if role not in by_role]
    extras = [role for role in by_role if role not in RESEARCH_ROLES]
    if missing or extras:
        raise RoleClaimEvidenceError("role_claim_projection_set_invalid")

    ordered = tuple(by_role[role] for role in RESEARCH_ROLES)
    merged_index = merge_claim_evidence_indexes(
        projection.evidence_index for projection in ordered
    )
    accepted = tuple(
        dict(claim)
        for projection in ordered
        for claim in projection.accepted_claims
    )
    withheld = tuple(
        dict(claim)
        for projection in ordered
        for claim in projection.withheld_claims
    )
    issues = tuple(
        dict(issue)
        for projection in ordered
        for issue in projection.issues
    )
    digest = _digest(
        {
            "schema_version": MERGED_SCHEMA_VERSION,
            "accepted_claim_ids": [item["claim_id"] for item in accepted],
            "withheld_claim_ids": [item["claim_id"] for item in withheld],
            "evidence_index_digest": merged_index.index_digest,
            "issues": list(issues),
        }
    )
    return MergedClaimEvidenceProjection(
        schema_version=MERGED_SCHEMA_VERSION,
        accepted_claims=accepted,
        withheld_claims=withheld,
        evidence_index=merged_index,
        issues=issues,
        projection_digest=digest,
    )


def accepted_claims_for_downstream(
    projection: MergedClaimEvidenceProjection,
) -> list[dict[str, Any]]:
    """Return copies of accepted claims for critic/synthesis input only."""

    if not isinstance(projection, MergedClaimEvidenceProjection):
        raise RoleClaimEvidenceError("role_claim_merged_projection_invalid")
    return [dict(claim) for claim in projection.accepted_claims]


def _qualified_claim(
    role: str,
    raw: Any,
) -> tuple[dict[str, Any], str | None]:
    if not isinstance(raw, Mapping):
        raise RoleClaimEvidenceError("role_claim_invalid")
    local_claim_id = _token(raw.get("claim_id"), "role_claim_local_id_invalid")
    section_id = _token(raw.get("section_id"), "role_claim_section_id_invalid")
    statement = _text(raw.get("statement"), "role_claim_statement_invalid")
    evidence_kind = _token(
        raw.get("evidence_kind"),
        "role_claim_evidence_kind_invalid",
    )
    inference = raw.get("inference")
    if evidence_kind not in {"grounded_external", "inference"}:
        raise RoleClaimEvidenceError("role_claim_evidence_kind_invalid")
    if type(inference) is not bool:
        raise RoleClaimEvidenceError("role_claim_inference_invalid")

    semantic_issue: str | None = None
    semantic_value: Any = raw.get("semantic_context")
    semantic_rule_ids: list[str] = []
    try:
        semantic = validate_claim_semantic_context(semantic_value)
    except ClaimSemanticContractError as error:
        semantic_issue = f"claim_semantic_{error.rule}"
    else:
        semantic_value = semantic.public_value()
        semantic_rule_ids = list(semantic.rule_ids)

    return (
        {
            **dict(raw),
            "claim_id": qualified_claim_id(role, local_claim_id),
            "local_claim_id": local_claim_id,
            "section_id": section_id,
            "statement": statement,
            "evidence_kind": evidence_kind,
            "inference": inference,
            "semantic_context": semantic_value,
            "semantic_rule_ids": semantic_rule_ids,
        },
        semantic_issue,
    )


def _claim_issue(
    *,
    role: str,
    pass_number: int,
    claim_id: str,
    rule: str | None,
) -> dict[str, Any]:
    rule_value = rule or "claim_evidence_invalid"
    semantic = rule_value.startswith("claim_semantic_")
    return {
        "schema_version": ISSUE_SCHEMA_VERSION,
        "role": role,
        "pass_number": pass_number,
        "claim_id": claim_id,
        "stage": (
            "claim_semantic_validation"
            if semantic
            else "claim_evidence_admission"
        ),
        "category": "semantic_quality" if semantic else "evidence_unavailable",
        "rule": rule_value,
        "disposition": "withhold",
        "action": "claim_withheld",
    }


def _research_role(value: Any) -> str:
    role = _token(value, "role_claim_role_invalid")
    if role not in RESEARCH_ROLES:
        raise RoleClaimEvidenceError("role_claim_role_invalid")
    return role


def _token(value: Any, code: str) -> str:
    text = _text(value, code)
    if len(text) > 192 or any(character.isspace() for character in text):
        raise RoleClaimEvidenceError(code)
    return text


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RoleClaimEvidenceError(code)
    text = value.strip()
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in text):
        raise RoleClaimEvidenceError(code)
    return text


def _digest(value: Any) -> str:
    return "sha256:" + sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
