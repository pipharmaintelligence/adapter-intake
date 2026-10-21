"""Provider-free behavioral qualification: no clinical data, network or authority fabrication."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import threading
import time

import pytest
from fakes import ASSET_ROOT, FakeInputs, CodedFailure, example_inputs
from clinical_failure_intelligence.contracts_v0_1_6 import ContractError, parse_request
from clinical_failure_intelligence.evidence_v0_1_6 import EvidenceLedger
from clinical_failure_intelligence.policies_v0_1_6 import Budget, ExecutionPolicy
from clinical_failure_intelligence.runtime_access_v0_1_6 import AgentRunner
from clinical_failure_intelligence.orchestration_v0_1_6 import run_analysis
from clinical_failure_intelligence.analysis_packets_v0_1_6 import agent_evidence_view, closed_packet, evidence_batches
from clinical_failure_intelligence.review_packets_v0_1_6 import critic_batches


class Inputs(FakeInputs):
    def agent_input_budget(self, role):
        return {"schema_version": "agent_input_budget.v1", "scope": "single_step_initial_request",
            "max_input_json_chars": 160000, "max_input_json_bytes": 262144}


def runner_fixture(limit=20, calls=64, inputs=None):
    inputs = inputs or Inputs()
    request = parse_request(example_inputs())
    budget = Budget(ExecutionPolicy(research_concurrency=limit, max_agent_calls=calls))
    runner = AgentRunner(inputs, budget)
    runner.prepare_input_budgets()
    evidence = EvidenceLedger('CASE_SYN','2025-02-01',example_inputs()['clinical_context']['evidence']).rows()
    def spec(index):
        return {"role": "literature_researcher", "request": request, "task_id": "task:"+str(index),
            "obligations": ["scope"], "packet_data": {"evidence_packet": evidence}}
    return runner, budget, spec


@pytest.mark.parametrize('limit',[1,2,3,20])
def test_run_wide_peak_is_bounded_and_preparation_performs_no_provider_work(limit):
    class Observed(Inputs):
        def __init__(self):
            super().__init__()
            self.active=0; self.peak=0
            self.barrier=threading.Barrier(limit)
        def invoke_agent(self,role,**kwargs):
            with self.lock:
                self.active+=1; self.peak=max(self.peak,self.active)
            try:
                self.barrier.wait(timeout=10)
                return super().invoke_agent(role,**kwargs)
            finally:
                with self.lock:self.active-=1
    inputs=Observed()
    runner,budget,spec=runner_fixture(limit=limit,inputs=inputs)
    specifications=[spec(i) for i in range(limit*2)]
    assert all(runner.prepare(**value) is None for value in specifications)
    assert inputs.calls==[]
    with ThreadPoolExecutor(max_workers=40) as pool:
        results=list(pool.map(lambda value:runner.call(**value),specifications))
    assert inputs.peak==limit and inputs.active==0
    assert all(row.status=='completed' for row in results)
    assert [row.task_id for row in results]==['task:'+str(i) for i in range(limit*2)]
    assert budget.calls==limit*2


def test_budget_reservation_order_is_stable_even_when_completion_order_reverses():
    class Delayed(Inputs):
        def invoke_agent(self,role,**kwargs):
            index=int(kwargs['input']['task_id'].split(':')[1])
            time.sleep((4-index)*.002)
            return super().invoke_agent(role,**kwargs)
    runner,budget,spec=runner_fixture(calls=4,inputs=Delayed())
    planned=[spec(i) for i in range(8)]
    prepared=[runner.prepare(**value) for value in planned]
    assert [value.task_id for value in prepared if value is not None]==['task:4','task:5','task:6','task:7']
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda value:runner.call(**value),planned))
    assert [value.task_id for value in results if value.status=='completed']==['task:0','task:1','task:2','task:3']
    assert budget.calls==4
    cached=runner.call(**planned[0])
    assert cached.cache_hit and budget.calls==4 and len(runner.inputs.calls)==4


def test_recoverable_failure_preserves_completed_independent_siblings_without_retry():
    class OneFailure(Inputs):
        def invoke_agent(self,role,**kwargs):
            if kwargs['input']['task_id']=='task:0':
                raise CodedFailure('agent_execution_provider_retry_exhausted','provider_execution_vertex_unavailable')
            return super().invoke_agent(role,**kwargs)
    runner,budget,spec=runner_fixture(inputs=OneFailure())
    planned=[spec(i) for i in range(20)]
    for value in planned:runner.prepare(**value)
    with ThreadPoolExecutor(max_workers=20) as pool:
        results=list(pool.map(lambda value:runner.call(**value),planned))
    assert Counter(value.status for value in results)=={'failed':1,'completed':19}
    assert results[0].code=='clinical_agent_availability_exhausted'
    assert budget.calls==20 and len(runner.inputs.calls)==19
    with pytest.raises(ContractError,match='clinical_agent_inflight_unresolved'):
        runner.call(**planned[0])
    assert budget.calls==20


def test_two_product_runs_share_external_admission_without_cross_run_budget_or_results():
    admission=threading.BoundedSemaphore(7)  # Simulated Core capacity, not adapter target selection.
    lock=threading.Lock(); state={'active':0,'peak':0}
    class Admitted(Inputs):
        def __init__(self,product):super().__init__();self.product=product
        def invoke_agent(self,role,**kwargs):
            with admission:
                with lock:
                    state['active']+=1;state['peak']=max(state['peak'],state['active'])
                try:
                    time.sleep(.003)
                    response=super().invoke_agent(role,**kwargs)
                    response['result']['metadata']['product_marker']=self.product
                    return response
                finally:
                    with lock:state['active']-=1
    def run(product):
        runner,budget,spec=runner_fixture(inputs=Admitted(product))
        jobs=[spec(i) for i in range(30)]
        for value in jobs:runner.prepare(**value)
        with ThreadPoolExecutor(max_workers=20) as pool:
            result=list(pool.map(lambda value:runner.call(**value),jobs))
        return result,budget.calls,len(runner.inputs.calls)
    with ThreadPoolExecutor(max_workers=2) as pool:
        one,two=list(pool.map(run,['product-one','product-two']))
    assert 1<state['peak']<=7 and state['active']==0
    assert one[1:]==two[1:]==(30,30)
    assert all(row.status=='completed' for row in one[0]+two[0])
    assert {row.semantic_metadata['metadata']['product_marker'] for row in one[0]}=={'product-one'}
    assert {row.semantic_metadata['metadata']['product_marker'] for row in two[0]}=={'product-two'}


def test_only_operational_provenance_is_factored_and_canonical_evidence_stays_exact():
    rows=example_inputs()['clinical_context']['evidence']
    rows[0]['source_context']={'source_result_id':'operation-only','source_result_digest':'sha256:'+'a'*64,
        'source_asset':'producer:1.0.0','acquisition':'retained','evidence_use':'posted_results',
        'source_pointer':'/registry_study/resultsSection/outcomes/0','identifiers':{'trial_id':'TRIAL_SYN'}}
    before=deepcopy(rows)
    view=agent_evidence_view(rows)
    assert rows==before and view[0]['text']==rows[0]['text']
    assert view[0]['source_context']=={k:v for k,v in rows[0]['source_context'].items()
        if k not in {'source_result_id','source_result_digest','source_asset','acquisition'}}
    assert all(view[0][key]==rows[0][key] for key in rows[0] if key!='source_context')


def test_grouped_critic_index_keeps_all_other_ids_types_and_trial_scopes():
    evidence=EvidenceLedger('CASE_SYN','2025-02-01',example_inputs()['clinical_context']['evidence']).rows()
    item={'item_id':'candidate','depends_on':[],'supporting_evidence_ids':['E_TRIAL'],'contradicting_evidence_ids':[]}
    packet=critic_batches([item],evidence,{},200000)[0]
    groups=packet['other_evidence_index']
    assert groups==[{'source_type':'original_research','trial_ids':['TRIAL_SYN'],'evidence_ids':['E_PAPER']}]
    assert packet['evidence_packet'][0]['text']==next(row['text'] for row in evidence if row['evidence_id']=='E_TRIAL')
    assert 'text_digest' in packet['evidence_packet'][0]


def test_new_profile_keeps_model_richness_and_all_previous_versions_immutable():
    frozen=json.loads((ASSET_ROOT/'tests/reference/published_015_frozen.json').read_text())
    manifest=json.loads((ASSET_ROOT/'clinical_failure_intelligence.asset.json').read_text())
    for version,value in frozen['manifest_contracts'].items():assert manifest['versions'][version]==value
    for name,sha in frozen['files'].items():assert hashlib.sha256((ASSET_ROOT/name).read_bytes()).hexdigest()==sha
    old=json.loads((ASSET_ROOT/'admission_requirements_v0_1_5.json').read_text())
    new=json.loads((ASSET_ROOT/'admission_requirements_v0_1_6.json').read_text())
    for before,after in zip(old['agent_contracts'],new['agent_contracts']):
        assert before['request_policy']==after['request_policy']
        assert before['prompt_digest']==after['prompt_digest']
    policy=Budget().policy
    assert policy.research_concurrency==20 and policy.max_agent_calls==64
    assert policy.max_packet_bytes==262144 and policy.stage_allowance_seconds==1200


@pytest.mark.parametrize('value',[0,21,True,'20'])
def test_parallelism_is_bounded_before_paid_work(value):
    inputs=example_inputs();inputs['variables']['agent_parallelism']=value
    with pytest.raises(ContractError,match='clinical_parallelism_invalid'):parse_request(inputs)


def test_small_case_keeps_phase_dependencies_and_never_writes_memory():
    inputs=Inputs()
    result=run_analysis(inputs)['outputs']['clinical_intelligence']
    assert result['asset'].endswith('@0.1.6')
    assert not result['memory_update']['write_attempted']
    plans=result['execution']['phase_plans']
    assert len(plans)==4 and all(row['planned']==row['ready'] for row in plans)
    assert all(row['concurrency_limit']==20 for row in plans)
    roles=[row['role'] for row in result['execution']['stages']]
    assert roles.index('outcome_adjudicator')>max(i for i,role in enumerate(roles) if role.endswith('researcher'))
    assert roles.index('hypothesis_analyst')>roles.index('outcome_adjudicator')
    assert roles.index('evidence_critic')>roles.index('hypothesis_analyst')


def test_prepared_queue_rechecks_deadline_before_provider_dispatch():
    runner, budget, spec = runner_fixture(limit=1)
    state = {"now": 0.0}
    budget.clock = lambda: state["now"]
    budget.started = 0.0
    job = spec(0)
    assert runner.prepare(**job) is None
    assert budget.calls == 1 and runner.inputs.calls == []
    state["now"] = budget.policy.deadline_seconds - budget.policy.completion_reserve_seconds
    stage = runner.call(**job)
    assert stage.status == "deferred" and stage.code == "clinical_completion_reserve_reached"
    assert runner.inputs.calls == [] and budget.calls == 1


def test_reviewed_admission_policy_matches_executed_defaults():
    from dataclasses import asdict
    value = json.loads((ASSET_ROOT/'admission_requirements_v0_1_6.json').read_text(encoding='utf-8'))
    assert value['execution_policy'] == asdict(ExecutionPolicy())
    requirements = value['parallel_execution_requirements']
    assert requirements['shared_capacity_required'] is True
    assert requirements['max_concurrent_product_runs'] == 2
    assert requirements['runtime_agent_max_inflight'] == 20


def test_two_complete_product_adapters_keep_subjects_memory_and_outputs_separate():
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
