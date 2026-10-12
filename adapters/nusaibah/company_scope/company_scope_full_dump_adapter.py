from __future__ import annotations

from typing import Any, ClassVar
from adapters.base import Adapter

if __package__:
    from .scope_contract import MAX_COMPANY_IDS, CompanyScopeError
    from .scope_page_contract import build_scope_page
else:
    from scope_contract import MAX_COMPANY_IDS, CompanyScopeError
    from scope_page_contract import build_scope_page


class CompanyScopeFullDumpAdapter(Adapter):
    """Project one governed full-dump page; Assets owns continuation and history."""

    key: ClassVar[str] = "nusaibah.company_scope"
    version: ClassVar[str] = "0.1.1"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        del context
        if not isinstance(inputs, dict) or set(inputs) != {"variables", "companies"}:
            raise CompanyScopeError("company_scope_input_invalid")
        page = build_scope_page(inputs["variables"], inputs["companies"])
        summary = {
            "schema_version": "company_scope_page_summary.v1",
            "company_count": page["company_count"],
            "max_company_ids": MAX_COMPANY_IDS,
            "page_index": page["page"]["page_index"],
            "record_offset": page["page"]["record_offset"],
            "batch_complete": True,
            "source_exhausted": page["source_exhausted"],
            "selection_completion": "framework_owned",
            "completion_scope": "current_page",
            "validation_scope": "resolved_page_only",
            "runtime_authority_verified": False,
            "agent_call_count": 0, "mutable_call_count": 0,
        }
        return {
            "response_version": "1", "status": "success",
            "outputs": {"company_scope_page": page, "company_scope_summary": summary},
            "metrics": {
                "company_count": page["company_count"],
                "agent_call_count": 0, "child_call_count": 0,
                "mutable_dynamic_skill_call_count": 0, "adapter_query_call_count": 0,
            },
        }
