from __future__ import annotations

from dataclasses import dataclass
from typing import Any


EXECUTION_PLAN_SCHEMA_VERSION = "execution_plan.v1"

ALLOWED_CAPABILITIES = {
    "local_agent",
}

ALLOWED_ROLES_BY_CAPABILITY = {
    "local_agent": {
        "summarize_records",
    },
}


class ExecutionPlanValidationError(ValueError):
    """Raised when a local capability execution plan is invalid."""


@dataclass(frozen=True)
class ExecutionPlanStep:
    """One validated step in a local capability execution plan."""

    sequence: int
    capability: str
    role: str
    required: bool


@dataclass(frozen=True)
class ExecutionPlan:
    """Validated execution_plan.v1 data."""

    schema_version: str
    company_id: int
    steps: tuple[ExecutionPlanStep, ...]


def validate_execution_plan(plan: Any) -> ExecutionPlan:
    """Validate and normalize one execution_plan.v1 object.

    This function performs local deterministic validation only. It does not
    execute Agents, providers, MCP tools, Skills, network requests, or storage
    operations.
    """
    if not isinstance(plan, dict):
        raise ExecutionPlanValidationError(
            "Execution plan must be a JSON object."
        )

    schema_version = plan.get("schema_version")
    if schema_version != EXECUTION_PLAN_SCHEMA_VERSION:
        raise ExecutionPlanValidationError(
            "Execution plan schema_version must be 'execution_plan.v1'."
        )

    company_id = plan.get("company_id")
    if (
        not isinstance(company_id, int)
        or isinstance(company_id, bool)
        or company_id <= 0
    ):
        raise ExecutionPlanValidationError(
            "Execution plan company_id must be a positive integer."
        )

    raw_steps = plan.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ExecutionPlanValidationError(
            "Execution plan steps must be a non-empty list."
        )

    validated_steps: list[ExecutionPlanStep] = []

    for expected_sequence, raw_step in enumerate(raw_steps, start=1):
        if not isinstance(raw_step, dict):
            raise ExecutionPlanValidationError(
                f"Execution plan step {expected_sequence} must be an object."
            )

        sequence = raw_step.get("sequence")
        if sequence != expected_sequence:
            raise ExecutionPlanValidationError(
                "Execution plan step sequence values must start at 1 "
                "and increase without gaps."
            )

        capability = raw_step.get("capability")
        if capability not in ALLOWED_CAPABILITIES:
            raise ExecutionPlanValidationError(
                f"Unsupported capability at step {sequence}: {capability!r}."
            )

        role = raw_step.get("role")
        allowed_roles = ALLOWED_ROLES_BY_CAPABILITY[capability]
        if role not in allowed_roles:
            raise ExecutionPlanValidationError(
                f"Unsupported role for capability {capability!r} "
                f"at step {sequence}: {role!r}."
            )

        required = raw_step.get("required")
        if not isinstance(required, bool):
            raise ExecutionPlanValidationError(
                f"Step {sequence} required must be a boolean."
            )

        validated_steps.append(
            ExecutionPlanStep(
                sequence=sequence,
                capability=capability,
                role=role,
                required=required,
            )
        )

    return ExecutionPlan(
        schema_version=schema_version,
        company_id=company_id,
        steps=tuple(validated_steps),
    )