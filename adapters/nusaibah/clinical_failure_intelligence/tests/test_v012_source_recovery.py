"""Source preparation repairs use synthetic transport; no provider or Agent calls."""
from copy import deepcopy
import hashlib
import json
import uuid
import pytest
from fakes import ASSET_ROOT, FakeInputs
from test_source_workflow import SourceExecutor, selection, hydrated_inputs
from test_source_bundle import terminology
from test_v010_completion_range import selected
from test_source_events import event, envelope
from clinical_failure_intelligence.contracts_v0_1_12 import ContractError, digest
from clinical_failure_intelligence.source_workflow_v0_1_12 import ClinicalSourceWorkflow, SourcePolicy, SourceReadUnavailable
from clinical_failure_intelligence.product_range_v0_1_12 import plan_products
from clinical_failure_intelligence.range_workflow_v0_1_12 import ProductRangeWorkflow
from clinical_failure_intelligence.orchestration_v0_1_12 import run_analysis


class Executor(SourceExecutor):
    def __init__(self,trial_pmids=('12345',),context_pmids=('12346',)):
        super().__init__(pmids=trial_pmids)
        self.context_pmids=context_pmids
    def __call__(self,asset,version,output,variables):
        operation=variables['operation']
        if operation=='article_search':
            self.calls.append((asset,version,output,deepcopy(variables)))
            ids=self.context_pmids
            result={'schema_version':'pubmed_evidence.v1','operation':operation,
                'status':'completed' if ids else 'no_match','records':[{'pmid':pmid} for pmid in ids],
                'record_count':len(ids),'coverage':{'has_more':False}}
            response={'run_uuid':str(uuid.UUID(int=len(self.calls))),'result':result}
        else:
            response=super().__call__(asset,version,output,variables)
        if asset=='umls_terminology':
            response['result']['query']=deepcopy(variables)
            response['result']['provenance']['runtime_fetch_evidence']['effective_selectors_digest']=digest([
                {'string':variables['text'],'searchType':variables['search_type']}])
        self.completed[response['run_uuid']]=(asset,version,output,deepcopy(response['result']))
        return response


def without_trial():
    raw,variables,subject=selection()
    subject=deepcopy(subject);subject['trial_ids']=[]
    raw['clinical_context']['subject']=subject
    raw['clinical_context']['case_scope'].update(trial_id=None,event_id=variables['event_ids'][0])
    variables.pop('trial_id');raw['variables'].pop('trial_id',None)
    return raw,variables,subject


def test_event_only_preparation_reads_literature_and_terms_without_inventing_nct():
    raw,variables,subject=without_trial();executor=Executor()
    prepared=ClinicalSourceWorkflow(executor).prepare(subject,variables)
    assert not any(row[0].endswith('clinical_trials_lookup') for row in executor.calls)
    assert executor.calls[0][3]['operation']=='article_search'
    assert executor.calls[0][3]['drug']==subject['product_name']
    assert executor.calls[0][3]['condition']==subject['indication']
    assert 'nct_id' not in executor.calls[0][3]
    assert prepared['status']=='partial' and prepared['source_calls']==5
    assert {row['code'] for row in prepared['issues']}=={'clinical_trial_identity_unresolved'}
    assert subject['trial_ids']==[] and 'trial_id' not in variables


def test_non_trial_retained_outputs_normalize_through_real_consumer_preflight():
    raw,variables,subject=without_trial();executor=Executor()
    prepared=ClinicalSourceWorkflow(executor).prepare(subject,variables)
    data=hydrated_inputs(raw,prepared,executor)
    data['variables'].update(preflight_only=True,memory_mode='off',supplementary_search=False)
    result=run_analysis(FakeInputs(data))['outputs']['clinical_intelligence']
    assert result['asset'].endswith('@0.1.12') and result['subject']['trial_ids']==[]
    assert result['execution']['logical_agent_calls']==0 and result['quality']['status']=='preflight'
    assert len(result['prepared_sources']['sources'])==5
    assert any(row['source_id'].startswith('pubmed:') for row in result['evidence'])
    assert all(row['may_support_outcome'] is False for row in result['prepared_sources']['terminology'])
    assert not result['memory_update']['write_attempted']


def test_empty_nct_discovery_falls_back_once_and_retains_both_discovery_receipts():
    raw,variables,subject=selection();executor=Executor(trial_pmids=())
    prepared=ClinicalSourceWorkflow(executor).prepare(subject,variables)
    assert prepared['status']=='prepared' and prepared['source_calls']==8
    assert [row[3]['operation'] for row in executor.calls][:4]==['study_get','results_get','trial_publications','article_search']
    assert {'literature_search_result','literature_context_search_result'}<=set(prepared['input_references'])
    assert next(row for row in prepared['source_receipts'] if row['role']=='literature_search_result')['status']=='no_match'
    assert 'clinical_no_publication_candidates' not in {row['code'] for row in prepared['issues']}
    data=hydrated_inputs(raw,prepared,executor);data['variables'].update(preflight_only=True,memory_mode='off')
    result=run_analysis(FakeInputs(data))['outputs']['clinical_intelligence']
    assert len(result['prepared_sources']['sources'])==8 and result['execution']['logical_agent_calls']==0


def test_successful_nct_search_is_not_broadened():
    raw,variables,subject=selection();executor=Executor()
    result=ClinicalSourceWorkflow(executor).prepare(subject,variables)
    assert result['source_calls']==7 and not any(row[3]['operation']=='article_search' for row in executor.calls)


def test_unavailable_discovery_does_not_authorize_unrelated_fallback_and_keeps_failure_identity():
    raw,variables,subject=selection();executor=Executor();calls=[]
    run=str(uuid.uuid4())
    def execute(asset,version,output,request):
        calls.append(request['operation'])
        if request['operation']=='trial_publications':
            raise SourceReadUnavailable('source_output_unavailable',detail={
                'run_uuid':run,'failure_code':'synthetic_source_failure','proof_stage':'python_execution',
                'provider_records':[{'unsafe':'never copied'}],'failure_cause_code':'invalid raw message !'})
        return executor(asset,version,output,request)
    result=ClinicalSourceWorkflow(execute).prepare(subject,variables)
    assert 'article_search' not in calls and 'terminology_source_result' in result['input_references']
    issue=next(row for row in result['issues'] if row.get('role')=='literature_search_result')
    assert issue=={'role':'literature_search_result','code':'source_output_unavailable','run_uuid':run,
        'failure_code':'synthetic_source_failure','proof_stage':'python_execution'}


def test_maximum_fallback_path_stays_within_twelve_source_executions():
    raw,variables,subject=selection();executor=Executor(trial_pmids=(),context_pmids=('12345','12346','12347'))
    result=ClinicalSourceWorkflow(executor).prepare(subject,variables)
    assert result['source_calls']==12 and len(executor.calls)==12 and not result['issues']


def test_unknown_acknowledgment_still_stops_without_fallback_or_retry():
    raw,variables,subject=without_trial();calls=[]
    def execute(*args):calls.append(args);raise RuntimeError('unknown transport outcome')
    with pytest.raises(RuntimeError,match='unknown transport outcome'):
        ClinicalSourceWorkflow(execute).prepare(subject,variables)
    assert len(calls)==1


@pytest.mark.parametrize('label',['https://example.invalid','Drug OR [All Fields]','Drug*','Drug" injected','Drug\ncontrol','Drug(unbalanced'])
def test_context_query_syntax_cannot_be_injected_by_source_labels(label):
    raw,variables,subject=without_trial();subject['product_name']=label;executor=Executor()
    result=ClinicalSourceWorkflow(executor,policy=SourcePolicy(include_terminology=False)).prepare(subject,variables)
    assert not executor.calls
    assert 'clinical_context_search_selector_unavailable' in {row['code'] for row in result['issues']}


def test_condition_separators_preserve_words_and_do_not_change_case_identity():
    raw,variables,subject=without_trial();subject['indication']="Head and Neck Cancer (HNC)"
    original=deepcopy(subject);executor=Executor()
    result=ClinicalSourceWorkflow(executor).prepare(subject,variables)
    assert executor.calls[0][3]['condition']=='Head and Neck Cancer HNC'
    assert subject==original
    receipt=result['selector_receipts'][0]
    assert receipt['original_label_digest']==digest(original['indication'])
    assert receipt['search_label_digest']==digest('Head and Neck Cancer HNC')
    assert receipt['source_subject_changed'] is False and receipt['clinical_identity_assigned'] is False
    subject['indication']="Crohn's disease";executor=Executor()
    ClinicalSourceWorkflow(executor).prepare(subject,variables)
    assert executor.calls[0][3]['condition']=='Crohn s disease'


def test_empty_context_discovery_is_an_explicit_valid_gap():
    raw,variables,subject=without_trial();executor=Executor(context_pmids=())
    result=ClinicalSourceWorkflow(executor).prepare(subject,variables)
    assert result['status']=='partial' and result['source_calls']==2
    assert set(result['input_references'])=={'literature_search_result','terminology_source_result'}
    assert 'clinical_no_publication_candidates' in {row['code'] for row in result['issues']}


def test_missing_trial_selector_cannot_ignore_existing_verified_trials():
    raw,variables,subject=selection();variables.pop('trial_id');executor=Executor()
    with pytest.raises(ContractError,match='exact_trial_required'):
        ClinicalSourceWorkflow(executor).prepare(subject,variables)
    assert not executor.calls


def test_call_budget_and_completed_reads_are_preserved_for_non_trial_cases():
    raw,variables,subject=without_trial();executor=Executor()
    flow=ClinicalSourceWorkflow(executor,policy=SourcePolicy(max_source_calls=1))
    result=flow.prepare(subject,variables)
    assert len(executor.calls)==1 and set(result['input_references'])=={'literature_search_result'}
    flow.prepare(subject,variables)
    assert len(executor.calls)==1


def test_ambiguous_association_gets_snapshot_bound_resolution_without_assignment():
    data=selected();row=data['clinical_context']['records'][2]
    row['indications'].append({'designation_id':'OTHER','designation_label':'Other indication'})
    plan=plan_products(data);blocked=plan['blocked_cases'][0];resolution=blocked['resolution_required']
    assert blocked['reason_code']=='clinical_source_selector_ambiguous'
    assert resolution['indication_candidates']==row['indications'] and resolution['automatic_assignment_permitted'] is False
    assert resolution['source_record_digest']==digest(row)
    assert not any(case['product_id']=='P1' for case in plan['cases'])
    same=plan_products(deepcopy(data))['blocked_cases'][0]['resolution_required']['deferred_case_id']
    assert same==resolution['deferred_case_id']
    data['clinical_context']['provenance']['sha256']='b'*64
    assert plan_products(data)['blocked_cases'][0]['resolution_required']['deferred_case_id']!=same


def test_source_only_range_continues_event_only_cases_and_never_starts_analysis():
    data=selected();data['clinical_context']=envelope(
        event('E0',products=[{'product_id':'P0','product_name':'Synthetic 0'}],trials=[]),
        event('E1',products=[{'product_id':'P0','product_name':'Synthetic 0'}],trials=[]),
        event('E2',products=[{'product_id':'P1','product_name':'Synthetic 1'}],trials=[]))
    plan=plan_products(data);scientific=[]
    def factory(key,variables):
        executor=Executor()
        def execute(asset,version,output,values,**kwargs):
            if output=='product_selection':return {'run_uuid':str(uuid.uuid4()),'result':plan}
            if asset=='nusaibah.clinical_failure_intelligence':
                assert values['preflight_only'] is True;scientific.append(values)
                case=next(case for case in plan['cases'] if case['case_id']==key)
                return {'run_uuid':str(uuid.uuid4()),'result':{'subject':case['subject']}}
            return executor(asset,version,output,values)
        return execute
    result=ProductRangeWorkflow(factory).run(data['variables'],prepare_sources=True)
    assert len(result['cases'])==3 and len(scientific)==3
    assert all(row['status']=='partial' and row['source_calls']==5 for row in result['cases'])
    assert all(row['provider_generation_requested'] is False for row in result['cases'])
    assert result['execution_scope']=='source_preparation' and not result['publication_confirmed']


def test_source_only_and_scientific_flags_cannot_be_combined():
    with pytest.raises(ContractError,match='execution_mode_conflict'):
        ProductRangeWorkflow(lambda *a:None).run({},analyze=True,prepare_sources=True)


def test_all_published_runtime_bytes_and_manifest_versions_are_preserved():
    frozen=json.loads((ASSET_ROOT/'tests/reference/published_011_frozen.json').read_text())
    for name,checksum in frozen['files'].items():assert hashlib.sha256((ASSET_ROOT/name).read_bytes()).hexdigest()==checksum,name
    manifest=json.loads((ASSET_ROOT/'clinical_failure_intelligence.asset.json').read_text())
    for version,checksum in frozen['versions'].items():
        assert hashlib.sha256(json.dumps(manifest['versions'][version],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()==checksum,version
    assert manifest['default']=='0.1.12'
    assert manifest['versions']['0.1.12']['inputs']['literature_context_search_result']['retained_output']=={
        'asset_identity':'nusaibah.pubmed_evidence:0.1.0','output_role':'literature_result'}


def test_scientific_completion_does_not_hide_partial_source_preparation():
    data=selected();data['clinical_context']=envelope(
        event('E0',products=[{'product_id':'P0','product_name':'Synthetic 0'}],trials=[]),
        event('E1',products=[{'product_id':'P1','product_name':'Synthetic 1'}],trials=[]))
    plan=plan_products(data)
    def factory(key,variables):
        executor=Executor()
        def execute(asset,version,output,values,**kwargs):
            if output=='product_selection':return {'run_uuid':str(uuid.uuid4()),'result':plan}
            if asset=='nusaibah.clinical_failure_intelligence':
                if values['preflight_only']:
                    case=next(case for case in plan['cases'] if case['case_id']==key)
                    return {'run_uuid':str(uuid.uuid4()),'result':{'subject':case['subject']}}
                assert kwargs['references'] and 'trial_study_result' not in kwargs['references']
                return {'run_uuid':str(uuid.uuid4()),'result':{'quality':{'status':'completed'},'evidence':[]}}
            return executor(asset,version,output,values)
        return execute
    result=ProductRangeWorkflow(factory).run(data['variables'],analyze=True)
    assert result['status']=='needs_attention' and len(result['cases'])==2
    assert all(row['scientific_quality_status']=='completed' and row['status']=='partial' for row in result['cases'])
    assert all(row['source_preparation_issues'] for row in result['cases'])


def test_admission_catalog_tracks_all_versioned_source_roles():
    from clinical_failure_intelligence.retained_sources_v0_1_12 import SOURCE_ROLES
    requirements=json.loads((ASSET_ROOT/'admission_requirements_v0_1_12.json').read_text())
    assert set(requirements['source_invocation_model']['source_roles'])==set(SOURCE_ROLES)


def test_source_only_operator_rejects_conflicting_flags_before_file_or_credential_access():
    from test_v011_file_binding import operator
    module=operator('run_product_range')
    with pytest.raises(module.ContractError,match='execution_mode_conflict'):
        module.main(['--config','never-read.json','--variables-file','never-read.json','--product-index-range','0:1',
            '--checkpoint-directory','never-created','--env-file','never-read.env','--live','--analyze','--prepare-sources-only'])


def test_source_failure_status_projection_excludes_messages_and_sensitive_records(monkeypatch):
    from types import ModuleType
    from test_v011_file_binding import operator
    import sys
    module=operator('run_clinical_workflow');api=ModuleType('devtools.obs_api_client')
    run=str(uuid.uuid4());calls=[]
    def status(**kwargs):
        calls.append(kwargs)
        return {'data':{'failure_code':'python_adapter_execution_failed','proof_stage':'python_execution',
            'failure_cause_code':'unreviewed raw text !','message':'excluded message','records':[{'data':'excluded'}]}}
    api.get_run_status=status
    monkeypatch.setitem(sys.modules,'devtools.obs_api_client',api)
    detail=module.source_failure_detail({'base_url':'synthetic'},run)
    assert detail=={'run_uuid':run,'failure_code':'python_adapter_execution_failed','proof_stage':'python_execution'}
    assert len(calls)==1
