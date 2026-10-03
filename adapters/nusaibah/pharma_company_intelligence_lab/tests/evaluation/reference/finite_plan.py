from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any


class PlanAdmissionError(ValueError):
    """Raised when a finite review plan exceeds declared authority or budget."""


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise PlanAdmissionError(f"{field} must be a positive integer.")
    return value


@dataclass(frozen=True)
class PlanBudget:
    max_tasks: int
    max_logical_calls: int
    max_provider_steps: int
    max_transport_attempts: int
    max_total_input_chars: int
    max_total_output_tokens: int
    max_concurrency: int
    max_execution_seconds: int

    def validate(self) -> None:
        for name, value in self.__dict__.items():
            _positive_int(value, field=name)
        if self.max_concurrency > self.max_tasks:
            raise PlanAdmissionError("max_concurrency cannot exceed max_tasks.")


@dataclass
class ReservationLedger:
    """Thread-safe one-way task reservation ledger."""

    _reserved: set[str] = field(default_factory=set)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def reserve(self, *, admitted_task_ids: set[str], task_id: str) -> None:
        with self._lock:
            if task_id not in admitted_task_ids:
                raise PlanAdmissionError("Cannot reserve an unknown task.")
            if task_id in self._reserved:
                raise PlanAdmissionError("Task capacity is already reserved.")
            self._reserved.add(task_id)

    def snapshot(self) -> frozenset[str]:
        with self._lock:
            return frozenset(self._reserved)


def admit_plan(
    tasks: list[dict[str, Any]],
    *,
    budget: PlanBudget,
    allowed_roles: set[str],
) -> dict[str, Any]:
    """Freeze and validate a finite task graph before dispatch."""

    budget.validate()
    if not isinstance(tasks, list) or not tasks:
        raise PlanAdmissionError("At least one review task is required.")
    if len(tasks) > budget.max_tasks:
        raise PlanAdmissionError("Logical task budget exceeded.")

    task_ids: set[str] = set()
    logical_calls = provider_steps = attempts = input_chars = output_tokens = 0
    max_task_timeout = 0

    required_task_keys = {
        "schema_version",
        "run_id",
        "entity_id",
        "task_id",
        "role",
        "requirement_ids",
        "chunk_ids",
        "memory_ref_ids",
        "output_schema",
        "logical_call_budget",
        "provider_step_budget",
        "transport_attempt_budget",
        "input_char_budget",
        "output_token_budget",
        "timeout_seconds",
    }

    for task in tasks:
        if not isinstance(task, dict):
            raise PlanAdmissionError("Each task must be an object.")
        if set(task) != required_task_keys:
            raise PlanAdmissionError("Task shape does not match admitted review-task schema.")

        task_id = str(task.get("task_id", "")).strip()
        role = str(task.get("role", "")).strip()
        if not task_id or task_id in task_ids:
            raise PlanAdmissionError("Task IDs must be unique and non-empty.")
        if role not in allowed_roles:
            raise PlanAdmissionError("Task role is not admitted.")
        task_ids.add(task_id)

        logical_calls += _positive_int(task["logical_call_budget"], field=f"{task_id}.logical_call_budget")
        provider_steps += _positive_int(task["provider_step_budget"], field=f"{task_id}.provider_step_budget")
        attempts += _positive_int(task["transport_attempt_budget"], field=f"{task_id}.transport_attempt_budget")
        input_chars += _positive_int(task["input_char_budget"], field=f"{task_id}.input_char_budget")
        output_tokens += _positive_int(task["output_token_budget"], field=f"{task_id}.output_token_budget")
        timeout_seconds = _positive_int(task["timeout_seconds"], field=f"{task_id}.timeout_seconds")
        max_task_timeout = max(max_task_timeout, timeout_seconds)

    if logical_calls > budget.max_logical_calls:
        raise PlanAdmissionError("Logical-call budget exceeded.")
    if provider_steps > budget.max_provider_steps:
        raise PlanAdmissionError("Provider-step budget exceeded.")
    if attempts > budget.max_transport_attempts:
        raise PlanAdmissionError("Transport-attempt budget exceeded.")
    if input_chars > budget.max_total_input_chars:
        raise PlanAdmissionError("Input-character budget exceeded.")
    if output_tokens > budget.max_total_output_tokens:
        raise PlanAdmissionError("Output-token budget exceeded.")
    if max_task_timeout > budget.max_execution_seconds:
        raise PlanAdmissionError("A task timeout exceeds the run execution budget.")

    return {
        "schema_version": "review_execution_plan.v1",
        "state": "admitted",
        "task_count": len(tasks),
        "logical_call_count": logical_calls,
        "provider_step_count": provider_steps,
        "transport_attempt_count": attempts,
        "input_character_budget": input_chars,
        "output_token_budget": output_tokens,
        "max_concurrency": budget.max_concurrency,
        "max_execution_seconds": budget.max_execution_seconds,
        "task_ids": [task["task_id"] for task in tasks],
        "tasks": [dict(task) for task in tasks],
    }


def reserve_task(
    plan: dict[str, Any],
    *,
    task_id: str,
    ledger: ReservationLedger,
) -> None:
    """Atomically reserve one admitted task exactly once before dispatch."""

    ledger.reserve(admitted_task_ids=set(plan["task_ids"]), task_id=task_id)
