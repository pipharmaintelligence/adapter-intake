"""Development consumer accepting the existing Bedrock terminal text contract."""
from __future__ import annotations

try:
    from . import mcp_discovery_agent_smoke_adapter as base
except ImportError:
    import mcp_discovery_agent_smoke_adapter as base

AGENT_ORCHESTRATION_OWNER = "python_adapter"


def _summary(envelope, observations):
    result = envelope.get("result") if isinstance(envelope, dict) else None
    if isinstance(result, dict) and result.get("schema_version") == "agent_result.v1" and result.get("kind") == "text":
        content = result.get("content")
        if (not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict)
                or set(content[0]) != {"type", "text"} or content[0]["type"] != "text"):
            raise RuntimeError("mcp_discovery_smoke_agent_content_invalid")
        # Reuse the same bounded, duplicate-key rejecting JSON parser and closed
        # observation contract as the existing local text response.
        envelope = {**envelope, "result": {"text": content[0]["text"]}}
    return base._summary(envelope, observations)


class McpDiscoveryAgentSmokeBedrockAdapter(base.McpDiscoveryAgentSmokeAdapter):
    key = "nusaibah.mcp_discovery_agent_smoke"
    version = "0.1.2"

    def invoke(self, inputs, context):
        del context
        variables = base._variables(inputs)
        child = inputs.invoke_asset("discovery", variables={"page_size": base.READ_PAGE_SIZE, **variables}, on_error="raise")
        observations = base._observations(child, queried="q" in variables)
        agent = inputs.invoke_agent(base.AGENT_ROLE, input={
            "task": "Summarize only this bounded read count. Do not infer totals, select candidates, call tools, or mutate data.",
            "observations": observations,
            "response_contract": {"schema_version": base.SUMMARY_SCHEMA, "role": base.AGENT_ROLE,
                **observations, "summary": "One sentence, at most 240 characters, describing only the observations."},
        }, on_error="raise")
        summary = _summary(agent, observations)
        return {"response_version": "1", "status": "success", "outputs": {"smoke_result": {
            "schema_version": "mcp_discovery_agent_smoke_result.v1", "status": "completed",
            **observations, "summary": summary, "child_call_count": 1, "agent_call_count": 1,
        }}, "metrics": {"tool_call_count": 1, "agent_call_count": 1, "mutable_dynamic_skill_call_count": 0}}
