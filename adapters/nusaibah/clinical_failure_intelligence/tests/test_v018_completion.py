"""Provider-free regressions for the retained-run defect shapes, never provider data."""
from copy import deepcopy
from pathlib import Path
import hashlib,json
import pytest
from jsonschema import Draft202012Validator
from fakes import FakeInputs,example_inputs,ASSET_ROOT
from clinical_failure_intelligence.analysis_packets_v0_1_8 import closed_packet,evidence_batches
from clinical_failure_intelligence.contracts_v0_1_8 import canonical_bytes,parse_request,ContractError,digest
from clinical_failure_intelligence.runtime_access_v0_1_8 import AgentRunner,StageResult
from clinical_failure_intelligence.policies_v0_1_8 import Budget,ExecutionPolicy
from clinical_failure_intelligence.orchestration_v0_1_8 import run_analysis
from clinical_failure_intelligence.memory_packets_v0_1_8 import memory_data,memory_batches
from clinical_failure_intelligence.business_recovery_v0_1_8 import correct_business
from clinical_failure_intelligence.evidence_v0_1_8 import EvidenceLedger


class Inputs(FakeInputs):
    def role_payload(self,role,packet):
        value=super().role_payload(role,packet)
        if role=='input_reconciler':
            context=packet['input_reconciliation'];ids=context['affected_item_ids']
            partition=context['mode']=='partition_input'
            value['items']=[{'original_task_id':context['original_task_id'],'target_role':context['target_role'],
                'action':'partition_input' if partition else 'prepare_retry','affected_item_ids':ids,
                'evidence_ids':[],'groups':[[key] for key in ids] if partition else [],'prepared_items':[],
                'rationale':'Use the exact supplied source digest and literal text; preserve original support polarity.'}]
        return value
    def agent_input_budget(self,role):
        return {'schema_version':'agent_input_budget.v1','scope':'single_step_initial_request',
                'max_input_json_chars':160000,'max_input_json_bytes':262144}


def test_outcome_closure_cannot_multiply_into_every_hypothesis_request():
    rows=[{**deepcopy(example_inputs()['clinical_context']['evidence'][0]),
        'evidence_id':'SOURCE_'+str(i),'text':'Whole synthetic source window. '*45} for i in range(461)]
    outcomes=[{'item_id':'O_'+str(i),'dimension':'primary_endpoint_result','value':'not_met',
        'trial_ids':['TRIAL_SYN'],'statement':'Complete provisional outcome. '*20,
        'supporting_evidence_ids':[row['evidence_id'] for row in rows[:278]],
        'contradicting_evidence_ids':[],'depends_on':[],'accepted':False,'review_status':'unreviewed'} for i in range(40)]
    original=deepcopy(outcomes)
    runner=AgentRunner(Inputs(),Budget());runner.prepare_input_budgets();request=parse_request(example_inputs())
    def packet(batch):
        return runner.packet('hypothesis_analyst',request,task_id='H:planning',obligations=['seed:SEED_SYN'],
            packet_data=closed_packet(batch,rows,[],{'case_trial_ids':['TRIAL_SYN']},outcomes=outcomes))
    batches=evidence_batches(rows,packet,max_bytes=262144,fits=lambda value:runner.packet_fits('hypothesis_analyst',value))
    assert len(batches)<15 and all(runner.packet_fits('hypothesis_analyst',packet(batch)) for batch in batches)
    assert [row['evidence_id'] for batch in batches for row in batch]==[row['evidence_id'] for row in rows]
    for batch in batches:
        value=packet(batch)
        assert len(value['case_assessments'])==40
        assert value['case_assessment_scope']['source_evidence'] is False
        assert all('supporting_evidence_ids' not in item for item in value['case_assessments'])
        assert value['evidence_packet']==batch
    assert outcomes==original


def test_unfit_shared_base_is_one_honest_deferral_not_461_futile_plans():
    rows=[{'evidence_id':'E'+str(i)} for i in range(461)]
    assert evidence_batches(rows,lambda batch:{'common':'X'*1000,'rows':batch},max_bytes=500)==[rows]


def test_critic_schema_rejects_other_candidate_refs_and_polarity_changes():
    runner=AgentRunner(Inputs(),Budget());request=parse_request(example_inputs())
    candidates=[{'item_id':'ONE','supporting_evidence_ids':['A'],'contradicting_evidence_ids':[]},
        {'item_id':'TWO','supporting_evidence_ids':['B'],'contradicting_evidence_ids':['C']}]
    packet=runner.packet('evidence_critic',request,task_id='REVIEW',obligations=['review:ONE','review:TWO'],packet_data={'candidate_items':candidates})
    schema=packet['response_contract']['json_schema']['properties']['items']
    validator=Draft202012Validator(schema)
    good=[{'item_id':row['item_id'],'verdict':'accepted','rationale':'Scoped support.',
        'scope_preserved':True,'supporting_evidence_ids':row['supporting_evidence_ids'],
        'contradicting_evidence_ids':row['contradicting_evidence_ids']} for row in candidates]
    validator.validate(good)
    for field,ref in [('supporting_evidence_ids','B'),('contradicting_evidence_ids','A')]:
        bad=deepcopy(good);bad[0][field]=[ref]
        assert list(validator.iter_errors(bad))


def test_small_case_all_roles_and_memory_preview_complete_without_side_effects():
    inputs=Inputs();value=run_analysis(inputs)['outputs']['clinical_intelligence']
    assert value['asset'].endswith('@0.1.8')
    assert value['quality']['status']=='completed',value['quality']['issues']
    assert all(value['quality']['required_roles_completed'].values())
    assert value['memory_update']['status']=='preview'
    assert value['memory_update']['write_attempted'] is False
    assert value['memory_update']['editorial_batches']['review_source']=='reviewed_derived_findings'
    editorial=[packet for role,packet in inputs.calls if role=='product_memory_editor' or packet.get('review_kind')=='product_memory_edits']
    assert editorial and all(not packet['evidence_packet'] for packet in editorial)
    assert all(packet['reviewed_findings_provenance']['raw_sources_supplied'] is False for packet in editorial)
    assert value['execution']['business_correction_tasks']==0


def test_editorial_preview_does_not_repeat_half_megabyte_source_closure():
    original=run_analysis(Inputs())['outputs']['clinical_intelligence']
    accepted=[row for row in original['case_assessments'] if row['accepted'] and row['value'] not in {'unknown','not_evaluable','not_applicable'}]
    ledger=[{'evidence_id':'E'+str(i),'text':'Full canonical passage. '*100} for i in range(278)]
    data=memory_data(accepted,{'_private':'ignored','status':'read'},ledger,{})
    assert data['accepted_items']==accepted and data['evidence_packet']==[]
    assert data['reviewed_findings_provenance']['canonical_evidence_count']==278
    assert len(canonical_bytes(data))<10000
    assert len(canonical_bytes(ledger))>500000
    assert memory_batches(list(range(6)),lambda batch:batch,lambda batch:len(batch)<=2)==[[0,1],[2,3],[4,5]]


def test_invalid_quote_gets_one_explicit_correction_and_valid_sibling_is_not_repeated():
    class Corrected(Inputs):
        def role_payload(self,role,packet):
            value=super().role_payload(role,packet)
            if role=='trial_researcher':
                if packet.get('business_correction'):
                    assert len(packet['business_correction']['rejected_items'])==1
                else:value['items'][0]['source_spans'][0]['quote']='A paraphrase that is not literal.'
            return value
    data=example_inputs();data['variables']['enable_refinement']=True
    inputs=Corrected(data);value=run_analysis(inputs)['outputs']['clinical_intelligence']
    fixes=[packet for role,packet in inputs.calls if packet.get('business_correction')]
    assert len(fixes)==1
    assert value['execution']['business_correction_tasks']==1
    assert not any(row['code']=='clinical_span_mismatch' for row in value['quality']['issues'])
    assert len(value['research_claims'])==2
    assert len([row for row in value['execution']['stages'] if row['task_id'].startswith('business_fix:')])==1


def test_failed_or_disabled_business_correction_never_accepts_a_paraphrased_quote():
    for enabled in (False,True):
        def corrupt(value,packet):
            value['items'][0]['source_spans'][0]['quote']='Unverifiable paraphrase.'
            return value
        data=example_inputs();data['variables']['enable_refinement']=enabled
        inputs=Inputs(data,transforms={'trial_researcher':corrupt})
        value=run_analysis(inputs)['outputs']['clinical_intelligence']
        assert any(row['code']=='clinical_span_mismatch' for row in value['quality']['issues'])
        assert len(value['research_claims'])==1
        assert value['execution']['business_correction_tasks']==int(enabled)
        assert value['memory_update']['write_attempted'] is False


def test_correction_budget_once_per_rejected_unit_and_four_for_whole_run():
    budget=Budget()
    assert budget.admit_business_repair('SAME') is True
    assert budget.admit_business_repair('SAME') is False
    assert [budget.admit_business_repair(str(i)) for i in range(5)]==[True,True,True,False,False]
    assert budget.proof()['business_correction_tasks']==4


def test_critic_correction_cannot_accept_a_new_reference_even_when_in_ledger():
    def contaminate(value,packet):
        if packet.get('review_kind')!='product_memory_edits':value['items'][0]['contradicting_evidence_ids']=['E_PAPER']
        return value
    data=example_inputs();data['variables']['enable_refinement']=True
    value=run_analysis(Inputs(data,transforms={'evidence_critic':contaminate}))['outputs']['clinical_intelligence']
    assert any(row['code']=='clinical_critic_evidence_mismatch' for row in value['quality']['issues'])
    first=value['case_assessments'][0]
    assert first['accepted'] is False and first['review_status']=='unreviewed'


def test_new_prompt_digests_and_model_policies_exact():
    from clinical_failure_intelligence.prompt_catalog_v0_1_8 import COMMON_PROMPT,PROMPTS,PROMPT_VERSION
    old=json.loads((ASSET_ROOT/'admission_requirements_v0_1_7.json').read_text())
    new=json.loads((ASSET_ROOT/'admission_requirements_v0_1_8.json').read_text())
    assert PROMPT_VERSION=='1.6.0'
    for before,after in zip(old['agent_contracts'],new['agent_contracts']):
        assert before['request_policy']==after['request_policy']
        assert after['prompt_digest']=='sha256:'+hashlib.sha256((COMMON_PROMPT+'\n\n'+PROMPTS[after['role']]).encode()).hexdigest()
        assert after['contract_version']=='1.6.0'
    manifest=json.loads((ASSET_ROOT/'clinical_failure_intelligence.asset.json').read_text())
    assert manifest['versions']['0.1.8']['skills']==manifest['versions']['0.1.7']['skills']
    assert manifest['versions']['0.1.8']['execution']==manifest['versions']['0.1.7']['execution']


def test_461_whole_windows_flow_through_every_required_role_within_64_calls():
    class Large(Inputs):
        def role_payload(self,role,packet):
            value=super().role_payload(role,packet)
            if role.endswith('researcher'):value['items']=[]
            elif role=='outcome_adjudicator':
                ref=packet['evidence_packet'][0]['evidence_id']
                for item in value['items']:
                    item['supporting_evidence_ids']=[ref]
                    item['trial_ids']=['NCT00000001']
            elif role=='hypothesis_analyst':
                value['items'][0]['supporting_evidence_ids']=[packet['evidence_packet'][0]['evidence_id']]
                value['items'][0]['depends_on']=[packet['case_assessments'][0]['item_id']]
            return value
    from test_source_bundle import case_inputs,bundle,entry,trial_result
    data=case_inputs();data['clinical_context']['evidence']=[]
    trial=trial_result()
    trial['records'][0]['registry_study']['resultsSection']['outcomeMeasuresModule']['outcomeMeasures']=[
        {'sequence':index,'observation':'Whole synthetic source window. '*25} for index in range(455)]
    data['clinical_evidence']=bundle(entry(trial))
    inputs=Large(data);value=run_analysis(inputs)['outputs']['clinical_intelligence']
    assert len(value['evidence'])==461
    assert value['hypothesis_results'] and all(value['quality']['required_roles_completed'].values())
    assert value['execution']['logical_agent_calls']<=64
    assert not any(row.get('code')=='clinical_packet_requires_partitioning' for row in value['execution']['stages'])
    assert value['memory_update']['write_attempted'] is False
    for role,packet in inputs.calls:
        assert len(canonical_bytes(packet))<=262144
        assert len(canonical_bytes(packet).decode())<=160000


def test_invalid_business_reference_shapes_do_not_escape_item_validation():
    def broken(value,packet):
        if packet.get('review_kind')!='product_memory_edits':value['items'][0]['supporting_evidence_ids']=[['nested']]
        return value
    data=example_inputs();data['variables']['enable_refinement']=True
    value=run_analysis(Inputs(data,transforms={'evidence_critic':broken}))['outputs']['clinical_intelligence']
    assert value['quality']['status']=='partial'
    assert value['case_assessments'][0]['accepted'] is False


def test_editorial_cross_batch_collision_and_unaccepted_support_remain_blocked():
    from clinical_failure_intelligence.product_memory_v0_1_8 import validate_edit_candidates,read_product_memory
    inputs=Inputs();request=parse_request(inputs);snapshot=read_product_memory(inputs,request)
    result=run_analysis(Inputs())['outputs']['clinical_intelligence']
    accepted=[row for row in result['case_assessments'] if row['accepted']]
    paragraph=snapshot['paragraphs'][0]
    edit={'edit_id':'A','operation':'replace_paragraph','target_paragraph_id':paragraph['paragraph_id'],
        'before_digest':paragraph['digest'],'section_path':snapshot['section_path'],
        'new_text':'Scoped summary.','supporting_item_ids':[accepted[0]['item_id']],'rationale':'Update summary.'}
    with pytest.raises(ContractError,match='clinical_memory_target_repeated'):
        validate_edit_candidates([edit,{**edit,'edit_id':'B'}],snapshot,accepted)
    with pytest.raises(ContractError,match='clinical_memory_unaccepted_evidence'):
        validate_edit_candidates([{**edit,'supporting_item_ids':['FORGED']}],snapshot,accepted)


def test_malformed_research_rows_are_flagged_without_entering_citation_correction():
    def broken(value,packet):
        value['items']=[None]
        return value
    data=example_inputs();data['variables']['enable_refinement']=True
    result=run_analysis(Inputs(data,transforms={'trial_researcher':broken}))['outputs']['clinical_intelligence']
    assert result['quality']['status']=='partial'
    assert result['execution']['business_correction_tasks']==0


def test_duplicate_bad_critic_id_remains_withheld_without_ambiguous_correction():
    def broken(value,packet):
        if packet.get('review_kind')!='product_memory_edits':
            value['items'][0]['contradicting_evidence_ids']=['E_PAPER']
            value['items'].append(deepcopy(value['items'][0]))
        return value
    data=example_inputs();data['variables']['enable_refinement']=True
    result=run_analysis(Inputs(data,transforms={'evidence_critic':broken}))['outputs']['clinical_intelligence']
    assert result['quality']['status']=='partial'
    assert result['case_assessments'][0]['accepted'] is False
    assert result['execution']['business_correction_tasks']==0
