from __future__ import annotations

from typing import Any, ClassVar
from adapters.base import Adapter

AGENT_ORCHESTRATION_OWNER = "python_adapter"

if __package__:
    from .supplied_source_review import run_review
else:
    from supplied_source_review import run_review


class NusaibahPharmaCompanyIntelligenceLabEvaluationV020Adapter(Adapter):
    """A separately versioned synthetic supplied-source review, not baseline replay."""

    key: ClassVar[str] = "nusaibah.pharma_company_intelligence_lab_evaluation"
    version: ClassVar[str] = "0.2.0"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        del context
        result = run_review(inputs)
        return {
            "response_version": "1", "status": "success",
            "outputs": {"evaluation_result": result},
            "logs": [{"level": "info", "message": "Supplied-source preview review finished."}],
            "metrics": {"agent_call_count": result["agent_call_count"],
                        "mutable_dynamic_skill_call_count": 0,
                        "chunk_count": len(result["plan"]["chunk_ids"])},
        }
