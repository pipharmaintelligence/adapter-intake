from __future__ import annotations

from typing import Any

from adapters.base import Adapter

try:
    from .abstract_mcp_capabilities import ABSTRACT_MCP_DLM_CAPABILITIES
except ImportError:  # Local external adapter root mode.
    from abstract_mcp_capabilities import ABSTRACT_MCP_DLM_CAPABILITIES

SUPPORTED_CAPABILITY = "dlm.lakes.list"
SUPPORTED_RESPONSE_FORMATS = {"json", "application/json"}
DEFAULT_LIMIT = 25
MAX_DIAGNOSTIC_LIMIT = 100


class AbstractMcpDlmAdapter(Adapter):
    """Lakes-only abstract MCP/DLM local test adapter.

    This adapter proves the local authoring shape for agent tool-call intent. It
    does not call DLM Core, OBS, storage, MCP servers, providers, or HTTP APIs.
    Live tool execution remains server-authorized through Assets/Core.
    """

    key = "nusaibah.abstract_mcp_dlm"
    version = "0.1.0"

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        tool_request = inputs.get("tool_request", {})
        records = tool_request.get("records", []) if isinstance(tool_request, dict) else []

        if not isinstance(records, list) or not records:
            results = [
                {
                    "status": "failed",
                    "reason_code": "tool_request_missing",
                    "message": "tool_request.records is required.",
                }
            ]
        else:
            results = [self._handle_record(record, inputs) for record in records]

        return {
            "response_version": "1",
            "status": "success",
            "outputs": {
                "tool_results": {
                    "format": "json",
                    "records": results,
                }
            },
            "logs": [
                {
                    "level": "info",
                    "message": "Evaluated lakes-only abstract MCP tool-call intent locally.",
                }
            ],
            "metrics": {
                "tool_result_count": len(results),
            },
        }

    def _handle_record(self, record: Any, inputs: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(record, dict):
            return {
                "status": "failed",
                "reason_code": "tool_request_record_invalid",
                "message": "Each tool_request record must be an object.",
            }

        capability_ref = record.get("capability_ref")
        requested_format = str(record.get("response_format") or "json").strip().lower()
        request_input = record.get("input", {})

        if capability_ref != SUPPORTED_CAPABILITY:
            return {
                "status": "failed",
                "reason_code": "capability_not_available",
                "message": "Only dlm.lakes.list is enabled in abstract_mcp_dlm.",
                "capability_ref": capability_ref if isinstance(capability_ref, str) else None,
            }

        if requested_format not in SUPPORTED_RESPONSE_FORMATS:
            return {
                "status": "failed",
                "reason_code": "response_format_not_supported",
                "message": "abstract_mcp_dlm supports JSON responses only.",
                "capability_ref": SUPPORTED_CAPABILITY,
                "response_format": requested_format,
            }

        if not isinstance(request_input, dict):
            return {
                "status": "failed",
                "reason_code": "tool_request_input_invalid",
                "message": "tool_request.records[].input must be an object.",
                "capability_ref": SUPPORTED_CAPABILITY,
            }

        limit = self._safe_limit(request_input.get("limit"))
        page = self._safe_page(request_input.get("page"))
        q = request_input.get("q") if isinstance(request_input.get("q"), str) else None
        capability = ABSTRACT_MCP_DLM_CAPABILITIES[SUPPORTED_CAPABILITY]

        invoke_tool = getattr(inputs, "invoke_tool", None)
        if callable(invoke_tool):
            tool_text = self._tool_text(limit=limit, page=page, q=q)
            tool_result = invoke_tool(
                "dlm_lakes_list",
                input={"text": tool_text},
                on_error="raise",
            )
            if isinstance(tool_result, dict):
                return {
                    "status": tool_result.get("status", "completed"),
                    "capability_ref": SUPPORTED_CAPABILITY,
                    "tool": capability["tool"],
                    "response_format": "json",
                    "authority": "assets_core_runtime_lease",
                    "binding": {
                        "tool_handle": "@tool.abstract_mcp_dlm",
                        "tool_server_ref": "mcp.abstract_dlm",
                        "binding_ref": "mcp.abstract_dlm",
                        "capability_ref": SUPPORTED_CAPABILITY,
                    },
                    "request_summary": {
                        "limit": limit,
                        "page": page,
                        "has_query": q is not None,
                    },
                    "result": {
                        "summary": tool_result.get("summary", ""),
                        "records": tool_result.get("records", []),
                        "record_count": len(tool_result.get("records", []))
                        if isinstance(tool_result.get("records"), list)
                        else 0,
                        "provenance": tool_result.get("provenance", {}),
                    },
                }

        return {
            "status": "completed",
            "capability_ref": SUPPORTED_CAPABILITY,
            "tool": capability["tool"],
            "response_format": "json",
            "authority": "server_authorized_intent_only",
            "binding": {
                "tool_handle": "@tool.abstract_mcp_dlm",
                "tool_server_ref": "mcp.abstract_dlm",
                "binding_ref": "mcp.abstract_dlm",
                "capability_ref": SUPPORTED_CAPABILITY,
            },
            "request_summary": {
                "limit": limit,
                "page": page,
                "has_query": q is not None,
            },
            "result": {
                "lakes": [],
                "record_count": 0,
                "note": "Local proof only. Core/Assets owns any live DLM MCP execution.",
            },
        }

    def _tool_text(self, *, limit: int, page: int | None, q: str | None) -> str:
        parts = ["list DLM lakes", f"limit {limit}"]

        if page is not None:
            parts.append(f"page {page}")

        if q is not None:
            parts.append(f"query {q[:120]}")

        return "; ".join(parts)

    def _safe_limit(self, value: Any) -> int:
        if isinstance(value, bool):
            return DEFAULT_LIMIT
        if isinstance(value, int):
            return min(max(value, 1), MAX_DIAGNOSTIC_LIMIT)
        return DEFAULT_LIMIT

    def _safe_page(self, value: Any) -> int | None:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, int):
            return min(max(value, 1), 100000)
        return None

