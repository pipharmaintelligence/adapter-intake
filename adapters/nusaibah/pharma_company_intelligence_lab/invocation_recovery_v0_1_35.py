"""Withhold explicit provider availability failures; do not revive authority failures."""
from devtools.runtime_agent_invocation import RuntimeAgentInvocationError
try:
    from .invocation_recovery_v0_1_33 import InvocationRecoveryInputs as ExistingRecovery,BoundedRecoveryInputs
    from . import legacy_preparation_helpers_v0_1_23 as legacy
except ImportError:
    from invocation_recovery_v0_1_33 import InvocationRecoveryInputs as ExistingRecovery,BoundedRecoveryInputs
    import legacy_preparation_helpers_v0_1_23 as legacy

class InvocationRecoveryInputs(ExistingRecovery):
    def invoke_agent(self,role,*,input,on_error='raise'):
        try:return super().invoke_agent(role,input=input,on_error=on_error)
        except RuntimeAgentInvocationError as error:
            if str(error)!='agent_execution_provider_member_refresh_failed':raise
            owner=input.get('original_role',role) if role==legacy.RESEARCH_RESOLVER_ROLE else role
            detail=legacy.evidence_diagnostic(role=owner,stage='agent_availability',
                field='provider_member',rule='provider_member_refresh_unavailable')
            self._issue(input,role,detail,'affected_chunk_withheld_no_provider_retry')
            if self._bounded is not None:
                self._bounded.record_response_recovery(company_id=input['company_id'],role=owner,
                    status='unresolved',diagnostic=detail)
            raise legacy.UnresolvedAgentResponse(detail) from None
