"""Contain exhausted availability waits; authority and unknown failures propagate."""
from devtools.runtime_agent_invocation import RuntimeAgentInvocationError
try:
    from .invocation_recovery_v0_1_40 import InvocationRecoveryInputs as Base, BoundedRecoveryInputs
    from . import legacy_preparation_helpers_v0_1_23 as legacy
except ImportError:
    from invocation_recovery_v0_1_40 import InvocationRecoveryInputs as Base, BoundedRecoveryInputs
    import legacy_preparation_helpers_v0_1_23 as legacy


class InvocationRecoveryInputs(Base):
    def invoke_agent(self, role, *, input, on_error='raise'):
        try:
            return super().invoke_agent(role,input=input,on_error=on_error)
        except RuntimeAgentInvocationError as error:
            code=getattr(error,'failure_code',None) or str(error)
            cause=getattr(error,'cause_code',None)
            if code not in {'agent_execution_provider_retry_exhausted','agent_execution_session_deadline_exceeded'} or cause not in {
                'provider_execution_transport_timeout','provider_execution_transport_failed',
                'provider_execution_vertex_rate_limited','provider_execution_vertex_unavailable'}:
                raise
            owner=input.get('original_role',role) if role==legacy.RESEARCH_RESOLVER_ROLE else role
            detail=legacy.evidence_diagnostic(role=owner,stage='agent_availability',field='provider_attempt',
                rule='provider_availability_budget_exhausted')
            self._issue(input,role,detail,'affected_chunk_withheld_no_provider_retry')
            if self._bounded is not None:
                self._bounded.record_response_recovery(company_id=input['company_id'],role=owner,
                    status='unresolved',diagnostic=detail)
            # A JSON resolver cannot repair a transport wait. Do not add paid
            # retries or fabricate an Agent response; preserve valid siblings.
            raise legacy.UnresolvedAgentResponse(detail) from None
