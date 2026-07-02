from __future__ import annotations

from typing import Final

ABSTRACT_MCP_DLM_CAPABILITIES: Final[dict[str, dict[str, str]]] = {
    "dlm.lakes.list": {
        "tool": "list_lakes",
        "response_format": "json",
        "authority": "server_authorized",
    }
}
