from __future__ import annotations

from typing import Any, ClassVar

AGENT_ORCHESTRATION_OWNER = "python_adapter"

if __package__:
    from .evaluation_replay import BaselineReplayError, run_company_replay_case
    from .nusaibah_pharma_company_intelligence_lab_evaluation_adapter import (
        NusaibahPharmaCompanyIntelligenceLabEvaluationAdapter as _EvaluationBase,
    )
else:
    from evaluation_replay import BaselineReplayError, run_company_replay_case
    from nusaibah_pharma_company_intelligence_lab_evaluation_adapter import (
        NusaibahPharmaCompanyIntelligenceLabEvaluationAdapter as _EvaluationBase,
    )


class NusaibahPharmaCompanyIntelligenceLabEvaluationV011Adapter(_EvaluationBase):
    """Diagnostic-only revision; inherited inputs and frozen decisions are unchanged."""

    key: ClassVar[str] = "nusaibah.pharma_company_intelligence_lab_evaluation"
    version: ClassVar[str] = "0.1.1"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        """Run exactly one company-research evaluation case in preview mode."""

        del context

        case = self._evaluation_case(inputs)
        case_index = self._case_index(inputs)

        replay = run_company_replay_case(
            case,
            case_index=case_index,
            runtime_delegate=inputs,
            diagnostic_failures=True,
        )

        if replay.get("executed") is not True:
            raise BaselineReplayError(
                "Evaluation case was not executable against the pinned baseline."
            )

        # The replay helper itself prohibits mutable Dynamic Skill roles.
        dynamic_roles = replay.get("dynamic_skill_calls", [])
        if any(
            role in {"company_memory_update", "company_methodology_update"}
            for role in dynamic_roles
        ):
            raise BaselineReplayError(
                "Evaluation replay attempted mutable Dynamic Skill authority."
            )

        return {
            "response_version": "1",
            "status": "success",
            "outputs": {
                "evaluation_result": replay,
            },
            "logs": [
                {
                    "level": "info",
                    "message": "WP1 evaluation replay completed.",
                }
            ],
            "metrics": {
                "executed_case_count": 1,
                "agent_call_count": len(replay.get("agent_calls", [])),
                "mutable_dynamic_skill_call_count": 0,
            },
        }
