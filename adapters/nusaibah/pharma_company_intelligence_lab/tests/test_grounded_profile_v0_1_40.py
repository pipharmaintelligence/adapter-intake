import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from test_source_parity_v0_1_35 import Inputs as PriorInputs
from test_orchestration_preview import _fake_citations
import legacy_preparation_helpers_v0_1_23 as legacy
from orchestration_v0_1_40 import invoke_v0_1_40
from methodology_learning_v0_1_40 import read_guidance,build_methodology_learning_proposal

class Inputs(PriorInputs):
    def invoke_agent(self,role,*,input,on_error='raise'):
        envelope=super().invoke_agent(role,input=input,on_error=on_error)
        if role in legacy.RESEARCH_ROLES:
            value=envelope['result']['content'][0]['value']
            allowed=(input.get('packing_scope') or {}).get('section_ids',input['planned_section_ids'])
            value['claims']=[c for c in value['claims'] if c['section_id'] in allowed]
        if role==legacy.CRITIC_ROLE:
            value=envelope['result']['content'][0]['value']
            rejected=set(value['unsupported_claim_ids'])|set(value['stale_claim_ids'])
            value['claim_reviews']=[{'claim_id':c['claim_id'],'decision':'unsupported' if c['claim_id'] in rejected else 'supported'} for c in input['research_evidence']['claims']]
            value['future_guidance']=[{'subsection_id':None,'observation':'The supplied evidence lacks a current dated primary report.',
                'next_action':'Locate the latest dated primary company report for this section.',
                'success_check':'Record the report date, exact entity and supporting source for each new claim.'}]
        return envelope


class NativeInputs(Inputs):
    text_mode=False
    def __init__(self):
        super().__init__()
        self.set_company_records([{'id':13,'company':'Tabuk Pharmaceuticals','country':'SA','website':'https://example.org/unavailable'}])
    def invoke_agent(self,role,*,input,on_error='raise'):
        envelope=super().invoke_agent(role,input=input,on_error=on_error)
        if role in legacy.RESEARCH_ROLES:
            value=envelope['result']['content'][0]['value']
            uri='https://example.org/primary/'+role
            for claim in value['claims']:
                claim['citation_locators']=[uri];claim['evidence_quotes']=[]
            envelope['result']['provider_metadata']['turns']=[{'provider_family':'vertex_ai','turn_index':0,
                'provider_schema':'vertex.generate_content.metadata.v1','native':{'candidate':{'groundingMetadata':{
                    'groundingChunks':[{'web':{'uri':uri,'title':'Dated primary fixture source'}}],
                    'groundingSupports':[{'segment':{'text':c['statement']},'groundingChunkIndices':[0]} for c in value['claims']]}}}}]
            if self.text_mode:
                text="'''```json\n"+json.dumps(value)+"\n```'''"
                envelope['result'].update(kind='text',text=text,content=[{'type':'text','text':text}])
        return envelope

def invoke(inputs):
    with patch.object(legacy,'_agent_citations',side_effect=_fake_citations):
        return invoke_v0_1_40(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.40')

class GroundedProfileTests(unittest.TestCase):
    def test_complete_fixture_preserves_publication_and_writes_real_critic_advice(self):
        inputs=Inputs();result=invoke(inputs);row=result['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'],row['skill_publication'])
        self.assertNotIn(legacy.PLANNER_ROLE,inputs.role_calls)
        self.assertNotIn(legacy.BENCHMARK_ROLE,inputs.role_calls)
        self.assertTrue(row['methodology_feedback'])
        self.assertTrue(read_guidance(inputs.store[(13,'company_methodology')]['text']))
        self.assertIn('Company Intelligence Update',inputs.store[(13,'company_memory')]['text'])

    def test_current_contracts_enable_grounding_without_modifying_old_release(self):
        current=json.loads((ROOT/'nusaibah_pharma_company_intelligence_lab.asset.json').read_text())['versions']['0.1.40']
        old=json.loads((ROOT/'tests/fixtures/release-0.1.39/nusaibah_pharma_company_intelligence_lab.asset.json').read_text())['versions']['0.1.39']
        for role in legacy.RESEARCH_ROLES:
            policy=current['agents'][role]['definition']['chain']['steps'][0]['provider_policy']
            self.assertTrue(policy['search_enabled']);self.assertEqual('provider_grounding',policy['search_mode'])
            self.assertEqual('text',policy['generation_policy']['response_format'])
            self.assertFalse(old['agents'][role]['definition']['chain']['steps'][0]['provider_policy']['search_enabled'])

    def test_native_grounding_survives_failed_optional_http_with_real_runtime_citation_projection(self):
        import devtools.agent_citation_view as view
        if not hasattr(view,'_validated_turns'):
            self.skipTest('Native citation qualification requires the real runtime, not the minimal citation stub')
        inputs=NativeInputs()
        result=invoke_v0_1_40(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.40')
        row=result['outputs']['intelligence_dossier']['company_results'][0]
        self.assertGreater(row['native_grounded_claim_count'],0)
        self.assertTrue(any(r['status']=='unavailable' for r in row['source_retrieval']))
        self.assertTrue(row['skill_publication']['publication_complete'],row['skill_publication'])
        self.assertEqual([],inputs.requests)
        self.assertIn('provider-grounded source',inputs.store[(13,'company_memory')]['text'])

    def test_real_text_kind_grounding_preserves_metadata_through_wrapped_json_parser(self):
        import devtools.agent_citation_view as view
        if not hasattr(view,'_validated_turns'):self.skipTest('Requires real runtime citation projection')
        inputs=NativeInputs();inputs.text_mode=True
        row=invoke_v0_1_40(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.40')['outputs']['intelligence_dossier']['company_results'][0]
        self.assertGreater(row['native_grounded_claim_count'],0)
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertNotIn(legacy.RESEARCH_RESOLVER_ROLE,inputs.role_calls)

    def test_format_repair_cannot_change_new_critic_decisions_or_feedback(self):
        from agent_response_recovery_v0_1_40 import require_preserved_business
        contract={'required_fields':['claim_reviews','future_guidance']}
        original={'claim_reviews':[{'claim_id':'f1','decision':'unsupported'}],
            'future_guidance':[{'subsection_id':None,'observation':'Original gap','next_action':'Verify dated source','success_check':'Exact evidence'}]}
        for field in ('claim_reviews','future_guidance'):
            changed=copy.deepcopy(original)
            if field=='claim_reviews':changed[field][0]['decision']='supported'
            else:changed[field][0]['next_action']='Invent a replacement'
            with self.assertRaises(ValueError):require_preserved_business(original,changed,contract=contract,role=legacy.CRITIC_ROLE)

    def test_negative_coverage_keeps_supported_claims_and_publishes_annex_and_guidance(self):
        class Partial(Inputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                envelope=super().invoke_agent(role,input=input,on_error=on_error)
                if role==legacy.CRITIC_ROLE:
                    value=envelope['result']['content'][0]['value']
                    value['recommendation']='fail';value['citation_coverage']['status']='insufficient'
                    value['missing_section_ids']=input['reviewed_section_ids']
                return envelope
        inputs=Partial();row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['research_incomplete']);self.assertGreater(row['accepted_claim_count'],0)
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertIn('### Annex: Need Review',inputs.store[(13,'company_memory')]['text'])
        self.assertIn('| Section / subsection | Paragraph | Issue | Ref. |',inputs.store[(13,'company_memory')]['text'])
        self.assertTrue(read_guidance(inputs.store[(13,'company_methodology')]['text']))

    def test_all_research_empty_can_still_publish_actionable_guidance_without_empty_memory(self):
        class Empty(Inputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                envelope=super().invoke_agent(role,input=input,on_error=on_error)
                if role in legacy.RESEARCH_ROLES:
                    envelope['result']['content'][0]['value']['claims']=[]
                return envelope
        inputs=Empty();before=inputs.store[(13,'company_memory')]['text']
        row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertEqual(before,inputs.store[(13,'company_memory')]['text'])
        self.assertEqual('no_change',row['skill_publication']['memory']['status'])
        self.assertEqual('applied',row['skill_publication']['methodology']['status'])

    def test_synthesis_failure_cannot_erase_reviewed_facts(self):
        class Broken(Inputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                if role in {legacy.SYNTHESIS_ROLE,legacy.RESEARCH_RESOLVER_ROLE}:
                    raise legacy.UnresolvedAgentResponse(legacy.evidence_diagnostic(role=role,stage='agent_response_payload',field='json',rule='invalid_schema'))
                return super().invoke_agent(role,input=input,on_error=on_error)
        inputs=Broken();row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertGreater(row['accepted_claim_count'],0)
        self.assertIn('Annex: Need Review',inputs.store[(13,'company_memory')]['text'])

    def test_next_run_consumes_prior_advice_by_section_and_deduplicates_it(self):
        inputs=Inputs();invoke(inputs);inputs.agent_inputs=[]
        before=inputs.store[(13,'company_methodology')]['text']
        row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['methodology_feedback_consumed'])
        self.assertEqual(before,inputs.store[(13,'company_methodology')]['text'])
        for role,_,payload in inputs.agent_inputs:
            for advice in payload.get('prior_critic_guidance',[]):
                sections=(payload.get('packing_scope') or {}).get('section_ids') or payload.get('reviewed_section_ids') or [c['section_id'] for c in payload.get('research_evidence',{}).get('claims',[])]
                self.assertIn(advice['section_id'],sections)

    def test_optional_reflection_reads_previous_memory_and_guidance_and_publishes_once(self):
        class Reflection(Inputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                self.assert_no_midrun_writes=not self.mutables
                if not self.assert_no_midrun_writes:raise AssertionError('Publication occurred before reflection completed')
                return super().invoke_agent(role,input=input,on_error=on_error)
        inputs=Reflection();inputs['variables']['portfolio_review_passes']=2
        row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertEqual(2,len(row['review_pass_trace']))
        self.assertTrue(row['skill_publication']['publication_complete'])
        second=[p for role,_,p in inputs.agent_inputs if role in legacy.RESEARCH_ROLES and p['review_iteration']['pass_number']==2]
        self.assertTrue(second)
        self.assertTrue(any(p['prior_critic_guidance'] for p in second))
        self.assertTrue(any(any('Company Intelligence Update' in s['text'] for s in p['retrieved_sources']) for p in second))
        self.assertEqual(2,inputs.mutables.count('company_memory'))
        self.assertEqual(2,inputs.mutables.count('company_methodology'))
        self.assertLessEqual(row['agent_input_preflight']['provider_dispatch_count'],48)

    def test_third_pass_respects_shared_budget_and_preserves_earlier_facts(self):
        inputs=Inputs();inputs['variables'].update(portfolio_review_passes=3,agent_chunk_max_calls=20)
        row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertGreater(row['accepted_claim_count'],0)
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertTrue(row['research_incomplete'])
        self.assertLessEqual(row['agent_input_preflight']['provider_dispatch_count'],20)
        self.assertIn('Annex: Need Review',inputs.store[(13,'company_memory')]['text'])

    def test_native_url_alone_is_not_evidence_and_actual_support_maps_redirect_without_guessing(self):
        from source_evidence_v0_1_40 import SourceEvidenceInputs
        from devtools.skill_citation import CitationRef
        source=SourceEvidenceInputs(Inputs(),record={'company_id':13,'company_name':'Fixture','corporate_id':1})
        uri='https://example.org/native-ref'
        ref=CitationRef(locator=uri,source_kind='agent_citation',provider_family='vertex_ai',provider_turn_index=0,
            source_pointer=('provider_metadata','turns',0,'native','candidate','groundingMetadata','groundingChunks',0))
        payload={'role':'portfolio_researcher','claims':[{'claim_id':'f1','statement':'Exact supported fixture claim.',
            'citation_locators':['https://example.org/model-written'],'evidence_quotes':[]}]}
        rejected,_=source.verify_source_claims(payload)
        self.assertEqual('runtime_grounding_or_readable_source_missing',rejected['claims'][0]['_source_issue'])
        metadata={'provider_metadata':{'turns':[{'provider_schema':'vertex.generate_content.metadata.v1','native':{'candidate':{'groundingMetadata':{
            'groundingChunks':[{'web':{'uri':uri}}],
            'groundingSupports':[{'segment':{'text':payload['claims'][0]['statement']},'groundingChunkIndices':[0]}]}}}}]}}
        admitted,_=source.verify_source_claims(payload,admitted=[ref],agent_result=metadata)
        claim=admitted['claims'][0]
        self.assertEqual([uri],claim['citation_locators']);self.assertTrue(claim['native_grounding']['provider_support_matched'])
        self.assertNotIn('source_spans',claim);self.assertEqual([],claim['evidence_quotes'])

    def test_exhausted_critic_backup_is_once_per_original_and_siblings_publish(self):
        from test_invocation_revival_v0_1_30 import invalid_json
        class Broken(Inputs):
            backups=0;originals=0
            def invoke_agent(self,role,*,input,on_error='raise'):
                if role==legacy.CRITIC_ROLE and input['reviewed_section_ids']==['company_profile']:
                    self.originals+=1;raise invalid_json()
                if role==legacy.RESEARCH_RESOLVER_ROLE:
                    self.backups+=1;raise invalid_json()
                return super().invoke_agent(role,input=input,on_error=on_error)
        inputs=Broken();row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertGreater(inputs.originals,0);self.assertEqual(inputs.originals,inputs.backups)
        self.assertTrue(row['research_incomplete']);self.assertGreater(row['accepted_claim_count'],0)
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertNotIn('company_profile',row['section_enrichment']['sections'])

    def test_large_memory_is_preserved_and_context_budget_is_local(self):
        inputs=Inputs();before='Existing protected memory.\n\n'*1600
        inputs.store[(13,'company_memory')]['text']=before
        row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertEqual(before,inputs.store[(13,'company_memory')]['text'])
        self.assertEqual('no_change',row['skill_publication']['memory']['status'])
        self.assertEqual('applied',row['skill_publication']['methodology']['status'])

    def test_concurrent_resource_change_prevents_overwrite(self):
        from automatic_publication_v0_1_40 import publish_company
        def concurrent(inputs,state):
            inputs.store[(13,'company_memory')]['resource']='changed archive resource'
            return publish_company(inputs,state)
        inputs=Inputs()
        with patch('orchestration_v0_1_40.publish_company',side_effect=concurrent):row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertFalse(row['skill_publication']['publication_complete']);self.assertEqual([],inputs.mutables)
        self.assertEqual('baseline_changed',row['skill_publication']['memory']['reason'])

    def test_resolved_guidance_stops_recurring_without_erasing_history(self):
        feedback={'section_id':'company_profile','subsection_id':'identity','origin':'section_critic',
            'observation':'Evidence lacks a current dated disclosure.','next_action':'Find a current primary disclosure.',
            'success_check':'A dated same-company disclosure supports the reviewed identity claim.'}
        before=build_methodology_learning_proposal('',feedback=[feedback]).candidate
        key=read_guidance(before)[0]['guidance_id']
        after=build_methodology_learning_proposal(before,feedback=[],resolved=[key]).candidate
        self.assertTrue(after.startswith(before));self.assertEqual([],read_guidance(after))
        self.assertEqual(after,build_methodology_learning_proposal(after,feedback=[feedback]).candidate)

    def test_new_memory_and_guidance_use_existing_sdk_initialization(self):
        try:
            from test_first_publication_v0_1_38 import Inputs as EmptyStore,state
        except unittest.SkipTest as error:self.skipTest(str(error))
        from automatic_publication_v0_1_40 import publish_company
        inputs=EmptyStore();candidate=state('Specific next research advice from a fixture critic.')
        candidate['critic'].update(reviewed_claim_ids=['f1'],rejected_claim_ids=[])
        result=publish_company(inputs,candidate)
        self.assertTrue(result['publication_complete'])
        self.assertEqual(['company_memory_update','company_methodology_update'],inputs.initializations)
        self.assertTrue(result['memory']['readback_verified']);self.assertTrue(result['methodology']['readback_verified'])

if __name__=='__main__':unittest.main()
