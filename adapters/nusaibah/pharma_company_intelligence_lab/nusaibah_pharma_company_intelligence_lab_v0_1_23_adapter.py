"""Executable entrypoint for pharma company intelligence adapter 0.1.23.

Role boundaries:
- methodology_planner plans bounded work without factual citation authority.
- portfolio_researcher owns company/profile and portfolio claims.
- market_researcher owns market and commercial claims.
- regulatory_risk_researcher owns regulatory, clinical and safety claims.
- strategic_analyst reasons only over accepted same-company evidence.
- evidence_critic assigns quality dispositions without mutation authority.
- intelligence_synthesizer prepares the dossier and memory candidate.
- memory_benchmark_reviewer scores supplied memory without adding facts.
- research_response_resolver performs one faithful format repair only.

The version-owned kernel retains non-completed business responses as issues.
Runtime completion and company/role authority remain strict. The unchanged
0.1.22 Agent contracts retain response budgets and thinking headroom.
Assets owns Agent/provider execution and output retention. Core owns governed
data and Dynamic Skill persistence. This version admits preview only.
"""
from __future__ import annotations

from typing import Any, ClassVar

from adapters.base import Adapter

try:
    from .orchestration_v0_1_23 import invoke_v0_1_23
except ImportError:  # pragma: no cover - flat intake execution
    from orchestration_v0_1_23 import invoke_v0_1_23


AGENT_ORCHESTRATION_OWNER = "python_adapter"


class NusaibahPharmaCompanyIntelligenceLabV023Adapter(Adapter):
    """Prepare claim-grounded, independently reviewable company intelligence."""

    key: ClassVar[str] = "nusaibah.pharma_company_intelligence_lab"
    version: ClassVar[str] = "0.1.23"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        """Run the bounded preview pipeline and return a review-pending dossier."""

        del context
        return invoke_v0_1_23(
            inputs,
            asset_identity=f"{self.key}:{self.version}",
        )
