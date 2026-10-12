"""Preserve the complete research envelope across the same one-shot fallback."""
try:
    from .invocation_recovery_v0_1_30 import InvocationRecoveryInputs as _Base,BoundedRecoveryInputs
    from .research_envelope_v0_1_26 import complete_research_contract,RESEARCH_ROLES
except ImportError:
    from invocation_recovery_v0_1_30 import InvocationRecoveryInputs as _Base,BoundedRecoveryInputs
    from research_envelope_v0_1_26 import complete_research_contract,RESEARCH_ROLES

class InvocationRecoveryInputs(_Base):
    def invoke_agent(self,role,*,input,on_error='raise'):
        research=(role in RESEARCH_ROLES or (role=='research_response_resolver'
            and input.get('original_role') in RESEARCH_ROLES
            and input.get('repair_scope')=='unavailable_business_json_from_sources'))
        if research and isinstance(input.get('response_contract'),dict):
            input={**input,'response_contract':complete_research_contract(input['response_contract'])}
        return super().invoke_agent(role,input=input,on_error=on_error)
