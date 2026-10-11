"""Add bounded review guidance to existing 0.1.21 Agent dispatch.

This facade delegates execution, counters and one-time recovery to the existing
runtime helpers. It owns no search, storage, mutation, retry or apply authority.
Historical helpers and their published versions remain unchanged.
"""
from __future__ import annotations

from typing import Any

try:
    from .claim_semantics_v0_1_21 import SEMANTIC_RULES
    from .methodology_learning_v0_1_21 import reviewed_methodology_addendum
except ImportError:  # pragma: no cover - flat intake execution
    from claim_semantics_v0_1_21 import SEMANTIC_RULES
    from methodology_learning_v0_1_21 import reviewed_methodology_addendum


_RESEARCH_ROLES = frozenset({
    "portfolio_researcher", "market_researcher", "regulatory_risk_researcher",
})
_REVIEW_ROLES = _RESEARCH_ROLES | {
    "strategic_analyst", "evidence_critic", "intelligence_synthesizer",
}


class PreparationContextInputs:
    """Forward unchanged runtime authority with version-owned input guidance."""

    def __init__(self, inputs: Any, *, learned_methodology_text: str) -> None:
        self._inputs = inputs
        self._learning = reviewed_methodology_addendum(learned_methodology_text)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inputs, name)

    def invoke_agent(self, role: str, *, input: dict[str, Any], on_error: str = "raise") -> Any:
        projected = dict(input)
        if role == "methodology_planner":
            projected["learned_methodology_addendum"] = self._learning
        if role in _REVIEW_ROLES:
            projected["semantic_review_rules"] = [
                {"rule_id": rule_id, "instruction": instruction}
                for rule_id, instruction in SEMANTIC_RULES
            ]
        return self._inputs.invoke_agent(role, input=projected, on_error=on_error)
