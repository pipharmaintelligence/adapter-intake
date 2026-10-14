"""Phase-aware admission for a bounded sixty-minute company work item."""
try:
    from .agent_chunks_v0_1_39 import ChunkCoordinator as Base, MeasuredDispatchInputs
    from . import legacy_preparation_helpers_v0_1_23 as legacy
except ImportError:
    from agent_chunks_v0_1_39 import ChunkCoordinator as Base, MeasuredDispatchInputs
    import legacy_preparation_helpers_v0_1_23 as legacy


class ChunkCoordinator(Base):
    def __init__(self, *, seconds=3300, call_timeout_seconds=1200,
                 publication_reserve_seconds=180, **kwargs):
        super().__init__(seconds=seconds, **kwargs)
        self.execution_seconds = seconds
        self.call_timeout_seconds = call_timeout_seconds
        self.publication_reserve_seconds = publication_reserve_seconds
        self.phase_admissions = []

    def owner(self, role, payload):
        return payload.get('original_role', role) if role == legacy.RESEARCH_RESOLVER_ROLE else role

    def reserve_after(self, owner):
        # Research cannot consume the last critic allowance. The critic can use
        # that allowance itself, leaving only the final storage/cleanup reserve.
        # Strategy/synthesis run after criticism and are presentation assistance.
        return self.publication_reserve_seconds + (self.call_timeout_seconds
            if owner in (*legacy.RESEARCH_ROLES, legacy.PLANNER_ROLE) else 0)

    def dispatch(self, role, payload, call):
        self.require_fit(role, payload, record=True)
        owner = self.owner(role, payload)
        needed = self.call_timeout_seconds + self.reserve_after(owner)
        remaining = self.deadline - self.clock()
        if remaining < needed or not self.semaphore.acquire(timeout=max(0, remaining-needed)):
            raise legacy.UnresolvedAgentResponse(legacy.evidence_diagnostic(
                role=owner, stage='chunk_admission', field='remaining_seconds',
                rule='execution_budget_reserved_for_consolidation'))
        try:
            # Recheck after waiting: another task cannot spend reserved time.
            if self.deadline-self.clock() < needed:
                raise legacy.UnresolvedAgentResponse(legacy.evidence_diagnostic(
                    role=owner, stage='chunk_admission', field='remaining_seconds',
                    rule='execution_budget_reserved_for_consolidation'))
            self.require_available(role, payload)
            with self.lock:
                count = self.company_role_dispatches.get((payload.get('company_id'), owner), 0)
                if self.calls >= self.max_calls or count >= self.role_budgets.get(owner, 0):
                    raise legacy.UnresolvedAgentResponse(legacy.evidence_diagnostic(
                        role=owner, stage='chunk_admission', field='calls',
                        rule='phase_call_budget_reserved_for_downstream'))
                self.company_role_dispatches[(payload.get('company_id'), owner)] = count+1
                self.role_dispatches[owner] = self.role_dispatches.get(owner, 0)+1
                self.calls += 1; self.active += 1; self.peak = max(self.peak, self.active)
                self.phase_admissions.append({'role': role, 'company_id': payload.get('company_id'),
                    'remaining_seconds': max(0, int(self.deadline-self.clock())),
                    'reserved_after_seconds': self.reserve_after(owner)})
            try:
                return call()
            finally:
                with self.lock: self.active -= 1
        finally:
            self.semaphore.release()

    def proof(self):
        value = super().proof()
        with self.lock:
            return {**value, 'execution_budget_seconds': self.execution_seconds,
                'agent_timeout_ceiling_seconds': self.call_timeout_seconds,
                'publication_reserve_seconds': self.publication_reserve_seconds,
                'critical_phase_priority': 'evidence_critic_before_optional_strategy_and_synthesis',
                'phase_admissions': list(self.phase_admissions)}
