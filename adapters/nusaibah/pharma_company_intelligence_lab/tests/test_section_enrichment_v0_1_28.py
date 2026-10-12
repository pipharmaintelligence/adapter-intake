import json,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from test_automatic_enrichment_v0_1_27 import EnrichmentInputs
from test_orchestration_preview import _fake_citations
from orchestration_v0_1_28 import invoke_v0_1_28
from section_enrichment_v0_1_28 import build_enrichment_candidate
from memory_contract import MemoryCandidate
import legacy_preparation_helpers_v0_1_23 as legacy

def invoke(inputs):
    with patch.object(legacy,'_agent_citations',side_effect=_fake_citations),patch(
        'benchmark_projection_v0_1_28.projected_memory_document',side_effect=lambda h,c,refs:h.read()+c.markdown):
        return invoke_v0_1_28(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.28')

class SectionEnrichmentParityTests(unittest.TestCase):
    def test_scoped_contract_declares_exact_validator_ids_and_no_global_requirements(self):
        inputs=EnrichmentInputs();result=invoke(inputs)
        self.assertTrue(result['outputs']['intelligence_dossier']['publication_complete'])
        critics=[p for role,_,p in inputs.agent_inputs if role==legacy.CRITIC_ROLE]
        self.assertEqual(8,len(critics))
        for p in critics:
            section=p['reviewed_section_ids'][0];contract=p['response_contract']
            self.assertEqual([section],contract['allowed_section_ids'])
            self.assertEqual([section],contract['validation_contract']['missing_section_ids_allowed_values'])
            self.assertEqual([c['claim_id'] for c in p['research_evidence']['claims']],contract['allowed_claim_ids'])
            self.assertTrue(all(r['section_id']==section and r['role'] is not None for r in p['planner_requirements']))
            self.assertEqual([r['requirement_id'] for r in p['planner_requirements']],contract['allowed_requirement_ids'])
    def test_planner_requirements_are_from_the_actual_section_chunk(self):
        inputs=EnrichmentInputs();invoke(inputs)
        # The fixture supplies distinct section-scoped questions through planner calls.
        for role,company,p in inputs.agent_inputs:
            if role!=legacy.CRITIC_ROLE:continue
            section=p['reviewed_section_ids'][0]
            planners=[v for r,c,v in inputs.agent_inputs if r==legacy.PLANNER_ROLE and c==company and v['planner_chunk']['section_id']==section]
            self.assertEqual(1,len(planners))
            self.assertTrue(all(q['reviewed_section_id']==section for q in p['scoped_planner_requirements']))
            self.assertNotIn('known_memory_gap',set(q['kind'] for q in p['planner_requirements']))
    def test_all_negative_verdicts_are_retained_in_incomplete_company_result(self):
        class Negative(EnrichmentInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                envelope=super().invoke_agent(role,input=input,on_error=on_error)
                if role==legacy.CRITIC_ROLE:
                    value=envelope['result']['content'][0]['value'];value['recommendation']='fail'
                    value['unsupported_claim_ids']=input['response_contract']['allowed_claim_ids']
                return envelope
        inputs=Negative();rows=invoke(inputs)['outputs']['intelligence_dossier']['company_results']
        self.assertEqual([],inputs.mutables)
        for row in rows:
            self.assertEqual(4,len(row['section_enrichment_checks']))
            self.assertTrue(all(c['recommendation']=='fail' for c in row['section_enrichment_checks']))
            self.assertFalse(row['skill_publication']['publication_complete'])
    def test_inference_is_not_rendered_as_an_unqualified_verified_fact(self):
        candidate=MemoryCandidate(14,legacy.MEMORY_TARGET_SECTION,'Unused.',('f1',))
        claim={'claim_id':'f1','section_id':'company_profile','statement':'Qualified interpretation.','inference':True,
            'semantic_context':{'relationship_kind':'bilateral','actor':'A','counterparty':'B','territory':'Jordan'},
            'source_spans':[{'locator':'source:1','source_snapshot_id':'snapshot:1'}]}
        value,_=build_enrichment_candidate(candidate,'Baseline.',[claim])
        self.assertIn('explicitly labelled model inference',value.markdown)
        self.assertIn('counterparty: B',value.markdown);self.assertIn('territory: Jordan',value.markdown)
    def test_full_memory_benchmark_preserves_other_sections_and_exact_citations(self):
        try:from devtools.skill_views import FixedSkillView
        except ImportError:self.skipTest('Real SDK structural engine required')
        from benchmark_projection_v0_1_28 import projected_memory_document
        text='---\nname: company-memory\ndescription: Test.\n---\n\n# Company\n\n## Current Public Research\n\nExisting.\n\n## Historical Recall\n\nA prior benchmark fact remains here.\n'
        handle=FixedSkillView(text)
        candidate=MemoryCandidate(14,'Current Public Research','Existing.\n\nNew supported fact.',('f1',))
        projected=projected_memory_document(handle,candidate,[{'locator':'https://example.test/evidence','source_kind':'business_reference','title':'Source'}])
        self.assertIn('## Historical Recall\n\nA prior benchmark fact remains here.',projected)
        self.assertIn('example.test/evidence',projected);self.assertEqual(text,handle.read())
    def test_current_manifest_and_all_agent_chain_versions_match(self):
        m=json.loads((ROOT/'tests/fixtures/release-0.1.28/nusaibah_pharma_company_intelligence_lab.asset.json').read_text())
        self.assertEqual({'0.1.28'},set(m['versions']))
        for a in m['versions']['0.1.28']['agents'].values():self.assertEqual(a['contract_version'],a['definition']['chain']['version'])
if __name__=='__main__':unittest.main()
