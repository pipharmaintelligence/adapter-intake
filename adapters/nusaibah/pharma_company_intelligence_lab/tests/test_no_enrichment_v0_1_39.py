"""Expected evidence gaps finish without synthesizing or publishing unsupported facts."""
import copy,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_source_parity_v0_1_35 import Inputs,legacy,_fake_citations
from orchestration_v0_1_39 import invoke_v0_1_39
from no_enrichment_v0_1_39 import complete_no_enrichment,no_enrichment_publication
from devtools.dynamic_skill_runtime import DynamicSkillRuntimeError


class NoSupportedEvidence(Inputs):
    def invoke_agent(self,role,*,input,on_error='raise'):
        response=super().invoke_agent(role,input=input,on_error=on_error)
        if role==legacy.CRITIC_ROLE and input['company_id']==13:
            value=response['result']['content'][0]['value']
            value['recommendation']='fail'
            value['citation_coverage']['status']='insufficient'
        return response


def invoke(inputs):
    with patch.object(legacy,'_agent_citations',side_effect=_fake_citations):
        return invoke_v0_1_39(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.39')


class NoEnrichmentTests(unittest.TestCase):
    def test_no_supported_company_completes_without_synthesis_or_mutation(self):
        inputs=NoSupportedEvidence();before=copy.deepcopy(inputs.store)
        result=invoke(inputs);dossier=result['outputs']['intelligence_dossier']
        self.assertEqual('success',result['status']);self.assertTrue(dossier['publication_complete'])
        self.assertEqual(0,dossier['failed_company_count'])
        rows={r['company_id']:r for r in dossier['company_results']}
        noop=rows[13];self.assertEqual('no_change',noop['business_result_state'])
        self.assertEqual(0,noop['accepted_claim_count']);self.assertFalse(noop['quality_gate_passed'])
        self.assertTrue(noop['research_incomplete']);self.assertEqual('no_change',noop['review_outcome'])
        for receipt in noop['skill_publication']['memory'],noop['skill_publication']['methodology']:
            self.assertEqual('no_change',receipt['status']);self.assertFalse(receipt['write_attempted'])
            self.assertTrue(receipt['no_change_verified']);self.assertFalse(receipt['readback_verified'])
            self.assertIsNone(receipt['upload_id']);self.assertIsNone(receipt['change_id'])
        self.assertEqual(before[(13,'company_memory')],inputs.store[(13,'company_memory')])
        self.assertEqual(before[(13,'company_methodology')],inputs.store[(13,'company_methodology')])
        self.assertFalse(any(role==legacy.SYNTHESIS_ROLE and cid==13 for role,cid,_ in inputs.agent_inputs))

    def test_supported_review_uses_the_unchanged_publication_path(self):
        row=invoke(Inputs())['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertEqual('applied',row['skill_publication']['memory']['status'])

    def test_empty_delta_does_not_create_an_empty_first_memory(self):
        from test_first_publication_v0_1_38 import Inputs as PublicationInputs,state
        from automatic_publication_v0_1_39 import publish_company
        inputs=PublicationInputs();candidate=state()
        candidate['memory_candidate'].fact_ids=()
        candidate['result']['section_enrichment']['added_fact_ids']=[]
        result=publish_company(inputs,candidate)
        self.assertTrue(result['publication_complete'])
        self.assertEqual('no_change',result['memory']['status'])
        self.assertEqual([],inputs.initializations);self.assertEqual({},inputs.store)

    def test_absent_skill_packages_are_not_created_for_a_no_change_review(self):
        class FirstRun(NoSupportedEvidence):
            def dynamic_skill(self,role,*,variables):
                if variables['company_id']=='13':
                    if role.endswith('_update'):raise AssertionError('No-change must not request write authority')
                    raise DynamicSkillRuntimeError('dynamic_skill_not_initialized')
                return super().dynamic_skill(role,variables=variables)
        rows=invoke(FirstRun())['outputs']['intelligence_dossier']['company_results']
        noop=next(r for r in rows if r['company_id']==13)
        self.assertTrue(noop['skill_publication']['publication_complete'])
        self.assertFalse(noop['memory_initialized']);self.assertFalse(noop['memory_initialization_required'])
        self.assertIsNone(noop['memory_after_digest'])

    def test_schema_exhaustion_and_unresolved_critic_are_not_relabelled_as_no_change(self):
        diagnostic={'rule':'no_supported_enrichment_after_section_critic','stage':'pre_synthesis_quality'}
        for extra in ({'agent_schema_incomplete':True},{'unresolved_agent_responses':[{'rule':'invalid_schema'}]}):
            state={'result':extra,'progress':{'research':{'portfolio_researcher':{}},'critic':{}}}
            self.assertFalse(complete_no_enrichment(state,diagnostic))
        state={'result':{},'progress':{'research':{'portfolio_researcher':{}},
               'critic':{'section_outcomes':[{'status':'unresolved'}]}}}
        self.assertFalse(complete_no_enrichment(state,diagnostic))

    def test_unrelated_exception_rules_remain_unchanged(self):
        state={'result':{},'progress':{'research':{'portfolio_researcher':{}}}}
        self.assertFalse(complete_no_enrichment(state,{'rule':'candidate_fact_id_unknown','stage':'pre_synthesis_quality'}))
        self.assertNotIn('no_supported_enrichment',state)

    def test_validated_research_with_no_claims_finishes_as_no_change(self):
        state={'result':{'issues_annex':{}},'progress':{
            'research':{role:{} for role in legacy.RESEARCH_ROLES},'joined_research':{'claims':[]}}}
        self.assertTrue(complete_no_enrichment(state,{'rule':'no_usable_research_evidence',
                                                    'stage':'pre_synthesis_quality'}))
        self.assertEqual(0,state['result']['accepted_claim_count'])
        self.assertFalse(state['incomplete_schema_preview'])

    def test_real_skill_read_failures_are_not_silenced(self):
        class Denied:
            def dynamic_skill(self,*args,**kwargs):raise DynamicSkillRuntimeError('dynamic_skill_delivery_failed')
        state={'company_id':13,'no_supported_enrichment':True,'memory_mutation_eligible':False,
               'result':{'accepted_claim_count':0}}
        with self.assertRaises(DynamicSkillRuntimeError):no_enrichment_publication(Denied(),state)

    def test_new_agent_and_skill_contracts_equal_the_released_contracts(self):
        import json
        old=json.loads((ROOT/'tests/fixtures/release-0.1.38/nusaibah_pharma_company_intelligence_lab.asset.json').read_text())['versions']['0.1.38']
        new=json.loads((ROOT/'tests/fixtures/release-0.1.39/nusaibah_pharma_company_intelligence_lab.asset.json').read_text())['versions']['0.1.39']
        for field in ('agents','runtime_skills','inputs','outputs','execution'):
            self.assertEqual(old.get(field),new.get(field),field)

if __name__=='__main__':unittest.main()
