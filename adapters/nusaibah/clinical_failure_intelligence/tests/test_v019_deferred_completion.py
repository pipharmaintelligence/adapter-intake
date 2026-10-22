"""Provider-free structural regressions; no scientific acceptance claim."""
from copy import deepcopy
import pytest
from jsonschema import Draft202012Validator
from fakes import example_inputs
from test_v018_completion import Inputs
from clinical_failure_intelligence.orchestration_v0_1_9 import run_analysis
from clinical_failure_intelligence.review_packets_v0_1_9 import isolate_dependencies,scoped_review,critic_batches
from clinical_failure_intelligence.runtime_access_v0_1_9 import AgentRunner
from clinical_failure_intelligence.policies_v0_1_9 import Budget,ExecutionPolicy
from clinical_failure_intelligence.contracts_v0_1_9 import parse_request,canonical_bytes,ContractError,digest
from clinical_failure_intelligence.evidence_v0_1_9 import EvidenceLedger
from clinical_failure_intelligence.deferred_work_v0_1_9 import hydrate_task
from clinical_failure_intelligence.review_references_v0_1_9 import expand_review


def base():
    return run_analysis(Inputs())['outputs']['clinical_intelligence']


def verdict(row):
    return {'item_id':row['item_id'],'verdict':'accepted','rationale':'Synthetic structural review.',
        'scope_preserved':True,'supporting_evidence_ids':row['supporting_evidence_ids'],
        'contradicting_evidence_ids':row['contradicting_evidence_ids']}


def test_small_case_and_exact_original_prompt_policy():
    value=base()
    assert value['asset'].endswith('@0.1.9')
    assert value['quality']['status']=='completed',value['quality']['issues']
    assert value['deferred_work']['tasks']==[]
    assert value['execution']['execution_limits']['analysis_deadline_seconds']==3600
    assert value['publication_readiness']['status']=='not_requested'
    assert value['persistence']['status']=='not_attested'


def test_97_candidates_missing_cycle_and_dependants_do_not_discard_independent_reviews():
    value=base();rows=[]
    for i in range(97):
        row=deepcopy((value['case_assessments'] if i<40 else value['hypothesis_results'])[0])
        row.update(item_id='C'+str(i),depends_on=[],accepted=False,review_status='unreviewed')
        rows.append(row)
    for i in range(4):rows[i]['depends_on']=['MISSING']
    rows[4]['depends_on']=['C0'];rows[5]['depends_on']=['C6'];rows[6]['depends_on']=['C5'];rows[7]['depends_on']=['C6']
    original=deepcopy(rows)
    valid,blocked,issues=isolate_dependencies(rows)
    assert len(valid)==89 and len(blocked)==8 and rows==original
    ledger=EvidenceLedger('CASE_SYN','2026-10-15',example_inputs()['clinical_context']['evidence'])
    reviewed,errors=scoped_review(rows,[verdict(row) for row in rows],ledger)
    assert len(reviewed)==97
    assert all(row['accepted'] and row['review_status']=='automated_reviewed' for row in reviewed[8:])
    assert all(not row['accepted'] and row['review_status']=='unreviewed' for row in reviewed[:8])
    assert reviewed[0]['unresolved_dependency_ids']==['MISSING']
    assert reviewed[0]['depends_on']==[]
    assert {row['code'] for row in issues}=={'clinical_dependency_unknown','clinical_dependency_cycle','clinical_dependency_unresolved'}


def test_critic_aliases_are_exact_and_schema_still_rejects_cross_item_polarity():
    runner=AgentRunner(Inputs(),Budget());runner.prepare_input_budgets()
    request=parse_request(example_inputs())
    data={'candidate_items':[{'item_id':'C1','depends_on':[], 'supporting_evidence_ids':['LONG_A'],'contradicting_evidence_ids':[]},
        {'item_id':'C2','depends_on':[],'supporting_evidence_ids':['LONG_B'],'contradicting_evidence_ids':['LONG_C']}],
        'evidence_packet':[{'evidence_id':'LONG_'+key,'text':'Literal text E1 and I1 are not rewritten.'} for key in 'ABC']}
    packet=runner.packet('evidence_critic',request,task_id='R',obligations=['review:C1','review:C2'],packet_data=data)
    assert packet['evidence_packet'][0]['text']==data['evidence_packet'][0]['text']
    validator=Draft202012Validator(packet['response_contract']['json_schema']['properties']['items'])
    good=[verdict(row) for row in packet['candidate_items']];validator.validate(good)
    bad=deepcopy(good);bad[0]['supporting_evidence_ids']=good[1]['supporting_evidence_ids']
    assert list(validator.iter_errors(bad))
    bad=deepcopy(good);bad[0]['contradicting_evidence_ids']=good[0]['supporting_evidence_ids']
    assert list(validator.iter_errors(bad))
    payload={'items':good,'coverage':[{'obligation_id':x,'status':'completed'} for x in packet['assigned_obligation_ids']], 'followup_requests':[]}
    restored=expand_review(payload,packet)
    assert restored['items']==[verdict(row) for row in data['candidate_items']]
    payload['items'][0]['supporting_evidence_ids']=['E9999']
    with pytest.raises(ContractError,match='clinical_review_alias_unknown'):expand_review(payload,packet)


def test_missing_candidate_is_quarantined_before_paid_critic_and_partial_artifact_is_prepared():
    class Broken(Inputs):
        def role_payload(self,role,packet):
            value=super().role_payload(role,packet)
            if role=='hypothesis_analyst':value['items'][0]['depends_on']=['MISSING']
            return value
    data=example_inputs();data['variables']['prepare_result_for_persistence']=True
    inputs=Broken(data);outputs=run_analysis(inputs)['outputs'];result=outputs['clinical_intelligence']
    assert result['quality']['status']=='partial'
    assert all(not packet.get('candidate_items') or all(row['kind']!='hypothesis' for row in packet['candidate_items'])
        for role,packet in inputs.calls if role=='evidence_critic')
    assert any(row['accepted'] for row in result['case_assessments'])
    assert result['hypothesis_results'][0]['accepted'] is False
    assert result['deferred_work']['tasks'] and result['deferred_work']['automatic_replay'] is False
    assert outputs['clinical_intelligence_records']=={'records':[result]}
    assert result['publication_readiness']['publication_confirmed'] is False
    assert result['memory_update']['write_attempted'] is False


def test_low_call_budget_saves_exact_deferred_inputs_without_replaying_paid_siblings():
    data=example_inputs();data['variables'].update(max_agent_calls=5,enable_refinement=False)
    inputs=Inputs(data);result=run_analysis(inputs)['outputs']['clinical_intelligence']
    deferred=result['deferred_work'];tasks=[row for row in deferred['tasks'] if row.get('input_packet')]
    assert tasks and len(inputs.calls)<=5 and result['quality']['status']=='partial'
    for task in tasks:
        packet=hydrate_task(task,deferred,result['evidence'])
        assert digest(packet)==task['input_digest']
        assert task['retry_authorized'] is False
    assert result['evidence']
    # Tampering is rejected before any future invocation is even considered.
    task=next((x for x in tasks if x['input_packet'].get('evidence_packet')),None)
    assert task
    changed=deepcopy(result['evidence']);changed[0]['text']+=' Changed.'
    with pytest.raises(ContractError):hydrate_task(task,deferred,changed)


@pytest.mark.parametrize('field,value', [('max_agent_calls',65),('max_agent_calls',True),('max_product_seconds',1500),('max_product_seconds',48301)])
def test_invalid_or_escalating_budget_controls_fail_closed(field,value):
    data=example_inputs();data['variables'][field]=value
    with pytest.raises(ContractError):parse_request(data)


def test_semantic_unresolved_is_durable_and_not_misreported_as_runtime_failure():
    def unresolved(value,packet):
        value['coverage'][0]['status']='unresolved';return value
    inputs=Inputs(transforms={'event_researcher':unresolved})
    result=run_analysis(inputs)['outputs']['clinical_intelligence']
    assert result['execution']['disposition']['scientifically_unresolved_tasks']==1
    assert any(row['kind']=='scientific_gap' and row['requires_new_evidence'] for row in result['deferred_work']['tasks'])
    assert result['quality']['required_roles_completed']['event_researcher'] is False


def test_published_dto_schema_accepts_new_result_and_preserves_nested_guards():
    from fakes import ASSET_ROOT
    import json
    schema=json.loads((ASSET_ROOT/'clinical_intelligence_v0_1_9.schema.json').read_text())
    Draft202012Validator.check_schema(schema)
    validator=Draft202012Validator(schema)
    result=base();validator.validate(result)
    bad=deepcopy(result);bad['publication_readiness']['publication_confirmed']=True
    assert list(validator.iter_errors(bad))
    bad=deepcopy(result);bad['hypothesis_results'][0].update(verdict='supported',accepted=False)
    assert list(validator.iter_errors(bad))


def test_out_of_packet_candidate_is_retained_for_later_without_becoming_evidence():
    def forged(value,packet):
        value['items'][0]['supporting_evidence_ids']=['NOT_SUPPLIED'];return value
    result=run_analysis(Inputs(transforms={'hypothesis_analyst':forged}))['outputs']['clinical_intelligence']
    tasks=[row for row in result['deferred_work']['tasks'] if row['kind']=='candidate_reconciliation']
    assert tasks and all(row['retry_authorized'] is False for row in tasks)
    candidate=result['deferred_work']['objects'][tasks[0]['candidate_ref']]
    assert candidate['supporting_evidence_ids']==['NOT_SUPPLIED']
    assert not result['hypothesis_results']


def test_completion_reserve_defers_without_dispatch_or_futile_reconciler():
    clock=[0.0];budget=Budget(clock=lambda:clock[0]);inputs=Inputs();runner=AgentRunner(inputs,budget);runner.prepare_input_budgets()
    clock[0]=budget.policy.deadline_seconds-1499
    stage=runner.call('trial_researcher',parse_request(example_inputs()),task_id='LATE',obligations=['clinical_outcome:0'],packet_data={'evidence_packet':[]})
    assert stage.code=='clinical_completion_reserve_reached' and inputs.calls==[]
    assert budget.business_repairs==0


def test_exact_jsonl_self_inspection_checks_core_schema_hash_and_nested_rules(tmp_path):
    from fakes import ASSET_ROOT
    from clinical_failure_intelligence.output_inspection_v0_1_9 import inspect_staged_payload
    import json,hashlib
    schema=json.loads((ASSET_ROOT/'clinical_intelligence_v0_1_9.schema.json').read_text())
    document={'metadata':{'version':'1.1.0'},'results':{'schema_type':'json_schema','format':'jsonl','contract':schema}}
    checksum=hashlib.sha256((json.dumps(document,ensure_ascii=False,indent=2,separators=(',',': '))+'\n').encode()).hexdigest()
    contract={'pointer':{'node_key':'results','schema_version':'1.1.0','schema_sha256':checksum},'schema':document}
    record=base();path=tmp_path/'result.jsonl';path.write_text(json.dumps(record)+'\n',encoding='utf-8')
    report=inspect_staged_payload(path,contract)
    assert report['status']=='passed' and report['records_inspected']==1 and report['records_failed']==0
    assert report['payload_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    bad=deepcopy(record);bad['hypothesis_results'][0].update(verdict='supported',accepted=False)
    path.write_text(json.dumps(bad)+'\n',encoding='utf-8')
    failed=inspect_staged_payload(path,contract)
    assert failed['status']=='failed' and failed['records_failed']==1
    assert all('instance' not in row and 'message' not in row for row in failed['errors'])
    corrupt=deepcopy(contract);corrupt['pointer']['schema_sha256']='0'*64
    assert inspect_staged_payload(path,corrupt)['status']=='failed'
    path.write_text('',encoding='utf-8')
    assert inspect_staged_payload(path,contract)['status']=='failed'


@pytest.mark.parametrize('reserved,downstream,expected',[(2,4,2),(0,2,2)])
def test_critic_recovery_consumes_only_its_own_reserved_calls(monkeypatch,reserved,downstream,expected):
    from clinical_failure_intelligence import input_reconciliation_v0_1_9 as recovery
    observed=[]
    def recover(runner,request,stage,**kwargs):
        observed.append(kwargs['downstream_reserve']);return stage
    monkeypatch.setattr(recovery,'recover_partition',recover)
    runner=AgentRunner(Inputs(),Budget());runner.prepare_input_budgets()
    data={'candidate_items':[{'item_id':'C1','depends_on':[],'supporting_evidence_ids':['E1'],'contradicting_evidence_ids':[]}],
        'evidence_packet':[{'evidence_id':'E1','text':'Whole source. '*20000}],
        'review_recovery_reserved_calls':reserved}
    stage=runner.call('evidence_critic',parse_request(example_inputs()),task_id='OVERSIZE',obligations=['review:C1'],packet_data=data,downstream_reserve=downstream)
    assert stage.code=='clinical_packet_requires_partitioning' and observed==[expected]


def test_461_window_pipeline_retains_all_sources_and_runs_bounded_019_review():
    from test_source_bundle import case_inputs,bundle,entry,trial_result
    class Large(Inputs):
        def role_payload(self,role,packet):
            value=super().role_payload(role,packet)
            if role.endswith('researcher'):value['items']=[]
            elif role=='outcome_adjudicator':
                for item in value['items']:
                    item['supporting_evidence_ids']=[packet['evidence_packet'][0]['evidence_id']]
                    item['trial_ids']=['NCT00000001']
            elif role=='hypothesis_analyst':
                value['items'][0]['supporting_evidence_ids']=[packet['evidence_packet'][0]['evidence_id']]
                value['items'][0]['depends_on']=[packet['case_assessments'][0]['item_id']]
            return value
    data=case_inputs();data['clinical_context']['evidence']=[]
    trial=trial_result();trial['records'][0]['registry_study']['resultsSection']['outcomeMeasuresModule']['outcomeMeasures']=[
        {'sequence':index,'observation':'Whole synthetic source window. '*25} for index in range(455)]
    data['clinical_evidence']=bundle(entry(trial));inputs=Large(data)
    value=run_analysis(inputs)['outputs']['clinical_intelligence']
    assert value['asset'].endswith('@0.1.9') and len(value['evidence'])==461
    assert value['execution']['logical_agent_calls']<=64
    assert all(value['quality']['required_roles_completed'].values())
    assert not any(row.get('code')=='clinical_packet_requires_partitioning' for row in value['execution']['stages'])
    assert value['memory_update']['write_attempted'] is False
    assert all(len(canonical_bytes(packet))<=262144 and len(canonical_bytes(packet).decode())<=160000 for role,packet in inputs.calls)
