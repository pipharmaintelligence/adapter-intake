"""One source-bound revival when trusted terminal JSON never reaches the adapter."""
from copy import deepcopy
from devtools.runtime_agent_invocation import RuntimeAgentInvocationError
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .invocation_recovery_v0_1_26 import invocation_diagnostic
    from .research_envelope_v0_1_26 import _ResearchContractInputs,RESEARCH_ROLES,MAX_RESPONSE_OBSERVATIONS
    from .agent_response_recovery_v0_1_17 import normalize_json_envelope,AgentResponseDiagnosticError
    from .orchestration_v0_1_26 import FinalBoundedAgentInputs
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy
    from invocation_recovery_v0_1_26 import invocation_diagnostic
    from research_envelope_v0_1_26 import _ResearchContractInputs,RESEARCH_ROLES,MAX_RESPONSE_OBSERVATIONS
    from agent_response_recovery_v0_1_17 import normalize_json_envelope,AgentResponseDiagnosticError
    from orchestration_v0_1_26 import FinalBoundedAgentInputs

ACTIVE_ROLES=RESEARCH_ROLES|{legacy.PLANNER_ROLE,legacy.STRATEGIC_ROLE,legacy.CRITIC_ROLE,legacy.SYNTHESIS_ROLE}
JSON_REQUIREMENTS=('Return exactly one complete JSON object for response_contract. Use double-quoted keys and strings; '
    'escape embedded quotes, newlines and control characters. No prose, Markdown fences, stringified JSON, extra fields, '
    'NaN or Infinity. Keep supported same-company evidence and exact references within all supplied field/item budgets. '
    'Never truncate JSON or invent evidence to satisfy the format.')

class BoundedRecoveryInputs(FinalBoundedAgentInputs):
    def invoke_response_resolver(self,*,original_role,input):
        with self._lock:
            key=(input['company_id'],original_role,self._role_calls.get((input['company_id'],original_role),0))
            spent=key in self._repair_reservations
        if spent:
            raise legacy.UnresolvedAgentResponse(legacy.evidence_diagnostic(role=original_role,
                stage='agent_response_resolver',field='content',rule='backup_exhausted'))
        return super().invoke_response_resolver(original_role=original_role,input=input)

class InvocationRecoveryInputs(_ResearchContractInputs):
    def __init__(self,inputs):
        super().__init__(inputs);self.invocation_issues=[];self._bounded=None
    def bind_recovery(self,bounded):self._bounded=bounded

    def _issue(self,input,role,diagnostic,action):
        with self._lock:
            if len(self.invocation_issues)<MAX_RESPONSE_OBSERVATIONS:
                self.invocation_issues.append({'company_id':input['company_id'],'role':role,'diagnostic':diagnostic,
                    'rejected_text_available':False,'action':action,'backup_attempted':role==legacy.RESEARCH_RESOLVER_ROLE})

    def invoke_agent(self,role,*,input,on_error='raise'):
        forwarded={**input,'json_serialization_requirements':JSON_REQUIREMENTS}
        try:
            envelope=super().invoke_agent(role,input=forwarded,on_error=on_error)
            try:envelope,wrappers=normalize_json_envelope(envelope,role=role)
            except AgentResponseDiagnosticError as error:
                if error.proof_failure_detail['stage']!='agent_response_json':raise
                return self._revive(role,forwarded,error.proof_failure_detail)
            if wrappers and role in ACTIVE_ROLES:
                self._bounded.record_response_recovery(company_id=input['company_id'],role=role,
                    status='json_unwrapped',wrappers=wrappers)
            return self._normalize_echo(envelope,role,input)
        except RuntimeAgentInvocationError as error:
            diagnostic=invocation_diagnostic(error,role=role)
            if diagnostic is None:raise
            return self._revive(role,forwarded,diagnostic)

    def _revive(self,role,input,diagnostic):
        if role==legacy.RESEARCH_RESOLVER_ROLE:
            original=input.get('original_role')
            detail={**diagnostic,'role':original if original in ACTIVE_ROLES else role,'stage':'agent_response_resolver'}
            self._issue(input,role,detail,'backup_unresolved')
            raise legacy.UnresolvedAgentResponse(detail) from None
        if role not in ACTIVE_ROLES or self._bounded is None:raise legacy.UnresolvedAgentResponse(diagnostic)
        self._issue(input,role,diagnostic,'one_source_bound_backup')
        original={key:deepcopy(value) for key,value in input.items()
                  if key not in {'response_contract','json_serialization_requirements'}}
        envelope=self._bounded.invoke_response_resolver(original_role=role,input={
            'company_id':input['company_id'],'failed_contract':diagnostic,
            'repair_scope':'unavailable_business_json_from_sources',
            'original_section_input':original,'response_contract':deepcopy(input['response_contract']),
            'recovery_instruction':'The original business JSON is unavailable. Produce one bounded replacement from only '
                'the original supplied section inputs and source chunks. No web reads, tools, new facts, stronger verdicts '
                'or mutation authority. Never claim that unavailable text was preserved. Original validators, exact-span '
                'checks and section critics must still validate the replacement. This is the only fallback attempt.'})
        self._bounded.record_response_recovery(company_id=input['company_id'],role=role,
            status='source_backup_returned_pending_validation',diagnostic=diagnostic)
        return self._normalize_echo(envelope,role,input)

    def _normalize_echo(self,envelope,role,input):
        # Normalize semantically identical model echoes only. Never substitute a different company or role.
        if role not in ACTIVE_ROLES or not isinstance(envelope,dict) or envelope.get('status')!='completed':return envelope
        result=envelope.get('result');content=result.get('content') if isinstance(result,dict) else None
        if not isinstance(content,list) or len(content)!=1 or not isinstance(content[0],dict):return envelope
        value=content[0].get('value')
        if not isinstance(value,dict):return envelope
        normalized=deepcopy(value);changed=[]
        cid=value.get('company_id')
        if isinstance(cid,str) and cid.strip()==str(input['company_id']):
            normalized['company_id']=input['company_id'];changed.append('company_id')
        echo=value.get('role')
        if isinstance(echo,str) and echo.strip().lower()==role and echo!=role:
            normalized['role']=role;changed.append('role')
        status=value.get('status')
        if isinstance(status,str) and status.strip().lower()=='completed' and status!='completed':
            normalized['status']='completed';changed.append('status')
        if not changed:return envelope
        self._bounded.record_response_recovery(company_id=input['company_id'],role=role,status='deterministic_echo_normalization')
        return {**envelope,'result':{**result,'content':[{**content[0],'value':normalized}]}}
