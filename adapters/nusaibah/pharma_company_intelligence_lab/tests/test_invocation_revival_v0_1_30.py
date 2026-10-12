import copy,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from test_automatic_enrichment_v0_1_27 import EnrichmentInputs
from test_orchestration_preview import _fake_citations
from orchestration_v0_1_30 import invoke_v0_1_30
from invocation_recovery_v0_1_30 import ACTIVE_ROLES
from devtools.runtime_agent_invocation import RuntimeAgentInvocationError
import legacy_preparation_helpers_v0_1_23 as legacy

PROOF={'schema_version':'proof_failure_detail.v1','proof_kind':'agent_contract','role':'provider',
 'stage':'terminal_content','rule':'agent_result_json_object_invalid','field':'content'}

def invalid_json():
    proof=PROOF
    try:
        from devtools.provider_execution_transport import _terminal_content_for_provider,ProviderExecutionTransportError
    except ImportError:pass  # CI stub exposes only the typed error surface.
    else:
        try:_terminal_content_for_provider('{"broken":','json_object',family='vertex')
        except ProviderExecutionTransportError as error:proof=error.proof_failure_detail
        else:raise AssertionError('SDK accepted malformed JSON')
    return RuntimeAgentInvocationError('provider_execution_vertex_response_invalid',
        cause_code='provider_execution_vertex_response_invalid',proof_failure_detail=proof)

class BoundaryInputs(EnrichmentInputs):
    def __init__(self,failed_role,*,backup_bad=False,backup_typed_bad=False,negative=False):
        super().__init__();self.failed_role=failed_role;self.failed=False;self.backup_bad=backup_bad
        self.backup_typed_bad=backup_typed_bad;self.negative=negative;self.dispatched=[];self.backups=[]
    def invoke_agent(self,role,*,input,on_error='raise'):
        self.dispatched.append((role,input['company_id']))
        if role==legacy.RESEARCH_RESOLVER_ROLE and input.get('repair_scope')=='unavailable_business_json_from_sources':
            self.backups.append(copy.deepcopy(input))
            if self.backup_bad:raise invalid_json()
            original={**input['original_section_input'],'response_contract':input['response_contract']}
            envelope=super().invoke_agent(input['original_role'],input=original,on_error=on_error)
            if self.backup_typed_bad:envelope['result']['content'][0]['value'].pop('sections',None)
            return envelope
        if role==self.failed_role and input['company_id']==self['variables']['company_ids'][0] and not self.failed:
            self.failed=True;raise invalid_json()
        envelope=super().invoke_agent(role,input=input,on_error=on_error)
        if self.negative and role==legacy.CRITIC_ROLE:envelope['result']['content'][0]['value']['recommendation']='fail'
        return envelope

def invoke(inputs):
    with patch.object(legacy,'_agent_citations',side_effect=_fake_citations):
        return invoke_v0_1_30(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.30')

class InvocationRevivalTests(unittest.TestCase):
    def test_real_terminal_json_rejection_gets_one_source_bound_backup_for_every_active_role(self):
        for role in sorted(ACTIVE_ROLES):
            with self.subTest(role=role):
                inputs=BoundaryInputs(role);result=invoke(inputs);rows=result['outputs']['intelligence_dossier']['company_results']
                self.assertEqual('success',result['status']);self.assertTrue(all(r['skill_publication']['publication_complete'] for r in rows))
                self.assertEqual(1,len(inputs.backups));backup=inputs.backups[0]
                self.assertEqual(role,backup['original_role']);self.assertEqual(13,backup['company_id'])
                self.assertNotIn('invalid_response',backup)
                self.assertIn('original_section_input',backup);self.assertIn('response_contract',backup)
                self.assertNotIn(legacy.BENCHMARK_ROLE,[name for name,_ in inputs.dispatched])
                self.assertEqual(1,rows[0]['agent_response_resolver_call_count'])

    def test_failed_backup_never_recurses_or_stops_other_company(self):
        for role in sorted(ACTIVE_ROLES):
            with self.subTest(role=role):
                inputs=BoundaryInputs(role,backup_bad=True);result=invoke(inputs)
                self.assertEqual('success',result['status']);self.assertEqual(1,len(inputs.backups))
                rows=result['outputs']['intelligence_dossier']['company_results'];self.assertTrue(rows[1]['skill_publication']['publication_complete'])
                self.assertEqual(1,rows[0]['agent_response_resolver_call_count'])
                if role==legacy.CRITIC_ROLE:
                    self.assertTrue(rows[0]['skill_publication']['publication_complete'])
                    self.assertIn('unresolved',[o['status'] for o in rows[0]['section_enrichment_checks']])
                else:self.assertFalse(rows[0]['skill_publication']['publication_complete'])

    def test_invalid_typed_source_backup_cannot_trigger_a_second_schema_backup(self):
        inputs=BoundaryInputs('portfolio_researcher',backup_typed_bad=True);result=invoke(inputs)
        self.assertEqual('success',result['status']);self.assertEqual(1,len(inputs.backups))
        self.assertEqual(1,sum(role==legacy.RESEARCH_RESOLVER_ROLE for role,_ in inputs.dispatched))

    def test_source_backup_does_not_clear_negative_critic_decisions(self):
        inputs=BoundaryInputs('market_researcher',negative=True);result=invoke(inputs)
        self.assertEqual('success',result['status']);self.assertFalse(result['outputs']['intelligence_dossier']['publication_complete'])
        self.assertEqual([],inputs.mutables)

    def test_same_company_string_echo_is_normalized_without_backup(self):
        class StringEcho(EnrichmentInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                envelope=super().invoke_agent(role,input=input,on_error=on_error)
                value=envelope['result']['content'][0]['value'];value['company_id']=str(value['company_id'])
                return envelope
        result=invoke(StringEcho());self.assertTrue(result['outputs']['intelligence_dossier']['publication_complete'])

    def test_different_model_company_echo_is_withheld_without_failing_entire_asset(self):
        class WrongEcho(EnrichmentInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                envelope=super().invoke_agent(role,input=input,on_error=on_error)
                if role==legacy.STRATEGIC_ROLE and input['company_id']==13:envelope['result']['content'][0]['value']['company_id']=999
                return envelope
        inputs=WrongEcho();result=invoke(inputs);rows=result['outputs']['intelligence_dossier']['company_results']
        self.assertEqual('success',result['status']);self.assertFalse(rows[0]['skill_publication']['publication_complete'])
        self.assertTrue(rows[1]['skill_publication']['publication_complete'])

    def test_privileged_or_untrusted_invocation_rejection_never_uses_content_backup(self):
        class AuthorityRejected(EnrichmentInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                raise RuntimeAgentInvocationError('authority rejected',cause_code='provider_execution_vertex_response_invalid',
                    proof_failure_detail={**PROOF,'rule':'agent_result_privileged_material_rejected'})
        inputs=AuthorityRejected()
        with self.assertRaises(RuntimeAgentInvocationError):invoke(inputs)
        self.assertEqual([],inputs.mutables)
if __name__=='__main__':unittest.main()
