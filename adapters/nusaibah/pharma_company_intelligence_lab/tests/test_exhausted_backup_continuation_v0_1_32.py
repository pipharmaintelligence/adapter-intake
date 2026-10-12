"""End-to-end role exhaustion preserves only independently validated siblings."""
import copy,unittest
from unittest.mock import patch
from test_invocation_revival_v0_1_30 import BoundaryInputs,legacy,invalid_json
from test_orchestration_preview import _fake_citations
from orchestration_v0_1_32 import invoke_v0_1_32

def invoke(inputs):
    with patch.object(legacy,'_agent_citations',side_effect=_fake_citations):
        return invoke_v0_1_32(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.32')

class ExhaustedBackupContinuationTests(unittest.TestCase):
    def test_failed_research_and_backup_preserve_sibling_validation_and_publication(self):
        for role in legacy.RESEARCH_ROLES:
            with self.subTest(role=role):
                inputs=BoundaryInputs(role,backup_bad=True)
                result=invoke(inputs);rows=result['outputs']['intelligence_dossier']['company_results']
                self.assertEqual('success',result['status'])
                self.assertEqual(1,len(inputs.backups))
                self.assertEqual(1,rows[0]['agent_response_resolver_call_count'])
                self.assertTrue(rows[0]['research_incomplete'])
                self.assertGreater(rows[0]['accepted_claim_count'],0)
                self.assertTrue(rows[0]['skill_publication']['publication_complete'])
                self.assertTrue(rows[1]['skill_publication']['publication_complete'])
                self.assertEqual(4,len(rows[0]['section_enrichment_checks']))
                self.assertTrue(any(r==legacy.SYNTHESIS_ROLE and cid==13 for r,cid in inputs.dispatched))
                issues=rows[0]['unresolved_agent_responses']
                self.assertTrue(any(d['role']==role and d['rule']=='agent_result_json_object_invalid' for d in issues))
                for _,cid,payload in inputs.agent_inputs:
                    if cid==13 and isinstance(payload.get('research_evidence'),dict):
                        self.assertTrue(all(not claim['claim_id'].startswith(role+':') for claim in payload['research_evidence']['claims']))
                self.assertFalse(any(r==legacy.BENCHMARK_ROLE for r,_ in inputs.dispatched))

    def test_negative_critics_still_withhold_even_when_siblings_complete(self):
        inputs=BoundaryInputs('market_researcher',backup_bad=True,negative=True)
        result=invoke(inputs);row=result['outputs']['intelligence_dossier']['company_results'][0]
        self.assertEqual('success',result['status']);self.assertFalse(row['skill_publication']['publication_complete'])
        self.assertEqual(1,len(inputs.backups));self.assertEqual([],inputs.mutables)
        self.assertTrue(row['section_enrichment_checks'])

    def test_exhaustion_is_one_backup_per_original_not_per_company(self):
        class Both(BoundaryInputs):
            def __init__(self):super().__init__('market_researcher',backup_bad=True);self.failed_companies=set()
            def invoke_agent(self,role,*,input,on_error='raise'):
                if role=='market_researcher' and input['company_id'] not in self.failed_companies:
                    self.failed_companies.add(input['company_id']);self.failed=True;raise invalid_json()
                return super().invoke_agent(role,input=input,on_error=on_error)
        inputs=Both();result=invoke(inputs)
        self.assertEqual(2,len(inputs.backups))
        self.assertTrue(all(row['skill_publication']['publication_complete'] for row in result['outputs']['intelligence_dossier']['company_results']))
        self.assertTrue(all(row['agent_response_resolver_call_count']==1 for row in result['outputs']['intelligence_dossier']['company_results']))

    def test_authority_failure_is_not_content_exhaustion(self):
        from devtools.runtime_agent_invocation import RuntimeAgentInvocationError
        class Authority(BoundaryInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                if role=='market_researcher':raise RuntimeAgentInvocationError('scope rejected',cause_code='provider_execution_authority_scope_mismatch')
                return super().invoke_agent(role,input=input,on_error=on_error)
        inputs=Authority('unused')
        with self.assertRaises(RuntimeAgentInvocationError):invoke(inputs)
        self.assertEqual([],inputs.backups);self.assertEqual([],inputs.mutables)

if __name__=='__main__':unittest.main()
