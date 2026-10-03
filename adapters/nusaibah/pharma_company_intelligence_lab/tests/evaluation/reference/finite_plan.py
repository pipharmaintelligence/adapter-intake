from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class PlanAdmissionError(ValueError):
    """Raised when a finite review plan exceeds declared authority or budget."""


@dataclass(frozen=True)
class PlanBudget:
    max_tasks: int
    max_provider_steps: int
    max_transport_attempts: int
    max_total_input_chars: int

    def validate(self) -> None:
        for name, value in self.__dict__.items():
            if not isinstance(value, int) or value < 1:
                raise PlanAdmissionError(f"{name} must be a positive integer.")


def admit_plan(
    tasks: list[dict[str, Any]],
    *,
    budget: PlanBudget,
    allowed_roles: set[str],
) -> dict[str, Any]:
    """Freeze and validate a finite task graph before dispatch."""

    budget.validate()
    if not tasks:
        raise PlanAdmissionError("At least one review task is required.")
    if len(tasks) > budget.max_tasks:
        raise PlanAdmissionError("Logical task budget exceeded.")

    task_ids: set[str] = set()
    provider_steps = 0
    attempts = 0
    input_chars = 0

    for task in tasks:
        task_id = str(task.get("task_id", "")).strip()
        role = str(task.get("role", "")).strip()
        if not task_id or task_id in task_ids:
            raise PlanAdmissionError("Task IDs must be unique and non-empty.")
        if role not in allowed_roles:
            raise PlanAdmissionError("Task role is not admitted.")
        task_ids.add(task_id)

        provider_steps += int(task.get("provider_step_budget", 0))
        attempts += int(task.get("transport_attempt_budget", 0))
        input_chars += int(task.get("input_char_budget", 0))

    if provider_steps > budget.max_provider_steps:
        raise PlanAdmissionError("Provider-step budget exceeded.")
    if attempts > budget.max_transport_attempts:
        raise PlanAdmissionError("Transport-attempt budget exceeded.")
    if input_chars > budget.max_total_input_chars:
        raise PlanAdmissionError("Input-character budget exceeded.")

    return {
        "schema_version": "review_execution_plan.v1",
        "state": "admitted",
        "task_count": len(tasks),
        "provider_step_count": provider_steps,
        "transport_attempt_count": attempts,
        "input_character_budget": input_chars,
        "task_ids": [task["task_id"] for task in tasks],
        "tasks": [dict(task) for task in tasks],
    }


def reserve_task(
    plan: dict[str, Any],
    *,
    task_id: str,
    reservations: set[str],
) -> None:
    """Reserve a task exactly once before dispatch."""

    if task_id not in set(plan["task_ids"]):
        raise PlanAdmissionError("Cannot reserve an unknown task.")
    if task_id in reservations:
        raise PlanAdmissionError("Task capacity is already reserved.")
    reservations.add(task_id)
