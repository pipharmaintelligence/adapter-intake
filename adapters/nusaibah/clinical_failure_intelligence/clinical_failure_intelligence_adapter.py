"""Runtime entrypoint for the independent clinical-failure intelligence preview."""
from __future__ import annotations
from typing import Any, ClassVar
from adapters.base import Adapter
if __package__:
    from .orchestration import run_analysis
else:
    from orchestration import run_analysis


class ClinicalFailureIntelligenceAdapter(Adapter):
    """Interpret governed context through admitted roles; never own execution authority."""
    key: ClassVar[str] = "nusaibah.clinical_failure_intelligence"
    version: ClassVar[str] = "0.1.0"

    def invoke(self, inputs: Any, context: Any) -> dict[str, Any]:
        """Return a validated preview without publishing or changing group memory."""
        del context
        return run_analysis(inputs)
