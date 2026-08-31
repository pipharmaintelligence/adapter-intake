from __future__ import annotations

from typing import Any

from adapters.base import Adapter

try:
    from .execution_plan import validate_execution_plan
except ImportError:  # pragma: no cover - local adapter-root execution path
    from execution_plan import validate_execution_plan


ALLOWED_PROOF_STAGES = {
    "scaffold",
    "agent_invocation",
    "fixed_skill_read",
}


def _resolve_proof_stage(variables: dict[str, Any]) -> str:
    """Return and validate the requested local capability proof stage."""
    proof_stage = str(variables.get("proof_stage", "scaffold")).strip()

    if proof_stage not in ALLOWED_PROOF_STAGES:
        allowed = ", ".join(sorted(ALLOWED_PROOF_STAGES))
        raise ValueError(
            f"Unsupported proof_stage '{proof_stage}'. "
            f"Allowed stages: {allowed}."
        )

    return proof_stage


class NusaibahAgentCapabilityLabAdapter(Adapter):
    """Local deterministic adapter for progressive capability proofs."""

    key = "nusaibah.agent_capability_lab"
    version = "0.1.0"

    def invoke(self, inputs, context):
        """Validate the requested proof stage and return local-only evidence."""
        dataset = inputs.get("companies", {})
        records = dataset.get("records", [])
        variables = inputs.get("variables", {})

        # Validate orchestration intent before any capability-specific proof.
        execution_plan_data = variables.get("execution_plan")
        validated_plan = validate_execution_plan(execution_plan_data)

        proof_stage = _resolve_proof_stage(variables)

        capability_result = {
            "record_count": len(records),
            "variables_present": bool(variables),
            "proof_stage": proof_stage,
            "execution_plan_schema": validated_plan.schema_version,
            "execution_plan_company_id": validated_plan.company_id,
            "execution_plan_step_count": len(validated_plan.steps),
        }

        if proof_stage == "fixed_skill_read":
            # Resolve the exact immutable Fixed Skill through the runtime.
            skill_view = inputs.skill(
                "nusaibah.capability-orchestration"
            )

            # Validate the manifest-pinned package and its safe provenance.
            skill_validation = skill_view.validate()

            # Read and inspect only.
            # We are not executing or interpreting Skill instructions yet.
            skill_text = skill_view.read()
            skill_inspection = skill_view.inspect()

            capability_result.update(
                {
                    "fixed_skill_status": skill_validation.status,
                    "fixed_skill_ref": skill_validation.skill_ref,
                    "fixed_skill_version": skill_validation.version,
                    "fixed_skill_resource_count": (
                        skill_validation.resource_count
                    ),
                    "fixed_skill_title": skill_inspection.title,
                    "fixed_skill_section_count": (
                        skill_inspection.section_count
                    ),
                    "fixed_skill_block_count": (
                        skill_inspection.block_count
                    ),
                    "fixed_skill_text_present": bool(skill_text),
                }
            )

        return {
            "response_version": "1",
            "status": "success",
            "outputs": {
                "capability_result": capability_result,
            },
            "logs": [
                {
                    "level": "info",
                    "message": (
                        f"Local capability proof stage validated: "
                        f"{proof_stage}."
                    ),
                },
            ],
            "metrics": {
                "record_count": len(records),
                "proof_stage_validated": 1,
            },
        }