"""Unregistered 0.1.3 candidate: preserve frozen discovery; add scoped memory."""
from __future__ import annotations

from typing import Any
from adapters.base import Adapter

try:
    from .lake_memory_contract_v0_1_3 import OPERATIONS
    from .lake_memory_runtime_v0_1_3 import invoke_memory
except ImportError:
    from lake_memory_contract_v0_1_3 import OPERATIONS
    from lake_memory_runtime_v0_1_3 import invoke_memory


class AbstractMcpDlmMemoryAdapter(Adapter):
    """Compose memory only after trusted server scope has been supplied."""

    key = "nusaibah.abstract_mcp_dlm"
    version = "0.1.3"

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Dispatch one operation; preserve existing discovery implementation bytes."""
        request = inputs.get("tool_request") if isinstance(inputs, dict) else None
        if isinstance(request, dict) and request.get("operation") in OPERATIONS:
            return invoke_memory(inputs, context)
        try:
            from .abstract_mcp_dlm_v0_1_2_adapter import AbstractMcpDlmCoreReadAdapter
        except ImportError:
            from abstract_mcp_dlm_v0_1_2_adapter import AbstractMcpDlmCoreReadAdapter
        return AbstractMcpDlmCoreReadAdapter().invoke(inputs, context)
