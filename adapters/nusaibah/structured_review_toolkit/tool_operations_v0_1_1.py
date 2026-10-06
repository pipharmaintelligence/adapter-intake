"""Seven closed operations; historical 0.1.0 executors remain unchanged."""
from __future__ import annotations

import json
from typing import Any

if __package__:
    from . import tool_operations as base
    from .exact_spans import resolve_exact_spans
else:
    import tool_operations as base
    from exact_spans import resolve_exact_spans

OPERATIONS = (*base.OPERATIONS, "resolve_exact_spans")


def execute_operation(request: Any) -> dict[str, Any]:
    base._object(request, {"schema_version", "operation", "arguments"})
    operation = request["operation"]
    if (request["schema_version"] != "review_tool_request.v1"
            or not isinstance(operation, str) or operation not in OPERATIONS):
        raise base.ReviewToolError("review_tool_operation_not_supported")
    if operation != "resolve_exact_spans":
        result = base.execute_operation(request)
        return {**result, "toolkit_version": "0.1.1"}
    try:
        encoded = base._json_bytes(request)
    except UnicodeError as exc:
        raise base.ReviewToolError("review_tool_json_invalid") from exc
    if len(encoded) > base.MAX_INPUT_BYTES:
        raise base.ReviewToolError("review_tool_input_size_limit")
    copied = json.loads(encoded)
    base._reject_authority(copied)
    try:
        output = resolve_exact_spans(base._object(copied["arguments"]))
    except base.ReviewToolError:
        raise
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        raise base.ReviewToolError("review_tool_contract_invalid") from exc
    result = {"schema_version": "review_tool_result.v1", "toolkit_version": "0.1.1",
              "operation": operation, "request_digest": base.stable_digest(copied),
              "validation_scope": "structural_and_supplied_verdict_only",
              "agent_call_count": 0, "mutable_call_count": 0, "output": output}
    if len(base._json_bytes(result)) > base.MAX_RESULT_BYTES:
        raise base.ReviewToolError("review_tool_result_size_limit")
    return result
