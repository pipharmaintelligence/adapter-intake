from __future__ import annotations

from typing import Any, ClassVar

AGENT_ORCHESTRATION_OWNER = "python_adapter"

if __package__:
    from .evaluation_preflight import require_diagnostic_preflight
    from .nusaibah_pharma_company_intelligence_lab_evaluation_v0_1_1_adapter import (
        NusaibahPharmaCompanyIntelligenceLabEvaluationV011Adapter as _DiagnosticBase,
    )
else:
    from evaluation_preflight import require_diagnostic_preflight
    from nusaibah_pharma_company_intelligence_lab_evaluation_v0_1_1_adapter import (
        NusaibahPharmaCompanyIntelligenceLabEvaluationV011Adapter as _DiagnosticBase,
    )


class NusaibahPharmaCompanyIntelligenceLabEvaluationV012Adapter(_DiagnosticBase):
    """Require explicit diagnostic purpose before the unchanged frozen replay."""

    key: ClassVar[str] = "nusaibah.pharma_company_intelligence_lab_evaluation"
    version: ClassVar[str] = "0.1.2"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        preflight = require_diagnostic_preflight(inputs)
        result = super().invoke(inputs, context)
        result["outputs"]["evaluation_result"]["execution_preflight"] = preflight
        return result

    @staticmethod
    def _case_index(inputs: Any) -> int:
        # Preflight validates the extra purpose before the inherited executor.
        require_diagnostic_preflight(inputs)
        return _DiagnosticBase._case_index({
            "variables": {"case_index": inputs["variables"]["case_index"]},
        })
