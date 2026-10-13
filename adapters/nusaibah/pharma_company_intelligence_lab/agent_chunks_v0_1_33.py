"""Finite, provider-neutral measurement and paragraph/subsection scheduling.

This helper owns no provider, storage, lake, query or mutation authority.
"""
from copy import deepcopy
from hashlib import sha256
import json,re,time
from threading import Lock,BoundedSemaphore
from concurrent.futures import ThreadPoolExecutor
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .research_envelope_v0_1_26 import complete_research_contract,RESEARCH_ROLES
    from .invocation_recovery_v0_1_30 import JSON_REQUIREMENTS
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy
    from research_envelope_v0_1_26 import complete_research_contract,RESEARCH_ROLES
    from invocation_recovery_v0_1_30 import JSON_REQUIREMENTS

def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def fingerprint(value):return sha256(canonical(value).encode()).hexdigest()
def unique(values):
    result=[];seen=set()
    for value in values:
        key=canonical(value)
        if key not in seen:seen.add(key);result.append(value)
    return result

def paragraph_units(text):
    """Exact original spans: headings stay with their subsection/paragraph.

    Never split characters, trim source text, or break a paragraph to fit.
    """
    if not isinstance(text,str):raise TypeError('source_text_must_be_string')
    starts=[0]
    for match in re.finditer(r'\n[ \t]*\n+',text):starts.append(match.end())
    for match in re.finditer(r'(?m)^#{1,6}[ \t]+\S',text):starts.append(match.start())
    starts=sorted(set(starts));result=[];heading=None
    for index,start in enumerate(starts):
        end=starts[index+1] if index+1<len(starts) else len(text)
        value=text[start:end]
        if not value.strip():continue
        found=re.match(r'[ \t]*(#{1,6})[ \t]+([^\n]+)',value)
        if found:heading=found.group(2).strip()
        result.append({'text':value,'source_start':start,'source_end':end,
                       'subsection':heading,'unit_id':'paragraph:'+fingerprint([start,end,value])})
    return result

def optimize_input(role,payload):
    """Remove redundant copies, never alter accepted facts or qualifications."""
    value={k:deepcopy(v) for k,v in payload.items() if not k.startswith('_piece_')}
    if value.get('scoped_planner_requirements')==value.get('planner_requirements'):
        value.pop('scoped_planner_requirements',None)
    if isinstance(value.get('research_evidence'),dict):
        evidence=value['research_evidence']
        for field in ('citation_sources','uncertainties'):
            if isinstance(evidence.get(field),list):evidence[field]=unique(evidence[field])
        # Withheld evidence cannot be a synthesis/analysis source. Its issues
        # remain in the run result, not duplicated in a model context.
        if role in {legacy.STRATEGIC_ROLE,legacy.SYNTHESIS_ROLE}:
            evidence.pop('withheld_claims',None)
    if role==legacy.SYNTHESIS_ROLE and isinstance(value.get('critic_findings'),dict):
        critic=value['critic_findings']
        # Preserve every verdict/ID/disposition. Repeated free-text notes are
        # not additional research evidence or candidate authority.
        for field in ('unmet_plan_requirements','section_outcomes'):
            if isinstance(critic.get(field),list):
                critic[field]=[{k:v for k,v in row.items() if k not in {'notes','evidence_notes'}}
                               for row in critic[field]]
    return value

def prepared_payload(role,payload):
    value=optimize_input(role,payload)
    if (role in RESEARCH_ROLES or (role==legacy.RESEARCH_RESOLVER_ROLE
        and value.get('original_role') in RESEARCH_ROLES)) and isinstance(value.get('response_contract'),dict):
        value['response_contract']=complete_research_contract(value['response_contract'])
    value['json_serialization_requirements']=JSON_REQUIREMENTS
    return value

class ChunkCoordinator:
    def __init__(self,*,parallelism=2,input_chars=42000,max_calls=48,seconds=1650,
                 prompt_chars=None,clock=time.monotonic):
        if type(parallelism) is not int or not 1<=parallelism<=3:raise ValueError('agent_parallelism_must_be_1_to_3')
        if type(input_chars) is not int or not 8000<=input_chars<=42000:raise ValueError('agent_input_limit_invalid')
        if type(max_calls) is not int or not 13<=max_calls<=48:raise ValueError('agent_chunk_call_limit_invalid')
        self.parallelism=parallelism;self.input_chars=input_chars;self.max_calls=max_calls
        self.clock=clock;self.deadline=clock()+seconds;self.prompt_chars=prompt_chars or {}
        self.semaphore=BoundedSemaphore(parallelism);self.lock=Lock();self.calls=0
        self.active=0;self.peak=0;self.measurements=[];self.coverage=[];self.outcomes=[]
        # Research cannot consume the budget reserved for validation/synthesis.
        # Limits include a role's originals and its source-bound backups.
        self.role_budgets={legacy.PLANNER_ROLE:8,**{r:6 for r in legacy.RESEARCH_ROLES},
            legacy.STRATEGIC_ROLE:6,legacy.CRITIC_ROLE:10,legacy.SYNTHESIS_ROLE:6}
        self.role_dispatches={}
    def measure(self,role,payload):
        encoded=canonical(prepared_payload(role,payload))
        return {'role':role,'input_chars':len(encoded),'input_bytes':len(encoded.encode()),
                'provider_prompt_bound_chars':len(encoded)+self.prompt_chars.get(role,8192)+2048,
                'within_input_budget':len(encoded)<=self.input_chars and len(encoded)+self.prompt_chars.get(role,8192)+2048<=64000}
    def require_fit(self,role,payload,*,record=False):
        measured=self.measure(role,payload)
        if record:
            with self.lock:self.measurements.append({**measured,'company_id':payload['company_id'],
                'chunk_id':payload.get('chunk_execution',{}).get('chunk_id'),
                'phase':'backup' if role==legacy.RESEARCH_RESOLVER_ROLE else 'original'})
        if not measured['within_input_budget']:
            raise legacy.UnresolvedAgentResponse(legacy.evidence_diagnostic(
                role=payload.get('original_role',role),stage='input_preflight',field='input',
                rule='backup_input_budget_exceeded' if role==legacy.RESEARCH_RESOLVER_ROLE else 'agent_input_budget_exceeded'))
        return measured
    def partition(self,role,base,units,attach):
        """Greedy subsection/paragraph packets, retaining every unfit atom."""
        packets=[];pending=[];omitted=[]
        def packet(rows,ordinal):
            value=attach(deepcopy(base),deepcopy(rows))
            private={k:v for k,v in value.items() if k.startswith('_piece_')}
            value['chunk_execution']={'chunk_id':'work:'+fingerprint([role,base['company_id'],ordinal,rows]),
                'chunk_index':ordinal,'scope':'supplied_paragraphs_or_subsection',
                'one_targeted_pass':True,'global_negative_inference_allowed':False}
            result=optimize_input(role,value);result.update(private);return result
        prior_scope=None
        for unit in units:
            scope=(unit.get('section_id'),unit.get('locator'),unit.get('subsection') or unit.get('unit_id'))
            if pending and scope!=prior_scope:
                packets.append(packet(pending,len(packets)+1));pending=[]
            prior_scope=scope
            candidate=packet([*pending,unit],len(packets)+1)
            if self.measure(role,candidate)['within_input_budget']:
                pending.append(unit);continue
            if pending:packets.append(packet(pending,len(packets)+1));pending=[]
            alone=packet([unit],len(packets)+1)
            if self.measure(role,alone)['within_input_budget']:pending=[unit]
            else:omitted.append({'unit_digest':fingerprint(unit),'reason':'indivisible_paragraph_or_subsection_exceeds_budget'})
        if pending:packets.append(packet(pending,len(packets)+1))
        with self.lock:self.coverage.append({'role':role,'company_id':base['company_id'],
            'unit_count':len(units),'chunk_count':len(packets),'unfit_units':omitted,
            'complete':not omitted})
        return packets,omitted
    def parallel(self,items,fn):
        admitted=items[:48]
        deferred=items[48:]
        def work(item):
            try:return {'status':'completed','value':fn(item)}
            except legacy.UnresolvedAgentResponse as error:return {'status':'unresolved','diagnostic':error.diagnostic}
            except legacy.AgentContractValidationError as error:
                if error.code not in {'pharma_agent_business_schema_invalid','pharma_agent_status_invalid',
                    'pharma_agent_company_id_invalid','pharma_agent_role_invalid'}:raise
                return {'status':'unresolved','diagnostic':legacy.safe_diagnostic(error,role='orchestration')}
        with ThreadPoolExecutor(max_workers=self.parallelism,thread_name_prefix='pharma-paragraph') as pool:
            results=list(pool.map(work,admitted))  # deterministic plan order, not completion order
        results.extend({'status':'unresolved','diagnostic':legacy.evidence_diagnostic(
            role='orchestration',stage='chunk_plan',field='chunks',rule='chunk_count_budget_exceeded')} for _ in deferred)
        with self.lock:
            self.outcomes.extend({'chunk_id':item.get('chunk_execution',{}).get('chunk_id') if isinstance(item,dict) else str(item),
                'status':result['status'],'diagnostic':result.get('diagnostic')} for item,result in zip(items,results))
        return results
    def dispatch(self,role,payload,call):
        self.require_fit(role,payload,record=True)
        remaining=self.deadline-self.clock()
        # The full 600-second thinking allowance and 180-second consolidation /
        # publication reserve must fit before a call starts. Never clamp output.
        if remaining<780 or not self.semaphore.acquire(timeout=max(0,remaining-780)):
            raise legacy.UnresolvedAgentResponse(legacy.evidence_diagnostic(role=payload.get('original_role',role),
                stage='chunk_admission',field='remaining_seconds',rule='execution_budget_reserved_for_consolidation'))
        try:
            if self.deadline-self.clock()<780:
                raise legacy.UnresolvedAgentResponse(legacy.evidence_diagnostic(role=payload.get('original_role',role),
                    stage='chunk_admission',field='remaining_seconds',rule='execution_budget_reserved_for_consolidation'))
            with self.lock:
                if self.calls>=self.max_calls:
                    raise legacy.UnresolvedAgentResponse(legacy.evidence_diagnostic(role=payload.get('original_role',role),
                        stage='chunk_admission',field='calls',rule='chunk_call_budget_exhausted'))
                owner=payload.get('original_role',role) if role==legacy.RESEARCH_RESOLVER_ROLE else role
                count=self.role_dispatches.get(owner,0)
                if count>=self.role_budgets.get(owner,0):
                    raise legacy.UnresolvedAgentResponse(legacy.evidence_diagnostic(role=owner,
                        stage='chunk_admission',field='calls',rule='phase_call_budget_reserved_for_downstream'))
                self.role_dispatches[owner]=count+1
                self.calls+=1;self.active+=1;self.peak=max(self.peak,self.active)
            try:return call()
            finally:
                with self.lock:self.active-=1
        finally:self.semaphore.release()
    def proof(self):
        with self.lock:return {'schema_version':'pharma_agent_input_preflight.v1','max_parallel_calls':self.parallelism,
            'observed_peak_parallel_calls':self.peak,'provider_dispatch_count':self.calls,'role_call_budgets':dict(self.role_budgets),
            'role_dispatch_counts':dict(self.role_dispatches),
            'measurements':deepcopy(self.measurements),'coverage':deepcopy(self.coverage),'outcomes':deepcopy(self.outcomes)}

class MeasuredDispatchInputs(dict):
    def __init__(self,inputs,coordinator):super().__init__(inputs);self._inputs=inputs;self.coordinator=coordinator
    def __getattr__(self,name):return getattr(self._inputs,name)
    def invoke_agent(self,role,*,input,on_error='raise'):
        forwarded=prepared_payload(role,input)
        return self.coordinator.dispatch(role,forwarded,lambda:self._inputs.invoke_agent(role,input=forwarded,on_error=on_error))
