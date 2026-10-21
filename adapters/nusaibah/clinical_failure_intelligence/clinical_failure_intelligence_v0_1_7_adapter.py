"""Runtime entrypoint for the independent clinical-failure intelligence preview."""
from __future__ import annotations
from typing import Any, ClassVar
from adapters.base import Adapter

AGENT_ORCHESTRATION_OWNER = "python_adapter"

if __package__:
    from .orchestration_v0_1_7 import run_analysis
else:
    from orchestration_v0_1_7 import run_analysis


class ClinicalFailureIntelligenceAdapter(Adapter):
    """Interpret governed context through admitted roles; never own execution authority."""
    key: ClassVar[str] = "nusaibah.clinical_failure_intelligence"
    version: ClassVar[str] = "0.1.7"

    def invoke(self, inputs: Any, context: Any) -> dict[str, Any]:
        """Return a validated preview without publishing or changing product/class memory."""
        del context
        return run_analysis(inputs)
