"""Research contract parity over the unchanged bounded, review-only kernel."""
from __future__ import annotations

from typing import Any, ClassVar
from adapters.base import Adapter

try:
    from .orchestration_v0_1_24 import invoke_v0_1_24
except ImportError:  # pragma: no cover - flat intake execution
    from orchestration_v0_1_24 import invoke_v0_1_24

AGENT_ORCHESTRATION_OWNER = "python_adapter"


class NusaibahPharmaCompanyIntelligenceLabV024Adapter(Adapter):
    key: ClassVar[str] = "nusaibah.pharma_company_intelligence_lab"
    version: ClassVar[str] = "0.1.24"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        del context
        return invoke_v0_1_24(inputs, asset_identity=f"{self.key}:{self.version}")
