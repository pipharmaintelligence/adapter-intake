import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from test_automatic_enrichment_v0_1_27 import EnrichmentInputs
from test_orchestration_preview import _fake_citations
from orchestration_v0_1_29 import invoke_v0_1_29
from benchmark_observation_v0_1_29 import observe_benchmark
import legacy_preparation_helpers_v0_1_23 as legacy

def invoke(inputs):
    with patch.object(legacy,'_agent_citations',side_effect=_fake_citations):
        return invoke_v0_1_29(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.29')

class BenchmarkDisabledTests(unittest.TestCase):
    def test_benchmark_never_calls_a_runtime_capability(self):
        class NoCapabilities:
            def __getattr__(self,name):raise AssertionError('disabled benchmark accessed '+name)
        with patch.object(legacy,'_run_benchmark',side_effect=AssertionError('benchmark must not execute')):
            result=observe_benchmark(NoCapabilities(),company_id=14)
        self.assertEqual('disabled',result['status']);self.assertFalse(result['scores_known'])
        self.assertEqual([],result['results'])

    def test_supported_enrichment_publishes_with_zero_benchmark_calls_or_backup(self):
        inputs=EnrichmentInputs()
        with patch.object(legacy,'_run_benchmark',side_effect=AssertionError('benchmark must not execute')):
            result=invoke(inputs)
        dossier=result['outputs']['intelligence_dossier'];self.assertTrue(dossier['publication_complete'])
        self.assertNotIn(legacy.BENCHMARK_ROLE,inputs.role_calls)
        self.assertNotIn(legacy.RESEARCH_RESOLVER_ROLE,inputs.role_calls)
        for row in dossier['company_results']:
            self.assertEqual('disabled',row['benchmark_observation']['status'])
            self.assertEqual(0,row['benchmark_agent_call_count']);self.assertFalse(row['benchmark_enabled'])
            self.assertIsNone(row['benchmark_non_regression'])
            self.assertIsNone(row['benchmark_before_covered_count']);self.assertIsNone(row['benchmark_after_covered_count'])
            self.assertEqual('applied',row['skill_publication']['memory']['status'])
            self.assertEqual('applied',row['skill_publication']['methodology']['status'])

    def test_all_active_role_json_wrappers_are_parsed_without_backup(self):
        class Wrapped(EnrichmentInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                envelope=super().invoke_agent(role,input=input,on_error=on_error)
                value=envelope['result']['content'][0]['value']
                envelope['result']['content'][0]['value']="\'\'\'```json\n"+json.dumps(value)+"\n```\'\'\'"
                return envelope
        inputs=Wrapped();dossier=invoke(inputs)['outputs']['intelligence_dossier']
        self.assertTrue(dossier['publication_complete'])
        self.assertNotIn(legacy.RESEARCH_RESOLVER_ROLE,inputs.role_calls)
        for row in dossier['company_results']:
            self.assertTrue(row['agent_response_recovery_trace'])
            self.assertFalse(row['agent_schema_incomplete'])

    def test_each_active_nonresearch_role_has_only_one_backup_and_preserves_sibling_company(self):
        fields={legacy.PLANNER_ROLE:'priority_rationale',legacy.STRATEGIC_ROLE:'implications',
            legacy.CRITIC_ROLE:'unmet_plan_requirements',legacy.SYNTHESIS_ROLE:'memory_candidate'}
        for failed_role,field in fields.items():
            with self.subTest(role=failed_role):
                class MissingField(EnrichmentInputs):
                    failed=False
                    def invoke_agent(self,role,*,input,on_error='raise'):
                        if role==legacy.RESEARCH_RESOLVER_ROLE:
                            self.role_calls.append(role)
                            self.agent_inputs.append((role,input['company_id'],copy.deepcopy(input)))
                            value=copy.deepcopy(input['invalid_response'])
                            return {'status':'completed','result':{'schema_version':'agent_result.v1','kind':'json',
                                'content':[{'type':'json','value':"\'\'\'"+json.dumps(value)+"\'\'\'"}]}}
                        envelope=super().invoke_agent(role,input=input,on_error=on_error)
                        if role==failed_role and input['company_id']==self['variables']['company_ids'][0] and not self.failed:
                            self.failed=True;del envelope['result']['content'][0]['value'][field]
                        return envelope
                inputs=MissingField();rows=invoke(inputs)['outputs']['intelligence_dossier']['company_results']
                self.assertEqual(1,inputs.role_calls.count(legacy.RESEARCH_RESOLVER_ROLE))
                if failed_role==legacy.CRITIC_ROLE:
                    self.assertTrue(rows[0]['skill_publication']['publication_complete'])
                    self.assertIn('unresolved',[o['status'] for o in rows[0]['section_enrichment_checks']])
                else:
                    self.assertFalse(rows[0]['skill_publication']['publication_complete'])
                self.assertTrue(rows[1]['skill_publication']['publication_complete'])
                backup=next(p for role,_,p in inputs.agent_inputs if role==legacy.RESEARCH_RESOLVER_ROLE)
                self.assertEqual(failed_role,backup['original_role'])
                self.assertEqual('business_json_format_only',backup['repair_scope'])

    def test_genuine_negative_critic_still_withholds_facts(self):
        class Negative(EnrichmentInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                envelope=super().invoke_agent(role,input=input,on_error=on_error)
                if role==legacy.CRITIC_ROLE:envelope['result']['content'][0]['value']['recommendation']='fail'
                return envelope
        inputs=Negative();result=invoke(inputs)
        self.assertFalse(result['outputs']['intelligence_dossier']['publication_complete']);self.assertEqual([],inputs.mutables)

    def test_active_role_authority_failure_is_never_suppressed(self):
        class Denied(EnrichmentInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                if role==legacy.PLANNER_ROLE:raise RuntimeError('authority denied')
                return super().invoke_agent(role,input=input,on_error=on_error)
        inputs=Denied()
        with self.assertRaisesRegex(RuntimeError,'authority denied'):invoke(inputs)
        self.assertEqual([],inputs.mutables)
if __name__=='__main__':unittest.main()
