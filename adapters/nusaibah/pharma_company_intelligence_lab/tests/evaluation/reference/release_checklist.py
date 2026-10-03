from __future__ import annotations

from typing import Any


REQUIRED_RELEASE_EVIDENCE = (
    "intake_commit",
    "asset_version",
    "runtime_version",
    "assets_promotion_commit",
    "package_ci_passed",
    "binding_identity",
    "agent_admission_identity",
    "evaluation_report_id",
    "single_company_preview_run",
    "multi_company_isolation_run",
)


def validate_release_checklist(checklist: dict[str, Any]) -> dict[str, Any]:
    """Validate immutable rollout evidence without conflating later proof stages."""

    missing = [
        field
        for field in REQUIRED_RELEASE_EVIDENCE
        if checklist.get(field) in (None, "", False)
    ]

    apply_proven = bool(checklist.get("memory_apply_receipt")) and bool(
        checklist.get("memory_fresh_readback")
    )
    publication_proven = bool(checklist.get("publication_receipt")) and bool(
        checklist.get("publication_readback")
    )

    return {
        "schema_version": "review_release_checklist_status.v1",
        "merge_ready_evidence_complete": not missing,
        "missing_release_evidence": missing,
        "memory_apply_proven": apply_proven,
        "publication_proven": publication_proven,
        "rollback_version": checklist.get("rollback_version"),
        "notes": [
            "Promotion does not prove deployment.",
            "Preview does not prove memory apply.",
            "Apply does not prove publication.",
            "Rollback selects a prior immutable admitted version; it never overwrites published bytes.",
        ],
    }
