"""Versioned consumer of manifest-owned semantic child input preparation."""
from __future__ import annotations

from .mcp_discovery_agent_smoke_adapter import McpDiscoveryAgentSmokeAdapter

AGENT_ORCHESTRATION_OWNER = "python_adapter"


class McpDiscoveryAgentSmokePreparedAdapter(McpDiscoveryAgentSmokeAdapter):
    version = "0.1.1"
