"""Provider-free product selection, complete review and version-isolation checks."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import threading
import time
import uuid
import pytest
from jsonschema import Draft202012Validator
from fakes import example_inputs, ASSET_ROOT
from test_v018_completion import Inputs
from test_source_events import event, envelope
from clinical_failure_intelligence.product_range_v0_1_10 import plan_products, scoped_inputs, range_selection
from clinical_failure_intelligence.range_workflow_v0_1_10 import ProductRangeWorkflow
from clinical_failure_intelligence.contracts_v0_1_10 import ContractError, digest, parse_request
from clinical_failure_intelligence.orchestration_v0_1_10 import run_analysis
from clinical_failure_intelligence.runtime_access_v0_1_10 import AgentRunner
from clinical_failure_intelligence.policies_v0_1_10 import Budget
from clinical_failure_intelligence.review_packets_v0_1_10 import critic_batches, scoped_review
from clinical_failure_intelligence.quality_v0_1_10 import review_items
from clinical_failure_intelligence.evidence_v0_1_10 import EvidenceLedger
from clinical_failure_intelligence.product_memory_v0_1_10 import validate_edit_candidates


def selected(value='0:1'):
    rows=[event(str(i),products=[{'product_id':'P'+str(i),'product_name':'Synthetic '+str(i)}]) for i in range(4)]
    rows.insert(1,event('again',products=[{'product_id':'P0','product_name':'Synthetic 0'}]))
    return {'variables':{'schema_version':'clinical_analysis_request.v1','request_id':'RANGE_SYN',
        'analysis_mode':'mechanistic_case','as_of_date':'2025-01-01','product_index_range':value,'preflight_only':True},
        'clinical_context':envelope(*rows)}


@pytest.mark.parametrize('value,expected',[('0:1',['P0','P1']),('2:3',['P2','P3']),('3:3',['P3'])])
def test_zero_based_inclusive_unique_product_order(value,expected):
    plan=plan_products(selected(value));receipt=plan['selection_receipt']
    assert receipt['selected_product_ids']==expected
    assert receipt['total_distinct_products']==4
    assert receipt['source_record_count']==5
    assert receipt['selected_product_count']==len(expected)
    assert plan['agent_calls']==0 and plan['workflow_concurrency']==2
    if value=='0:1':assert plan['cases'][0]['event_ids']==['0','again']


@pytest.mark.parametrize('value',['-1:1','1:0','0:9','0','00:1','0:01','0: 1',' 0:1','0:1:2',True,None,0])
def test_invalid_ranges_rejected_without_dispatch(value):
    with pytest.raises(ContractError):plan_products(selected(value))


def test_snapshot_and_order_pinned_and_exact_case_revalidated():
    data=selected();plan=plan_products(data)
    case=plan['cases'][0]
    values=deepcopy(case['variables'])
    scoped,receipt=scoped_inputs({'variables':values,'clinical_context':data['clinical_context']})
    assert 'product_index_range' not in scoped['variables']
    assert receipt['executed_product_id']=='P0'
    changed=deepcopy(data['clinical_context']);changed['provenance']['sha256']='b'*64
    with pytest.raises(ContractError,match='snapshot_changed'):
        scoped_inputs({'variables':values,'clinical_context':changed})
    values['product_id']='P1'
    with pytest.raises(ContractError,match='case_mismatch'):
        scoped_inputs({'variables':values,'clinical_context':data['clinical_context']})


def test_ambiguous_event_retains_product_index_without_cartesian_join():
    data=selected();row=data['clinical_context']['records'][2]
    row['indications'].append({'designation_id':'ANOTHER','designation_label':'Another indication'})
    plan=plan_products(data)
    assert plan['selection_receipt']['selected_product_ids']==['P0','P1']
    assert plan['status']=='needs_attention'
    assert plan['blocked_cases']==[{'product_index':1,'product_id':'P1','event_id':'1','reason_code':'clinical_source_selector_ambiguous'}]
    assert all(row['product_id']=='P0' for row in plan['cases'])


def test_range_planner_rejects_hidden_single_case_and_source_overrides():
    data=selected();data['variables']['product_id']='P0'
    with pytest.raises(ContractError,match='selector_conflict'):range_selection(data)
    data=selected();data['clinical_evidence']={}
    with pytest.raises(ContractError,match='source_scope_conflict'):range_selection(data)
    data=selected();data['variables']['preflight_only']=False
    with pytest.raises(ContractError,match='requires_preflight_plan'):range_selection(data)


def test_range_preflight_and_old_single_case_unchanged():
    response=range_selection(selected())
    assert response['metrics']['logical_agent_calls']==0
    value=run_analysis(Inputs())['outputs']['clinical_intelligence']
    assert value['asset'].endswith('@0.1.10')
    assert value['quality']['status']=='completed',value['quality']['issues']
    assert value['memory_update']['write_attempted'] is False


def test_two_product_workflows_maximum_and_separate_checkpoint_hosts():
    data=selected();variables=data['variables'];lock=threading.Lock();active=0;peak=0;hosts=[]
    def factory(key,values):
        hosts.append(key)
        def execute(asset,version,output,request,**kwargs):
            nonlocal active,peak
            assert version=='0.1.10'
            if output=='product_selection':return {'run_uuid':str(uuid.uuid4()),'result':plan_products(data)}
            with lock:active+=1;peak=max(peak,active)
            time.sleep(.02)
            with lock:active-=1
            assert key!='selection' and request['product_id'] in {'P0','P1'}
            return {'run_uuid':str(uuid.uuid4()),'result':{'subject':{'product_id':request['product_id']}}}
        return execute
    result=ProductRangeWorkflow(factory).run(variables,analyze=False)
    assert result['status']=='preflight_completed' and len(result['cases'])==2
    assert peak==2 and len(hosts)==3 and len(set(hosts))==3
    assert all(not row['provider_generation_requested'] for row in result['cases'])


def test_wrong_case_subject_stops_before_source_preparation():
    data=selected()
    def factory(key,values):
        def execute(asset,version,output,request,**kwargs):
            if output=='product_selection':return {'run_uuid':str(uuid.uuid4()),'result':plan_products(data)}
            return {'run_uuid':str(uuid.uuid4()),'result':{'subject':{'product_id':'UNRELATED'}}}
        return execute
    result=ProductRangeWorkflow(factory).run(data['variables'],analyze=True)
    assert result['status']=='needs_attention'
    assert all(row['reason_code']=='clinical_range_case_subject_changed' for row in result['cases'])


def test_dependency_response_schema_only_allows_supplied_canonical_ids():
    runner=AgentRunner(Inputs(),Budget());request=parse_request(example_inputs())
    packet=runner.packet('hypothesis_analyst',request,task_id='H',obligations=['hypothesis_assessment'],
        packet_data={'case_assessments':[{'item_id':'EXACT_CANONICAL'}]})
    schema=packet['response_contract']['json_schema']['properties']['items']['items']['properties']['depends_on']
    validator=Draft202012Validator(schema)
    validator.validate(['EXACT_CANONICAL'])
    assert list(validator.iter_errors(['claim:invented']))
    assert list(validator.iter_errors(['outcome:6:invented']))


def test_dependency_closure_is_reviewed_separately_and_never_copied_into_every_packet():
    value=run_analysis(Inputs())['outputs']['clinical_intelligence']
    evidence=[{**deepcopy(value['evidence'][0]),'evidence_id':'E'+str(i),'source_type':'original_research',
        'trial_ids':[],'text':'Whole synthetic source. '*40} for i in range(200)]
    premise=deepcopy(value['case_assessments'][0]);premise.update(item_id='PREMISE',depends_on=[],
        supporting_evidence_ids=[row['evidence_id'] for row in evidence[:199]],contradicting_evidence_ids=[])
    candidate=deepcopy(value['hypothesis_results'][0]);candidate.update(item_id='H',depends_on=['PREMISE'],
        supporting_evidence_ids=['E199'],contradicting_evidence_ids=[])
    packets=critic_batches([premise,candidate],evidence,{},25000,max_items=1)
    packet=next(p for p in packets if p['candidate_items'][0]['item_id']=='H')
    assert packet['dependency_context']==[premise]
    assert [row['evidence_id'] for row in packet['evidence_packet']]==['E199']
    assert packet['dependency_review_policy']['final_acceptance_requires_all_premises_accepted'] is True
    assert evidence[0]['text'].startswith('Whole synthetic source.')


def test_missing_dependency_can_be_reviewed_but_cannot_be_accepted():
    value=run_analysis(Inputs())['outputs']['clinical_intelligence'];row=deepcopy(value['hypothesis_results'][0])
    row.update(depends_on=[],unresolved_dependency_ids=['MISSING'])
    ledger=EvidenceLedger('CASE_SYN','2025-02-01',example_inputs()['clinical_context']['evidence'])
    decision={'item_id':row['item_id'],'verdict':'accepted','rationale':'Synthetic test verdict.',
        'scope_preserved':True,'supporting_evidence_ids':row['supporting_evidence_ids'],
        'contradicting_evidence_ids':row['contradicting_evidence_ids']}
    reviewed,issues=review_items([row],[decision],ledger)
    assert reviewed[0]['review_status']=='automated_reviewed'
    assert reviewed[0]['accepted'] is False and reviewed[0]['verdict']=='inconclusive'


def test_memory_schema_matches_actual_section_existence_and_exact_old_target():
    runner=AgentRunner(Inputs(),Budget());request=parse_request(example_inputs())
    snapshot={'section_path':['Synthetic case'],'section_exists':False,'paragraphs':[]}
    data={'memory_context':snapshot,'accepted_items':[{'item_id':'ACCEPTED'}]}
    packet=runner.packet('product_memory_editor',request,task_id='M',obligations=['product_memory_delta'],packet_data=data)
    validator=Draft202012Validator(packet['response_contract']['json_schema']['properties']['items'])
    edit={'edit_id':'EDIT','operation':'add_section','target_paragraph_id':None,'before_digest':None,
        'section_path':snapshot['section_path'],'new_text':'A synthetic reviewed finding.',
        'supporting_item_ids':['ACCEPTED'],'rationale':'A synthetic test.'}
    validator.validate([edit]);edit['operation']='append_paragraph'
    assert list(validator.iter_errors([edit]))
    edit['operation']='add_section';edit['supporting_item_ids']=['UNREVIEWED']
    assert list(validator.iter_errors([edit]))


def test_all_previously_published_bytes_and_version_objects_are_frozen():
    frozen=json.loads((ASSET_ROOT/'tests/reference/published_019_frozen.json').read_text())
    for name,checksum in frozen['files'].items():
        assert hashlib.sha256((ASSET_ROOT/name).read_bytes()).hexdigest()==checksum,name
    manifest=json.loads((ASSET_ROOT/'clinical_failure_intelligence.asset.json').read_text())
    for version,checksum in frozen['versions'].items():
        actual=json.dumps(manifest['versions'][version],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
        assert hashlib.sha256(actual).hexdigest()==checksum,version


def test_case_scoping_preserves_admitted_runtime_capabilities_without_mutating_input():
    data=selected();plan=plan_products(data);data['variables']=plan['cases'][0]['variables']
    inputs=Inputs(data);original=deepcopy(inputs['variables'])
    scoped,receipt=scoped_inputs(inputs)
    assert callable(scoped.invoke_agent) and callable(scoped.skill) and callable(scoped.dynamic_skill)
    assert scoped is not inputs and inputs['variables']==original
    assert scoped.calls is inputs.calls


def test_analysis_uses_each_products_own_source_runs_and_only_uuid_references():
    from test_source_workflow import SourceExecutor
    from test_source_bundle import trial_result,terminology
    data=selected();plan=plan_products(data);seen={};reference_sets=[]
    def factory(key,variables):
        executor=SourceExecutor(pmids=());seen[key]=[]
        def execute(asset,version,output,request,**kwargs):
            seen[key].append((asset,request.get('operation'),kwargs))
            if output=='product_selection':return {'run_uuid':str(uuid.uuid4()),'result':plan}
            if asset=='nusaibah.clinical_failure_intelligence':
                if request['preflight_only']:
                    case=next(row for row in plan['cases'] if row['case_id']==key)
                    return {'run_uuid':str(uuid.uuid4()),'result':{'subject':case['subject']}}
                references=kwargs['references']
                assert all(set(ref)=={'run_uuid'} for ref in references.values())
                reference_sets.append({ref['run_uuid'] for ref in references.values()})
                assert request['product_id']==variables['product_id']
                return {'run_uuid':str(uuid.uuid4()),'result':{'quality':{'status':'completed'},'evidence':[{}]}}
            response=({'run_uuid':str(uuid.uuid4()),'result':terminology()}
                if asset=='umls_terminology' else executor(asset,version,output,request))
            # Independent synthetic producer UUIDs for each product host.
            response['run_uuid']=str(uuid.uuid4())
            if asset.endswith('clinical_trials_lookup'):
                response['result']=trial_result(nct=request['nct_id'],operation=request['operation'])
            elif asset=='umls_terminology':
                response['result']['query']=request
                response['result']['provenance']['runtime_fetch_evidence']['effective_selectors_digest']=digest([
                    {'string':request['text'],'searchType':request['search_type']}])
            return response
        return execute
    receipt=ProductRangeWorkflow(factory).run(data['variables'],analyze=True)
    assert len(reference_sets)==2 and reference_sets[0].isdisjoint(reference_sets[1]),json.dumps(receipt['cases'])
    assert len(receipt['cases'])==2
    assert all(row['source_calls']==4 for row in receipt['cases'])
    assert all(row['publication_confirmed'] is False for row in receipt['cases'])
    assert seen['selection']==[('nusaibah.clinical_failure_intelligence',None,{})]


def test_runtime_authority_failure_in_one_product_does_not_resubmit_its_case():
    data=selected();plan=plan_products(data);counts={}
    def factory(key,variables):
        def execute(asset,version,output,request,**kwargs):
            counts[key]=counts.get(key,0)+1
            if output=='product_selection':return {'run_uuid':str(uuid.uuid4()),'result':plan}
            if variables['product_id']=='P0':raise RuntimeError('unknown acknowledgment')
            return {'run_uuid':str(uuid.uuid4()),'result':{'subject':{'product_id':variables['product_id']}}}
        return execute
    receipt=ProductRangeWorkflow(factory).run(data['variables'])
    failed=next(row for row in receipt['cases'] if row['product_id']=='P0')
    assert failed['status']=='needs_attention' and failed['resume_requires_same_checkpoint'] is True
    assert counts[failed['case_id']]==1
    assert next(row for row in receipt['cases'] if row['product_id']=='P1')['status']=='preflight_completed'


def test_new_prompt_contract_hashes_and_manifest_roles_match_exact_files():
    from clinical_failure_intelligence import prompt_catalog_v0_1_10 as catalog
    manifest=json.loads((ASSET_ROOT/'clinical_failure_intelligence.asset.json').read_text())['versions']['0.1.10']
    requirements=json.loads((ASSET_ROOT/'admission_requirements_v0_1_10.json').read_text())
    assert requirements['asset']=='nusaibah.clinical_failure_intelligence@0.1.10'
    for row in requirements['agent_contracts']:
        prompt=(ASSET_ROOT/row['prompt_file']).read_text()
        assert prompt==catalog.PROMPTS[row['role']]
        checksum='sha256:'+hashlib.sha256((catalog.COMMON_PROMPT+'\n\n'+prompt).encode()).hexdigest()
        assert row['prompt_digest']==checksum
        assert row['contract_version']==row['prompt_version']=='1.7.0'
        assert manifest['agents'][row['role']]['contract_version']=='1.7.0'
    assert manifest['inputs']['previous_continuation']['retained_output']=={
        'asset_identity':'nusaibah.clinical_failure_intelligence:0.1.10','output_role':'clinical_intelligence'}
