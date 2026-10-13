"""Concurrency-safe one-backup reservation for each original chunk call."""
from threading import local
try:
    from .invocation_recovery_v0_1_31 import InvocationRecoveryInputs
    from .orchestration_v0_1_26 import FinalBoundedAgentInputs
    from . import legacy_preparation_helpers_v0_1_23 as legacy
except ImportError:
    from invocation_recovery_v0_1_31 import InvocationRecoveryInputs
    from orchestration_v0_1_26 import FinalBoundedAgentInputs
    import legacy_preparation_helpers_v0_1_23 as legacy

class BoundedRecoveryInputs(FinalBoundedAgentInputs):
    def __init__(self,*args,coordinator,**kwargs):
        super().__init__(*args,**kwargs);self.coordinator=coordinator;self._original_ordinals=local()
        self._ordinary_company_limit=48;self._per_company_limit=96
        self.agent_call_limit=len(self._company_calls)*96
        for role in self._role_limits:self._role_limits[role]=48
        self._role_limits[legacy.BENCHMARK_ROLE]=0
    def invoke_agent(self,role,*,input,on_error='raise'):
        company_id=input.get('company_id')
        self.coordinator.require_fit(role,input)
        with self._lock:
            if role==legacy.RESEARCH_RESOLVER_ROLE:
                reservation=(company_id,input.get('original_role'),input.get('original_invocation_ordinal'))
                if reservation not in self._repair_reservations or reservation in self._repair_dispatches:
                    raise legacy.UnresolvedAgentResponse(legacy.evidence_diagnostic(role=input.get('original_role',role),
                        stage='agent_response_resolver',field='content',rule='backup_exhausted'))
                self._repair_dispatches.add(reservation)
            self._check_available(company_id,role)
            self.agent_call_count+=1;self._company_calls[company_id]+=1
            key=(company_id,role);ordinal=self._role_calls.get(key,0)+1;self._role_calls[key]=ordinal
            if role!=legacy.RESEARCH_RESOLVER_ROLE:
                values=getattr(self._original_ordinals,'values',{});values[key]=ordinal
                self._original_ordinals.values=values
        return self._inputs.invoke_agent(role,input=input,on_error=on_error)
    def invoke_response_resolver(self,*,original_role,input):
        company_id=input['company_id']
        ordinal=getattr(self._original_ordinals,'values',{}).get((company_id,original_role),0)
        reservation=(company_id,original_role,ordinal)
        with self._lock:
            if original_role==legacy.RESEARCH_RESOLVER_ROLE or ordinal<1 or reservation in self._repair_reservations:
                raise legacy.UnresolvedAgentResponse(legacy.evidence_diagnostic(role=original_role,
                    stage='agent_response_resolver',field='content',rule='backup_exhausted'))
            self._repair_reservations.add(reservation)
        return self.invoke_agent(legacy.RESEARCH_RESOLVER_ROLE,input={**input,
            'original_role':original_role,'original_invocation_ordinal':ordinal},on_error='raise')
    def invoke_asset(self,role,*,variables=None,on_error='raise'):
        with self._source_lock:
            if self._source_toolkit_calls>=32:
                raise legacy.UnresolvedAgentResponse(legacy.evidence_diagnostic(role='orchestration',
                    stage='source_verification',field='calls',rule='source_toolkit_budget_exhausted'))
            self._source_toolkit_calls+=1
        return self._runtime_inputs.invoke_asset(role,variables=variables,on_error=on_error)
