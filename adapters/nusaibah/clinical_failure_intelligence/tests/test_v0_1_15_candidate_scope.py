"""Synthetic regressions for the live trial-scope failure; no clinical records."""
from copy import deepcopy
import hashlib,json
import pytest
from jsonschema import Draft202012Validator
from fakes import ASSET_ROOT,example_inputs
from test_v018_completion import Inputs
from clinical_failure_intelligence import orchestration_v0_1_15 as current
from clinical_failure_intelligence.contracts_v0_1_15 import ContractError,parse_request
from clinical_failure_intelligence.runtime_access_v0_1_15 import AgentRunner
from clinical_failure_intelligence.policies_v0_1_15 import Budget

BAD_TRIAL='TRIAL_OTHER_SYN'
BAD_ITEM='outcome_study_disposition'

def data(empty=False,refinement=False):
    raw=example_inputs();raw['variables'].update(enable_refinement=refinement,prepare_result_for_persistence=True,max_agent_calls=64,max_product_seconds=3600)
    if empty:
        raw['clinical_context']['subject']['trial_ids']=[]
        raw['clinical_context']['case_scope'].update(trial_id=None,event_id='EVENT_SYN')
    return raw

class ScopeInputs(Inputs):
    def __init__(self,*args,bad=True,correction='valid',**kwargs):
        super().__init__(*args,**kwargs);self.bad=bad;self.correction=correction;self.original_bad=None
    def role_payload(self,role,packet):
        payload=super().role_payload(role,packet)
        if role=='outcome_adjudicator':
            for row in payload['items']:row['trial_ids']=list(packet.get('case_trial_ids',[]))
            if packet.get('business_correction'):
                ids={r['item_id'] for r in packet['business_correction']['rejected_items']}
                payload['items']=[r for r in payload['items'] if r['item_id'] in ids]
                for row in payload['items']:
                    if self.correction=='still_invalid':row['trial_ids']=[BAD_TRIAL]
                    if self.correction=='strip_only':row['trial_ids']=[]
                    if self.correction=='malformed_id':row['item_id']=['NOT_AN_ID']
            elif self.bad:
                row=next(r for r in payload['items'] if r['item_id']==BAD_ITEM);row['trial_ids']=[BAD_TRIAL]
                self.original_bad=deepcopy(row)
        return payload

def rejected(dto):return [r for r in dto['deferred_work']['tasks'] if r['kind']=='candidate_reconciliation']

@pytest.mark.parametrize('empty',[True,False])
def test_model_schema_only_allows_canonical_trial_ids_including_empty_set(empty):
    host=ScopeInputs(data(empty=empty),bad=False);request=parse_request(host);runner=AgentRunner(host,Budget())
    packet=runner.packet('outcome_adjudicator',request,task_id='outcome:test',obligations=['outcome:study_disposition'],packet_data={'case_trial_ids':request['context']['subject']['trial_ids']})
    schema=packet['response_contract']['json_schema'];payload=host.role_payload('outcome_adjudicator',packet)
    Draft202012Validator.check_schema(schema);Draft202012Validator(schema).validate(payload)
    invalid=deepcopy(payload);invalid['items'][0]['trial_ids']=[BAD_TRIAL]
    assert list(Draft202012Validator(schema).iter_errors(invalid))
    if empty:assert schema['properties']['items']['items']['properties']['trial_ids']['maxItems']==0

@pytest.mark.parametrize('empty',[True,False])
def test_one_bad_trial_candidate_does_not_abort_or_discard_valid_siblings(empty):
    host=ScopeInputs(data(empty=empty));original_context=deepcopy(host['clinical_context'])
    outputs=current.run_analysis(host)['outputs'];dto=outputs['clinical_intelligence']
    assert dto['quality']['status']=='partial' and not dto['quality']['required_roles_completed']['outcome_adjudicator']
    assert len(dto['case_assessments'])==4 and all(r['item_id']!=BAD_ITEM for r in dto['case_assessments'])
    assert any(r['accepted'] for r in dto['case_assessments'])
    pending=rejected(dto);assert len(pending)==1 and pending[0]['reason']=='clinical_outcome_trial_scope_mismatch'
    assert dto['deferred_work']['objects'][pending[0]['candidate_ref']]==host.original_bad
    assert pending[0]['retry_authorized'] is False and dto['deferred_work']['automatic_replay'] is False
    assert host['clinical_context']==original_context and not dto['memory_update']['write_attempted']
    assert outputs['clinical_intelligence_records']=={'records':[dto]}
    Draft202012Validator(json.loads((ASSET_ROOT/'clinical_intelligence_v0_1_15.schema.json').read_text())).validate(dto)

def test_empty_case_scope_defers_without_spending_two_calls_on_invented_authority():
    host=ScopeInputs(data(empty=True,refinement=True));dto=current.run_analysis(host)['outputs']['clinical_intelligence']
    corrections=[p for role,p in host.calls if p.get('business_correction') or role=='input_reconciler']
    assert corrections==[] and len(rejected(dto))==1
    receipts=dto['execution']['input_reconciliation']['receipts']
    assert any(r['code']=='clinical_reconciliation_case_trial_scope_unavailable' for r in receipts)
    assert dto['subject']['trial_ids']==[] and dto['execution']['logical_agent_calls']<=64

def test_existing_case_trial_can_be_reconciled_once_for_only_the_invalid_item():
    host=ScopeInputs(data(refinement=True));dto=current.run_analysis(host)['outputs']['clinical_intelligence']
    fixes=[p for role,p in host.calls if p.get('business_correction')]
    assert len(fixes)==1 and len(fixes[0]['business_correction']['rejected_items'])==1
    assert fixes[0]['business_correction']['rejected_items'][0]['item_id']==BAD_ITEM
    assert fixes[0]['case_trial_ids']==['TRIAL_SYN']
    assert all(r['trial_ids']==['TRIAL_SYN'] for r in dto['case_assessments'])
    assert len(dto['case_assessments'])==5 and not rejected(dto)
    assert dto['execution']['business_correction_tasks']==1 and dto['execution']['reconciliation_agent_calls']==2

@pytest.mark.parametrize('correction',['still_invalid','strip_only','malformed_id'])
def test_invalid_or_qualifier_stripping_correction_stays_deferred_without_loop(correction):
    host=ScopeInputs(data(refinement=True),correction=correction);dto=current.run_analysis(host)['outputs']['clinical_intelligence']
    assert len([p for role,p in host.calls if p.get('business_correction')])==1
    assert all(r['item_id']!=BAD_ITEM for r in dto['case_assessments'])
    assert len(dto['case_assessments'])==4 and len(rejected(dto))==1
    assert not dto['quality']['required_roles_completed']['outcome_adjudicator']
    assert dto['execution']['reconciliation_agent_calls']==2 and dto['execution']['logical_agent_calls']<=64

def test_all_five_outcomes_outside_empty_case_scope_still_produce_partial_records():
    def corrupt(payload,packet):
        for row in payload['items']:row['trial_ids']=[BAD_TRIAL]
        return payload
    host=ScopeInputs(data(empty=True,refinement=True),bad=False,transforms={'outcome_adjudicator':corrupt})
    before=deepcopy(host['clinical_context']);outputs=current.run_analysis(host)['outputs'];dto=outputs['clinical_intelligence']
    assert dto['case_assessments']==[] and len(rejected(dto))==5
    assert dto['evidence'] and dto['research_claims'] and host['clinical_context']==before
    assert dto['quality']['status']=='partial' and not dto['quality']['required_roles_completed']['outcome_adjudicator']
    assert not [p for role,p in host.calls if p.get('business_correction')]
    assert outputs['clinical_intelligence_records']=={'records':[dto]}

def test_rejected_retry_index_maps_back_to_affected_item_after_valid_siblings():
    second='outcome_safety_assessment'
    class LaterBad(ScopeInputs):
        def role_payload(self,role,packet):
            payload=super().role_payload(role,packet)
            if role=='outcome_adjudicator':
                for row in payload['items']:
                    if row['item_id']==second:row['trial_ids']=[BAD_TRIAL]
            return payload
    host=LaterBad(data(refinement=True),bad=False);dto=current.run_analysis(host)['outputs']['clinical_intelligence']
    pending=rejected(dto);assert len(pending)==1
    assert dto['deferred_work']['objects'][pending[0]['candidate_ref']]['item_id']==second
    assert any(r['item_id']==BAD_ITEM and r['accepted'] for r in dto['case_assessments'])

def test_insufficient_budget_defers_scope_repair_and_never_exceeds_call_limit():
    raw=data(refinement=True);raw['variables']['max_agent_calls']=8
    host=ScopeInputs(raw);dto=current.run_analysis(host)['outputs']['clinical_intelligence']
    assert dto['execution']['logical_agent_calls']<=8 and len(rejected(dto))==1
    assert not dto['memory_update']['write_attempted']
    assert dto['deferred_work']['automatic_replay'] is False

def test_model_wrong_subject_is_quarantined_but_forged_input_scope_still_blocks():
    def wrong(payload,packet):payload['items'][0]['subject_id']='OTHER_SUBJECT_SYN';return payload
    host=ScopeInputs(data(),bad=False,transforms={'outcome_adjudicator':wrong})
    dto=current.run_analysis(host)['outputs']['clinical_intelligence']
    assert len(dto['case_assessments'])==4 and rejected(dto)[0]['reason']=='clinical_candidate_subject_mismatch'
    assert not dto['quality']['required_roles_completed']['outcome_adjudicator']
    raw=data();raw['clinical_context']['subject']['subject_id']='OTHER_SUBJECT_SYN'
    with pytest.raises(ContractError):current.run_analysis(ScopeInputs(raw,bad=False))

def test_duplicate_model_id_only_discards_ambiguous_candidates_not_unique_siblings():
    def duplicate(payload,packet):payload['items'][1]['item_id']=payload['items'][0]['item_id'];return payload
    host=ScopeInputs(data(),bad=False,transforms={'outcome_adjudicator':duplicate})
    dto=current.run_analysis(host)['outputs']['clinical_intelligence']
    assert len(dto['case_assessments'])==3
    assert len(rejected(dto))==2 and all(r['reason']=='clinical_item_duplicate' for r in rejected(dto))

def test_historical_014_files_and_manifest_remain_immutable():
    baseline=json.loads((ASSET_ROOT/'tests/reference/published_0_1_14_frozen.json').read_text())
    for name,sha in baseline['files'].items():assert hashlib.sha256((ASSET_ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==sha
    manifest=json.loads((ASSET_ROOT/'clinical_failure_intelligence.asset.json').read_text())
    sha=hashlib.sha256(json.dumps(manifest['versions']['0.1.14'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    assert sha==baseline['version_sha256'] and manifest['default']=='0.1.15'
