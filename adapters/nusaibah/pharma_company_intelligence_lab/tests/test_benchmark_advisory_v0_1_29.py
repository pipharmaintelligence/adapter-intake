import sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from test_automatic_enrichment_v0_1_27 import EnrichmentInputs
from test_orchestration_preview import _fake_citations
from orchestration_v0_1_29 import invoke_v0_1_29
import legacy_preparation_helpers_v0_1_23 as legacy

def invoke(inputs):
    with patch.object(legacy,'_agent_citations',side_effect=_fake_citations),patch(
        'benchmark_projection_v0_1_28.projected_memory_document',side_effect=lambda h,c,refs:h.read()+c.markdown):
        return invoke_v0_1_29(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.29')

class BenchmarkAdvisoryTests(unittest.TestCase):
    def test_unrepairable_benchmark_is_unscored_and_cannot_stop_supported_enrichment(self):
        def unscored(inputs,**kwargs):
            raise legacy.UnresolvedAgentResponse(legacy.evidence_diagnostic(role=legacy.BENCHMARK_ROLE,
                stage='agent_response_payload',field='business_evidence',rule='repair_changed_business_content'))
        inputs=EnrichmentInputs()
        with patch.object(legacy,'_run_benchmark',side_effect=unscored):result=invoke(inputs)
        dossier=result['outputs']['intelligence_dossier'];self.assertTrue(dossier['publication_complete'])
        for row in dossier['company_results']:
            self.assertEqual('unscored',row['benchmark_observation']['status'])
            self.assertIsNone(row['benchmark_non_regression']);self.assertIsNone(row['benchmark_before_covered_count'])
            self.assertIsNone(row['benchmark_after_covered_count'])
            self.assertIs(False,row['benchmark_observation']['is_publication_authority'])
            self.assertEqual('applied',row['skill_publication']['memory']['status'])
            self.assertEqual('applied',row['skill_publication']['methodology']['status'])
    def test_genuine_negative_critic_still_withholds_facts_even_when_benchmark_is_optional(self):
        class Negative(EnrichmentInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                envelope=super().invoke_agent(role,input=input,on_error=on_error)
                if role==legacy.CRITIC_ROLE:envelope['result']['content'][0]['value']['recommendation']='fail'
                return envelope
        inputs=Negative();result=invoke(inputs)
        self.assertFalse(result['outputs']['intelligence_dossier']['publication_complete']);self.assertEqual([],inputs.mutables)
    def test_authority_failure_is_never_contained_as_an_unscored_benchmark(self):
        inputs=EnrichmentInputs()
        with patch.object(legacy,'_run_benchmark',side_effect=RuntimeError('authority denied')):
            with self.assertRaisesRegex(RuntimeError,'authority denied'):invoke(inputs)
        self.assertEqual([],inputs.mutables)
if __name__=='__main__':unittest.main()
