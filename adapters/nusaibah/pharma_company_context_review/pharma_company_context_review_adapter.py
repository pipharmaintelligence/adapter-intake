from __future__ import annotations

from typing import Any, ClassVar
from adapters.base import Adapter

AGENT_ORCHESTRATION_OWNER = "python_adapter"

if __package__:
    from .company_context_review import run_review
else:
    from company_context_review import run_review


class NusaibahPharmaCompanyContextReviewAdapter(Adapter):
    key: ClassVar[str] = "nusaibah.pharma_company_context_review"
    version: ClassVar[str] = "0.1.0"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        del context
        result = run_review(inputs)
        summary = {key: result[key] for key in ("review_outcome", "agent_call_count", "mutable_call_count",
            "child_call_count", "execution_state", "preview_only", "publication_allowed", "synthetic")}
        summary.update({"schema_version": "company_context_review_summary.v1",
            "accepted_finding_count": len(result["accepted_findings"]), "withheld_finding_count": len(result["withheld_findings"])})
        return {"response_version": "1", "status": "success", "outputs": {
            "evaluation_result": {"record": result}, "evaluation_summary": summary}, "metrics": {
            "agent_call_count": result["agent_call_count"], "tool_call_count": result["child_call_count"],
            "mutable_dynamic_skill_call_count": 0, "company_count": 1}}
