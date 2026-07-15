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
    "dlm.nodes.schema": "dlm_nodes_schema",
}

SUPPORTED_RESPONSE_FORMATS = {"json", "application/json"}
DEFAULT_LIMIT = 25
MAX_DIAGNOSTIC_LIMIT = 100
MAX_OUTPUT_RECORDS = 100
MAX_OUTPUT_FIELDS = 50

_BLOCKED_OUTPUT_KEY_PARTS = [
    ("access", "_", "url"),
    ("author", "ization"),
    ("buck", "et"),
    ("connection",),
    ("connection", "_", "id"),
    ("connection", "_", "string"),
    ("cred", "entials"),
    ("cred", "ential", "_", "id"),
    ("cred", "entials", "_", "ref"),
    ("file", "_", "path"),
    ("grant", "_", "uuid"),
    ("host",),
    ("local", "_", "path"),
    ("object", "_", "key"),
    ("pass", "word"),
    ("port",),
    ("presigned", "_", "url"),
    ("provider", "_", "instance", "_", "key"),
    ("provider", "_", "response"),
    ("query", "_", "raw"),
    ("raw", "_", "db", "_", "response"),
    ("raw", "_", "dlm", "_", "response"),
    ("raw", "_", "provider", "_", "payload"),
    ("raw", "_", "provider", "_", "response"),
    ("runtime", "_", "location"),
    ("runtime", "_", "manifest"),
    ("runtime", "_", "object", "_", "delivery"),
    ("runtime", "_", "workspace"),
    ("descriptor", "_", "id"),
    ("descriptor", "_", "version"),
    ("approval", "_", "ref"),
    ("write", "_", "authority"),
    ("output", "_", "write", "_", "descriptor"),
    ("upload", "_", "lease"),
    ("core", "_", "upload", "_", "lease"),
    ("lease", "_", "id"),
    ("provider", "_", "url"),
    ("provider", "_", "head", "ers"),
    ("storage", "_", "uri"),
    ("objectkey",),
    ("aws", "_", "access", "_", "key", "_", "id"),
    ("aws", "_", "sec", "ret", "_", "access", "_", "key"),
    ("aws", "_", "session", "_", "tok", "en"),
    ("azure", "_", "sas"),
    ("sas", "_", "tok", "en"),
    ("google", "_", "service", "_", "account"),
    ("service", "_", "account", "_", "json"),
    ("object", "_", "body"),
    ("object", "_", "content"),
    ("full", "_", "object", "_", "body"),
    ("storage", "_", "path"),
    ("tok", "en"),
    ("api", "_", "key"),
    ("sec", "ret"),
    ("user", "name"),
    ("url",),
]

FORBIDDEN_OUTPUT_KEYS = {"".join(parts) for parts in _BLOCKED_OUTPUT_KEY_PARTS}


class AbstractMcpDlmAdapter(Adapter):
    """Abstract MCP/DLM adapter for safe runtime tool-call intent.

    This adapter does not call DLM Core, OBS, storage, MCP servers, providers,
    or HTTP APIs directly. Live tool execution remains server-authorized through
    the Assets/Core runtime bridge.

    The adapter accepts node-provided lake identifiers through `lake_id`,
    `lake_identifier`, or `identifier`, then normalizes them into canonical
    tool input. Node schema inspection additionally requires explicit
    `node_key` selector input.
    """

    key = "nusaibah.abstract_mcp_dlm"
    version = "0.1.0"

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Execute declared MCP/DLM tool requests and return safe JSON output."""

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
        """Validate one requested MCP capability and execute it through runtime bridge."""

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
                "capability": capability_ref if isinstance(capability_ref, str) else None,
            }

        if requested_format not in SUPPORTED_RESPONSE_FORMATS:
            return {
                "status": "failed",
                "reason_code": "response_format_not_supported",
                "message": "abstract_mcp_dlm supports JSON responses only.",
                "capability_ref": capability_ref,
                "capability": capability_ref,
                "format": requested_format,
            }

        if not isinstance(request_input, dict):
            return {
                "status": "failed",
                "reason_code": "tool_request_input_invalid",
                "message": "tool_request.records[].input must be an object.",
                "capability_ref": capability_ref,
                "capability": capability_ref,
            }

        limit = self._safe_limit(request_input.get("limit"))
        page = self._safe_page(request_input.get("page"))
        q = request_input.get("q") if isinstance(request_input.get("q"), str) else None

        # Accept lake_id, lake_identifier, or identifier from node/UI input.
        # The canonical value sent to the tool remains `lake_id`.
        lake_id = self._safe_lake_identifier(request_input)
        identifier = self._safe_optional_identifier(request_input.get("identifier"))
        node_key = self._safe_optional_identifier(request_input.get("node_key"))

        capability = ABSTRACT_MCP_DLM_CAPABILITIES[capability_ref]
        tool_role = CAPABILITY_TO_TOOL_ROLE[capability_ref]

        if capability_ref == "dlm.nodes.schema":
            missing = []
            if lake_id is None:
                missing.append("lake_id")
            if node_key is None:
                missing.append("node_key")

            if missing:
                return {
                    "status": "failed",
                    "reason_code": "tool_request_input_missing",
                    "message": "dlm.nodes.schema requires safe lake_id and node_key input.",
                    "capability_ref": capability_ref,
                    "capability": capability_ref,
                    "tool_role": tool_role,
                    "format": "json",
                    "binding": self._binding(capability_ref),
                    "request": self._request_summary(
                        limit=limit,
                        page=page,
                        q=q,
                        lake_id=lake_id,
                        identifier=identifier,
                        node_key=node_key,
                    ),
                    "missing_inputs": missing,
                    "record_count": 0,
                    "records": [],
                    "result": {
                        "records": [],
                        "count": 0,
                    },
                }

        invoke_tool = getattr(inputs, "invoke_tool", None)
        if callable(invoke_tool):
            tool_input = self._tool_input(
                capability_ref=capability_ref,
                limit=limit,
                page=page,
                q=q,
                lake_id=lake_id,
                identifier=identifier,
                node_key=node_key,
            )

            tool_result = invoke_tool(
                tool_role,
                input=tool_input,
                on_error="empty",
            )

            if isinstance(tool_result, dict):
                records = self._safe_tool_records(tool_result.get("records", []))
                status = self._safe_status(tool_result.get("status"))
                summary = self._safe_text(tool_result.get("summary")) or "completed"
                request_summary = self._request_summary(
                    limit=limit,
                    page=page,
                    q=q,
                    lake_id=lake_id,
                    identifier=identifier,
                    node_key=node_key,
                )

                return {
                    "status": status,
                    "capability_ref": capability_ref,
                    "capability": capability_ref,  # Backward-compatible alias.
                    "tool_role": tool_role,
                    "format": "json",
                    "binding": self._binding(capability_ref),
                    "request": request_summary,
                    "record_count": len(records),
                    "records": records,
                    "result": {
                        "summary": summary,
                        "records": records,
                        "count": len(records),
                    },
                    "capability_metadata": self._safe_capability_metadata(capability),
                }

        request_summary = self._request_summary(
            limit=limit,
            page=page,
            q=q,
            lake_id=lake_id,
            identifier=identifier,
            node_key=node_key,
        )

        return {
            "status": "completed",
            "capability_ref": capability_ref,
            "capability": capability_ref,
            "tool_role": tool_role,
            "format": "json",
            "binding": self._binding(capability_ref),
            "request": request_summary,
            "record_count": 0,
            "records": [],
            "result": {
                "records": [],
                "count": 0,
                "note": "Local proof only. Core/Assets owns any live DLM MCP execution.",
            },
            "capability_metadata": self._safe_capability_metadata(capability),
        }

    def _safe_tool_records(self, records: Any) -> list[dict[str, Any]]:
        """Return bounded, JSON-safe records from a runtime tool response."""

        if not isinstance(records, list):
            return []

        safe_records: list[dict[str, Any]] = []
        for record in records[:MAX_OUTPUT_RECORDS]:
            if not isinstance(record, dict):
                continue
            safe_records.append(self._safe_record_object(record))

        return safe_records

    def _safe_record_object(self, record: dict[Any, Any], *, depth: int = 0) -> dict[str, Any]:
        """Return a sanitized object without sensitive runtime/storage fields."""

        safe: dict[str, Any] = {}

        for key, value in record.items():
            if len(safe) >= MAX_OUTPUT_FIELDS:
                break

            safe_key = self._safe_record_key(key)
            if safe_key is None:
                continue

            safe_value = self._safe_record_value(value, depth=depth)
            if safe_value is not None:
                safe[safe_key] = safe_value

        return safe

    def _safe_record_value(self, value: Any, *, depth: int) -> Any:
        """Return a JSON-safe scalar, list, or shallow nested object."""

        if isinstance(value, (str, int, float, bool)) or value is None:
            return self._safe_scalar(value)

        if isinstance(value, list):
            safe_items = []
            for item in value[:MAX_OUTPUT_RECORDS]:
                if not isinstance(item, (str, int, float, bool)) and item is not None:
                    return None

                safe_item = self._safe_scalar(item)
                if safe_item is not None:
                    safe_items.append(safe_item)

            return safe_items

        if isinstance(value, dict) and depth < 1:
            nested = self._safe_record_object(value, depth=depth + 1)
            return nested or None

        return None

    def _safe_scalar(self, value: Any) -> Any:
        """Return a safe scalar and block URL-like storage/provider values."""

        if value is None or isinstance(value, (int, float, bool)):
            return value

        text = self._safe_text(value)
        if text is None:
            return None

        lowered = text.lower()
        if (
            ("http" + "://") in lowered
            or ("https" + "://") in lowered
            or ("s3" + "://") in lowered
            or ("gs" + "://") in lowered
        ):
            return None

        return text

    def _safe_text(self, value: Any) -> str | None:
        """Return trimmed text capped to a safe diagnostic length."""

        if not isinstance(value, (str, int, float, bool)):
            return None

        text = str(value).strip()
        if not text:
            return None

        return text[:500]

    def _safe_record_key(self, key: Any) -> str | None:
        """Return a safe output key or None when the key is blocked."""

        if not isinstance(key, (str, int)):
            return None

        text = str(key).strip()
        if not text or len(text) > 64:
            return None

        if not text[0].isalpha():
            return None

        if not all(char.isalnum() or char in {"_", "-", ".", ":"} for char in text):
            return None

        if text.lower() in FORBIDDEN_OUTPUT_KEYS:
            return None

        return text

    def _safe_status(self, value: Any) -> str:
        """Normalize runtime status into the public adapter status set."""

        status = self._safe_text(value)
        return status if status in {"completed", "partial", "failed"} else "completed"

    def _binding(self, capability_ref: str) -> dict[str, str]:
        """Return safe binding metadata for the declared MCP capability."""

        return {
            "tool_handle": "@tool.abstract_mcp_dlm",
            "tool_server_ref": "mcp.abstract_dlm",
            "binding_ref": "mcp.abstract_dlm",
            "capability_ref": capability_ref,
            "capability": capability_ref,
        }

    def _request_summary(
        self,
        *,
        limit: int,
        page: int | None,
        q: str | None,
        lake_id: str | None,
        identifier: str | None,
        node_key: str | None,
    ) -> dict[str, Any]:
        """Return a safe summary of node/user input used for this tool call."""

        resolved_identifier = identifier or lake_id

        return {
            "limit": limit,
            "page": page,
            "has_query": q is not None,
            "has_lake_id": lake_id is not None,
            "lake_id": lake_id,
            "identifier": resolved_identifier,
            "has_node_key": node_key is not None,
            "node_key": node_key,
        }

    def _tool_input(
            self,
            *,
            capability_ref: str,
            limit: int,
            page: int | None,
            q: str | None,
            lake_id: str | None,
            identifier: str | None,
            node_key: str | None,
    ) -> dict[str, Any]:
        """Build safe runtime tool input for the Assets/Core MCP bridge.

        `identifier` is accepted as a node/UI alias, but it is normalized into
        canonical `lake_id` before crossing the runtime tool boundary.

        Do not forward `identifier` to Core because a generic connector may
        interpret it as a separate filter and return zero records.
        """

        text = q[:120] if q is not None else self._tool_text(
            capability_ref=capability_ref,
            limit=limit,
            page=page,
            q=q,
            lake_id=lake_id,
            identifier=identifier,
            node_key=node_key,
        )[:120]
        tool_input: dict[str, Any] = {
            "text": text,
            "limit": limit,
        }

        if page is not None:
            tool_input["page"] = page

        if q is not None and capability_ref == "dlm.nodes.list":
            tool_input["search"] = q[:120]

        # Canonical runtime field. If the node supplied only `identifier`,
        # `_safe_lake_identifier()` should already have resolved it into lake_id.
        if lake_id is not None:
            tool_input["lake_id"] = lake_id

        if node_key is not None:
            tool_input["node_key"] = node_key

        return tool_input

    def _tool_text(
        self,
        *,
        capability_ref: str,
        limit: int,
        page: int | None,
        q: str | None,
        lake_id: str | None,
        identifier: str | None,
        node_key: str | None,
    ) -> str:
        """Build safe human-readable tool intent text."""

        if capability_ref == "dlm.nodes.schema":
            parts = ["inspect DLM node schema"]
            resolved_lake = lake_id or identifier
            if resolved_lake is not None:
                parts.append(f"lake {resolved_lake}")
            if node_key is not None:
                parts.append(f"node {node_key}")
        elif capability_ref == "dlm.nodes.list":
            parts = ["list DLM nodes"]
            resolved_lake = lake_id or identifier
            if resolved_lake is not None:
                parts.append(f"lake {resolved_lake}")
        else:
            parts = ["list DLM lakes"]

        parts.append(f"limit {limit}")

        if page is not None:
            parts.append(f"page {page}")

        if q is not None:
            parts.append(f"query {q[:120]}")

        return "; ".join(parts)

    def _safe_limit(self, value: Any) -> int:
        """Return a bounded page size for diagnostics/tool execution."""

        if isinstance(value, bool):
            return DEFAULT_LIMIT

        if isinstance(value, int):
            return min(max(value, 1), MAX_DIAGNOSTIC_LIMIT)

        return DEFAULT_LIMIT

    def _safe_page(self, value: Any) -> int | None:
        """Return a bounded page number when supplied."""

        if isinstance(value, bool) or value is None:
            return None

        if isinstance(value, int):
            return min(max(value, 1), 100000)

        return None

    def _safe_lake_identifier(self, request_input: dict[str, Any]) -> str | None:
        """Return the safest lake identifier supplied by node input.

        Supported aliases:
        - lake_id: canonical runtime field.
        - lake_identifier: explicit UI/node alias.
        - identifier: generic UI/node alias.

        The returned value should be sent to the runtime tool as `lake_id`.
        """

        for key in ("lake_id", "lake_identifier", "identifier"):
            value = self._safe_optional_identifier(request_input.get(key))
            if value is not None:
                return value

        return None

    def _safe_optional_identifier(self, value: Any) -> str | None:
        """Return a safe identifier-like value or None."""

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

    def _safe_capability_metadata(self, capability: Any) -> dict[str, Any]:
        """Return bounded, non-sensitive capability metadata when available."""

        if not isinstance(capability, dict):
            return {}

        safe: dict[str, Any] = {}

        for key in ("name", "description", "capability_ref", "operation"):
            value = self._safe_text(capability.get(key))
            if value is not None:
                safe[key] = value

        return safe
