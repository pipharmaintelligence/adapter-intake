from __future__ import annotations

import hashlib
import json
from typing import Any, ClassVar
from adapters.base import Adapter


class SyntheticReviewToolsDemoAdapter(Adapter):
    """Domain configuration over the same admitted deterministic toolkit."""

    key: ClassVar[str] = 'nusaibah.company_review_tools_demo'
    version: ClassVar[str] = "0.1.0"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        del context
        values = inputs.get("variables")
        expected = {"source", "policy", "source_hash", "evidence", "findings", "semantic_verdicts", "result"}
        if not isinstance(values, dict) or set(values) != expected:
            raise ValueError("synthetic_review_input_invalid")
        source = values.get("source")
        if not isinstance(source, dict) or not isinstance(source.get("entity_id"), str) or not source["entity_id"].startswith('synthetic-company:'):
            raise ValueError("synthetic_review_entity_scope_invalid")
        request = {
            "schema_version": "review_tool_request.v1", "operation": "assemble_preview",
            "arguments": {**values, "methodology": {"ref": 'demo.company-identity', "version": "1.0.0", "requirements": ['company.identity']}},
        }
        response = inputs.invoke_asset("review_toolkit", variables=request, on_error="raise")
        if not isinstance(response, dict) or response.get("status") != "success":
            raise ValueError("synthetic_review_tool_failed")
        result = response.get("result")
        if not isinstance(result, dict) or result.get("toolkit_version") != "0.1.0" or result.get("operation") != "assemble_preview":
            raise ValueError("synthetic_review_tool_result_invalid")
        digest = hashlib.sha256(json.dumps(request, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
        output = result.get("output")
        if (result.get("schema_version") != "review_tool_result.v1"
                or result.get("request_digest") != digest
                or result.get("validation_scope") != "structural_and_supplied_verdict_only"
                or type(result.get("agent_call_count")) is not int or result["agent_call_count"] != 0
                or type(result.get("mutable_call_count")) is not int or result["mutable_call_count"] != 0
                or not isinstance(output, dict) or output.get("source_hash") != values["source_hash"]
                or output.get("preview_only") is not True or output.get("publication_allowed") is not False
                or output.get("semantic_authority_verified") is not False
                or output.get("external_truth_verified") is not False):
            raise ValueError("synthetic_review_tool_result_invalid")
        return {"response_version": "1", "status": "success", "outputs": {"review_preview": result},
                "metrics": {"tool_call_count": 1, "agent_call_count": 0, "mutable_dynamic_skill_call_count": 0}}
