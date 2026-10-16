"""One run budget and closed availability handling; no provider retries here."""
from __future__ import annotations
from dataclasses import dataclass
import threading
import math
import time
from typing import Callable
try:
    from .contracts import ContractError, require
except ImportError:
    from contracts import ContractError, require


@dataclass(frozen=True)
class ExecutionPolicy:
    """Reviewed local work bounds, not a replacement for runtime I/O deadlines."""
    max_agent_calls: int = 12
    research_concurrency: int = 2
    deadline_seconds: float = 1800.0
    completion_reserve_seconds: float = 120.0
    stage_allowance_seconds: float = 180.0
    max_reference_reads: int = 16
    max_packet_bytes: int = 120_000
    max_task_items: int = 32


class DeferredWork(ContractError):
    """A task was not dispatched; existing validated state remains usable."""


class Budget:
    """Thread-safe shared counters and completion reserve for a single execution."""
    def __init__(self, policy: ExecutionPolicy | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.policy = policy or ExecutionPolicy()
        p = self.policy
        require(type(p.research_concurrency) is int and 1 <= p.research_concurrency <= 2,
                "clinical_concurrency_invalid")
        for value, minimum, maximum in ((p.max_agent_calls, 1, 64),
                (p.max_reference_reads, 0, 16), (p.max_packet_bytes, 1024, 262144),
                (p.max_task_items, 1, 32)):
            require(type(value) is int and minimum <= value <= maximum,
                    "clinical_execution_policy_invalid")
        for value in (p.deadline_seconds, p.completion_reserve_seconds, p.stage_allowance_seconds):
            require(type(value) in (int, float) and math.isfinite(value) and value > 0,
                    "clinical_execution_policy_invalid")
        require(p.deadline_seconds > p.completion_reserve_seconds + p.stage_allowance_seconds,
                "clinical_execution_policy_invalid")
        self.clock = clock
        self.started = clock()
        self.lock = threading.Lock()
        self.calls = 0
        self.reads = 0
        self.refinements = 0
        self.repairs = 0

    def reserve(self, *, kind: str = "agent", minimum_calls_remaining: int = 0) -> None:
        """Reserve before dispatch; every research chunk shares these counters."""
        require(kind in {"agent", "reference"} and type(minimum_calls_remaining) is int
                and minimum_calls_remaining >= 0, "clinical_reservation_invalid")
        with self.lock:
            p = self.policy
            remaining = p.deadline_seconds - (self.clock() - self.started)
            if remaining < p.completion_reserve_seconds + p.stage_allowance_seconds:
                raise DeferredWork("clinical_completion_reserve_reached")
            if kind == "reference":
                if self.reads >= p.max_reference_reads:
                    raise DeferredWork("clinical_reference_budget_exhausted")
                self.reads += 1
            else:
                if self.calls + 1 + minimum_calls_remaining > p.max_agent_calls:
                    raise DeferredWork("clinical_agent_budget_reserved")
                self.calls += 1

    def refine_once(self) -> bool:
        """Admit at most one focused research/adjudication/analysis/review round."""
        with self.lock:
            if self.refinements or self.calls + 4 > self.policy.max_agent_calls:
                return False
            self.refinements = 1
            return True

    def proof(self) -> dict:
        """Return counts only; do not invent provider usage or durable state."""
        with self.lock:
            return {"logical_agent_calls": self.calls, "reference_reads": self.reads,
                    "refinement_rounds": self.refinements, "model_repair_calls": self.repairs,
                    "elapsed_seconds": round(max(0.0, self.clock() - self.started), 4)}


def recoverable_availability(error: Exception) -> bool:
    """Recognize reviewed exhausted transport codes, never broad exception text."""
    code = getattr(error, "failure_code", None) or getattr(error, "code", None)
    cause = getattr(error, "cause_code", None)
    return code in {"agent_execution_provider_retry_exhausted", "agent_execution_session_deadline_exceeded"} and cause in {
        "provider_execution_transport_timeout", "provider_execution_transport_failed",
        "provider_execution_vertex_rate_limited", "provider_execution_vertex_unavailable"}
