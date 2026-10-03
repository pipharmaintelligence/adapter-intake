from __future__ import annotations

from typing import Any


PROMOTION_P0_P8_FIELDS = (
    "intake_repository",
    "intake_commit",
    "intake_contract_ci_run",
    "asset_version",
    "methodology_identity",
    "runtime_version",
    "assets_base_commit",
    "promotion_plan_run",
    "materialization_report_id",
    "runtime_catalog_identity",
    "package_ci_run",
    "assets_merge_commit",
    "deployment_substrate",
    "deployment_identity",
)

DOWNSTREAM_LIVE_FIELDS = (
    "binding_identity",
    "agent_admission_identity",
    "evaluation_report_id",
    "single_company_preview_run",
    "multi_company_isolation_run",
    "rollback_version",
)


def _missing(checklist: dict[str, Any], fields: tuple[str, ...]) -> list[str]:
    return [
        field
        for field in fields
        if checklist.get(field) in (None, "", False)
    ]


def validate_release_checklist(checklist: dict[str, Any]) -> dict[str, Any]:
    """Validate immutable rollout evidence without conflating lifecycle stages."""

    promotion_missing = _missing(checklist, PROMOTION_P0_P8_FIELDS)
    live_missing = _missing(checklist, DOWNSTREAM_LIVE_FIELDS)

    apply_proven = bool(checklist.get("memory_apply_receipt")) and bool(
        checklist.get("memory_fresh_readback")
    )
    publication_proven = bool(checklist.get("publication_receipt")) and bool(
        checklist.get("publication_readback")
    )

    promotion_complete = not promotion_missing
    live_preview_complete = promotion_complete and not live_missing

    return {
        "schema_version": "review_release_checklist_status.v1",
        "promotion_p0_p8_complete": promotion_complete,
        "missing_promotion_evidence": promotion_missing,
        "live_preview_evidence_complete": live_preview_complete,
        "missing_live_evidence": live_missing,
        "memory_apply_proven": apply_proven,
        "publication_proven": publication_proven,
        "rollback_version": checklist.get("rollback_version"),
        "notes": [
            "Intake CI does not prove Assets materialization or package CI.",
            "Promotion/package CI does not prove deployment.",
            "Deployment does not prove governed binding or Agent admission.",
            "Preview does not prove memory apply.",
            "Apply does not prove publication.",
            "Rollback selects a prior immutable admitted version; it never overwrites published bytes.",
        ],
    }
