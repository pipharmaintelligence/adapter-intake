"""Provider-free quality and robustness regressions from the observed failures."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import hashlib,json,threading,time
import pytest
from fakes import ASSET_ROOT,FakeInputs,CodedFailure,example_inputs
from clinical_failure_intelligence.analysis_packets_v0_1_7 import closed_packet
from clinical_failure_intelligence.case_context_v0_1_7 import case_context_ids
from clinical_failure_intelligence.review_packets_v0_1_7 import critic_batches
from clinical_failure_intelligence.quality_v0_1_7 import enforce_consistency
from clinical_failure_intelligence.runtime_access_v0_1_7 import AgentRunner,response_contract
from clinical_failure_intelligence.policies_v0_1_7 import Budget,ExecutionPolicy,trusted_terminal_json_failure
from clinical_failure_intelligence.contracts_v0_1_7 import parse_request,ContractError
from clinical_failure_intelligence.orchestration_v0_1_7 import run_analysis
try:
    from devtools.runtime_agent_invocation import RuntimeAgentInvocationError
    HAS_INSTALLED_SDK = True
except ImportError:
    # Intake's cross-platform CI has no runtime dependency. The separate E:
    # qualification runs these same cases with the actual SDK exception class.
    HAS_INSTALLED_SDK = False
    class RuntimeAgentInvocationError(RuntimeError):
        def __init__(self,reason,*,failure_code=None,cause_code=None,proof_failure_detail=None):
            super().__init__(reason)
            self.failure_code=failure_code or reason
            self.cause_code=cause_code
            self.proof_failure_detail=proof_failure_detail


@pytest.fixture(autouse=True)
def sdk_type_boundary(monkeypatch):
    if not HAS_INSTALLED_SDK:
        import sys,types
        module=types.ModuleType('devtools.runtime_agent_invocation')
        module.RuntimeAgentInvocationError=RuntimeAgentInvocationError
        monkeypatch.setitem(sys.modules,'devtools.runtime_agent_invocation',module)


PROOF={'schema_version':'proof_failure_detail.v1','proof_kind':'agent_contract','role':'provider','stage':'terminal_content','rule':'agent_result_json_object_invalid','field':'content'}
def failure():return RuntimeAgentInvocationError('Agent invocation failed',failure_code='agent_bridge_invocation_failed',cause_code='provider_execution_vertex_response_invalid',proof_failure_detail=PROOF)


class Inputs(FakeInputs):
    def agent_input_budget(self,role):return {'schema_version':'agent_input_budget.v1','scope':'single_step_initial_request','max_input_json_chars':160000,'max_input_json_bytes':262144}


def evidence():
    base=deepcopy(example_inputs()['clinical_context']['evidence'][0])
    rows=[]
    for key,pointer,value in [
        ('STATUS','/registry_study/protocolSection/statusModule',{'overallStatus':'TERMINATED','whyStopped':'The primary endpoint was not met.'}),
        ('PRIMARY','/registry_study/resultsSection/outcomeMeasuresModule/outcomeMeasures/1',{'type':'PRIMARY','title':'Overall survival'}),
        ('PRIMARY_VALUES','/registry_study/resultsSection/outcomeMeasuresModule/outcomeMeasures/1/measurements/0',{'value':10.6}),
        ('SECONDARY','/registry_study/resultsSection/outcomeMeasuresModule/outcomeMeasures/2',{'type':'SECONDARY','title':'Primary care visits'}),
        ('LOCAL','/registry_study/resultsSection/adverseEventsModule/otherEvents/0',{'event':'Synthetic event'})]:
        row={**deepcopy(base),'evidence_id':key,'text':json.dumps(value),'source_context':{'source_result_id':'SAME_CASE_SOURCE','source_pointer':pointer,'evidence_use':'posted_results','purpose':'case'}}
        rows.append(row)
    return rows


def test_global_status_and_primary_endpoint_follow_each_local_analysis_packet_without_text_loss():
    rows=evidence();before=deepcopy(rows)
    claim={'claim_id':'KNOWN_ENDPOINT','supporting_evidence_ids':['PRIMARY_VALUES'],'contradicting_evidence_ids':[],'statement':'Synthetic primary outcome was not met.'}
    packet=closed_packet([rows[-1]],rows,[claim],{'case_trial_ids':['TRIAL_SYN']})
    by_id={x['evidence_id']:x for x in packet['evidence_packet']}
    assert {'STATUS','PRIMARY','PRIMARY_VALUES','LOCAL'}<=set(by_id)
    assert 'SECONDARY' not in packet['case_context_evidence_ids']
    assert packet['research_claims']==[]
    assert closed_packet([rows[2]],rows,[claim],{'case_trial_ids':['TRIAL_SYN']})['research_claims']==[claim]
    assert all(by_id[x['evidence_id']]['text']==x['text'] for x in rows if x['evidence_id'] in by_id)
    assert rows==before
    other=deepcopy(rows[0]);other['evidence_id']='OTHER_TRIAL';other['trial_ids']=['UNRELATED_TRIAL']
    assert 'OTHER_TRIAL' not in case_context_ids(rows+[other],['TRIAL_SYN'])


def test_critic_unknown_candidate_gets_the_same_global_evidence_and_whole_coverage_contract():
    item={'item_id':'OUTCOME_UNKNOWN','depends_on':[],'supporting_evidence_ids':[],'contradicting_evidence_ids':[]}
    packet=critic_batches([item],evidence(),{'case_trial_ids':['TRIAL_SYN']},200000)[0]
    assert {'STATUS','PRIMARY','PRIMARY_VALUES'}<={x['evidence_id'] for x in packet['evidence_packet']}
    contract=response_contract('evidence_critic',task_id='REVIEW',subject_id='CASE_SYN',obligations=['review:ONE','review:TWO'])
    schema=contract['json_schema']['properties']['items']
    assert schema['minItems']==schema['maxItems']==2
    assert schema['items']['properties']['item_id']['enum']==['ONE','TWO']
    from jsonschema import Draft202012Validator
    validator=Draft202012Validator(schema)
    with pytest.raises(Exception):validator.validate([])
    assert response_contract('evidence_critic',task_id='MEMORY',subject_id='CASE_SYN',obligations=['independent_memory_review'])['json_schema']['properties']['items']['items']=={'type':'object'}


def outcome(key,value):return {'item_id':key,'kind':'outcome','dimension':'primary_endpoint_result','value':value,'trial_ids':['TRIAL_SYN'],'accepted':True,'depends_on':[],'review_reason':None}


def test_reviewed_known_outcome_reconciles_local_unknown_without_deleting_candidates():
    rows=[outcome('LOCAL_UNKNOWN','unknown'),outcome('KNOWN_NOT_MET','not_met')]
    assert enforce_consistency(rows)==[]
    assert len(rows)==2 and rows[1]['accepted'] is True and rows[0]['accepted'] is False
    assert 'KNOWN_NOT_MET' in rows[0]['review_reason']
    contrary=[outcome('MET','met'),outcome('NOT_MET','not_met')]
    assert enforce_consistency(contrary)
    assert not any(x['accepted'] for x in contrary)
    not_estimable=[outcome('NOT_ESTIMABLE','not_evaluable'),outcome('NOT_MET','not_met')]
    assert enforce_consistency(not_estimable)
    separate=[outcome('OTHER_UNKNOWN','unknown'),outcome('KNOWN_NOT_MET','not_met')]
    separate[0]['trial_ids']=['OTHER_TRIAL']
    assert enforce_consistency(separate)==[] and all(x['accepted'] for x in separate)


@pytest.mark.parametrize('limit',[2,10,20])
def test_actual_bounded_parallel_siblings_survive_one_trusted_terminal_json_rejection(limit):
    class Concurrent(Inputs):
        def __init__(self):super().__init__();self.active=0;self.peak=0;self.lock=threading.Lock()
        def invoke_agent(self,role,**kwargs):
            with self.lock:self.active+=1;self.peak=max(self.peak,self.active)
            try:
                time.sleep(.025)
                if kwargs['input']['task_id']=='TASK:0' or kwargs['input'].get('response_recovery'):raise failure()
                return super().invoke_agent(role,**kwargs)
            finally:
                with self.lock:self.active-=1
    from dataclasses import replace
    inputs=Concurrent();budget=Budget(replace(ExecutionPolicy(),research_concurrency=limit));runner=AgentRunner(inputs,budget);runner.prepare_input_budgets()
    request=parse_request(example_inputs())
    specs=[{'role':'trial_researcher','request':request,'task_id':'TASK:'+str(i),'obligations':['clinical_outcome:'+str(i)],'packet_data':{'evidence_packet':[]}} for i in range(limit*2)]
    for spec in specs:runner.prepare(**spec)
    with ThreadPoolExecutor(max_workers=40) as pool:results=list(pool.map(lambda spec:runner.call(**spec),specs))
    assert inputs.peak==limit and inputs.active==0
    assert len([x for x in results if x.status=='completed'])==limit*2-1
    assert results[0].code=='clinical_agent_terminal_json_invalid'
    assert len(results[0].attempts)==2 and budget.repairs==1
    assert runner.call(**specs[0]).cache_hit is True
    assert budget.repairs==1


def test_untrusted_similar_error_or_security_rejection_is_never_suppressed():
    forged=CodedFailure('provider_execution_vertex_response_invalid');forged.proof_failure_detail=PROOF
    assert not trusted_terminal_json_failure(forged)
    altered={**PROOF,'rule':'agent_result_privileged_material_rejected'}
    assert not trusted_terminal_json_failure(RuntimeAgentInvocationError('Agent invocation failed',failure_code='agent_bridge_invocation_failed',cause_code='provider_execution_vertex_response_invalid',proof_failure_detail=altered))
    assert not trusted_terminal_json_failure(RuntimeAgentInvocationError('agent_checkpoint_scope_invalid',cause_code='provider_execution_vertex_response_invalid',proof_failure_detail=PROOF))


def test_one_retry_can_recover_and_never_replays_again_or_broadens_evidence():
    class Once(Inputs):
        def __init__(self):super().__init__();self.invocations=[]
        def invoke_agent(self,role,**kwargs):
            self.invocations.append(deepcopy(kwargs['input']))
            if len(self.invocations)==1:raise failure()
            return super().invoke_agent(role,**kwargs)
    inputs=Once();budget=Budget();runner=AgentRunner(inputs,budget);runner.prepare_input_budgets()
    spec=dict(role='trial_researcher',request=parse_request(example_inputs()),task_id='RESEARCH',obligations=['clinical_outcome:0'],packet_data={'evidence_packet':[]})
    result=runner.call(**spec)
    assert result.status=='completed' and len(result.attempts)==2
    assert budget.calls==2 and budget.repairs==1 and len(inputs.invocations)==2
    first,second=inputs.invocations
    assert second['response_recovery']['failed_task_id']=='RESEARCH'
    assert second['evidence_packet']==first['evidence_packet']
    assert second['assigned_obligation_ids']==first['assigned_obligation_ids']
    assert runner.call(**spec).cache_hit is True and len(inputs.invocations)==2


def test_json_retry_obeys_remaining_call_budget_and_does_not_repeat_security_or_unknown_outcomes():
    from dataclasses import replace
    inputs=Inputs(faults={'trial_researcher':failure()});budget=Budget(replace(ExecutionPolicy(),max_agent_calls=1))
    runner=AgentRunner(inputs,budget);runner.prepare_input_budgets()
    spec=dict(role='trial_researcher',request=parse_request(example_inputs()),task_id='RESEARCH',obligations=['clinical_outcome:0'],packet_data={'evidence_packet':[]})
    result=runner.call(**spec)
    assert result.status=='deferred' and result.code=='clinical_agent_budget_reserved'
    assert len(inputs.calls)==1 and budget.calls==1 and budget.repairs==0 and len(result.attempts)==2
    for cause in ('provider_execution_transport_timeout','provider_execution_capacity_outcome_unknown','provider_execution_vertex_auth_failed'):
        fault=RuntimeAgentInvocationError('Agent invocation failed',failure_code='agent_bridge_invocation_failed',cause_code=cause,proof_failure_detail=PROOF)
        bad=Inputs(faults={'trial_researcher':fault});runner=AgentRunner(bad,Budget());runner.prepare_input_budgets()
        with pytest.raises(ContractError,match='clinical_agent_runtime_blocked'):runner.call(**spec)
        assert len(bad.calls)==1


def test_invalid_business_json_in_typed_text_also_gets_exactly_one_retry():
    class BrokenText(Inputs):
        def __init__(self):super().__init__();self.attempt_count=0
        def invoke_agent(self,role,**kwargs):
            self.attempt_count+=1
            if self.attempt_count==1:
                return {'status':'completed','result':{'schema_version':'agent_result.v1','kind':'text','content':[{'type':'text','text':'{"incomplete":'}]}}
            return super().invoke_agent(role,**kwargs)
    inputs=BrokenText();runner=AgentRunner(inputs,Budget());runner.prepare_input_budgets()
    result=runner.call('trial_researcher',parse_request(example_inputs()),task_id='TEXT',obligations=['clinical_outcome:0'],packet_data={'evidence_packet':[]})
    assert result.status=='completed' and inputs.attempt_count==2 and len(result.attempts)==2


def test_full_workflow_repeated_json_failure_is_partial_and_retains_valid_phases():
    class FailsHypothesis(Inputs):
        def invoke_agent(self,role,**kwargs):
            if role=='hypothesis_analyst':raise failure()
            return super().invoke_agent(role,**kwargs)
    result=run_analysis(FailsHypothesis())['outputs']['clinical_intelligence']
    assert result['quality']['status']=='partial'
    assert result['case_assessments'] and all(x['review_status']=='automated_reviewed' for x in result['case_assessments'])
    failed=[x for x in result['execution']['stages'] if x['role']=='hypothesis_analyst']
    assert failed and len(failed[0]['attempts'])==2
    assert result['execution']['model_repair_calls']==1
    assert result['memory_update']['write_attempted'] is False


def test_complete_small_case_still_uses_every_phase_and_never_writes_memory():
    result=run_analysis(Inputs())['outputs']['clinical_intelligence']
    assert result['asset'].endswith('@0.1.7')
    assert 'study_disposition' in result['decision_summary']['clinical_dimensions']
    assert result['decision_summary']['review_coverage']['unreviewed']==0
    assert result['decision_summary']['causal_priorities']
    assert all(x['causal_certainty_claimed'] is False for x in result['decision_summary']['causal_priorities'])
    assert 'Reconciled case and causal questions' in result['report_markdown']
    assert result['memory_update']['write_attempted'] is False


def test_all_previous_published_bytes_contracts_and_model_policies_stay_exact():
    frozen=json.loads((ASSET_ROOT/'tests/reference/published_016_frozen.json').read_text())
    manifest=json.loads((ASSET_ROOT/'clinical_failure_intelligence.asset.json').read_text())
    for version,value in frozen['manifest_contracts'].items():assert manifest['versions'][version]==value
    for name,sha in frozen['files'].items():assert hashlib.sha256((ASSET_ROOT/name).read_bytes()).hexdigest()==sha
    before=json.loads((ASSET_ROOT/'admission_requirements_v0_1_6.json').read_text())
    after=json.loads((ASSET_ROOT/'admission_requirements_v0_1_7.json').read_text())
    for a,b in zip(before['agent_contracts'],after['agent_contracts']):assert a['request_policy']==b['request_policy']


def test_all_admitted_prompt_digests_match_generated_text_and_structured_variables():
    from clinical_failure_intelligence.prompt_catalog_v0_1_7 import COMMON_PROMPT,PROMPTS,PROMPT_VERSION
    assert PROMPT_VERSION=='1.5.0'
    assert COMMON_PROMPT==(ASSET_ROOT/'prompt_common_v0_1_7.md').read_text(encoding='utf-8')
    requirements=json.loads((ASSET_ROOT/'admission_requirements_v0_1_7.json').read_text())
    for row in requirements['agent_contracts']:
        role=row['role']
        assert PROMPTS[role]==(ASSET_ROOT/row['prompt_file']).read_text(encoding='utf-8')
        expected='sha256:'+hashlib.sha256((COMMON_PROMPT+'\n\n'+PROMPTS[role]).encode('utf-8')).hexdigest()
        assert row['prompt_digest']==expected and row['contract_version']==PROMPT_VERSION
    runner=AgentRunner(Inputs(),Budget())
    packet=runner.packet('hypothesis_analyst',parse_request(example_inputs()),task_id='SAFE_ID',obligations=['seed:SEED_SYN'],packet_data={'evidence_packet':[{'text':'Untrusted {braces} and "quotes" stay data.'}]})
    assert packet['task_context']['product_id']=='PRODUCT_SYN'
    assert packet['response_contract']['json_schema']['properties']['task_id']=={'const':'SAFE_ID'}
    assert packet['evidence_packet'][0]['text']=='Untrusted {braces} and "quotes" stay data.'


def test_two_complete_v017_product_adapters_keep_subjects_memory_and_outputs_separate():
    admission = threading.BoundedSemaphore(2)
    arrivals = threading.Barrier(2)

    def remap(value, suffix):
        if isinstance(value, dict): return {key: remap(item, suffix) for key, item in value.items()}
        if isinstance(value, list): return [remap(item, suffix) for item in value]
        if isinstance(value, str):
            for prefix in ('CASE_', 'PRODUCT_', 'REQUEST_', 'CONTEXT_'):
                value = value.replace(prefix+'SYN', prefix+suffix)
        return value

    class ProductInputs(Inputs):
        def __init__(self, suffix):
            self.suffix = suffix
            super().__init__(remap(example_inputs(), suffix))
            self.first_call = True
        def dynamic_skill(self, role, *, variables):
            assert role == 'product_memory' and variables == {'product_id': 'PRODUCT_'+self.suffix}
            self.memory_calls.append((role, deepcopy(variables)))
            return self.memory
        def role_payload(self, role, packet):
            return remap(super().role_payload(role, packet), self.suffix)
        def invoke_agent(self, role, **kwargs):
            with self.lock:
                first = self.first_call
                self.first_call = False
            if first: arrivals.wait(timeout=10)
            with admission:
                assert kwargs['input']['subject_id'] == 'CASE_'+self.suffix
                assert kwargs['input']['task_context']['product_id'] == 'PRODUCT_'+self.suffix
                return super().invoke_agent(role, **kwargs)

    inputs = [ProductInputs('ONE'), ProductInputs('TWO')]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run_analysis, inputs))
    for suffix, value, source in zip(('ONE','TWO'), results, inputs):
        result = value['outputs']['clinical_intelligence']
        assert result['subject']['product_id'] == 'PRODUCT_'+suffix
        assert all(row['subject_id'] == 'CASE_'+suffix for row in result['evidence'])
        assert result['request_id'] == 'REQUEST_'+suffix
        assert not result['memory_update']['write_attempted']
        assert source.calls and len(source.memory_calls) == 1
