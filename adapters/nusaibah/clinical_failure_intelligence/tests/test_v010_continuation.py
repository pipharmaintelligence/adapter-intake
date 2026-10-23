"""Synthetic continuation only: no provider, storage, publication or SDK authority."""
from copy import deepcopy
import json
import hashlib
import pytest
from jsonschema import Draft202012Validator
from fakes import example_inputs, ASSET_ROOT, CodedFailure
from test_v018_completion import Inputs
from clinical_failure_intelligence.orchestration_v0_1_9 import run_analysis as prior_analysis
from clinical_failure_intelligence.continuation_v0_1_10 import preparation, continue_analysis
from clinical_failure_intelligence.contracts_v0_1_10 import digest, ContractError
from clinical_failure_intelligence.review_packets_v0_1_10 import scoped_review
from clinical_failure_intelligence.evidence_v0_1_10 import EvidenceLedger
from clinical_failure_intelligence.deferred_work_v0_1_9 import deferred_work


@pytest.fixture
def pending():
    value=prior_analysis(Inputs())['outputs']['clinical_intelligence']
    target=value['hypothesis_results'][0]
    target.update(review_status='unreviewed',accepted=False,review_reason='clinical_critic_item_not_reviewed')
    value['quality']['status']='partial'
    value['quality']['required_roles_completed']['evidence_critic']=False
    value['quality']['issues'].append({'code':'clinical_critic_item_not_reviewed','item_id':target['item_id']})
    value['deferred_work']=deferred_work(value,{})
    work=next(row['work_id'] for row in value['deferred_work']['tasks'] if row.get('item_id')==target['item_id'])
    data=example_inputs();data['variables'].update(resume_work_ids=[work],max_continuation_calls=3)
    data['previous_assessment']={'value':value,'provenance':{'source':'retained_asset_output','authority':'core_artifact',
        'run_uuid':'11111111-2222-4333-8444-555555555555','asset_identity':'nusaibah.clinical_failure_intelligence:0.1.9',
        'output_role':'clinical_intelligence','checksum_sha256':'a'*64}}
    return data


def test_plan_reads_verified_retained_assessment_without_dispatch(pending):
    pending['variables']['preflight_only']=True
    inputs=Inputs(pending);response=continue_analysis(inputs)
    plan=response['outputs']['continuation_plan']
    assert plan['review_candidate_ids']==[pending['previous_assessment']['value']['hypothesis_results'][0]['item_id']]
    assert plan['max_agent_calls']==3
    assert response['metrics']['logical_agent_calls']==0 and inputs.calls==[]
    assert plan['automatic_replay'] is False and plan['publication_confirmed'] is False


def test_selected_review_keeps_unselected_premises_and_never_repeats_research(pending):
    original=deepcopy(pending['previous_assessment']['value'])
    inputs=Inputs(pending);outputs=continue_analysis(inputs)['outputs'];result=outputs['clinical_intelligence']
    assert len(inputs.calls)==1 and inputs.calls[0][0]=='evidence_critic'
    assert len(inputs.calls[0][1]['candidate_items'])==1
    assert result['case_assessments']==original['case_assessments']
    assert result['evidence']==original['evidence']
    assert result['hypothesis_results'][0]['review_status']=='automated_reviewed'
    assert outputs['continuation_receipt']['resolved_work_ids']==pending['variables']['resume_work_ids']
    assert outputs['continuation_receipt']['unchanged_source_ledger'] is True
    assert outputs['continuation_receipt']['original_result_rewritten'] is False
    assert pending['previous_assessment']['value']==original
    assert result['execution']['inherited_logical_agent_calls']==original['execution']['logical_agent_calls']
    assert result['execution']['logical_agent_calls']==1
    assert result['memory_update']['write_attempted'] is False
    schema=json.loads((ASSET_ROOT/'clinical_intelligence_v0_1_10.schema.json').read_text())
    Draft202012Validator(schema).validate(result)


@pytest.mark.parametrize('change', ['authority','version','unknown_work','case','source','oversize_budget','inline','tampered_candidate'])
def test_forgery_drift_and_scope_escalation_block_before_calls(pending,change):
    if change=='authority':pending['previous_assessment']['provenance']['authority']='caller'
    elif change=='version':pending['previous_assessment']['provenance']['asset_identity']='other:0.1.9'
    elif change=='unknown_work':pending['variables']['resume_work_ids']=['unknown']
    elif change=='case':pending['clinical_context']['subject']['product_id']='OTHER'
    elif change=='source':pending['clinical_context']['evidence'][0]['text']+=' changed'
    elif change=='oversize_budget':pending['variables']['max_continuation_calls']=9
    elif change=='inline':pending['previous_assessment']['value']=[]
    elif change=='tampered_candidate':
        pending['previous_assessment']['value']['hypothesis_results'][0]['statement']+=' changed'
    inputs=Inputs(pending)
    with pytest.raises(ValueError):continue_analysis(inputs)
    assert inputs.calls==[]


def test_unknown_dependency_is_reviewed_inconclusive_and_never_promoted(pending):
    row=deepcopy(pending['previous_assessment']['value']['hypothesis_results'][0])
    row['depends_on']=['MISSING']
    verdict={'item_id':row['item_id'],'verdict':'accepted','scope_preserved':True,'rationale':'Synthetic decision.',
        'supporting_evidence_ids':row['supporting_evidence_ids'],'contradicting_evidence_ids':[]}
    ledger=EvidenceLedger('CASE_SYN','2025-02-01',example_inputs()['clinical_context']['evidence'])
    reviewed,issues=scoped_review([row],[verdict],ledger)
    assert reviewed[0]['review_status']=='automated_reviewed'
    assert reviewed[0]['unresolved_dependency_ids']==['MISSING']
    assert reviewed[0]['accepted'] is False and reviewed[0]['verdict']=='inconclusive'
    assert any(issue['code']=='clinical_dependency_unknown' for issue in issues)


def test_failed_selected_call_retains_work_and_no_automatic_retry(pending):
    inputs=Inputs(pending,faults={'evidence_critic':CodedFailure('agent_execution_provider_retry_exhausted','provider_execution_vertex_unavailable')})
    result=continue_analysis(inputs)['outputs']
    assert len(inputs.calls)==1
    assert result['continuation_receipt']['resolved_work_ids']==[]
    assert result['continuation_receipt']['remaining_work_count']>=1
    assert result['clinical_intelligence']['quality']['status']=='partial'


def test_memory_only_continuation_does_not_repeat_scientific_roles(pending):
    pending['previous_assessment']['value']['memory_update'].update(status='deferred',reason='clinical_memory_section_operation_invalid')
    pending['variables']['resume_work_ids']=['memory_preview']
    inputs=Inputs(pending);outputs=continue_analysis(inputs)['outputs']
    assert set(role for role,packet in inputs.calls)<={'product_memory_editor','evidence_critic'}
    assert all(packet.get('review_kind')=='product_memory_edits' for role,packet in inputs.calls if role=='evidence_critic')
    assert outputs['clinical_intelligence']['memory_update']['status']=='preview'
    assert outputs['clinical_intelligence']['memory_update']['write_attempted'] is False
    assert outputs['continuation_receipt']['resolved_work_ids']==['memory_preview']


def test_unselected_verdict_cannot_change_existing_premise(pending):
    prior=pending['previous_assessment']['value'];target=prior['hypothesis_results'][0]
    rows=prior['case_assessments']+[target]
    premise=prior['case_assessments'][0]
    bad={'item_id':premise['item_id'],'verdict':'invalid','scope_preserved':False,'rationale':'Not assigned.',
        'supporting_evidence_ids':[],'contradicting_evidence_ids':[]}
    ledger=EvidenceLedger('CASE_SYN','2025-02-01',example_inputs()['clinical_context']['evidence'])
    reviewed,issues=scoped_review(rows,[bad],ledger,assigned_ids={target['item_id']})
    assert reviewed[0]==premise
    assert any(row['code']=='clinical_critic_identity_invalid' for row in issues)


def test_finalization_preserves_partial_science_without_agent_or_skill_access(pending):
    pending['variables'].pop('resume_work_ids')
    pending['variables'].update(finalize_only=True,prepare_result_for_persistence=True,
        memory_mode='off',enable_refinement=False,supplementary_search=False)
    original=deepcopy(pending['previous_assessment']['value'])
    inputs=Inputs(pending);outputs=continue_analysis(inputs)['outputs'];result=outputs['clinical_intelligence']
    assert inputs.calls==[] and inputs.memory_calls==[]
    assert result['evidence']==original['evidence']
    assert result['quality']==original['quality']
    assert {k:v for k,v in result['execution'].items() if k!='retained_finalization'}==original['execution']
    assert result['case_assessments']==original['case_assessments']
    assert result['hypothesis_results']==original['hypothesis_results']
    assert result['deferred_work']==original['deferred_work']
    assert result['execution']['retained_finalization']['scientific_processing_repeated'] is False
    assert result['publication_readiness']['publication_confirmed'] is False
    assert outputs['clinical_intelligence_records']=={'records':[result]}
    assert pending['previous_assessment']['value']==original
    schema=json.loads((ASSET_ROOT/'clinical_intelligence_v0_1_10.schema.json').read_text())
    Draft202012Validator(schema).validate(result)


@pytest.mark.parametrize('field,value', [('memory_mode','preview'),('supplementary_search',True),
    ('enable_refinement',True),('prepare_result_for_persistence',False),('resume_work_ids',['memory_preview'])])
def test_finalization_conflicting_work_or_side_effects_rejected(pending,field,value):
    pending['variables'].pop('resume_work_ids')
    pending['variables'].update(finalize_only=True,prepare_result_for_persistence=True,
        memory_mode='off',enable_refinement=False,supplementary_search=False)
    pending['variables'][field]=value
    inputs=Inputs(pending)
    with pytest.raises(ValueError):continue_analysis(inputs)
    assert inputs.calls==[]


def test_finalization_self_inspection_passes_exact_dto_and_blocks_stale_node_schema(pending,tmp_path):
    from clinical_failure_intelligence.output_inspection_v0_1_10 import inspect_staged_payload
    pending['variables'].pop('resume_work_ids')
    pending['variables'].update(finalize_only=True,prepare_result_for_persistence=True,
        memory_mode='off',enable_refinement=False,supplementary_search=False)
    result=continue_analysis(Inputs(pending))['outputs']['clinical_intelligence']
    path=tmp_path/'retained.jsonl';path.write_text(json.dumps(result)+'\n',encoding='utf-8')
    def contract(version):
        document={'metadata':{'version':'1.2.0'},'results':{'format':'jsonl',
            'contract':json.loads((ASSET_ROOT/('clinical_intelligence_v0_1_'+version+'.schema.json')).read_text())}}
        checksum=hashlib.sha256((json.dumps(document,ensure_ascii=False,indent=2,separators=(',',': '))+'\n').encode()).hexdigest()
        return {'pointer':{'schema_version':'1.2.0','schema_sha256':checksum},'schema':document}
    assert inspect_staged_payload(path,contract('10'))['status']=='passed'
    stale=inspect_staged_payload(path,contract('9'))
    assert stale['status']=='failed' and stale['records_failed']==1


def test_scientific_continuation_invalidates_stale_memory_preview(pending):
    result=continue_analysis(Inputs(pending))['outputs']['clinical_intelligence']
    assert result['memory_update']['status']=='deferred'
    assert result['memory_update']['operations']==[]
    assert result['memory_update']['reason']=='clinical_memory_preview_requires_refresh'
    assert result['memory_update']['write_attempted'] is False


def test_successive_continuation_uses_new_exact_producer_and_cumulative_lineage(pending):
    first=continue_analysis(Inputs(pending))['outputs']['clinical_intelligence']
    second=deepcopy(pending);second.pop('previous_assessment')
    second['previous_continuation']={'value':first,'provenance':{'source':'retained_asset_output',
        'authority':'core_artifact','asset_identity':'nusaibah.clinical_failure_intelligence:0.1.10',
        'run_uuid':'11111111-2222-4333-8444-666666666666','output_role':'clinical_intelligence','checksum_sha256':'b'*64}}
    second['variables']['resume_work_ids']=['memory_preview']
    result=continue_analysis(Inputs(second))['outputs']['clinical_intelligence']
    assert result['memory_update']['status']=='preview'
    assert result['execution']['inherited_logical_agent_calls']==first['execution']['inherited_logical_agent_calls']+1
    assert result['evidence']==first['evidence']
    assert len(result['execution']['prior_stages'])==len(first['execution']['prior_stages'])+1


def test_both_retained_producer_roles_are_ambiguous_and_rejected(pending):
    pending['previous_continuation']=deepcopy(pending['previous_assessment'])
    inputs=Inputs(pending)
    with pytest.raises(ContractError,match='retained_input_required'):continue_analysis(inputs)
    assert inputs.calls==[]
