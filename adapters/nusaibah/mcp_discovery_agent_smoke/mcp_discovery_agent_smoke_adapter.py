"""Development consumer: one declared read, then one count-only Agent summary."""
from __future__ import annotations

import json
from typing import Any, ClassVar

from adapters.base import Adapter

AGENT_ORCHESTRATION_OWNER = "python_adapter"
CHILD_IDENTITY = ("nusaibah.abstract_mcp_dlm", "0.1.1")
AGENT_ROLE = "read_summarizer"
SUMMARY_SCHEMA = "mcp_discovery_agent_summary.v1"
MAX_RECORDS = 50
READ_PAGE_SIZE = 5
MAX_RESULT_BYTES = 65536
LOOKUP_STATES = {"not_requested", "exact", "suggestions", "ambiguous", "no_match", "unresolved"}


def _variables(inputs: Any) -> dict[str, Any]:
    values = inputs.get("variables", {})
    if not isinstance(values, dict) or set(values) - {"q"}:
        raise ValueError("mcp_discovery_smoke_variables_invalid")
    if "q" in values:
        query = values["q"]
        if (not isinstance(query, str) or not query.strip() or len(query) > 120
                or any(ord(char) < 32 or ord(char) == 127 for char in query)
                or "://" in query):
            raise ValueError("mcp_discovery_smoke_query_invalid")
        return {"q": query.strip()}
    return {}


def _observations(envelope: Any, *, queried: bool) -> dict[str, Any]:
    if not isinstance(envelope, dict) or envelope.get("status") != "success":
        raise RuntimeError("mcp_discovery_smoke_child_failed")
    provenance = envelope.get("provenance")
    if (not isinstance(provenance, dict)
            or provenance.get("callable_asset") is not True
            or (provenance.get("asset_key"), provenance.get("asset_version")) != CHILD_IDENTITY):
        raise RuntimeError("mcp_discovery_smoke_child_identity_invalid")
    result = envelope.get("result")
    if not isinstance(result, dict) or result.get("status") != "completed":
        raise RuntimeError("mcp_discovery_smoke_child_result_invalid")
    if len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_RESULT_BYTES:
        raise RuntimeError("mcp_discovery_smoke_child_result_too_large")
    records = result.get("records")
    count = result.get("record_count")
    if (not isinstance(records, list) or len(records) > MAX_RECORDS
            or any(not isinstance(record, dict) for record in records)
            or type(count) is not int or count != len(records)):
        raise RuntimeError("mcp_discovery_smoke_child_count_invalid")
    state, confirmation = "not_requested", False
    if queried:
        lookup = result.get("lookup")
        if (not isinstance(lookup, dict) or lookup.get("status") not in LOOKUP_STATES - {"not_requested"}
                or type(lookup.get("requires_confirmation")) is not bool):
            raise RuntimeError("mcp_discovery_smoke_lookup_invalid")
        state, confirmation = lookup["status"], lookup["requires_confirmation"]
        if (state == "exact") == confirmation:
            raise RuntimeError("mcp_discovery_smoke_lookup_confirmation_invalid")
    # Counts describe this bounded response. They never imply full search coverage.
    return {"returned_record_count": count, "lookup_status": state,
            "requires_confirmation": confirmation}


def _json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("mcp_discovery_smoke_agent_duplicate_key")
        value[key] = item
    return value


def _summary(envelope: Any, observations: dict[str, Any]) -> str:
    if not isinstance(envelope, dict) or envelope.get("status") != "completed":
        raise RuntimeError("mcp_discovery_smoke_agent_failed")
    result = envelope.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("mcp_discovery_smoke_agent_result_invalid")
    if result.get("schema_version") == "agent_result.v1" and result.get("kind") == "json":
        content = result.get("content")
        if (not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict)
                or content[0].get("type") != "json" or not isinstance(content[0].get("value"), dict)):
            raise RuntimeError("mcp_discovery_smoke_agent_content_invalid")
        value = content[0]["value"]
    elif set(result) == {"text"} and isinstance(result["text"], str) and len(result["text"]) <= 2048:
        # The existing local PHP bridge returns JSON text; the signed Agent lane
        # returns agent_result.v1. Both still require the same closed business result.
        value = json.loads(result["text"], object_pairs_hook=_json_pairs)
    else:
        raise RuntimeError("mcp_discovery_smoke_agent_content_invalid")
    required = {"schema_version", "role", "summary", *observations.keys()}
    if not isinstance(value, dict) or set(value) != required:
        raise RuntimeError("mcp_discovery_smoke_agent_schema_invalid")
    if value["schema_version"] != SUMMARY_SCHEMA or value["role"] != AGENT_ROLE:
        raise RuntimeError("mcp_discovery_smoke_agent_identity_invalid")
    if any(type(value[key]) is not type(expected) or value[key] != expected
           for key, expected in observations.items()):
        raise RuntimeError("mcp_discovery_smoke_agent_observation_mismatch")
    summary = value["summary"]
    if (not isinstance(summary, str) or not summary.strip() or len(summary) > 240
            or any(ord(char) < 32 or ord(char) == 127 for char in summary)
            or "://" in summary):
        raise RuntimeError("mcp_discovery_smoke_agent_summary_invalid")
    return summary.strip()


class McpDiscoveryAgentSmokeAdapter(Adapter):
    key: ClassVar[str] = "nusaibah.mcp_discovery_agent_smoke"
    version: ClassVar[str] = "0.1.0"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        del context
        variables = _variables(inputs)
        child = inputs.invoke_asset("discovery", variables={"page_size": READ_PAGE_SIZE, **variables}, on_error="raise")
        observations = _observations(child, queried="q" in variables)
        agent = inputs.invoke_agent(AGENT_ROLE, input={
            "task": "Summarize only this bounded read count. Do not infer totals, select candidates, call tools, or mutate data.",
            "observations": observations,
            "response_contract": {"schema_version": SUMMARY_SCHEMA, "role": AGENT_ROLE,
                **observations, "summary": "One sentence, at most 240 characters, describing only the observations."},
        }, on_error="raise")
        summary = _summary(agent, observations)
        return {"response_version": "1", "status": "success", "outputs": {"smoke_result": {
            "schema_version": "mcp_discovery_agent_smoke_result.v1", "status": "completed",
            **observations, "summary": summary, "child_call_count": 1, "agent_call_count": 1,
        }}, "metrics": {"tool_call_count": 1, "agent_call_count": 1, "mutable_dynamic_skill_call_count": 0}}
