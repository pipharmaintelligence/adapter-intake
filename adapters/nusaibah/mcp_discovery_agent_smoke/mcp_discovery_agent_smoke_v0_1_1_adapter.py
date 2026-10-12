"""Versioned consumer of manifest-owned semantic child input preparation."""
from __future__ import annotations

try:
    from .mcp_discovery_agent_smoke_adapter import McpDiscoveryAgentSmokeAdapter
except ImportError:  # Existing external adapter-root discovery mode.
    from mcp_discovery_agent_smoke_adapter import McpDiscoveryAgentSmokeAdapter

AGENT_ORCHESTRATION_OWNER = "python_adapter"


class McpDiscoveryAgentSmokePreparedAdapter(McpDiscoveryAgentSmokeAdapter):
    key = "nusaibah.mcp_discovery_agent_smoke"
    version = "0.1.1"
