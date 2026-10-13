import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent))
from structured_review_toolkit.tool_operations_v0_1_2 import execute_operation
from test_agent_chunks_v0_1_33 import ChunkInputs
from test_automatic_enrichment_v0_1_27 import legacy,_fake_citations
from orchestration_v0_1_35 import invoke_v0_1_35
from source_evidence_v0_1_35 import SourceEvidenceInputs,canonical,digest
from devtools.runtime_agent_invocation import RuntimeAgentInvocationError
from devtools.trusted_runtime_callable_child_bridge import RuntimeCallableBridgeError

class Inputs(ChunkInputs):
    def __init__(self):super().__init__();self.requests=[]
    def invoke_asset(self,role,*,variables,on_error):
        assert role=='review_toolkit' and on_error=='raise'
        self.requests.append(variables)
        return {'status':'success','result':execute_operation(variables)}

def invoke(inputs):
    with patch.object(legacy,'_agent_citations',side_effect=_fake_citations):
        return invoke_v0_1_35(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.35')

class SourceParityTests(unittest.TestCase):
    def test_7193_character_memory_is_accepted_by_the_pinned_native_tool(self):
        raw=Inputs();source=SourceEvidenceInputs(raw,record={'company_id':13,'corporate_id':1,'company_name':'Fixture'},memory_text='a'*7193)
        material={'entity_id':source.entity_id,'snapshot_id':source.snapshot_id,'source_units':source.units}
        result=execute_operation({'schema_version':'review_tool_request.v1','operation':'resolve_exact_spans',
            'arguments':{**material,'source_digest':digest(material),'requests':[]}})
        self.assertEqual('resolved',result['output']['status']);self.assertEqual('0.1.2',result['toolkit_version'])
    def test_complete_consumer_uses_native_toolkit_012_and_publishes_fixture(self):
        inputs=Inputs();value=invoke(inputs);row=value['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete']);self.assertEqual(0,row['benchmark_agent_call_count'])
        self.assertTrue(inputs.requests)
    def test_refresh_unavailability_withholds_piece_without_paid_backup_or_asset_failure(self):
        class Unavailable(Inputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                if role=='portfolio_researcher' and not getattr(self,'failed',False):
                    self.failed=True;raise RuntimeAgentInvocationError('agent_execution_provider_member_refresh_failed')
                return super().invoke_agent(role,input=input,on_error=on_error)
        inputs=Unavailable();value=invoke(inputs);row=value['outputs']['intelligence_dossier']['company_results'][0]
        self.assertEqual('success',value['status']);self.assertTrue(row['research_incomplete'])
        self.assertNotIn(legacy.RESEARCH_RESOLVER_ROLE,inputs.role_calls)
        self.assertTrue(row['unresolved_agent_responses'])
    def test_effect_free_child_unavailability_is_local(self):
        class Unavailable(Inputs):
            def invoke_asset(self,role,*,variables,on_error):
                if not getattr(self,'failed',False):
                    self.failed=True;raise RuntimeCallableBridgeError('direct_runtime_callable_execution_failed')
                return super().invoke_asset(role,variables=variables,on_error=on_error)
        value=invoke(Unavailable());self.assertEqual('success',value['status'])
        self.assertTrue(value['outputs']['intelligence_dossier']['company_results'][0]['research_incomplete'])
    def test_refresh_mismatch_remains_strict_authority_failure(self):
        class Mismatch(Inputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                if role=='portfolio_researcher':raise RuntimeAgentInvocationError('agent_execution_provider_member_refresh_mismatch')
                return super().invoke_agent(role,input=input,on_error=on_error)
        inputs=Mismatch()
        with self.assertRaises(RuntimeAgentInvocationError):invoke(inputs)
        self.assertFalse(inputs.mutables)
    def test_forged_toolkit_spans_are_never_treated_as_availability(self):
        class Forged(Inputs):
            def invoke_asset(self,role,*,variables,on_error):
                value=super().invoke_asset(role,variables=variables,on_error=on_error)
                value['result']['output']['spans'][0]['end']+=1
                return value
        inputs=Forged()
        with self.assertRaises(ValueError):invoke(inputs)
        self.assertFalse(inputs.mutables)
