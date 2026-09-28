from __future__ import annotations

from typing import Any

from adapters.base import Adapter

try:
    from .dossier_contract import DOSSIER_SCHEMA_VERSION, render_empty_sections
    from .input_contract import (
        company_name,
        order_records_for_request,
        resolve_company_records,
        validate_batch_request,
    )
except ImportError:  # pragma: no cover - local adapter-root execution path
    from dossier_contract import DOSSIER_SCHEMA_VERSION, render_empty_sections
    from input_contract import (
        company_name,
        order_records_for_request,
        resolve_company_records,
        validate_batch_request,
    )


class NusaibahPharmaCompanyIntelligenceLabAdapter(Adapter):
    """Foundation adapter for governed multi-company intelligence orchestration.

    v0.1.0 foundation code intentionally performs no provider execution. It
    validates the governed batch contract and emits the canonical DTO hierarchy
    so intake/package checks can be proven before live Agent composition is added.
    """

    key = "nusaibah.pharma_company_intelligence_lab"
    version = "0.1.0"

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Validate batch isolation and return deterministic canonical DTO shells."""
        request = validate_batch_request(inputs)
        records = order_records_for_request(resolve_company_records(inputs), request)

        company_results = [
            {
                "company_id": record["company_id"],
                "company_name": company_name(record),
                "status": "foundation_ready",
                "sections": render_empty_sections(),
                "quality_gate_passed": False,
                "memory_update_status": "not_evaluated",
                "memory_readback_verified": False,
            }
            for record in records
        ]

        dossier = {
            "schema_version": DOSSIER_SCHEMA_VERSION,
            "status": "foundation_ready",
            "requested_company_count": len(request.company_ids),
            "completed_company_count": len(company_results),
            "failed_company_count": 0,
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
                        "Validated governed batch identity and rendered the canonical dossier DTO foundation."
                    ),
                }
            ],
            "metrics": {
                "requested_company_count": len(request.company_ids),
                "resolved_company_count": len(records),
                "provider_calls_made": 0,
                "memory_mutations_made": 0,
            },
        }
