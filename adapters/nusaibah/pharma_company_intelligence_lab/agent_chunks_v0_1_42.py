"""Share the existing global limits with claim and paragraph criticism."""
try:
    from .agent_chunks_v0_1_41 import ChunkCoordinator as Base, MeasuredDispatchInputs
    from . import legacy_preparation_helpers_v0_1_23 as legacy
except ImportError:
    from agent_chunks_v0_1_41 import ChunkCoordinator as Base, MeasuredDispatchInputs
    import legacy_preparation_helpers_v0_1_23 as legacy

class ChunkCoordinator(Base):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        # Planner does not dispatch in this version. Allocate room for the
        # paragraph check within the SAME 48-call / 3300-second global cap.
        self.role_budgets[legacy.CRITIC_ROLE]=16
