"""Publication uses exact parent paths even after prior enrichment creates children."""
import sys,unittest
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from test_final_cycle_v0_1_26 import Handle
from test_source_parity_v0_1_35 import Inputs,legacy,_fake_citations
from unittest.mock import patch
from orchestration_v0_1_37 import invoke_v0_1_37
from skill_publication_v0_1_37 import apply_section,EnrichmentPublicationError
from automatic_publication_v0_1_37 import diagnostic

class ExactPublicationTests(unittest.TestCase):
    def sdk(self):
        try:
            from devtools.skill_changes import SkillChangeSet
            from devtools.skill_document import SkillDocument
            from devtools.skill_navigation import find_sections
        except ImportError:self.skipTest('Real SDK publication engine unavailable in CI stubs')
        class SDKHandle(Handle):
            def new_changeset(self):return SkillChangeSet()
            def preview(self,changes):return changes.preview(self.read())
            def section_text(self,name):return SkillDocument.parse(self.read()).section_text(name)
            def find_sections(self,name):return find_sections(SkillDocument.parse(self.read()),name)
            def apply(self,changes,*,expected_digest):
                assert self.mutable and self.content_digest()==expected_digest
                preview=self.preview(changes);self.store[self.key]['text']=preview.source
                receipt=SimpleNamespace(change_id='sdk-nested-fixture',before_content_digest=preview.diff.old_digest,after_content_digest=preview.diff.new_digest)
                self.store[self.key]['receipt']=receipt;return receipt
        return SDKHandle
    def test_existing_nested_parent_publishes_with_real_preview_readback_and_history(self):
        from skill_publication_v0_1_27 import apply_section as previous
        from devtools.skill_citation import CitationRef
        HandleType=self.sdk()
        for section,role in [('Current Public Research','company_memory'),('Methodology Learning','company_methodology')]:
            with self.subTest(role=role):
                text='---\nname: fixture\ndescription: Nested baseline.\n---\n\n# Company\n\n## '+section+'\n\nPreserved baseline.\n\n'+''.join('### Child '+str(i)+'\n\nQualified old paragraph.\n\n' for i in range(14))+'## Other\n\nUnchanged sibling.\n'
                key=(14,role);store={key:{'text':text}}
                baseline=HandleType(store,key)
                class Runtime:
                    def dynamic_skill(self,role,*,variables):return HandleType(store,key,role.endswith('_update'))
                candidate=baseline.section_text(section).rstrip()+'\n\n### New Enrichment\n\nSupported fixture fact.'
                self.assertEqual(15,len(baseline.find_sections(section)))
                with self.assertRaises(previous.__globals__['EnrichmentPublicationError']) as caught:
                    previous(Runtime(),14,role,role+'_update',section,candidate,baseline.content_digest(),baseline.provenance().package_digest,())
                self.assertEqual('section_ambiguous',caught.exception.rule);self.assertEqual(text,store[key]['text'])
                result=apply_section(Runtime(),14,role,role+'_update',section,candidate,baseline.content_digest(),baseline.provenance().package_digest,[CitationRef(locator='https://example.test/evidence',title='Fixture source')])
                self.assertEqual('applied',result['status']);self.assertTrue(result['readback_verified']);self.assertTrue(result['history_verified'])
                self.assertIn('## Other\n\nUnchanged sibling.',store[key]['text'])
                self.assertIn('Qualified old paragraph.',store[key]['text'])
    def test_duplicate_exact_parent_stays_rejected_without_apply(self):
        HandleType=self.sdk();key=(14,'company_memory')
        text='---\nname: fixture\ndescription: Duplicate.\n---\n\n# Company\n\n## Current Public Research\n\nFirst.\n\n## Current Public Research\n\nSecond.\n'
        store={key:{'text':text}};baseline=HandleType(store,key)
        class Runtime:
            def dynamic_skill(self,role,*,variables):return HandleType(store,key,True)
        with self.assertRaises(EnrichmentPublicationError) as caught:
            apply_section(Runtime(),14,'company_memory','company_memory_update','Current Public Research','Candidate.',baseline.content_digest(),baseline.provenance().package_digest,())
        self.assertEqual('section_ambiguous',caught.exception.rule);self.assertEqual(text,store[key]['text'])
    def test_static_publication_rule_survives_projection(self):
        value=diagnostic(EnrichmentPublicationError('section_ambiguous'))
        self.assertEqual('section_ambiguous',value['publication_rule'])
        self.assertEqual('pharma_enrichment_publication_invalid',value['failure_code'])
        self.assertIsNone(diagnostic(ValueError('untrusted business text'))['publication_rule'])
    def test_complete_enrichment_fixture_uses_new_publication_helper(self):
        inputs=Inputs()
        with patch.object(legacy,'_agent_citations',side_effect=_fake_citations):
            value=invoke_v0_1_37(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.37')
        self.assertTrue(value['outputs']['intelligence_dossier']['publication_complete'])
        self.assertEqual(0,value['outputs']['intelligence_dossier']['company_results'][0]['benchmark_agent_call_count'])

if __name__=='__main__':unittest.main()
