"""Research contract parity over the bounded, invocation-recovering review-only kernel."""
from __future__ import annotations

from typing import Any, ClassVar
from adapters.base import Adapter

try:
    from .orchestration_v0_1_25 import invoke_v0_1_25
except ImportError:  # pragma: no cover - flat intake execution
    from orchestration_v0_1_25 import invoke_v0_1_25

AGENT_ORCHESTRATION_OWNER = "python_adapter"


class NusaibahPharmaCompanyIntelligenceLabV025Adapter(Adapter):
    key: ClassVar[str] = "nusaibah.pharma_company_intelligence_lab"
    version: ClassVar[str] = "0.1.25"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        del context
        return invoke_v0_1_25(inputs, asset_identity=f"{self.key}:{self.version}")
