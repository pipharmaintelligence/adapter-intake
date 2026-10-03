from __future__ import annotations

from typing import Any, ClassVar

from adapters.base import Adapter

AGENT_ORCHESTRATION_OWNER = "python_adapter"

from evaluation_replay import (
    COMPANY_CASE_MODE,
    BaselineReplayError,
    run_company_replay_case,
)


class NusaibahPharmaCompanyIntelligenceLabEvaluationAdapter(Adapter):
    """Execute one synthetic WP1 company replay against frozen 0.1.12 semantics.

    This adapter exists only for evaluation. It does not own provider
    credentials, production bindings, Dynamic Skill mutation, publication,
    storage placement, retries, or provider execution.

    Trusted Agent and Fixed Skill authority must be supplied by RuntimeInputs.
    """

    key: ClassVar[str] = "nusaibah.pharma_company_intelligence_lab_evaluation"
    version: ClassVar[str] = "0.1.0"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        """Run exactly one company-research evaluation case in preview mode."""

        del context

        case = self._evaluation_case(inputs)
        case_index = self._case_index(inputs)

        replay = run_company_replay_case(
            case,
            case_index=case_index,
            runtime_delegate=inputs,
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

    @staticmethod
    def _evaluation_case(inputs: Any) -> dict[str, Any]:
        """Return one bounded synthetic case without adjudication truth."""

        payload = inputs.get("evaluation_case")
        if not isinstance(payload, dict):
            raise BaselineReplayError(
                "evaluation_case must be a runtime input object."
            )

        records = payload.get("records")
        if not isinstance(records, list) or len(records) != 1:
            raise BaselineReplayError(
                "evaluation_case must contain exactly one record."
            )

        raw = records[0]
        if not isinstance(raw, dict):
            raise BaselineReplayError(
                "evaluation_case record must be an object."
            )

        # Fail closed if expected answers, thresholds, reviewer data or other
        # suite metadata accidentally reaches the provider execution asset.
        allowed_fields = {"case_id", "mode", "source_units"}
        unexpected = set(raw) - allowed_fields
        if unexpected:
            raise BaselineReplayError(
                "evaluation_case contains fields outside the allowed replay contract."
            )

        case_id = raw.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise BaselineReplayError("evaluation_case.case_id is required.")

        if raw.get("mode") != COMPANY_CASE_MODE:
            raise BaselineReplayError(
                "Only company_research evaluation cases are executable."
            )

        source_units = raw.get("source_units")
        if not isinstance(source_units, list) or not source_units:
            raise BaselineReplayError(
                "evaluation_case.source_units must be a non-empty list."
            )

        return {
            "case_id": case_id,
            "mode": COMPANY_CASE_MODE,
            "source_units": source_units,
        }

    @staticmethod
    def _case_index(inputs: Any) -> int:
        """Return the immutable suite index used for synthetic company identity."""

        variables = inputs.get("variables")
        if not isinstance(variables, dict):
            raise BaselineReplayError("variables must be an object.")

        if set(variables) != {"case_index"}:
            raise BaselineReplayError(
                "Only variables.case_index is allowed for evaluation replay."
            )

        case_index = variables.get("case_index")
        if (
            isinstance(case_index, bool)
            or not isinstance(case_index, int)
            or not 0 <= case_index < 24
        ):
            raise BaselineReplayError(
                "variables.case_index must be an integer from 0 through 23."
            )

        return case_index
