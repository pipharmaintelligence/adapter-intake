"""Company names in both first and updated Skill documents; partition stays numeric."""
import sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
try:
    from devtools.skill_changes import SkillChangeSet
    from devtools.skill_document import SkillDocument
except ImportError:
    raise unittest.SkipTest('Title integration requires the real Skill SDK')
from test_first_publication_v0_1_38 import Inputs
import test_publication_target_v0_1_37 as publication_fixture
from skill_initialization_v0_1_42 import initialize_section
from skill_publication_v0_1_42 import apply_section
from company_title_v0_1_42 import company_title
from devtools.skill_citation import CitationRef
from unittest.mock import patch


class CompanyTitleTests(unittest.TestCase):
    def test_old_runtime_is_detected_before_any_preparation(self):
        import nusaibah_pharma_company_intelligence_lab_v0_1_42_adapter as adapter
        with patch.object(SkillChangeSet,'rename_title',None,create=True),patch.object(adapter,'invoke_v0_1_42') as invoke:
            with self.assertRaisesRegex(RuntimeError,'skill_title_capability_required'):
                adapter.NusaibahPharmaCompanyIntelligenceLabV042Adapter().invoke({}, {})
            invoke.assert_not_called()

    def test_first_memory_and_methodology_use_supplied_name(self):
        inputs=Inputs()
        for role,section in [('company_memory','Current Public Research'),('company_methodology','Methodology Learning')]:
            result=initialize_section(inputs,59,role,role+'_update',section,'Reviewed fixture prose.',(),company_name='Pfizer')
            self.assertEqual('initialized',result['status'])
            self.assertEqual('Pfizer',SkillDocument.parse(inputs.store[role]).title)
            self.assertIn('name: '+role.replace('_','-'),inputs.store[role])

    def test_existing_title_changes_in_same_update_with_history(self):
        if not hasattr(SkillChangeSet,'rename_title'):self.skipTest('Requires companion Assets title capability')
        handle_type=publication_fixture.ExactPublicationTests().sdk()
        for role,section in [('company_memory','Current Public Research'),('company_methodology','Methodology Learning')]:
            key=(59,role)
            source='---\nname: '+role.replace('_','-')+'\ndescription: Fixture.\n---\n# Company 59\n\n## '+section+'\n\nOld.\n\n## Other\n\nUnchanged.\n'
            store={key:{'text':source}}
            baseline=handle_type(store,key)
            class Runtime:
                def dynamic_skill(self,role,*,variables):
                    assert variables=={'company_id':'59'}
                    return handle_type(store,key,role.endswith('_update'))
            text='Reviewed prose. [R1]\n\n### Annex: Evidence\n\n[R1] <https://example.org/report>\n'
            result=apply_section(Runtime(),59,role,role+'_update',section,text,baseline.content_digest(),baseline.provenance().package_digest,
                                 (CitationRef(locator='https://example.org/report',source_kind='agent_citation'),),company_name='Pfizer')
            self.assertEqual('applied',result['status'],result)
            self.assertTrue(result['readback_verified']);self.assertTrue(result['history_verified'])
            document=SkillDocument.parse(store[key]['text'])
            self.assertEqual('Pfizer',document.title)
            self.assertEqual(1,store[key]['text'].count('https://example.org/report'))
            self.assertEqual('Unchanged.\n',document.section_text('Other'))

    def test_company_name_is_inert_single_line_text(self):
        title=company_title('  Example *Group*\n# holdings <test>  ')
        self.assertNotIn('\n',title);self.assertNotIn('#',title.replace('&#',''))
        self.assertIn('Example',title)
        self.assertEqual('Company Profile',company_title(None))
