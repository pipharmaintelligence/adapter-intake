"""Read-only DLM MCP results: deterministic shaping, never transport authority.

Local fixtures can inject an approved tool invoker. Governed local_worker/ECS
execution must supply a separately admitted trusted tool bridge. Without one,
this adapter fails rather than treating intent or zero records as success.
"""
from __future__ import annotations

import json
import re
from typing import Any

from adapters.base import Adapter
try:
    from .mcp_read_resolution_v0_1_1 import (
        NameProfile, ReadContract, resolve_names, validate_read_result,
    )
except ImportError:  # Existing local external adapter-root discovery mode.
    from mcp_read_resolution_v0_1_1 import (
        NameProfile, ReadContract, resolve_names, validate_read_result,
    )


TOOL_ROLES = {
    "lakes.list": "dlm_lakes_list",
    "nodes.list": "dlm_nodes_list",
    "nodes.schema": "dlm_nodes_schema",
}
TOOL_CAPABILITIES = {
    "lakes.list": "dlm.lakes.list",
    "nodes.list": "dlm.nodes.list",
    "nodes.schema": "dlm.nodes.schema",
}
TRUSTED_TOOL_HANDLE = "@tool.abstract_mcp_dlm"
TRUSTED_TOOL_SERVER_REF = "mcp.abstract_dlm"
_ALLOWED_KEYS = {
    "lakes.list": frozenset({"operation", "q", "page_size"}),
    "nodes.list": frozenset({"operation", "lake_id", "q", "page", "page_size"}),
    "nodes.schema": frozenset({"operation", "lake_id", "node_key"}),
}
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_LABEL = re.compile(r"^[\w .()\-]{1,120}$", re.UNICODE)
_TYPE = re.compile(r"^[\w .(),:<>\[\]-]{1,96}$", re.UNICODE)
MAX_PAGE_SIZE = 50
MAX_PAGE = 1000
MAX_SCHEMA_FIELDS = 100
MAX_OUTPUT_BYTES = 65536


class DlmMcpReadError(RuntimeError):
    """Value-safe failure; no provider/Core exception text is returned."""

    def __init__(self, code: str) -> None:
        self.failure_code = code
        super().__init__(code)


class AbstractMcpDlmReadAdapter(Adapter):
    """Shape exactly one admitted, read-only Core MCP operation.

    The caller supplies semantic selectors only. No client, actor, authorization,
    provider, URL, storage or execution selector is accepted from input.
    """

    key = "nusaibah.abstract_mcp_dlm"
    version = "0.1.1"

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Execute a declared role, verify its terminal result and project safe fields.

        All real permissions and tool execution are enforced outside this adapter.
        This function performs only a second, deterministic contract check.
        """
        if (
            not isinstance(inputs, dict) or "tool_request" not in inputs
            or set(inputs) - {"tool_request", "variables"}
        ):
            raise DlmMcpReadError("dlm_mcp_input_roles_invalid")
        request = inputs["tool_request"]
        if not isinstance(request, dict) or isinstance(request, list):
            raise DlmMcpReadError("dlm_mcp_request_invalid")
        operation = request.get("operation")
        if not isinstance(operation, str) or operation not in TOOL_ROLES:
            raise DlmMcpReadError("dlm_mcp_operation_unavailable")
        if set(request) - _ALLOWED_KEYS[operation]:
            raise DlmMcpReadError("dlm_mcp_request_fields_forbidden")

        # Callable reuse keeps operation and resource scope in the required,
        # trusted prepared tool_request. Variables carry only bounded filters.
        # The runtime also applies its generic callable-variables guard.
        if "variables" in inputs:
            variables = inputs["variables"]
            allowed = _ALLOWED_KEYS[operation] & {"q", "page", "page_size"}
            if not isinstance(variables, dict) or set(variables) - allowed:
                raise DlmMcpReadError("dlm_mcp_variables_invalid")
            if any(key in request and request[key] != value for key, value in variables.items()):
                raise DlmMcpReadError("dlm_mcp_variables_conflict")
            request = {**request, **variables}

        tool_input = self._arguments(operation, request)
        invoke_tool = getattr(inputs, "invoke_tool", None)
        if not callable(invoke_tool):
            raise DlmMcpReadError("dlm_mcp_trusted_tool_bridge_unavailable")

        role = TOOL_ROLES[operation]
        try:
            result = invoke_tool(role, input=tool_input, on_error="raise")
        except Exception:
            # Never surface upstream exception messages or fabricate empty success.
            raise DlmMcpReadError("dlm_mcp_tool_execution_failed") from None

        # This only checks the trusted bridge's declared result shape; it is
        # not proof of Core admission or cryptographic execution authority.
        _validate_runtime_tool_envelope(result, operation=operation, role=role)
        raw_records = result["records"]
        max_records = MAX_SCHEMA_FIELDS if operation == "nodes.schema" else MAX_PAGE_SIZE
        if len(raw_records) > max_records:
            raise DlmMcpReadError("dlm_mcp_response_limit_exceeded")
        # A backend must not exceed the page-size ceiling selected by the caller.
        if operation != "nodes.schema" and len(raw_records) > tool_input["limit"]:
            raise DlmMcpReadError("dlm_mcp_response_limit_exceeded")

        # Core reports unavailable schema as a failed read, never as a
        # successful zero-column response. Keep list emptiness independent.
        if operation == "nodes.schema" and not raw_records:
            raise DlmMcpReadError("dlm_mcp_schema_unavailable")

        records = self._project(operation, raw_records, tool_input)
        # A typo may make Core's literal search return zero hits. Search a
        # bounded, already authorized catalogue only when needed, and expose
        # candidates for conversation without silently selecting one.
        lookup = None
        if operation in ("lakes.list", "nodes.list") and "q" in request:
            lookup = self._search_lookup(
                operation, request["q"], records, result, tool_input,
                role, invoke_tool,
            )
        projected: dict[str, Any] = {
            "schema_version": "dlm_mcp_read.v1",
            "operation": operation,
            "status": "completed",
            "records": records,
            "record_count": len(records),
        }
        if lookup is not None:
            projected["lookup"] = lookup
        if operation == "nodes.schema":
            projected["field_count"] = len(records[0]["fields"])
        else:
            projected["page_size"] = tool_input["limit"]
            if operation == "nodes.list":
                projected["page"] = tool_input["page"]

        # Real trusted tool envelopes may omit pagination metadata. Do not
        # invent has_more=false or a next page from the returned row count.
        if "has_more" in result:
            has_more = result["has_more"]
            if operation == "nodes.schema" or type(has_more) is not bool:
                raise DlmMcpReadError("dlm_mcp_pagination_invalid")
            if has_more and not records:
                raise DlmMcpReadError("dlm_mcp_pagination_invalid")
            projected["has_more"] = has_more
            if has_more:
                if operation == "nodes.list" and tool_input["page"] < MAX_PAGE:
                    projected["next_page"] = tool_input["page"] + 1
                else:
                    # Lake discovery has no page selector in the current Core
                    # API. At MAX_PAGE, node pagination is also exhausted.
                    projected["truncated"] = True

        response = {
            "response_version": "1",
            "status": "success",
            "outputs": {"tool_results": projected},
            "logs": [],
            "metrics": {"tool_result_count": 1},
        }
        encoded = json.dumps(response, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_OUTPUT_BYTES:
            raise DlmMcpReadError("dlm_mcp_response_limit_exceeded")
        return response

    @staticmethod
    def _search_lookup(
        operation: str,
        query: str,
        records: list[dict[str, Any]],
        result: dict[str, Any],
        selectors: dict[str, Any],
        role: str,
        invoke_tool: Any,
    ) -> dict[str, Any]:
        """Use the resource-neutral resolver with the reviewed DLM profile."""
        fallback = None
        if operation == "lakes.list" or selectors["page"] == 1:
            fallback = {"limit": MAX_PAGE_SIZE}
            if operation == "nodes.list":
                fallback.update({"lake_id": selectors["lake_id"], "page": 1})
        return resolve_names(
            query=query, records=records, result=result,
            contract=_read_contract(operation, role),
            profile=NameProfile(
                id_key="lake_id" if operation == "lakes.list" else "node_key",
                candidate_keys=("lake_id", "name") if operation == "lakes.list"
                else ("lake_id", "node_key", "name"),
                ignored_nouns=("lake", "node"),
            ),
            invoke_tool=invoke_tool,
            project=lambda rows, scope: AbstractMcpDlmReadAdapter._project(operation, rows, scope),
            fallback_input=fallback, error=_read_error,
        )

    @staticmethod
    def _arguments(operation: str, request: dict[str, Any]) -> dict[str, Any]:
        """Validate strict caller selectors and build bounded semantic tool input."""
        tool_input: dict[str, Any] = {}
        if operation != "nodes.schema":
            page_size = request.get("page_size", 20)
            if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
                raise DlmMcpReadError("dlm_mcp_page_size_invalid")
            tool_input["limit"] = page_size

        if operation == "nodes.list":
            tool_input["lake_id"] = _identifier(request.get("lake_id"))
            page = request.get("page", 1)
            if type(page) is not int or not 1 <= page <= MAX_PAGE:
                raise DlmMcpReadError("dlm_mcp_page_invalid")
            tool_input["page"] = page
        elif operation == "nodes.schema":
            tool_input["lake_id"] = _identifier(request.get("lake_id"))
            tool_input["node_key"] = _identifier(request.get("node_key"))

        if "q" in request:
            query = request["q"]
            if not isinstance(query, str) or not _LABEL.fullmatch(query.strip()):
                raise DlmMcpReadError("dlm_mcp_query_invalid")
            # The registered Core generic HTTP capability takes its primary
            # query through text and maps it to the connector's query field.
            tool_input["text" if operation == "lakes.list" else "search"] = query.strip()
        return tool_input

    @staticmethod
    def _project(
        operation: str,
        raw_records: list[Any],
        selectors: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Positive allowlist: never forward the raw tool or Core envelope."""
        if operation == "nodes.schema":
            return _schema_records(raw_records, selectors)
        projected = []
        for row in raw_records:
            if not isinstance(row, dict):
                raise DlmMcpReadError("dlm_mcp_record_shape_invalid")
            if operation == "lakes.list":
                lake_id = _identifier(row.get("lake_id", row.get("id")))
                name = _label(row.get("lake_name", row.get("name", lake_id)))
                projected.append({"lake_id": lake_id, "name": name})
                continue
            # Core may return node records that contain storage/source metadata.
            # Only these deliberately selected fields leave the adapter.
            requested_lake = selectors["lake_id"]
            if "lake_id" in row and _identifier(row["lake_id"]) != requested_lake:
                raise DlmMcpReadError("dlm_mcp_scope_result_mismatch")
            node_key = _identifier(row.get("node_key"))
            node = {"lake_id": requested_lake, "node_key": node_key}
            if "name" in row:
                node["name"] = _label(row["name"])
            for name in ("source_type", "schema_status", "processing_status"):
                if name in row and row[name] is not None:
                    node[name] = _label(row[name])
            if "object_count" in row:
                count = row["object_count"]
                if type(count) is not int or count < 0:
                    raise DlmMcpReadError("dlm_mcp_record_shape_invalid")
                node["object_count"] = count
            projected.append(node)
        return projected


def _read_error(code: str) -> DlmMcpReadError:
    return DlmMcpReadError("dlm_mcp_" + code)


def _read_contract(operation: str, role: str) -> ReadContract:
    return ReadContract(
        role=role, capability_ref=TOOL_CAPABILITIES[operation],
        tool_handle=TRUSTED_TOOL_HANDLE, tool_server_ref=TRUSTED_TOOL_SERVER_REF,
        max_records=MAX_SCHEMA_FIELDS if operation == "nodes.schema" else MAX_PAGE_SIZE,
    )


def _validate_runtime_tool_envelope(result: Any, *, operation: str, role: str) -> None:
    validate_read_result(result, _read_contract(operation, role), _read_error)


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value.strip()):
        raise DlmMcpReadError("dlm_mcp_identifier_invalid")
    return value.strip()


def _label(value: Any, *, field_type: bool = False) -> str:
    pattern = _TYPE if field_type else _LABEL
    if not isinstance(value, str) or not pattern.fullmatch(value.strip()):
        raise DlmMcpReadError("dlm_mcp_record_shape_invalid")
    return value.strip()


def _schema_records(records: list[Any], request: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize either Core schema columns or a bounded list of column rows."""
    if not records:
        return []

    if len(records) == 1 and isinstance(records[0], dict):
        parent = records[0]
        if "lake_id" in parent and _identifier(parent["lake_id"]) != request["lake_id"]:
            raise DlmMcpReadError("dlm_mcp_scope_result_mismatch")
        if "node_key" in parent and _identifier(parent["node_key"]) != request["node_key"]:
            raise DlmMcpReadError("dlm_mcp_scope_result_mismatch")
        definition = parent.get("schema_definition")
        if isinstance(definition, dict):
            fields = definition.get("columns", definition.get("fields"))
        elif "columns" in parent:
            fields = parent["columns"]
        elif "fields" in parent:
            fields = parent["fields"]
        else:
            fields = records
    else:
        fields = records

    if not isinstance(fields, list):
        raise DlmMcpReadError("dlm_mcp_schema_invalid")
    if len(fields) > MAX_SCHEMA_FIELDS:
        raise DlmMcpReadError("dlm_mcp_response_limit_exceeded")
    result_fields = []
    for raw in fields:
        if not isinstance(raw, dict):
            raise DlmMcpReadError("dlm_mcp_schema_invalid")
        name = _label(raw.get("column_name", raw.get("name")))
        data_type = _label(raw.get("data_type", raw.get("type")), field_type=True)
        field: dict[str, Any] = {"name": name, "type": data_type}
        if "nullable" in raw:
            if not isinstance(raw["nullable"], bool):
                raise DlmMcpReadError("dlm_mcp_schema_invalid")
            field["nullable"] = raw["nullable"]
        result_fields.append(field)
    return [{
        "lake_id": request["lake_id"],
        "node_key": request["node_key"],
        "fields": result_fields,
    }]
