"""Read-only callable child: independently governed input and Agent."""
from __future__ import annotations
from typing import Any, ClassVar
from adapters.base import Adapter

class CallableProbeChildAdapter(Adapter):
    """Consume a bounded governed record set and invoke one child-owned Agent."""
    key: ClassVar[str] = "nusaibah.callable_probe_child"
    version: ClassVar[str] = "0.1.0"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        """Return only count and execution-status flags; no raw data."""
        del context
        variables = inputs.get("variables", {})
        if not isinstance(variables, dict) or set(variables) - {"proof_tag"}:
            raise ValueError("callable_probe_variables_invalid")
        data = inputs.get("records")
        if not isinstance(data, dict) or not isinstance(data.get("records"), list):
            raise ValueError("callable_probe_governed_records_missing")
        count = len(data["records"])
        if count > 20 or any(not isinstance(r, dict) for r in data["records"]):
            raise ValueError("callable_probe_record_shape_invalid")
        agent = inputs.invoke_agent("summarizer", input={
            "task": "Acknowledge this bounded record count only.",
            "record_count": count
        }, on_error="raise")
        if not isinstance(agent, dict) or agent.get("status") != "completed":
            raise RuntimeError("callable_probe_agent_incomplete")
        return {"response_version": "1", "status": "success",
            "outputs": {"probe_result": {
                "schema_version": "callable_probe_result.v1",
                "record_count": count, "agent_completed": True, "preview_only": True
            }},
            "metrics": {"agent_call_count": 1, "mutable_dynamic_skill_call_count": 0}}
