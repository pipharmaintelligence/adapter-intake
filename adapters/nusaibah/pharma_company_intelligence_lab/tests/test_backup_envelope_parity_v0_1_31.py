import unittest
from unittest.mock import patch
import test_invocation_revival_v0_1_30 as recovery_tests
from test_invocation_revival_v0_1_30 import BoundaryInputs,legacy
from test_orchestration_preview import _fake_citations
from orchestration_v0_1_31 import invoke_v0_1_31
from research_envelope_v0_1_26 import BUSINESS_FIELDS
from research_response_contract_v0_1_26 import RESEARCH_SCHEMA_VERSION

def invoke(inputs):
    with patch.object(legacy,'_agent_citations',side_effect=_fake_citations):
        return invoke_v0_1_31(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.31')

class BackupEnvelopeParityTests(recovery_tests.InvocationRevivalTests):
    def setUp(self):
        self.route=patch('test_invocation_revival_v0_1_30.invoke',side_effect=invoke);self.route.start();self.addCleanup(self.route.stop)
    def test_each_dispatched_research_backup_has_the_complete_envelope_and_original_bounds(self):
        for role in ('portfolio_researcher','market_researcher','regulatory_risk_researcher'):
            with self.subTest(role=role):
                class Observed(BoundaryInputs):
                    def __init__(self,role):super().__init__(role);self.payloads=[]
                    def invoke_agent(self,role,*,input,on_error='raise'):
                        self.payloads.append((role,input))
                        return super().invoke_agent(role,input=input,on_error=on_error)
                inputs=Observed(role);invoke(inputs);contract=inputs.backups[0]['response_contract']
                original=next(p['response_contract'] for name,p in inputs.payloads if name==role)
                self.assertEqual(original,contract)
                self.assertEqual(list(BUSINESS_FIELDS),contract['required_fields'])
                self.assertEqual(RESEARCH_SCHEMA_VERSION,contract['schema_version']['required_value'])
                self.assertEqual('completed',contract['status']['required_value'])
                self.assertIs(False,contract['additional_response_fields_allowed'])
                self.assertIn('claim_evidence',contract);self.assertIn('claims',contract)
if __name__=='__main__':unittest.main()
