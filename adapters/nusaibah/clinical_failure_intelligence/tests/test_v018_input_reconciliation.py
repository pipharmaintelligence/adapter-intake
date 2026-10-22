"""Scoped additional-Agent recovery; no providers, credentials or fabricated source data."""
from copy import deepcopy
from dataclasses import replace
import json
import pytest
from fakes import example_inputs,ASSET_ROOT
from test_v018_completion import Inputs
from clinical_failure_intelligence.contracts_v0_1_8 import parse_request,canonical_bytes,ContractError
from clinical_failure_intelligence.runtime_access_v0_1_8 import AgentRunner
from clinical_failure_intelligence.evidence_v0_1_8 import EvidenceLedger
from clinical_failure_intelligence.orchestration_v0_1_8 import run_analysis
from clinical_failure_intelligence.policies_v0_1_8 import Budget,ExecutionPolicy


def oversize_spec(inputs=None,policy=None):
    class Small(Inputs):
        def agent_input_budget(self,role):
            value=super().agent_input_budget(role)
            if role=='trial_researcher':value['max_input_json_chars']=10000
            return value
    inputs=inputs or Small()
    request=parse_request(inputs);request['enable_refinement']=True
    rows=deepcopy(example_inputs()['clinical_context']['evidence'])
    for row in rows:row['text']='Complete synthetic scientific source window. '*115
    rows=EvidenceLedger('CASE_SYN','2025-02-01',rows).rows()
    runner=AgentRunner(inputs,Budget(policy));runner.prepare_input_budgets()
    spec={'role':'trial_researcher','request':request,'task_id':'OVERSIZE',
        'obligations':['clinical_outcome:0'],'packet_data':{'evidence_packet':rows}}
    return runner,inputs,spec,rows


def test_oversize_input_reconciles_by_ids_and_retries_only_whole_fragments_once():
    runner,inputs,spec,rows=oversize_spec();before=deepcopy(rows)
    assert runner.prepare(**spec).code=='clinical_packet_requires_partitioning'
    result=runner.call(**spec)
    assert result.status=='completed',result.summary()
    assert [role for role,packet in inputs.calls]==['input_reconciler','trial_researcher','trial_researcher']
    recovery_packet=inputs.calls[0][1]
    assert 'evidence_packet' not in recovery_packet
    assert recovery_packet['input_reconciliation']['affected_fragment']==[]
    assert [unit['unit_id'] for unit in recovery_packet['input_reconciliation']['input_inventory']]==[row['evidence_id'] for row in rows]
    retried=[packet['evidence_packet'][0] for role,packet in inputs.calls[1:]]
    assert retried==rows and rows==before
    assert len({row['claim_id'] for row in result.payload['items']})==2
    assert runner.budget.calls==3 and runner.budget.reconciliation_calls==3
    assert len(result.attempts)==4
    assert runner.call(**spec).cache_hit and len(inputs.calls)==3


@pytest.mark.parametrize('fault',['omit','duplicate','foreign','too_many','source_edit','wrong_target'])
def test_invalid_partition_proposals_never_dispatch_an_original_role_retry(fault):
    def alter(value,packet):
        plan=value['items'][0]
        if fault=='omit':plan['groups']=[plan['groups'][0]]
        if fault=='duplicate':plan['groups']=[['E_TRIAL'],['E_TRIAL']]
        if fault=='foreign':plan['groups']=[['E_TRIAL'],['UNSUPPLIED']]
        if fault=='too_many':plan['groups']=[['E_TRIAL'],['E_PAPER'],['EXTRA']]
        if fault=='source_edit':plan['prepared_items']=[{'evidence_id':'E_TRIAL','text':'Edited science'}]
        if fault=='wrong_target':plan['target_role']='hypothesis_analyst'
        return value
    runner,inputs,spec,rows=oversize_spec();inputs.transforms['input_reconciler']=alter
    result=runner.call(**spec)
    assert result.status=='deferred' and result.code=='clinical_packet_requires_partitioning'
    assert [role for role,packet in inputs.calls]==['input_reconciler']
    assert runner.reconciliation_receipts[-1]['disposition']=='unresolved'


def test_reconciler_receives_only_affected_claim_not_valid_sibling_or_full_case():
    def corrupt(value,packet):
        if not packet.get('business_correction'):
            value['items'][0]['source_spans'][0]['quote']='Unverifiable paraphrase.'
        return value
    data=example_inputs();data['variables']['enable_refinement']=True
    second=deepcopy(data['clinical_context']['evidence'][0]);second['evidence_id']='VALID_SIBLING';second['text']+=' An independently stated synthetic qualification.'
    data['clinical_context']['evidence'].append(second)
    inputs=Inputs(data,transforms={'trial_researcher':corrupt})
    result=run_analysis(inputs)['outputs']['clinical_intelligence']
    packets=[packet for role,packet in inputs.calls if role=='input_reconciler']
    assert len(packets)==1
    packet=packets[0];fragment=packet['input_reconciliation']['affected_fragment']
    assert len(fragment)==1 and fragment[0]['claim_id']=='claim_0'
    assert [row['evidence_id'] for row in packet['evidence_packet']]==['E_TRIAL']
    assert all(key not in packet for key in ('clinical_context','prepared_sources','research_claims','memory_context'))
    assert len(result['research_claims'])==3
    assert result['execution']['reconciliation_agent_calls']==2
    assert len(result['execution']['input_reconciliation']['stages'])==1
    assert result['memory_update']['write_attempted'] is False


def test_proposed_scientific_rewrite_is_rejected_before_original_role_retry():
    def corrupt(value,packet):
        value['items'][0]['source_spans'][0]['quote']='Unverifiable paraphrase.'
        return value
    def rewrite(value,packet):
        proposal=deepcopy(packet['input_reconciliation']['affected_fragment'][0])
        proposal['statement']='A definite cause invented by reconciliation.'
        value['items'][0]['prepared_items']=[proposal]
        return value
    data=example_inputs();data['variables']['enable_refinement']=True
    inputs=Inputs(data,transforms={'trial_researcher':corrupt,'input_reconciler':rewrite})
    result=run_analysis(inputs)['outputs']['clinical_intelligence']
    assert result['execution']['reconciliation_agent_calls']==1
    assert any(row['code']=='clinical_span_mismatch' for row in result['quality']['issues'])
    assert not any(packet.get('business_correction') for role,packet in inputs.calls)


def test_reconciler_can_abstain_and_missing_role_admission_does_not_break_valid_work():
    for absent in (False,True):
        class Optional(Inputs):
            def agent_input_budget(self,role):
                return None if absent and role=='input_reconciler' else super().agent_input_budget(role)
        def corrupt(value,packet):
            value['items'][0]['source_spans'][0]['quote']='No literal support.';return value
        def abstain(value,packet):
            value['items'][0]['action']='unresolved';return value
        data=example_inputs();data['variables']['enable_refinement']=True
        inputs=Optional(data,transforms={'trial_researcher':corrupt,'input_reconciler':abstain})
        result=run_analysis(inputs)['outputs']['clinical_intelligence']
        assert result['case_assessments'] and result['quality']['status']=='partial'
        assert result['execution']['reconciliation_agent_calls']==int(not absent)
        assert result['execution']['input_reconciliation']['receipts'][-1]['disposition']=='unresolved'


def test_reconciliation_has_run_wide_call_limit_and_never_recurses_on_bad_response():
    runner,inputs,spec,rows=oversize_spec(policy=replace(ExecutionPolicy(),max_reconciliation_agent_calls=1))
    result=runner.call(**spec)
    assert result.status=='partial'
    assert [role for role,packet in inputs.calls]==['input_reconciler']
    assert runner.budget.calls==1 and runner.budget.reconciliation_calls==1
    assert all(row['status']=='deferred' for row in result.attempts[2:])
    # Malformed terminal reconciliation JSON gets no extra reconciliation/JSON loop.
    class Bad(Inputs):
        def invoke_agent(self,role,**kwargs):
            if role=='input_reconciler':
                self.calls.append((role,deepcopy(kwargs['input'])))
                return {'status':'completed','result':{'text':'{invalid'}}
            return super().invoke_agent(role,**kwargs)
    runner,inputs,spec,rows=oversize_spec()
    original=inputs.invoke_agent
    def bad(role,**kwargs):
        if role=='input_reconciler':
            inputs.calls.append((role,deepcopy(kwargs['input'])))
            return {'status':'completed','result':{'text':'{invalid'}}
        return original(role,**kwargs)
    inputs.invoke_agent=bad
    assert runner.call(**spec).status=='deferred'
    assert len(inputs.calls)==1


def test_no_agent_can_fix_auth_authority_missing_budget_or_unknown_dispatch():
    from clinical_failure_intelligence.runtime_access_v0_1_8 import StageResult
    from clinical_failure_intelligence.input_reconciliation_v0_1_8 import ask_reconciler
    runner,inputs,spec,rows=oversize_spec()
    stage=StageResult('FAILED','trial_researcher','failed','sha256:'+'a'*64,{'items':[]},{})
    fragment=[{'claim_id':'ONE'}]
    for code in ('clinical_agent_runtime_blocked','clinical_authority_material_forbidden',
                 'provider_execution_vertex_auth_failed','clinical_agent_budget_reserved','unrecognized_new_error'):
        assert ask_reconciler(runner,spec['request'],stage,mode='retry_items',data={},
            errors=[{'code':code}],originals=fragment) is None
    assert inputs.calls==[] and runner.budget.calls==0


def test_eighth_role_is_admitted_argon_high_and_no_public_search():
    from clinical_failure_intelligence.prompt_catalog_v0_1_8 import PROMPTS
    data=json.loads((ASSET_ROOT/'admission_requirements_v0_1_8.json').read_text())
    row=next(row for row in data['agent_contracts'] if row['role']=='input_reconciler')
    assert len(data['agent_contracts'])==8
    assert row['request_policy']['model']=='gemini-4-argon'
    assert row['request_policy']['thinking_level']=='high'
    assert row['grounded_search_policy']['enabled'] is False
    assert 'one reconciliation pass' in PROMPTS['input_reconciler']
    assert 'Do not return valid original siblings' in PROMPTS['input_reconciler']


def test_new_outcome_enum_error_reconciles_only_bad_candidate_before_review():
    def wrong(value,packet):
        if packet.get('business_correction'):
            allowed={row['item_id'] for row in packet['business_correction']['rejected_items']}
            value['items']=[row for row in value['items'] if row['item_id'] in allowed]
        else:value['items'][0]['value']='an_invalid_enum'
        return value
    data=example_inputs();data['variables']['enable_refinement']=True
    inputs=Inputs(data,transforms={'outcome_adjudicator':wrong})
    result=run_analysis(inputs)['outputs']['clinical_intelligence']
    assert len(result['case_assessments'])==5
    assert not any(row['code']=='clinical_outcome_value_invalid' for row in result['quality']['issues'])
    recon=[packet for role,packet in inputs.calls if role=='input_reconciler']
    assert len(recon)==1 and len(recon[0]['input_reconciliation']['affected_fragment'])==1
    assert result['execution']['reconciliation_agent_calls']==2


def test_editorial_shape_error_retries_specific_edit_and_still_requires_edit_critic():
    def wrong(value,packet):
        if not packet.get('business_correction'):value['items'][0]['operation']='append'
        return value
    data=example_inputs();data['variables']['enable_refinement']=True
    inputs=Inputs(data,transforms={'product_memory_editor':wrong})
    result=run_analysis(inputs)['outputs']['clinical_intelligence']
    assert result['memory_update']['status']=='preview'
    assert result['memory_update']['write_attempted'] is False
    recon=[packet for role,packet in inputs.calls if role=='input_reconciler']
    assert len(recon)==1 and recon[0]['input_reconciliation']['target_role']=='product_memory_editor'
    assert 'memory_context' in recon[0]
    assert any(role=='evidence_critic' and packet.get('review_kind')=='product_memory_edits' for role,packet in inputs.calls)
    assert result['execution']['reconciliation_agent_calls']==2


def test_all_new_prompt_digests_match_exact_eighth_role_source():
    import hashlib
    from clinical_failure_intelligence.prompt_catalog_v0_1_8 import COMMON_PROMPT,PROMPTS
    data=json.loads((ASSET_ROOT/'admission_requirements_v0_1_8.json').read_text())
    for row in data['agent_contracts']:
        assert row['prompt_digest']=='sha256:'+hashlib.sha256((COMMON_PROMPT+'\n\n'+PROMPTS[row['role']]).encode()).hexdigest()


@pytest.mark.parametrize('fault',['none','bad_digest','malformed_span','dropped_span'])
def test_exact_span_preparation_is_checked_before_original_role_retry(fault):
    def corrupt(value,packet):
        if not packet.get('business_correction'):value['items'][0]['source_spans'][0]['quote']='A nonliteral paraphrase.'
        return value
    def prepare(value,packet):
        row=deepcopy(packet['input_reconciliation']['affected_fragment'][0])
        source=packet['evidence_packet'][0]
        row['source_spans']=[{'evidence_id':source['evidence_id'],'start':0,'end':len(source['text']),
            'quote':source['text'],'text_digest':source['text_digest']}]
        if fault=='bad_digest':row['source_spans'][0]['text_digest']='sha256:'+'f'*64
        if fault=='malformed_span':row['source_spans']=[None]
        if fault=='dropped_span':row['source_spans']=[]
        value['items'][0]['prepared_items']=[row]
        return value
    data=example_inputs();data['variables']['enable_refinement']=True
    inputs=Inputs(data,transforms={'trial_researcher':corrupt,'input_reconciler':prepare})
    result=run_analysis(inputs)['outputs']['clinical_intelligence']
    retries=[packet for role,packet in inputs.calls if packet.get('business_correction')]
    assert len(retries)==int(fault=='none')
    assert any(row['code']=='clinical_span_mismatch' for row in result['quality']['issues'])==(fault!='none')
    if retries:
        assert retries[0]['input_reconciliation_retry']['prepared_fragment'][0]['statement']==retries[0]['business_correction']['rejected_items'][0]['statement']


def test_original_role_and_reconciler_are_both_charged_to_existing_global_call_budget():
    runner,inputs,spec,rows=oversize_spec(policy=replace(ExecutionPolicy(),max_agent_calls=1))
    result=runner.call(**spec)
    assert result.status=='deferred'
    # Reserve the original-role retry before spending on optional reconciliation.
    assert inputs.calls==[] and runner.budget.calls==0
    assert runner.reconciliation_stages[0].code=='clinical_agent_budget_reserved'


def test_wrong_reconciler_envelope_identity_is_unresolved_without_new_role_retry():
    def mismatch(value,packet):value['subject_id']='OTHER_CASE';return value
    runner,inputs,spec,rows=oversize_spec();inputs.transforms['input_reconciler']=mismatch
    assert runner.call(**spec).status=='deferred'
    assert [role for role,packet in inputs.calls]==['input_reconciler']
    assert runner.reconciliation_receipts[-1]['code']=='clinical_reconciliation_identity_invalid'
