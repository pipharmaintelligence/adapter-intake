from __future__ import annotations

from typing import Final

ABSTRACT_MCP_DLM_CAPABILITIES: Final[dict[str, dict[str, str]]] = {
    "dlm.lakes.list": {
        "tool": "list_lakes",
        "response_format": "json",
        "authority": "server_authorized",
    },
    "dlm.nodes.list": {
        "tool": "list_nodes",
        "response_format": "json",
        "authority": "server_authorized",
    },
    "dlm.nodes.schema": {
        "tool": "node_schema",
        "response_format": "json",
        "authority": "server_authorized",
    },
}
