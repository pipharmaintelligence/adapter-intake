"""Continuation keeps paid siblings and true write errors distinct."""
import copy,json,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_source_parity_v0_1_35 import Inputs,legacy,_fake_citations
from test_no_enrichment_v0_1_39 import invoke
from agent_chunks_v0_1_39 import ChunkCoordinator
from continuation_v0_1_39 import admit_retention,review_annex,allow_incomplete_continuation
from devtools.runtime_agent_invocation import RuntimeAgentInvocationError


class ContinuationTests(unittest.TestCase):
    def test_two_companies_keep_their_own_phase_budget(self):
        inputs=Inputs();inputs['variables']['company_ids']=[13,14]
        inputs.set_company_records([{'id':13,'company':'Tabuk Pharmaceuticals','country':'SA'},
                                  {'id':14,'company':'SPIMACO','country':'SA'}])
        for role in ('company_memory','company_methodology'):
            inputs.store[(14,role)]=copy.deepcopy(inputs.store[(13,role)])
        result=invoke(inputs)['outputs']['intelligence_dossier']
        self.assertTrue(result['execution_complete']);self.assertTrue(result['continuation_allowed'])
        self.assertEqual(0,result['failed_company_count'])
        proof=result['company_results'][0]['agent_input_preflight']
        self.assertEqual('company',proof['role_call_budget_scope'])
        self.assertLessEqual(proof['provider_dispatch_count'],48)
        self.assertLessEqual(proof['observed_peak_parallel_calls'],2)

    def test_first_company_role_ceiling_does_not_starve_second_company(self):
        engine=ChunkCoordinator()
        for company_id in (13,14):
            for _ in range(10):
                engine.dispatch(legacy.CRITIC_ROLE,{'company_id':company_id},lambda:None)
        self.assertEqual(20,engine.calls)
        self.assertEqual(10,engine.company_role_dispatches[(14,legacy.CRITIC_ROLE)])

    def test_exhausted_planner_section_does_not_erase_other_sections(self):
        class Partial(Inputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                if role==legacy.PLANNER_ROLE and input.get('planner_chunk',{}).get('section_id')=='company_profile':
                    raise RuntimeAgentInvocationError('agent_execution_provider_member_refresh_failed')
                return super().invoke_agent(role,input=input,on_error=on_error)
        inputs=Partial();row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['research_incomplete']);self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertNotIn('company_profile',row['section_enrichment']['sections'])
        self.assertTrue(row['issues_annex']['items'])

    def test_all_planners_exhausted_retain_incomplete_and_do_not_write(self):
        class Unplanned(Inputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                if role==legacy.PLANNER_ROLE:raise RuntimeAgentInvocationError('agent_execution_provider_member_refresh_failed')
                return super().invoke_agent(role,input=input,on_error=on_error)
        inputs=Unplanned();dossier=invoke(inputs)['outputs']['intelligence_dossier'];row=dossier['company_results'][0]
        self.assertTrue(dossier['execution_complete']);self.assertTrue(dossier['continuation_allowed'])
        self.assertFalse(dossier['publication_complete']);self.assertEqual([],inputs.mutables)
        self.assertEqual('Annex: Need Review',row['issues_annex']['title'])

    def test_exhausted_research_contract_does_not_raise_none_type(self):
        import research_execution_v0_1_39 as research
        from research_response_contract_v0_1_26 import ResearchResponseContractError
        inputs=Inputs();original=research.validate_research_payload_v0_1_26
        def invalid(value,**kwargs):
            if kwargs['role']=='portfolio_researcher':
                raise ResearchResponseContractError(role=kwargs['role'],rule='fixture_invalid',field='claims')
            return original(value,**kwargs)
        diagnostic=legacy.evidence_diagnostic(role='portfolio_researcher',stage='research_json',
                                             rule='invalid_schema',field='claims')
        with patch.object(research,'validate_research_payload_v0_1_26',side_effect=invalid),\
             patch.object(research,'_repair_research_response_v0_1_26',return_value=(None,[],diagnostic)):
            value=invoke(inputs)
        self.assertEqual('success',value['status'])
        self.assertTrue(value['outputs']['intelligence_dossier']['company_results'][0]['research_incomplete'])

    def test_oversize_company_cannot_erase_a_fitting_sibling(self):
        large={'company_id':13,'result':{'company_id':13,'sections':'x'*500000}}
        small={'company_id':14,'result':{'company_id':14,'sections':'fitting validated work'}}
        engine=SimpleNamespace(proof=lambda:{})
        forwarded=SimpleNamespace(observations=[],invocation_issues=[])
        admit_retention([large,small],engine,forwarded)
        self.assertTrue(large['incomplete_schema_preview'])
        self.assertEqual('fitting validated work',small['result']['sections'])
        self.assertNotIn('incomplete_schema_preview',small)
        self.assertFalse(large['result']['retention_admission']['candidate_truncated'])

    def test_annex_is_one_compact_table_with_paragraph_reference_and_no_quote(self):
        text='First paragraph.\n\nSecond paragraph.'
        state={'company_id':13,'result':{},'progress':{'retrieved_source_snapshot':{
            'source_units':[{'locator':'https://example.test/source','text':text}]},
            'joined_research':{'claims':[{'section_id':'company_profile','source_spans':[
                {'locator':'https://example.test/source','start':18,'end':35,'quote':'Second paragraph.'}]}]},
            'critic':{'section_outcomes':[{'section_id':'company_profile','status':'needs_enrichment'}]}}}
        annex=review_annex(state,SimpleNamespace(proof=lambda:{'outcomes':[]}))
        self.assertEqual(2,annex['items'][0]['paragraph']);self.assertEqual('[1]',annex['items'][0]['citation'])
        self.assertEqual('Annex: Need Review',annex['title'])
        self.assertNotIn('Second paragraph.',json.dumps(annex));self.assertNotIn('quote',json.dumps(annex))

    def test_mutation_failure_or_acknowledged_commit_is_not_a_skip(self):
        for status in ('apply_failed_or_unconfirmed','initialized_readback_unverified','committed_readback_unverified'):
            publication={'publication_complete':False,'memory':{'status':status,'upload_id':1},
                         'methodology':None}
            self.assertNotIn('continuation_allowed',allow_incomplete_continuation(publication))

    def test_source_claim_and_toolkit_quotas_are_scoped_diagnostics(self):
        from source_evidence_v0_1_39 import SourceEvidenceInputs
        source=SourceEvidenceInputs(Inputs(),record={'company_id':13,'corporate_id':1,'company_name':'Fixture'})
        with self.assertRaises(legacy.UnresolvedAgentResponse) as claims:
            source.verify_source_claims({'role':'portfolio_researcher','claims':[{}]*17})
        self.assertEqual('pharma_source_claim_limit',claims.exception.diagnostic['rule'])
        unit=source.units[0];source.toolkit_calls=32
        claim={'claim_id':'fixture','citation_locators':[unit['locator']],
               'evidence_quotes':[{'locator':unit['locator'],'quote':unit['text']}]}
        with self.assertRaises(legacy.UnresolvedAgentResponse) as calls:
            source.verify_source_claims({'role':'portfolio_researcher','claims':[claim]})
        self.assertEqual('pharma_source_toolkit_call_limit',calls.exception.diagnostic['rule'])

    def test_no_synthesis_and_invalid_candidate_remain_completed_incomplete(self):
        from candidate_validation_v0_1_21 import CandidateContractError
        for failure in (legacy.UnresolvedAgentResponse(legacy.evidence_diagnostic(role=legacy.SYNTHESIS_ROLE,
                            stage='chunk_consolidation',field='chunks',rule='no_validated_synthesis_chunks')),
                        CandidateContractError(rule='candidate_fact_id_unknown',field='memory_candidate.fact_ids')):
            inputs=Inputs()
            with patch('company_preparation_v0_1_39.run_synthesis',side_effect=failure,create=True):
                # run_synthesis is a function-local import; patch its owning helper.
                with patch('downstream_chunks_v0_1_33.run_synthesis',side_effect=failure):
                    value=invoke(inputs)
            dossier=value['outputs']['intelligence_dossier']
            self.assertTrue(dossier['execution_complete']);self.assertTrue(dossier['continuation_allowed'])
            self.assertFalse(dossier['publication_complete']);self.assertEqual([],inputs.mutables)

if __name__=='__main__':unittest.main()
