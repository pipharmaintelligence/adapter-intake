from __future__ import annotations

from typing import Any, ClassVar
from adapters.base import Adapter

AGENT_ORCHESTRATION_OWNER = "python_adapter"

if __package__:
    from .supplied_source_review import run_review
else:
    from supplied_source_review import run_review


class NusaibahPharmaCompanyIntelligenceLabEvaluationV021Adapter(Adapter):
    """Supplied-source review with a bounded scalar result summary."""

    key: ClassVar[str] = "nusaibah.pharma_company_intelligence_lab_evaluation"
    version: ClassVar[str] = "0.2.1"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        del context
        result = run_review(inputs)
        summary = {key: result[key] for key in (
            "review_outcome", "agent_call_count", "mutable_call_count", "execution_state",
            "preview_only", "publication_allowed", "baseline_comparable", "external_truth_verified",
        )}
        summary.update({
            "schema_version": "pharma_supplied_source_review_summary.v1",
            "accepted_finding_count": len(result["accepted_findings"]),
            "withheld_finding_count": len(result["withheld_findings"]),
            "chunk_count": len(result["plan"]["chunk_ids"]),
        })
        return {
            "response_version": "1", "status": "success",
            "outputs": {"evaluation_result": result, "evaluation_summary": summary},
            "logs": [{"level": "info", "message": "Supplied-source preview review finished."}],
            "metrics": {"agent_call_count": result["agent_call_count"],
                        "mutable_dynamic_skill_call_count": 0,
                        "chunk_count": len(result["plan"]["chunk_ids"])},
        }
