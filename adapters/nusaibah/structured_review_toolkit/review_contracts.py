from __future__ import annotations

from typing import Any, Iterable


class ReviewContractError(ValueError):
    """Raised when a versioned structural review contract is invalid."""


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


def _require_text_list(
    value: Any,
    *,
    field: str,
    allow_empty: bool = True,
) -> list[str]:
    items = [
        _require_text(item, field=f"{field}[]")
        for item in _require_list(value, field=field)
    ]
    if not allow_empty and not items:
        raise ReviewContractError(f"{field} must not be empty.")
    if len(items) != len(set(items)):
        raise ReviewContractError(f"{field} must contain unique values.")
    return items


def _exact_keys(value: dict[str, Any], required: Iterable[str], *, field: str) -> None:
    expected = set(required)
    actual = set(value)
    if actual != expected:
        raise ReviewContractError(
            f"{field} keys must exactly match {sorted(expected)}; got {sorted(actual)}."
        )


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
            "proposition_id",
            "polarity",
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
    for key in (
        "finding_id",
        "entity_id",
        "requirement_id",
        "section_id",
        "proposition_id",
        "statement",
    ):
        _require_text(obj[key], field=f"finding.{key}")
    if obj["polarity"] not in {"affirmed", "negated"}:
        raise ReviewContractError("Finding polarity must be affirmed or negated.")
    if obj["requirement_id"] not in known_requirement_ids:
        raise ReviewContractError("Finding requirement ID is not admitted.")

    evidence_refs = _require_text_list(
        obj["evidence_refs"],
        field="finding.evidence_refs",
    )
    contradictions = _require_text_list(
        obj["contradicting_evidence_refs"],
        field="finding.contradicting_evidence_refs",
    )
    if set(evidence_refs) & set(contradictions):
        raise ReviewContractError("One evidence reference cannot be both supporting and contradicting.")
    if not set(evidence_refs).issubset(known_evidence_refs) or not set(contradictions).issubset(
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
    if obj["date"] is not None:
        _require_text(obj["date"], field="finding.date")
    if obj["jurisdiction"] is not None:
        _require_text(obj["jurisdiction"], field="finding.jurisdiction")
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
    _require_text_list(obj["task_ids"], field="coverage_entry.task_ids")

    if obj["status"] == "reviewed" and obj["outcome"] is None:
        raise ReviewContractError("Reviewed coverage requires an explicit evidence outcome.")
    if obj["status"] != "reviewed" and obj["outcome"] is not None:
        raise ReviewContractError("Only reviewed coverage may carry an evidence outcome.")
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

    coverage = [
        validate_coverage_entry(item)
        for item in _require_list(obj["coverage"], field="review_result.coverage")
    ]
    finding_ids = _require_text_list(obj["finding_ids"], field="review_result.finding_ids")
    _require_text_list(obj["limitations"], field="review_result.limitations")
    if obj["persistence_state"] not in {"not_requested", "preview_only", "applied", "failed"}:
        raise ReviewContractError("Invalid persistence state.")

    obligation_keys = [
        (item["obligation_type"], item["obligation_id"])
        for item in coverage
    ]
    if len(obligation_keys) != len(set(obligation_keys)):
        raise ReviewContractError("Coverage contains duplicate obligation dispositions.")
    if len(finding_ids) != len(set(finding_ids)):
        raise ReviewContractError("Review result finding IDs must be unique.")

    admitted_obligations = {
        *{("requirement", item) for item in required_requirement_ids},
        *{("source_unit", item) for item in in_scope_source_ids},
    }
    covered_obligations = {
        (item["obligation_type"], item["obligation_id"])
        for item in coverage
    }
    if covered_obligations != admitted_obligations:
        raise ReviewContractError(
            "Review coverage must account for every admitted obligation exactly once."
        )

    admitted_items = [
        item
        for item in coverage
        if (item["obligation_type"], item["obligation_id"]) in admitted_obligations
    ]
    if any(item["status"] == "excluded_by_scope" for item in admitted_items):
        raise ReviewContractError(
            "An admitted obligation cannot be excluded by scope."
        )

    complete_outcome = obj["review_outcome"] in {
        "review_complete",
        "review_complete_with_evidence_gaps",
    }
    if complete_outcome and any(item["status"] != "reviewed" for item in admitted_items):
        raise ReviewContractError(
            "A complete review requires every admitted obligation to be reviewed."
        )
    if obj["review_outcome"] in {"review_complete", "review_complete_with_evidence_gaps"} and obj[
        "execution_state"
    ] != "completed":
        raise ReviewContractError("A complete review requires completed execution.")
    if obj["execution_state"] == "failed" and obj["review_outcome"] != "failed":
        raise ReviewContractError("Failed execution must project a failed review outcome.")
    if obj["execution_state"] == "blocked" and obj["review_outcome"] != "blocked":
        raise ReviewContractError("Blocked execution must project a blocked review outcome.")
    return dict(obj)
