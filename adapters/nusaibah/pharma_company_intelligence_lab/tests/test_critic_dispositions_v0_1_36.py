"""Contract-valid critic gaps cannot crash the asset or erase supported siblings."""
import copy,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from test_source_parity_v0_1_35 import Inputs,legacy,_fake_citations
from orchestration_v0_1_36 import invoke_v0_1_36
from section_critic_v0_1_36 import merge_requirement_dispositions

def invoke(inputs):
    with patch.object(legacy,'_agent_citations',side_effect=_fake_citations):
        return invoke_v0_1_36(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.36')

class GapInputs(Inputs):
    disposition='unresolved_evidence'
    only_first_section=False
    def invoke_agent(self,role,*,input,on_error='raise'):
        response=super().invoke_agent(role,input=input,on_error=on_error)
        if role==legacy.CRITIC_ROLE and input['planner_requirements']:
            first=legacy.RESEARCH_ROLE_SECTIONS[legacy.RESEARCH_ROLES[0]][0]
            if not self.only_first_section or input['reviewed_section_ids']==[first]:
                response['result']['content'][0]['value']['unmet_plan_requirements']=[{
                    'requirement_id':input['planner_requirements'][0]['requirement_id'],
                    'disposition':self.disposition,'notes':'Fixture requirement has unavailable evidence.'}]
        return response

class CriticDispositionTests(unittest.TestCase):
    def test_every_valid_disposition_completes_without_schema_backup(self):
        allowed=legacy.response_contract_for_role(legacy.CRITIC_ROLE,company_id=13)['unmet_plan_requirement_dispositions']
        self.assertEqual({'unresolved_evidence','unsatisfied'},set(allowed))
        for disposition in allowed:
            with self.subTest(disposition=disposition):
                inputs=GapInputs();inputs.disposition=disposition
                result=invoke(inputs);row=result['outputs']['intelligence_dossier']['company_results'][0]
                self.assertEqual('success',result['status'])
                self.assertNotIn(legacy.RESEARCH_RESOLVER_ROLE,inputs.role_calls)
                self.assertTrue(any(o.get('requirement_dispositions') for o in row['section_enrichment_checks']))
                if disposition=='unsatisfied':
                    self.assertFalse(row['skill_publication']['publication_complete']);self.assertFalse(inputs.mutables)
                else:self.assertTrue(row['skill_publication']['publication_complete'])
    def test_unsatisfied_section_preserves_sibling_synthesis(self):
        inputs=GapInputs();inputs.disposition='unsatisfied';inputs.only_first_section=True
        value=invoke(inputs);row=value['outputs']['intelligence_dossier']['company_results'][0]
        self.assertEqual('success',value['status']);self.assertTrue(row['research_incomplete'])
        self.assertIn(legacy.SYNTHESIS_ROLE,inputs.role_calls)
        self.assertTrue(any(o['status']=='validated' for o in row['section_enrichment_checks']))
        self.assertTrue(any(o['status']=='needs_enrichment' for o in row['section_enrichment_checks']))
    def test_mixed_repeated_dispositions_keep_strongest_negative_and_all_notes(self):
        rows=[{'unmet_plan_requirements':[{'requirement_id':'r1','disposition':d,'notes':n}]} for d,n in
            [('unresolved_evidence','First gap.'),('unsatisfied','Concrete unmet rule.'),('unresolved_evidence','Another gap.')]]
        original=copy.deepcopy(rows)
        result=merge_requirement_dispositions(rows,['r1'])
        self.assertEqual('unsatisfied',result[0]['disposition'])
        self.assertEqual('First gap.\n\nConcrete unmet rule.\n\nAnother gap.',result[0]['notes'])
        self.assertEqual(original,rows)
    def test_unresolved_negative_verdict_remains_withheld(self):
        class Negative(GapInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                value=super().invoke_agent(role,input=input,on_error=on_error)
                if role==legacy.CRITIC_ROLE:
                    value['result']['content'][0]['value']['recommendation']='fail'
                return value
        inputs=Negative();value=invoke(inputs)
        self.assertFalse(value['outputs']['intelligence_dossier']['publication_complete'])
        self.assertFalse(inputs.mutables)

if __name__=='__main__':unittest.main()
