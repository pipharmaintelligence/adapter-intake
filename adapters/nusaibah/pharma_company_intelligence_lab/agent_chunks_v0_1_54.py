"""Versioned fifteen-call scheduler sharing all existing admission budgets."""
from threading import BoundedSemaphore

try:
    from .agent_chunks_v0_1_47 import ChunkCoordinator as Base, MeasuredDispatchInputs
except ImportError:
    from agent_chunks_v0_1_47 import ChunkCoordinator as Base, MeasuredDispatchInputs


MAX_AGENT_PARALLELISM = 15


class ChunkCoordinator(Base):
    def __init__(self, *, parallelism=MAX_AGENT_PARALLELISM, **kwargs):
        if type(parallelism) is not int or not 1 <= parallelism <= MAX_AGENT_PARALLELISM:
            raise ValueError('agent_parallelism_must_be_1_to_15')
        # The historical constructor initializes counters, phase reserves and
        # budgets without dispatching work. Keep its published 1..3 contract
        # intact, then select this version's scheduler before exposing it to
        # any caller. Every role and backup still uses the same semaphore.
        super().__init__(parallelism=1, **kwargs)
        self.parallelism = parallelism
        self.semaphore = BoundedSemaphore(parallelism)
