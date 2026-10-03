from __future__ import annotations

from typing import Any, Iterable


class ReviewContractError(ValueError):
    """Raised when an evaluation-only specialized-review contract is invalid."""


SCOPE_MODES = frozenset({"exhaustive_in_scope", "focused"})
EVIDENCE_STATES = frozenset({"supported", "contradicted", "insufficient", "not_applicable"})
EVIDENCE_STRENGTHS = frozenset({"inspected_span", "reference_only", "memory_context"})
COVERAGE_STATUSES = frozenset(
    {"assigned", "reviewed", "excluded_by_scope", "inaccessible", "unreviewed"}
)
REVIEW_OUTCOMES = frozenset(
    {
        "review_complete",
        "review_complete_with_evidence_gaps",
        "review_incomplete",
        "blocked",
        "failed",
    }
)
EXECUTION_STATES = frozenset({"completed", "incomplete", "blocked", "failed"})


def _require_mapping(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReviewContractError(f"{field} must be an object.")
    return value


def _require_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewContractError(f"{field} must be non-empty text.")
    return value.strip()


def _require_list(value: Any, *, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReviewContractError(f"{field} must be a list.")
    return value


def _exact_keys(value: dict[str, Any], required: Iterable[str], *, field: str) -> None:
    expected = set(required)
    actual = set(value)
    if actual != expected:
        raise ReviewContractError(
            f"{field} keys must exactly match {sorted(expected)}; got {sorted(actual)}."
        )


def validate_source_snapshot(value: Any) -> dict[str, Any]:
    """Validate immutable source identity and declared review scope."""

    obj = _require_mapping(value, field="source_snapshot")
    _exact_keys(
        obj,
        {
            "schema_version",
            "entity_id",
            "source_id",
            "source_version",
            "source_hash",
            "extraction_version",
            "scope_mode",
            "inventory_ids",
            "inaccessible_ids",
        },
        field="source_snapshot",
    )
    if obj["schema_version"] != "review_source_snapshot.v1":
        raise ReviewContractError("Unsupported source snapshot schema.")
    for key in ("entity_id", "source_id", "source_version", "source_hash", "extraction_version"):
        _require_text(obj[key], field=f"source_snapshot.{key}")
    if obj["scope_mode"] not in SCOPE_MODES:
        raise ReviewContractError("Invalid review scope mode.")

    inventory = [_require_text(item, field="inventory_id") for item in _require_list(
        obj["inventory_ids"], field="source_snapshot.inventory_ids"
    )]
    inaccessible = [_require_text(item, field="inaccessible_id") for item in _require_list(
        obj["inaccessible_ids"], field="source_snapshot.inaccessible_ids"
    )]
    if len(inventory) != len(set(inventory)):
        raise ReviewContractError("Source inventory IDs must be unique.")
    if not set(inaccessible).issubset(inventory):
        raise ReviewContractError("Inaccessible source IDs must belong to the inventory.")
    return dict(obj)


def validate_source_chunk(value: Any, *, snapshot: dict[str, Any]) -> dict[str, Any]:
    """Validate stable chunk identity without granting source authority."""

    obj = _require_mapping(value, field="source_chunk")
    _exact_keys(
        obj,
        {
            "schema_version",
            "chunk_id",
            "snapshot_id",
            "entity_id",
            "source_hash",
            "chunk_digest",
            "locators",
            "text",
            "quality_flags",
            "context_only_locators",
        },
        field="source_chunk",
    )
    if obj["schema_version"] != "review_source_chunk.v1":
        raise ReviewContractError("Unsupported source chunk schema.")
    _require_text(obj["chunk_id"], field="source_chunk.chunk_id")
    _require_text(obj["chunk_digest"], field="source_chunk.chunk_digest")
    if obj["entity_id"] != snapshot["entity_id"] or obj["source_hash"] != snapshot["source_hash"]:
        raise ReviewContractError("Chunk source identity does not match the admitted snapshot.")
    locators = [_require_text(item, field="source_chunk.locator") for item in _require_list(
        obj["locators"], field="source_chunk.locators"
    )]
    if not set(locators).issubset(set(snapshot["inventory_ids"])):
        raise ReviewContractError("Chunk references a locator outside the source inventory.")
    context_only = [_require_text(item, field="source_chunk.context_only_locator") for item in _require_list(
        obj["context_only_locators"], field="source_chunk.context_only_locators"
    )]
    if not set(context_only).issubset(set(locators)):
        raise ReviewContractError("Context-only locators must be part of the chunk.")
    if not isinstance(obj["text"], str):
        raise ReviewContractError("source_chunk.text must be a string.")
    _require_list(obj["quality_flags"], field="source_chunk.quality_flags")
    return dict(obj)


def validate_methodology_requirement(value: Any) -> dict[str, Any]:
    obj = _require_mapping(value, field="methodology_requirement")
    _exact_keys(
        obj,
        {
            "schema_version",
            "methodology_ref",
            "methodology_version",
            "methodology_digest",
            "requirement_id",
            "role",
            "risk_class",
            "mandatory",
            "applicability_rule",
            "expected_evidence_class",
            "acceptance_criterion",
        },
        field="methodology_requirement",
    )
    if obj["schema_version"] != "review_requirement.v1":
        raise ReviewContractError("Unsupported requirement schema.")
    for key in (
        "methodology_ref",
        "methodology_version",
        "methodology_digest",
        "requirement_id",
        "role",
        "risk_class",
        "applicability_rule",
        "expected_evidence_class",
        "acceptance_criterion",
    ):
        _require_text(obj[key], field=f"methodology_requirement.{key}")
    if not isinstance(obj["mandatory"], bool):
        raise ReviewContractError("methodology_requirement.mandatory must be boolean.")
    return dict(obj)


def validate_review_task(
    value: Any,
    *,
    known_requirement_ids: set[str],
    known_chunk_ids: set[str],
) -> dict[str, Any]:
    obj = _require_mapping(value, field="review_task")
    _exact_keys(
        obj,
        {
            "schema_version",
            "run_id",
            "entity_id",
            "task_id",
            "role",
            "requirement_ids",
            "chunk_ids",
            "memory_ref_ids",
            "output_schema",
            "logical_call_budget",
            "provider_step_budget",
            "transport_attempt_budget",
        },
        field="review_task",
    )
    if obj["schema_version"] != "review_task.v1":
        raise ReviewContractError("Unsupported task schema.")
    for key in ("run_id", "entity_id", "task_id", "role", "output_schema"):
        _require_text(obj[key], field=f"review_task.{key}")
    requirement_ids = set(_require_list(obj["requirement_ids"], field="review_task.requirement_ids"))
    chunk_ids = set(_require_list(obj["chunk_ids"], field="review_task.chunk_ids"))
    if not requirement_ids or not requirement_ids.issubset(known_requirement_ids):
        raise ReviewContractError("Task requirement IDs must be non-empty and admitted.")
    if not chunk_ids or not chunk_ids.issubset(known_chunk_ids):
        raise ReviewContractError("Task chunk IDs must be non-empty and admitted.")
    _require_list(obj["memory_ref_ids"], field="review_task.memory_ref_ids")
    for field in ("logical_call_budget", "provider_step_budget", "transport_attempt_budget"):
        if not isinstance(obj[field], int) or obj[field] < 1:
            raise ReviewContractError(f"review_task.{field} must be a positive integer.")
    return dict(obj)


def validate_finding(
    value: Any,
    *,
    known_requirement_ids: set[str],
    known_evidence_refs: set[str],
) -> dict[str, Any]:
    obj = _require_mapping(value, field="finding")
    _exact_keys(
        obj,
        {
            "schema_version",
            "finding_id",
            "entity_id",
            "requirement_id",
            "section_id",
            "statement",
            "evidence_refs",
            "contradicting_evidence_refs",
            "evidence_state",
            "evidence_strength",
            "observed_or_inferred",
            "date",
            "jurisdiction",
            "high_impact",
            "verification_reason",
        },
        field="finding",
    )
    if obj["schema_version"] != "review_finding.v1":
        raise ReviewContractError("Unsupported finding schema.")
    for key in ("finding_id", "entity_id", "requirement_id", "section_id", "statement"):
        _require_text(obj[key], field=f"finding.{key}")
    if obj["requirement_id"] not in known_requirement_ids:
        raise ReviewContractError("Finding requirement ID is not admitted.")
    evidence_refs = set(_require_list(obj["evidence_refs"], field="finding.evidence_refs"))
    contradictions = set(
        _require_list(
            obj["contradicting_evidence_refs"],
            field="finding.contradicting_evidence_refs",
        )
    )
    if not evidence_refs.issubset(known_evidence_refs) or not contradictions.issubset(
        known_evidence_refs
    ):
        raise ReviewContractError("Finding cites an unknown evidence reference.")
    if obj["evidence_state"] not in EVIDENCE_STATES:
        raise ReviewContractError("Invalid finding evidence state.")
    if obj["evidence_strength"] not in EVIDENCE_STRENGTHS:
        raise ReviewContractError("Invalid finding evidence strength.")
    if obj["observed_or_inferred"] not in {"observed", "inferred"}:
        raise ReviewContractError("Finding must distinguish observed from inferred.")
    if not isinstance(obj["high_impact"], bool):
        raise ReviewContractError("finding.high_impact must be boolean.")
    if obj["date"] is not None and not isinstance(obj["date"], str):
        raise ReviewContractError("finding.date must be text or null.")
    if obj["jurisdiction"] is not None and not isinstance(obj["jurisdiction"], str):
        raise ReviewContractError("finding.jurisdiction must be text or null.")
    _require_text(obj["verification_reason"], field="finding.verification_reason")
    return dict(obj)


def validate_coverage_entry(value: Any) -> dict[str, Any]:
    obj = _require_mapping(value, field="coverage_entry")
    _exact_keys(
        obj,
        {
            "schema_version",
            "obligation_type",
            "obligation_id",
            "status",
            "outcome",
            "reason",
            "task_ids",
        },
        field="coverage_entry",
    )
    if obj["schema_version"] != "review_coverage.v1":
        raise ReviewContractError("Unsupported coverage schema.")
    if obj["obligation_type"] not in {"requirement", "source_unit"}:
        raise ReviewContractError("Invalid coverage obligation type.")
    _require_text(obj["obligation_id"], field="coverage_entry.obligation_id")
    if obj["status"] not in COVERAGE_STATUSES:
        raise ReviewContractError("Invalid coverage status.")
    if obj["outcome"] is not None and obj["outcome"] not in EVIDENCE_STATES:
        raise ReviewContractError("Invalid coverage evidence outcome.")
    _require_text(obj["reason"], field="coverage_entry.reason")
    _require_list(obj["task_ids"], field="coverage_entry.task_ids")
    if obj["status"] == "reviewed" and obj["outcome"] is None:
        raise ReviewContractError("Reviewed coverage requires an explicit evidence outcome.")
    return dict(obj)


def validate_review_result(
    value: Any,
    *,
    required_requirement_ids: set[str],
    in_scope_source_ids: set[str],
) -> dict[str, Any]:
    obj = _require_mapping(value, field="review_result")
    _exact_keys(
        obj,
        {
            "schema_version",
            "scope_mode",
            "execution_state",
            "review_outcome",
            "coverage",
            "finding_ids",
            "limitations",
            "persistence_state",
        },
        field="review_result",
    )
    if obj["schema_version"] != "review_result.v1":
        raise ReviewContractError("Unsupported review-result schema.")
    if obj["scope_mode"] not in SCOPE_MODES:
        raise ReviewContractError("Invalid result scope mode.")
    if obj["execution_state"] not in EXECUTION_STATES:
        raise ReviewContractError("Invalid execution state.")
    if obj["review_outcome"] not in REVIEW_OUTCOMES:
        raise ReviewContractError("Invalid review outcome.")
    coverage = [validate_coverage_entry(item) for item in _require_list(
        obj["coverage"], field="review_result.coverage"
    )]
    _require_list(obj["finding_ids"], field="review_result.finding_ids")
    _require_list(obj["limitations"], field="review_result.limitations")
    if obj["persistence_state"] not in {"not_requested", "preview_only", "applied", "failed"}:
        raise ReviewContractError("Invalid persistence state.")

    covered_requirements = {
        item["obligation_id"] for item in coverage if item["obligation_type"] == "requirement"
    }
    covered_sources = {
        item["obligation_id"] for item in coverage if item["obligation_type"] == "source_unit"
    }
    if obj["scope_mode"] == "exhaustive_in_scope":
        if covered_requirements != required_requirement_ids:
            raise ReviewContractError("Exhaustive review must account for every requirement.")
        if covered_sources != in_scope_source_ids:
            raise ReviewContractError("Exhaustive review must account for every source unit.")

    incomplete = any(
        item["status"] in {"inaccessible", "unreviewed", "assigned"}
        for item in coverage
    )
    if incomplete and obj["review_outcome"] in {
        "review_complete",
        "review_complete_with_evidence_gaps",
    }:
        raise ReviewContractError("Unreviewed/inaccessible work cannot be reported complete.")
    return dict(obj)
