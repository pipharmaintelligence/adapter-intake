"""0.1.2 execution identity; reuse the reviewed read-only DLM implementation.

This intake submission still requires reviewed Assets promotion and release.
"""

try:
    from .abstract_mcp_dlm_v0_1_1_adapter import AbstractMcpDlmReadAdapter
except ImportError:
    from abstract_mcp_dlm_v0_1_1_adapter import AbstractMcpDlmReadAdapter


class AbstractMcpDlmCoreReadAdapter(AbstractMcpDlmReadAdapter):
    key = "nusaibah.abstract_mcp_dlm"
    version = "0.1.2"
