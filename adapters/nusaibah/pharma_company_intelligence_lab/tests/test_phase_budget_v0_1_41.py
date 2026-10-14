"""No-provider proof of critic priority, fair discovery and bounded heavy work."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from test_grounded_profile_v0_1_40 import Inputs,NativeInputs
from test_orchestration_preview import _fake_citations
from test_invocation_revival_v0_1_30 import invalid_json
import legacy_preparation_helpers_v0_1_23 as legacy
from agent_chunks_v0_1_41 import ChunkCoordinator
from orchestration_v0_1_41 import invoke_v0_1_41
from devtools.runtime_agent_invocation import RuntimeAgentInvocationError


def invoke(inputs):
    with patch.object(legacy,'_agent_citations',side_effect=_fake_citations):
        return invoke_v0_1_41(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.41')


class PhaseBudgetTests(unittest.TestCase):
    def test_complete_publication_runs_criticism_before_optional_presentation(self):
        inputs=Inputs()
        row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'],row['skill_publication'])
        self.assertLess(inputs.role_calls.index(legacy.CRITIC_ROLE),inputs.role_calls.index(legacy.STRATEGIC_ROLE))
        self.assertGreater(row['accepted_claim_count'],0)
        self.assertTrue(row['methodology_feedback'])
        self.assertEqual(3300,row['agent_input_preflight']['execution_budget_seconds'])
        self.assertLessEqual(row['agent_input_preflight']['observed_peak_parallel_calls'],2)

    def test_critic_can_use_its_reserve_after_the_previous_global_cutoff(self):
        now=[0.0];coordinator=ChunkCoordinator(clock=lambda:now[0])
        now[0]=1042
        with self.assertRaises(legacy.UnresolvedAgentResponse):
            coordinator.dispatch(legacy.RESEARCH_ROLES[0],{'company_id':13},lambda:None)
        seen=[]
        coordinator.dispatch(legacy.CRITIC_ROLE,{'company_id':13},lambda:seen.append('critic'))
        self.assertEqual(['critic'],seen)
        self.assertEqual(180,coordinator.phase_admissions[0]['reserved_after_seconds'])

    def test_publication_reserve_and_absolute_budget_are_still_enforced(self):
        now=[0.0];coordinator=ChunkCoordinator(clock=lambda:now[0])
        now[0]=2000
        called=[]
        with self.assertRaises(legacy.UnresolvedAgentResponse):
            coordinator.dispatch(legacy.CRITIC_ROLE,{'company_id':13},lambda:called.append(True))
        self.assertEqual([],called)
        self.assertEqual(0,coordinator.calls)

    def test_slow_research_keeps_a_reviewed_sibling_and_does_not_stop_the_company(self):
        now=[0.0]
        class Slow(Inputs):
            advanced=False
            def invoke_agent(self,role,*,input,on_error='raise'):
                result=super().invoke_agent(role,input=input,on_error=on_error)
                if role in legacy.RESEARCH_ROLES and not self.advanced:
                    self.advanced=True;now[0]=1042
                return result
        real=ChunkCoordinator
        class Clocked(real):
            def __init__(self,**kwargs):super().__init__(clock=lambda:now[0],**kwargs)
        inputs=Slow();inputs['variables']['agent_chunk_parallelism']=1
        with patch('agent_chunks_v0_1_41.ChunkCoordinator',Clocked):
            row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertIn(legacy.CRITIC_ROLE,inputs.role_calls)
        self.assertTrue(row['research_incomplete'])
        self.assertGreater(row['accepted_claim_count'],0)
        self.assertTrue(row['skill_publication']['publication_complete'],row['skill_publication'])
        self.assertTrue(row['issues_annex']['items'])

    def test_discovery_interleaves_roles_before_supplemental_packets(self):
        inputs=Inputs();inputs['variables']['agent_chunk_parallelism']=1
        invoke(inputs)
        research=[r for r in inputs.role_calls if r in legacy.RESEARCH_ROLES]
        self.assertEqual(list(legacy.RESEARCH_ROLES),research[:3])

    def test_exhausted_optional_presentation_backup_preserves_critic_reviewed_facts(self):
        class Broken(Inputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                if role in {legacy.STRATEGIC_ROLE,legacy.SYNTHESIS_ROLE}:raise invalid_json()
                if role==legacy.RESEARCH_RESOLVER_ROLE and input['original_role'] in {legacy.STRATEGIC_ROLE,legacy.SYNTHESIS_ROLE}:raise invalid_json()
                return super().invoke_agent(role,input=input,on_error=on_error)
        row=invoke(Broken())['outputs']['intelligence_dossier']['company_results'][0]
        self.assertGreater(row['accepted_claim_count'],0)
        self.assertTrue(row['skill_publication']['publication_complete'],row['skill_publication'])
        self.assertTrue(row['issues_annex']['items'])

    def test_contract_time_expansion_is_new_and_historical_manifest_remains_pinned(self):
        current=json.loads((ROOT/'nusaibah_pharma_company_intelligence_lab.asset.json').read_text())
        prior=json.loads((ROOT/'tests/fixtures/release-0.1.40/nusaibah_pharma_company_intelligence_lab.asset.json').read_text())
        self.assertEqual('0.1.41',current['default'])
        self.assertEqual(prior['execution'],current['execution'])
        self.assertEqual(3600,current['versions']['0.1.41']['execution']['timeout_seconds'])
        self.assertEqual(prior['execution']['allowed_substrates'],current['versions']['0.1.41']['execution']['allowed_substrates'])
        self.assertEqual(1800,prior['execution']['timeout_seconds'])
        for role,agent in current['versions']['0.1.41']['agents'].items():
            old=prior['versions']['0.1.40']['agents'][role]
            self.assertNotEqual(old['contract_version'],agent['contract_version'])
            self.assertEqual(1200,agent['definition']['chain']['steps'][0]['provider_policy']['timeout_seconds'])
            self.assertEqual(600,old['definition']['chain']['steps'][0]['provider_policy']['timeout_seconds'])

    def test_exhausted_transport_is_local_and_does_not_spend_on_a_format_resolver(self):
        class Unavailable(Inputs):
            backups=0
            critic_has_claims=[]
            def invoke_agent(self,role,*,input,on_error='raise'):
                if role==legacy.RESEARCH_ROLES[0]:
                    raise RuntimeAgentInvocationError('agent_execution_provider_retry_exhausted',cause_code='provider_execution_transport_timeout')
                if role==legacy.RESEARCH_RESOLVER_ROLE:self.backups+=1
                if role==legacy.CRITIC_ROLE:self.critic_has_claims.append(bool(input['research_evidence']['claims']))
                return super().invoke_agent(role,input=input,on_error=on_error)
        inputs=Unavailable();row=invoke(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertEqual(0,inputs.backups)
        self.assertTrue(inputs.critic_has_claims[0])
        self.assertGreater(row['accepted_claim_count'],0)
        self.assertTrue(row['skill_publication']['publication_complete'],row['skill_publication'])
        self.assertTrue(row['issues_annex']['items'])

    def test_authority_failures_are_not_reclassified_as_optional_research_gaps(self):
        class Rejected(Inputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                if role in legacy.RESEARCH_ROLES:
                    raise RuntimeAgentInvocationError('agent_execution_provider_retry_exhausted',cause_code='provider_execution_vertex_credential_rejected')
                return super().invoke_agent(role,input=input,on_error=on_error)
        with self.assertRaises(RuntimeAgentInvocationError):invoke(Rejected())

    def test_complete_and_slow_terminal_rows_pass_the_real_retention_boundary(self):
        try:
            from devtools.preview_output_validator import validate_preview_outputs
        except ImportError:
            self.skipTest('Real runtime retention validator is tested in SDK qualification')
        result=invoke(Inputs())
        validate_preview_outputs(result['outputs'])

    def test_native_text_json_and_citation_output_pass_the_real_retention_boundary(self):
        try:
            from devtools.preview_output_validator import validate_preview_outputs
            from devtools.agent_citation_view import _validated_turns
        except ImportError:
            self.skipTest('Native citation and retention boundaries need the real SDK')
        inputs=NativeInputs();inputs.text_mode=True
        result=invoke_v0_1_41(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.41')
        validate_preview_outputs(result['outputs'])
        row=result['outputs']['intelligence_dossier']['company_results'][0]
        self.assertGreater(row['native_grounded_claim_count'],0)
        self.assertTrue(row['skill_publication']['publication_complete'],row['skill_publication'])


if __name__=='__main__':unittest.main()
