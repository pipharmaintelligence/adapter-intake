"""Generic parent for signed callable child qualification."""
from __future__ import annotations
from typing import Any, ClassVar
from adapters.base import Adapter

class CallableProbeParentAdapter(Adapter):
    """Invoke one pinned child and validate its safe output."""
    key: ClassVar[str] = "nusaibah.callable_probe_parent"
    version: ClassVar[str] = "0.1.0"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        """Return a count-only preview from the exact callable child."""
        del context
        variables = inputs.get("variables", {})
        if not isinstance(variables, dict) or set(variables) - {"proof_tag"}:
            raise ValueError("callable_probe_parent_variables_invalid")
        response = inputs.invoke_asset("probe", variables=variables, on_error="raise")
        if not isinstance(response, dict) or response.get("status") != "success":
            raise RuntimeError("callable_probe_child_failed")
        source = response.get("provenance")
        if (not isinstance(source, dict) or source.get("callable_asset") is not True
            or source.get("asset_key") != "nusaibah.callable_probe_child"
            or source.get("asset_version") != "0.1.0"):
            raise RuntimeError("callable_probe_child_identity_invalid")
        result = response.get("result")
        if (not isinstance(result, dict) or result.get("schema_version") != "callable_probe_result.v1"
            or type(result.get("record_count")) is not int or not 0 <= result["record_count"] <= 20
            or result.get("agent_completed") is not True or result.get("preview_only") is not True):
            raise RuntimeError("callable_probe_child_result_invalid")
        return {"response_version": "1", "status": "success",
            "outputs": {"probe_summary": dict(result)},
            "metrics": {"callable_child_call_count": 1, "mutable_dynamic_skill_call_count": 0}}
