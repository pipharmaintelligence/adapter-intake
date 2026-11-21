"""Independent read-only keyword search of governed DLM lake names/IDs.

Core and Assets own identity, tool admission, transport, and execution. This
adapter only validates one public request and one trusted normalized tool result.
No storage, credentials, Core HTTP, provider SDKs, or publication occurs here.
"""
from __future__ import annotations

import json
import re
from typing import Any

from adapters.base import Adapter

ROLE = "dlm_lakes_search"
CAPABILITY = "dlm.lakes.search"
TOOL_HANDLE = "@tool.abstract_mcp_dlm"
TOOL_SERVER = "mcp.abstract_dlm"
MAX_ROWS = 50
MAX_BYTES = 65536

_KEYWORD = re.compile(r"^[\w .()\-]{1,120}$", re.UNICODE)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_INVOCATION_ID = re.compile(
    r"^mti_(?:[a-f0-9]{32}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$"
)


class DlmLakesSearchError(RuntimeError):
    """Bounded, safe failure code without raw Core/runtime exception text."""


class DlmLakesKeywordSearchAdapter(Adapter):
    """Execute only the separately admitted dlm.lakes.search tool role."""

    key = "nusaibah.dlm_lakes_search"
    version = "0.1.0"

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Validate a user keyword, execute one trusted role, and project safe lake IDs.

        The public q/page_size names are distinct from the server-owned Core
        tool input text/limit. No caller-provided authority field is admitted.
        """
        del context
        if not isinstance(inputs, dict) or set(inputs) != {"tool_request"}:
            raise DlmLakesSearchError("dlm_search_input_invalid")
        request = inputs["tool_request"]
        if not isinstance(request, dict) or isinstance(request, list):
            raise DlmLakesSearchError("dlm_search_request_invalid")
        if set(request) - {"operation", "q", "page_size"} or request.get("operation") != "lakes.search":
            raise DlmLakesSearchError("dlm_search_operation_invalid")

        keyword = request.get("q")
        if not isinstance(keyword, str) or not _KEYWORD.fullmatch(keyword.strip()):
            raise DlmLakesSearchError("dlm_search_keyword_invalid")
        keyword = keyword.strip()

        page_size = request.get("page_size", 20)
        if type(page_size) is not int or not 1 <= page_size <= MAX_ROWS:
            raise DlmLakesSearchError("dlm_search_page_size_invalid")

        invoke_tool = getattr(inputs, "invoke_tool", None)
        if not callable(invoke_tool):
            raise DlmLakesSearchError("dlm_search_trusted_tool_unavailable")

        try:
            result = invoke_tool(ROLE, input={"text": keyword, "limit": page_size}, on_error="raise")
        except Exception:
            raise DlmLakesSearchError("dlm_search_tool_execution_failed") from None

        records = _validated_records(result, page_size)
        output: dict[str, Any] = {
            "schema_version": "dlm_mcp_read.v1",
            "operation": "lakes.search",
            "status": "completed",
            "records": records,
            "record_count": len(records),
            "page_size": page_size,
        }
        if "has_more" in result:
            if type(result["has_more"]) is not bool or (result["has_more"] and not records):
                raise DlmLakesSearchError("dlm_search_pagination_invalid")
            output["has_more"] = result["has_more"]
            if result["has_more"]:
                # Search has no trusted cursor contract. Never fabricate a page.
                output["truncated"] = True

        response = {
            "response_version": "1",
            "status": "success",
            "outputs": {"tool_results": output},
            "logs": [],
            "metrics": {"tool_result_count": 1},
        }
        encoded = json.dumps(response, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_BYTES:
            raise DlmLakesSearchError("dlm_search_output_too_large")
        return response


def _validated_records(result: Any, limit: int) -> list[dict[str, str]]:
    """Require the approved Assets tool envelope and a strict lake DTO."""
    if not isinstance(result, dict) or result.get("status") != "completed":
        raise DlmLakesSearchError("dlm_search_tool_result_invalid")
    if (
        result.get("operation") != "invoke"
        or result.get("capability_ref") != CAPABILITY
        or result.get("tool_handle") != TOOL_HANDLE
        or result.get("tool_server_ref") != TOOL_SERVER
    ):
        raise DlmLakesSearchError("dlm_search_tool_identity_invalid")

    rows = result.get("records")
    if not isinstance(rows, list) or len(rows) > limit:
        raise DlmLakesSearchError("dlm_search_record_limit_invalid")

    proof = result.get("provenance")
    if not isinstance(proof, dict):
        raise DlmLakesSearchError("dlm_search_provenance_invalid")
    invocation = proof.get("invocation_id")
    if (
        proof.get("runtime_mcp_tool") is not True
        or proof.get("role") != ROLE
        or not isinstance(invocation, str)
        or _INVOCATION_ID.fullmatch(invocation) is None
        or type(proof.get("record_count")) is not int
        or proof["record_count"] != len(rows)
        or type(proof.get("cache_hit")) is not bool
        or type(proof.get("duration_ms")) is not int
        or proof["duration_ms"] < 0
    ):
        raise DlmLakesSearchError("dlm_search_provenance_invalid")

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or isinstance(row, list):
            raise DlmLakesSearchError("dlm_search_record_invalid")
        lake_id, name = row.get("lake_id"), row.get("name")
        if (
            not isinstance(lake_id, str)
            or _IDENTIFIER.fullmatch(lake_id) is None
            or lake_id in seen
            or not isinstance(name, str)
            or not 1 <= len(name.strip()) <= 120
            or not name.strip().isprintable()
        ):
            raise DlmLakesSearchError("dlm_search_record_invalid")
        seen.add(lake_id)
        records.append({"lake_id": lake_id, "name": name.strip()})

    return records
