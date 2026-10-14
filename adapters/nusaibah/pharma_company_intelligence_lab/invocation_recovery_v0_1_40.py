"""Normalize grounded text JSON without changing its admitted citation envelope."""
try:
    from .invocation_recovery_v0_1_35 import InvocationRecoveryInputs as Base,BoundedRecoveryInputs
    from .agent_response_recovery_v0_1_40 import normalize_json_envelope,AgentResponseDiagnosticError
except ImportError:
    from invocation_recovery_v0_1_35 import InvocationRecoveryInputs as Base,BoundedRecoveryInputs
    from agent_response_recovery_v0_1_40 import normalize_json_envelope,AgentResponseDiagnosticError

class InvocationRecoveryInputs(Base):
    def invoke_agent(self,role,*,input,on_error='raise'):
        envelope=super().invoke_agent(role,input=input,on_error=on_error)
        try:normalized,wrappers=normalize_json_envelope(envelope,role=role)
        except AgentResponseDiagnosticError as error:
            return self._revive(role,input,error.proof_failure_detail)
        if normalized is not envelope and self._bounded is not None:
            self._bounded.record_response_recovery(company_id=input['company_id'],role=role,
                status='grounded_text_json_parsed',wrappers=wrappers)
        return self._normalize_echo(normalized,role,input)
