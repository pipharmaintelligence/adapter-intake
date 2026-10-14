"""Final-cycle contracts: real toolkit primitives, stale review denial, no Agents on apply."""
import copy,json,sys,unittest
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(ROOT.parent))
from structured_review_toolkit.tool_operations_v0_1_1 import execute_operation
from source_evidence_v0_1_26 import SourceEvidenceInputs, canonical, digest
from claim_semantics_v0_1_26 import validate_claim_semantic_context, ClaimSemanticContractError
from research_claim_evidence_v0_1_26 import project_role_claim_evidence
from research_response_contract_v0_1_26 import validate_research_payload_v0_1_26, require_repair_preserves_claim_evidence_v0_1_26
from reviewed_apply_v0_1_26 import apply_reviewed, ReviewedApplyError
from test_research_envelope_parity_v0_1_24 import ContractFollowingInputs
from test_orchestration_preview import _fake_citations
from orchestration_v0_1_26 import invoke_v0_1_26
from devtools.public_reference import PublicReferenceError
import legacy_preparation_helpers_v0_1_23 as legacy

def semantic(**kwargs):
    value={'schema_version':'pharma_claim_semantic_context.v2','relationship_kind':'none',
       'event_date':None,'publication_date':None,'status_as_of_date':None,'event_state':'not_applicable',
       'observation_kind':'not_applicable','actor':'Ficta','counterparty':None,'territory':'Jordan',
       'manufacturing_responsibility':None,'reported_total':None,'component_total':None,'remainder_label':None,
       'governed_snapshot_relation':'not_applicable','entity_label_kind':'governed_display_name'}
    return {**value,**kwargs}

class SourceInputs(dict):
    def __init__(self,corrupt=False):
        super().__init__(); self.requests=[]; self.corrupt=corrupt
    def invoke_asset(self,role,*,variables,on_error):
        assert role=='review_toolkit' and on_error=='raise'
        self.requests.append(variables)
        result=execute_operation(variables)
        if self.corrupt:
            result['output']['spans'][0]['end']+=1
        return {'status':'success','result':result}

class FinalSourceTests(unittest.TestCase):
    def test_single_company_actor_and_location_do_not_invent_a_counterparty(self):
        context=validate_claim_semantic_context(semantic())
        self.assertNotIn('commercial_rights_direction',context.rule_ids)
        self.assertEqual('none',context.public_value()['relationship_kind'])
    def test_real_relationship_stays_strict_and_cannot_be_disguised_as_none(self):
        for values in (semantic(relationship_kind='bilateral'),semantic(counterparty='Actual Partner')):
            with self.assertRaises(ClaimSemanticContractError): validate_claim_semantic_context(values)
        self.assertIn('commercial_rights_direction',validate_claim_semantic_context(
            semantic(relationship_kind='bilateral',counterparty='Actual Partner')).rule_ids)
    def test_temporal_guard_is_preserved(self):
        with self.assertRaises(ClaimSemanticContractError):
            validate_claim_semantic_context(semantic(event_state='completed'))
    def source(self,corrupt=False):
        inputs=SourceInputs(corrupt)
        source=SourceEvidenceInputs(inputs,record={'company_id':1,'company_name':'Ficta','corporate_id':1})
        text=source.units[0]['text']; locator=source.units[0]['locator']
        claim={'claim_id':'f1','section_id':'company_profile','statement':'Ficta is the governed display name.',
           'evidence_kind':'grounded_external','as_of_date':None,'confidence':'high','inference':False,
           'citation_locators':[locator],'evidence_qualifiers':[],'semantic_context':semantic(),
           'evidence_quotes':[{'locator':locator,'quote':text}]}
        return inputs,source,claim
    def test_valid_sibling_survives_missing_source_and_ambiguous_quote(self):
        inputs,source,good=self.source()
        missing={**good,'claim_id':'f2','evidence_quotes':[{'locator':'https://unretrieved.example','quote':'fiction'}]}
        ambiguous={**good,'claim_id':'f3','evidence_quotes':[{'locator':good['citation_locators'][0],'quote':'"'}]}
        payload={'role':'portfolio_researcher','claims':[good,missing,ambiguous]}
        value,citations=source.verify_source_claims(payload)
        projection=project_role_claim_evidence(role='portfolio_researcher',pass_number=1,payload=value,citations=citations)
        self.assertEqual(1,len(inputs.requests)); self.assertEqual(1,len(projection.accepted_claims))
        self.assertEqual(2,len(projection.withheld_claims))
        self.assertTrue(projection.accepted_claims[0]['source_spans'])
        self.assertEqual(good['evidence_quotes'][0]['quote'],projection.accepted_claims[0]['source_spans'][0]['quote'])
    def test_corrupt_toolkit_offset_cannot_become_accepted_evidence(self):
        _,source,claim=self.source(corrupt=True)
        with self.assertRaisesRegex(ValueError,'toolkit_result_invalid'):
            source.verify_source_claims({'claims':[claim]})
    def test_backup_cannot_change_exact_quotes(self):
        _,_,claim=self.source()
        payload={'claims':[claim],'sections':[],'uncertainties':[]}; changed=copy.deepcopy(payload)
        changed['claims'][0]['evidence_quotes'][0]['quote']='invented'
        with self.assertRaises(ValueError):
            require_repair_preserves_claim_evidence_v0_1_26(payload,changed,role='portfolio_researcher')

class Change:
    def __init__(self,text=''): self.text=text; self.citations=[]
    def rename_title(self,title): self.title=title; return self
    def replace_section(self,path,text): self.text=text; return self
    def add_citation(self,path,citation): self.citations.append(citation); return self

class Handle:
    def __init__(self,store,key,mutable=False): self.store=store; self.key=key; self.mutable=mutable
    def provenance(self):
        package='sha256:'+sha256((self.read()+self.store[self.key].get('resource','')).encode()).hexdigest()
        return SimpleNamespace(mutable=self.mutable,package_digest=package,snapshot_id='fixture:'+package)
    def read(self): return self.store[self.key]['text']
    def content_digest(self): return 'sha256:'+sha256(self.read().encode()).hexdigest()
    def has_section(self,name): return True
    def section_text(self,name): return self.read().strip()
    def find_sections(self,name): return [SimpleNamespace(path=name)]
    def new_changeset(self): return Change()
    def preview(self,changes):
        return SimpleNamespace(diff=SimpleNamespace(old_digest=self.content_digest(),new_digest='sha256:'+sha256(changes.text.encode()).hexdigest()))
    def apply(self,changes,*,expected_digest):
        assert self.mutable and self.content_digest()==expected_digest
        if self.store[self.key].get('deny'): raise RuntimeError('fixture denial')
        before=self.content_digest(); self.store[self.key]['text']=changes.text
        receipt=SimpleNamespace(change_id='fixture-'+str(self.key),before_content_digest=before,after_content_digest=self.content_digest())
        self.store[self.key]['receipt']=receipt
        return receipt
    def history(self,limit):
        return SimpleNamespace(latest_change=lambda:self.store[self.key]['receipt'])

class ApplyInputs(ContractFollowingInputs):
    def __init__(self):
        super().__init__(); self['variables']['memory_mode']='apply'; self.mutables=[]; self.agent_count=0
        self.store={(cid,role):{'text':'Before '+role+'\n'} for cid in self['variables']['company_ids'] for role in ('company_memory','company_methodology')}
    def invoke_agent(self,*args,**kwargs): self.agent_count+=1; raise AssertionError('apply must not call Agents')
    def dynamic_skill(self,role,*,variables):
        mutable=role.endswith('_update'); role=role.removesuffix('_update')
        if mutable:self.mutables.append(role)
        return Handle(self.store,(int(variables['company_id']),role),mutable)

def reviewed(inputs):
    companies=[]
    for cid in inputs['variables']['company_ids']:
        proposals={}
        for name,role,section in (('memory','company_memory',legacy.MEMORY_TARGET_SECTION),
                                 ('methodology','company_methodology',legacy.METHODOLOGY_LEARNING_SECTION)):
            text='Reviewed '+role+'\n'
            proposals[name+'_proposal']={'target_section':section,'replacement_text':text,
               'replacement_sha256':'sha256:'+sha256(text.encode()).hexdigest(),
               'baseline_content_digest':Handle(inputs.store,(cid,role)).content_digest(),
               'baseline_package_digest':Handle(inputs.store,(cid,role)).provenance().package_digest,
               'baseline_snapshot_id':Handle(inputs.store,(cid,role)).provenance().snapshot_id}
        proposals['memory_proposal'].update(pre_review_candidate_eligible=True,fact_ids=['f1'])
        companies.append({'company_id':cid,'preparation_status':'review_pending','apply_authority':False,**proposals,
          'memory_apply_citations':[{'locator':'company_context:'+str(cid),'title':'Fixture','source_kind':'business_reference'}],
          'benchmark':{'projected':{'company_id':cid}}})
    packet={'schema_version':'pharma_prepared_review.v2','asset_identity':'nusaibah.pharma_company_intelligence_lab:0.1.26',
        'apply_authority':False,'fixed_methodology_digest':'fixture-methodology','companies':companies}
    packet['packet_sha256']='sha256:'+sha256(canonical(packet)).hexdigest()
    provenance={'source':'retained_asset_output','authority':'core_artifact','run_uuid':'00000000-0000-0000-0000-000000000001',
        'asset_identity':packet['asset_identity'],'output_role':'intelligence_dossier','checksum_sha256':'a'*64}
    inputs['reviewed_result']={'value':{'business_result_state':'review_pending','review_packet':packet},'provenance':provenance}
    inputs['variables']['review_decision']={'schema_version':'pharma_independent_review.v1','decision':'approve',
       'reviewer_name':'Fixture Reviewer','qualification_basis':'Deterministic test fixture, not a live review',
       'source_run_uuid':provenance['run_uuid'],'source_checksum_sha256':provenance['checksum_sha256'],
       'packet_sha256':packet['packet_sha256'],'companies':[{'company_id':c['company_id'],
       'memory_replacement_sha256':c['memory_proposal']['replacement_sha256'],
       'methodology_replacement_sha256':c['methodology_proposal']['replacement_sha256'],'approved_fact_ids':['f1']} for c in companies]}
    return inputs

class FinalApplyTests(unittest.TestCase):
    def invoke(self,inputs):
        request=legacy.validate_batch_request(inputs)
        with patch.object(legacy,'load_methodology',return_value=SimpleNamespace(package_digest='fixture-methodology')):
            return apply_reviewed(inputs,request,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.26')
    def test_reviewed_exact_apply_checks_real_receipt_readback_and_no_agents(self):
        inputs=reviewed(ApplyInputs()); response=self.invoke(inputs)
        result=response['outputs']['intelligence_dossier']; self.assertTrue(result['publication_complete'])
        self.assertEqual(0,inputs.agent_count)
        for row in result['company_results']:
            for role in ('memory','methodology'):
                self.assertTrue(row[role]['readback_verified']); self.assertTrue(row[role]['history_verified'])
    def test_changed_review_and_changed_packet_are_rejected_before_mutable_handles(self):
        for field in ('packet_sha256','source_checksum_sha256'):
            inputs=reviewed(ApplyInputs()); inputs['variables']['review_decision'][field]='altered'
            with self.assertRaises(ReviewedApplyError):self.invoke(inputs)
            self.assertEqual([],inputs.mutables)
        inputs=reviewed(ApplyInputs()); inputs['reviewed_result']['value']['review_packet']['companies'][0]['memory_proposal']['replacement_text']='altered'
        with self.assertRaises(ReviewedApplyError):self.invoke(inputs)
        self.assertEqual([],inputs.mutables)
    def test_second_company_stale_baseline_stops_before_first_commit(self):
        inputs=reviewed(ApplyInputs()); last=inputs['variables']['company_ids'][-1]
        inputs.store[(last,'company_memory')]['text']='Concurrent change\n'
        with self.assertRaises(ReviewedApplyError):self.invoke(inputs)
        self.assertEqual([],inputs.mutables)
    def test_resource_only_change_rejects_review_before_first_mutable_handle(self):
        inputs=reviewed(ApplyInputs()); last=inputs['variables']['company_ids'][-1]
        inputs.store[(last,'company_memory')]['resource']='Changed resource with identical SKILL text'
        with self.assertRaises(ReviewedApplyError):self.invoke(inputs)
        self.assertEqual([],inputs.mutables)
    def test_partial_commit_is_reported_and_not_retried_or_rolled_back(self):
        inputs=reviewed(ApplyInputs()); cid=inputs['variables']['company_ids'][0]
        inputs.store[(cid,'company_methodology')]['deny']=True
        result=self.invoke(inputs)['outputs']['intelligence_dossier']
        self.assertFalse(result['publication_complete']); self.assertEqual('partial_or_unconfirmed',result['status'])
        first=result['company_results'][0]
        self.assertEqual('applied',first['memory']['status']); self.assertIsNotNone(first['memory']['change_id'])
        self.assertEqual('apply_failed_or_unconfirmed',first['methodology']['status'])

class FullPreviewInputs(ContractFollowingInputs):
    def __init__(self):
        super().__init__(); self.toolkit_requests=[]; self.role_calls=[]
    def open_reference(self,target,*,mode):
        raise PublicReferenceError('public_reference_fixture_unavailable')
    def invoke_asset(self,role,*,variables,on_error):
        self.toolkit_requests.append(variables)
        return {'status':'success','result':execute_operation(variables)}
    def invoke_agent(self,role,*,input,on_error='raise'):
        self.role_calls.append(role)
        envelope=super().invoke_agent(role,input=input,on_error=on_error)
        if role in ('portfolio_researcher','market_researcher','regulatory_risk_researcher'):
            value=envelope['result']['content'][0]['value']
            value['schema_version']='pharma_research_agent.v3'
            source=input['retrieved_sources'][0]
            for claim in value['claims']:
                claim['semantic_context']['schema_version']='pharma_claim_semantic_context.v2'
                claim['semantic_context']['relationship_kind']='bilateral' if claim['semantic_context'].get('counterparty') else 'none'
                claim['citation_locators']=[source['locator']]
                claim['evidence_quotes']=[{'locator':source['locator'],'quote':source['text']}]
        return envelope

class FullPreviewTests(unittest.TestCase):
    def test_source_preflight_checks_real_toolkit_path_without_agents_or_publication_authority(self):
        inputs=FullPreviewInputs(); inputs['variables']['preflight_only']=True
        response=invoke_v0_1_26(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.26')
        dossier=response['outputs']['intelligence_dossier']
        self.assertEqual('source_preflight',dossier['business_result_state'])
        self.assertIs(False,dossier['apply_authority']); self.assertEqual([],inputs.role_calls)
        self.assertTrue(all(c['toolkit_spans_verified'] for c in dossier['company_results']))
    def test_two_company_two_pass_preview_retains_exact_quotes_and_methodology(self):
        inputs=FullPreviewInputs()
        with patch.object(legacy,'_agent_citations',side_effect=_fake_citations):
            response=invoke_v0_1_26(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.26')
        dossier=response['outputs']['intelligence_dossier']
        self.assertEqual('review_pending',dossier['business_result_state'])
        self.assertLessEqual(len(inputs.toolkit_requests),8)
        self.assertEqual(0,response['metrics']['memory_mutations_made'])
        for row,packet in zip(dossier['company_results'],dossier['review_packet']['companies']):
            self.assertEqual(['validated','validated'],[p['status'] for p in row['portfolio_review_trace']])
            self.assertTrue(row['accepted_claim_count']>0)
            self.assertTrue(packet['retrieved_source_snapshot'])
            self.assertTrue(all(c['source_spans'] for c in packet['accepted_claims']))
    def test_three_pass_request_over_budget_is_rejected_before_agents(self):
        inputs=FullPreviewInputs(); inputs['variables']['portfolio_review_passes']=3
        with self.assertRaisesRegex(ValueError,'eight-child-call budget'):
            invoke_v0_1_26(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.26')
        self.assertEqual([],inputs.toolkit_requests)

class FullCycleInputs(FullPreviewInputs):
    def __init__(self):
        super().__init__()
        self.store={(cid,role):{'text':'Before '+role+'\n'} for cid in self['variables']['company_ids'] for role in ('company_memory','company_methodology')}
        self.mutables=[]
    def dynamic_skill(self,role,*,variables):
        mutable=role.endswith('_update'); role=role.removesuffix('_update')
        if mutable:self.mutables.append(role)
        return Handle(self.store,(int(variables['company_id']),role),mutable)

class FullCycleTests(unittest.TestCase):
    def test_prepare_review_apply_readback_cycle_uses_exact_candidate_without_new_agents(self):
        inputs=FullCycleInputs(); identity='nusaibah.pharma_company_intelligence_lab:0.1.26'
        with patch.object(legacy,'_agent_citations',side_effect=_fake_citations):
            preview=invoke_v0_1_26(inputs,asset_identity=identity)
        dossier=preview['outputs']['intelligence_dossier']; packet=dossier['review_packet']
        self.assertEqual('review_pending',dossier['business_result_state'])
        self.assertTrue(all(c['memory_proposal']['pre_review_candidate_eligible'] for c in packet['companies']))
        count=len(inputs.role_calls)
        run='00000000-0000-0000-0000-000000000001'
        inputs['variables']['memory_mode']='apply'
        inputs['reviewed_result']={'value':dossier,'provenance':{'source':'retained_asset_output','authority':'core_artifact',
            'run_uuid':run,'asset_identity':identity,'output_role':'intelligence_dossier','checksum_sha256':'a'*64}}
        inputs['variables']['review_decision']={'schema_version':'pharma_independent_review.v1','decision':'approve',
           'reviewer_name':'Fixture Reviewer','qualification_basis':'Fixture, not live approval',
           'source_run_uuid':run,'source_checksum_sha256':'a'*64,'packet_sha256':packet['packet_sha256'],
           'companies':[{'company_id':c['company_id'],'approved_fact_ids':c['memory_proposal']['fact_ids'],
              'memory_replacement_sha256':c['memory_proposal']['replacement_sha256'],
              'methodology_replacement_sha256':c['methodology_proposal']['replacement_sha256']} for c in packet['companies']]}
        applied=invoke_v0_1_26(inputs,asset_identity=identity)['outputs']['intelligence_dossier']
        self.assertTrue(applied['publication_complete'])
        self.assertEqual(count,len(inputs.role_calls))
        for row,company in zip(applied['company_results'],packet['companies']):
            for name,role in (('memory','company_memory'),('methodology','company_methodology')):
                self.assertEqual(company[name+'_proposal']['replacement_text'],inputs.store[(row['company_id'],role)]['text'])
                self.assertTrue(row[name]['readback_verified'])
                self.assertTrue(row[name]['history_verified'])

if __name__=='__main__':unittest.main()
