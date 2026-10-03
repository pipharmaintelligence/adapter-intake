from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

from review_evaluation_status import source_digest


class AdjudicationReceiptError(ValueError):
    """Raised when a WP1 adjudication receipt is incomplete or inconsistent."""


RECEIPT_SCHEMA_VERSION = "pharma_review_adjudication_receipt.v1"


def adjudication_input_digest(value: Any) -> str:
    """Return a deterministic digest binding reviewer approval to exact input content."""

    try:
        canonical = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AdjudicationReceiptError(
            "Adjudication input must be JSON-compatible."
        ) from exc
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def build_adjudication_receipt_template(
    suite: dict[str, Any],
    taxonomy: dict[str, Any],
) -> dict[str, Any]:
    """Build a reviewer-facing receipt bound to the exact candidate inputs."""

    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "suite_id": suite["suite_id"],
        "suite_input_digest": adjudication_input_digest(suite),
        "taxonomy_input_digest": adjudication_input_digest(taxonomy),
        "reviewer": {
            "name": None,
            "qualification_basis": None,
        },
        "taxonomy": {
            "decision": "pending",
            "notes": None,
        },
        "thresholds": {
            "decision": "pending",
            "domain_owner": None,
            "decision_note": None,
            "factual_faithfulness_min": None,
            "noncritical_precision_min": None,
            "noncritical_recall_min": None,
        },
        "cases": [
            {
                "case_id": case["case_id"],
                "decision": "pending",
                "notes": None,
                "disagreement": False,
                "secondary_reviewer": None,
                "disagreement_resolution": None,
            }
            for case in suite["cases"]
        ],
    }


def _nonempty_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AdjudicationReceiptError(f"{field} must be non-empty text.")
    return value.strip()


def _unit_interval(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AdjudicationReceiptError(f"{field} must be numeric.")
    numeric = float(value)
    if not 0 <= numeric <= 1:
        raise AdjudicationReceiptError(f"{field} must be between 0 and 1.")
    return numeric


def apply_adjudication_receipt(
    suite: dict[str, Any],
    taxonomy: dict[str, Any],
    receipt: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply a complete human/domain-owner approval receipt to copies of WP1 fixtures.

    This helper never edits source semantics. Any requested revision must be applied and
    reviewed before a new all-approved receipt is used.
    """

    if not isinstance(receipt, dict):
        raise AdjudicationReceiptError("receipt must be an object.")
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise AdjudicationReceiptError("Unsupported adjudication receipt schema.")
    if receipt.get("suite_id") != suite.get("suite_id"):
        raise AdjudicationReceiptError("Receipt suite identity mismatch.")
    if receipt.get("suite_input_digest") != adjudication_input_digest(suite):
        raise AdjudicationReceiptError(
            "Receipt does not match the exact suite content reviewed."
        )
    if receipt.get("taxonomy_input_digest") != adjudication_input_digest(taxonomy):
        raise AdjudicationReceiptError(
            "Receipt does not match the exact taxonomy content reviewed."
        )

    reviewer = receipt.get("reviewer")
    if not isinstance(reviewer, dict):
        raise AdjudicationReceiptError("reviewer must be an object.")
    reviewer_name = _nonempty_text(reviewer.get("name"), field="reviewer.name")
    _nonempty_text(
        reviewer.get("qualification_basis"),
        field="reviewer.qualification_basis",
    )

    taxonomy_receipt = receipt.get("taxonomy")
    if not isinstance(taxonomy_receipt, dict):
        raise AdjudicationReceiptError("taxonomy must be an object.")
    if taxonomy_receipt.get("decision") != "approved":
        raise AdjudicationReceiptError(
            "Taxonomy must be explicitly approved before WP1 can close."
        )
    _nonempty_text(taxonomy_receipt.get("notes"), field="taxonomy.notes")

    threshold_receipt = receipt.get("thresholds")
    if not isinstance(threshold_receipt, dict):
        raise AdjudicationReceiptError("thresholds must be an object.")
    if threshold_receipt.get("decision") != "approved":
        raise AdjudicationReceiptError(
            "Threshold calibration must be explicitly approved before WP1 can close."
        )
    domain_owner = _nonempty_text(
        threshold_receipt.get("domain_owner"),
        field="thresholds.domain_owner",
    )
    decision_note = _nonempty_text(
        threshold_receipt.get("decision_note"),
        field="thresholds.decision_note",
    )
    calibrated = {
        field: _unit_interval(threshold_receipt.get(field), field=f"thresholds.{field}")
        for field in (
            "factual_faithfulness_min",
            "noncritical_precision_min",
            "noncritical_recall_min",
        )
    }

    case_receipts = receipt.get("cases")
    if not isinstance(case_receipts, list):
        raise AdjudicationReceiptError("cases must be a list.")

    expected_ids = [case["case_id"] for case in suite["cases"]]
    by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(case_receipts):
        if not isinstance(item, dict):
            raise AdjudicationReceiptError(f"cases[{index}] must be an object.")
        case_id = _nonempty_text(item.get("case_id"), field=f"cases[{index}].case_id")
        if case_id in by_id:
            raise AdjudicationReceiptError("Duplicate case receipt.")
        by_id[case_id] = item

    if set(by_id) != set(expected_ids):
        raise AdjudicationReceiptError(
            "Receipt must account for every suite case exactly once."
        )

    approved_cases: dict[str, dict[str, Any]] = {}
    for case_id in expected_ids:
        item = by_id[case_id]
        if item.get("decision") != "approved":
            raise AdjudicationReceiptError(
                f"{case_id} must be approved after any requested revisions are applied."
            )
        notes = _nonempty_text(item.get("notes"), field=f"{case_id}.notes")
        disagreement = item.get("disagreement")
        if not isinstance(disagreement, bool):
            raise AdjudicationReceiptError(f"{case_id}.disagreement must be boolean.")

        secondary_reviewer = item.get("secondary_reviewer")
        if disagreement:
            secondary_reviewer = _nonempty_text(
                secondary_reviewer,
                field=f"{case_id}.secondary_reviewer",
            )
            _nonempty_text(
                item.get("disagreement_resolution"),
                field=f"{case_id}.disagreement_resolution",
            )
        elif secondary_reviewer is not None and (
            not isinstance(secondary_reviewer, str) or not secondary_reviewer.strip()
        ):
            raise AdjudicationReceiptError(
                f"{case_id}.secondary_reviewer must be null or non-empty text."
            )

        approved_cases[case_id] = {
            "notes": notes,
            "disagreement": disagreement,
            "secondary_reviewer": (
                secondary_reviewer.strip()
                if isinstance(secondary_reviewer, str)
                else None
            ),
        }

    updated_suite = deepcopy(suite)
    updated_taxonomy = deepcopy(taxonomy)

    updated_suite["status"] = "adjudicated"
    updated_suite["adjudication_policy"]["assigned_domain_reviewer"] = reviewer_name

    for case in updated_suite["cases"]:
        decision = approved_cases[case["case_id"]]
        case["adjudication"] = {
            "status": "adjudicated",
            "primary_reviewer": reviewer_name,
            "secondary_reviewer": decision["secondary_reviewer"],
            "disagreement": decision["disagreement"],
            "review_notes": decision["notes"],
        }
        case["source_identity"]["digest_status"] = "frozen"
        case["source_identity"]["content_sha256"] = source_digest(case)

    policy = updated_suite["quality_threshold_policy"]
    policy["status"] = "calibrated"
    policy["calibrated_thresholds"] = calibrated
    policy["calibration"]["assigned_domain_owner"] = domain_owner
    policy["calibration"]["decision_note"] = decision_note

    updated_taxonomy["status"] = "adjudicated"
    updated_taxonomy["adjudication"]["assigned_domain_reviewer"] = reviewer_name
    updated_taxonomy["adjudication"]["review_notes"] = taxonomy_receipt["notes"].strip()

    return updated_suite, updated_taxonomy
