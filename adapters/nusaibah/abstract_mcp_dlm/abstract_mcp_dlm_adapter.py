from __future__ import annotations

from typing import Any

from adapters.base import Adapter

try:
    from .abstract_mcp_capabilities import ABSTRACT_MCP_DLM_CAPABILITIES
except ImportError:  # Local external adapter root mode.
    from abstract_mcp_capabilities import ABSTRACT_MCP_DLM_CAPABILITIES

CAPABILITY_TO_TOOL_ROLE = {
    "dlm.lakes.list": "dlm_lakes_list",
    "dlm.nodes.list": "dlm_nodes_list",
}
SUPPORTED_RESPONSE_FORMATS = {"json", "application/json"}
DEFAULT_LIMIT = 25
MAX_DIAGNOSTIC_LIMIT = 100


class AbstractMcpDlmAdapter(Adapter):
    """Abstract MCP/DLM local test adapter for safe runtime tool-call intent.

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
                    "message": "Evaluated abstract MCP tool-call intent locally.",
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

        if not isinstance(capability_ref, str) or capability_ref not in CAPABILITY_TO_TOOL_ROLE:
            return {
                "status": "failed",
                "reason_code": "capability_not_available",
                "message": "Only declared abstract DLM MCP capabilities are enabled.",
                "capability_ref": capability_ref if isinstance(capability_ref, str) else None,
            }

        if requested_format not in SUPPORTED_RESPONSE_FORMATS:
            return {
                "status": "failed",
                "reason_code": "response_format_not_supported",
                "message": "abstract_mcp_dlm supports JSON responses only.",
                "capability_ref": capability_ref,
                "response_format": requested_format,
            }

        if not isinstance(request_input, dict):
            return {
                "status": "failed",
                "reason_code": "tool_request_input_invalid",
                "message": "tool_request.records[].input must be an object.",
                "capability_ref": capability_ref,
            }

        limit = self._safe_limit(request_input.get("limit"))
        page = self._safe_page(request_input.get("page"))
        q = request_input.get("q") if isinstance(request_input.get("q"), str) else None
        lake_id = self._safe_optional_identifier(request_input.get("lake_id"))
        capability = ABSTRACT_MCP_DLM_CAPABILITIES[capability_ref]
        tool_role = CAPABILITY_TO_TOOL_ROLE[capability_ref]

        invoke_tool = getattr(inputs, "invoke_tool", None)
        if callable(invoke_tool):
            tool_input = self._tool_input(capability_ref=capability_ref, limit=limit, page=page, q=q, lake_id=lake_id)
            tool_result = invoke_tool(
                tool_role,
                input=tool_input,
                on_error="null",
            )
            if isinstance(tool_result, dict):
                records = tool_result.get("records", [])
                return {
                    "status": tool_result.get("status", "completed"),
                    "capability_ref": capability_ref,
                    "tool": capability["tool"],
                    "response_format": "json",
                    "authority": "assets_core_runtime_lease",
                    "binding": self._binding(capability_ref),
                    "request_summary": self._request_summary(limit=limit, page=page, q=q, lake_id=lake_id),
                    "result": {
                        "summary": tool_result.get("summary", ""),
                        "records": records,
                        "record_count": len(records) if isinstance(records, list) else 0,
                        "provenance": tool_result.get("provenance", {}),
                    },
                }

        return {
            "status": "completed",
            "capability_ref": capability_ref,
            "tool": capability["tool"],
            "response_format": "json",
            "authority": "server_authorized_intent_only",
            "binding": self._binding(capability_ref),
            "request_summary": self._request_summary(limit=limit, page=page, q=q, lake_id=lake_id),
            "result": {
                "records": [],
                "record_count": 0,
                "note": "Local proof only. Core/Assets owns any live DLM MCP execution.",
            },
        }

    def _binding(self, capability_ref: str) -> dict[str, str]:
        return {
            "tool_handle": "@tool.abstract_mcp_dlm",
            "tool_server_ref": "mcp.abstract_dlm",
            "binding_ref": "mcp.abstract_dlm",
            "capability_ref": capability_ref,
        }

    def _request_summary(self, *, limit: int, page: int | None, q: str | None, lake_id: str | None) -> dict[str, Any]:
        return {
            "limit": limit,
            "page": page,
            "has_query": q is not None,
            "has_lake_id": lake_id is not None,
        }

    def _tool_input(
        self,
        *,
        capability_ref: str,
        limit: int,
        page: int | None,
        q: str | None,
        lake_id: str | None,
    ) -> dict[str, Any]:
        text = self._tool_text(capability_ref=capability_ref, limit=limit, page=page, q=q, lake_id=lake_id)
        tool_input: dict[str, Any] = {"text": text, "limit": limit}

        if page is not None:
            tool_input["page"] = page

        if q is not None:
            tool_input["q"] = q[:120]

        if lake_id is not None:
            tool_input["lake_id"] = lake_id

        return tool_input

    def _tool_text(self, *, capability_ref: str, limit: int, page: int | None, q: str | None, lake_id: str | None) -> str:
        if capability_ref == "dlm.nodes.list":
            parts = ["list DLM nodes"]
            if lake_id is not None:
                parts.append(f"lake {lake_id}")
        else:
            parts = ["list DLM lakes"]

        parts.append(f"limit {limit}")

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

    def _safe_optional_identifier(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 80:
            return None
        if not all(char.isalnum() or char in {"_", "-", ".", ":"} for char in normalized):
            return None
        return normalized
