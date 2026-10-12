from __future__ import annotations

from typing import Any, ClassVar
from adapters.base import Adapter

if __package__:
    from .scope_contract import MAX_COMPANY_IDS, CompanyScopeError, build_scope_result
else:
    from scope_contract import MAX_COMPANY_IDS, CompanyScopeError, build_scope_result


class CompanyScopeAdapter(Adapter):
    """Assemble bounded contexts from an already-resolved binding-only role."""

    key: ClassVar[str] = "nusaibah.company_scope"
    version: ClassVar[str] = "0.1.0"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        del context
        if not isinstance(inputs, dict) or set(inputs) != {"variables", "companies"}:
            raise CompanyScopeError("company_scope_input_invalid")
        result = build_scope_result(inputs["variables"], inputs["companies"])
        # No company values, IDs, or digests in the scalar summary or metrics.
        summary = {
            "schema_version": "company_scope_summary.v1",
            "company_count": result["company_count"],
            "duplicate_id_count": result["duplicate_id_count"],
            "complete": True,
            "max_company_ids": MAX_COMPANY_IDS,
            "validation_scope": "resolved_rows_only",
            "runtime_authority_verified": False,
            "agent_call_count": 0,
            "mutable_call_count": 0,
        }
        return {
            "response_version": "1", "status": "success",
            "outputs": {"company_scope_result": result, "company_scope_summary": summary},
            "metrics": {
                "company_count": result["company_count"],
                "agent_call_count": 0, "child_call_count": 0,
                "mutable_dynamic_skill_call_count": 0, "adapter_query_call_count": 0,
            },
        }
