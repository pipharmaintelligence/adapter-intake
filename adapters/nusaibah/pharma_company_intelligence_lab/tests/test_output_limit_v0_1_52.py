"""Network-disabled 64K policy parity and trusted exhaustion containment."""
from copy import deepcopy
import json
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(Path(__file__).parent)]
from test_durable_batched_v0_1_51 import BatchedInputs
from invocation_recovery_v0_1_52 import InvocationRecoveryInputs
from invocation_recovery_v0_1_30 import ACTIVE_ROLES
from orchestration_v0_1_51 import invoke_v0_1_51
from orchestration_v0_1_52 import invoke_v0_1_52
from devtools.runtime_agent_invocation import RuntimeAgentInvocationError
import legacy_preparation_helpers_v0_1_23 as legacy


def exhausted():
    return RuntimeAgentInvocationError('agent_bridge_callback_failed',
        cause_code='provider_execution_output_limit_reached')


class ExhaustionInputs(BatchedInputs):
    def __init__(self, failed_role=None):
        super().__init__()
        self.failed_role=failed_role
        self.failed=False
        self.dispatched=[]
    def invoke_agent(self,role,*,input,on_error='raise'):
        self.dispatched.append((role,input['company_id']))
        if role==self.failed_role and not self.failed:
            self.failed=True
            raise exhausted()
        return super().invoke_agent(role,input=input,on_error=on_error)


class OutputLimitTests(unittest.TestCase):
    def setUp(self):
        guard=patch.object(socket.socket,'connect',side_effect=AssertionError('Unexpected network access'))
        guard.start();self.addCleanup(guard.stop)

    def test_successful_memory_and_evidence_are_identical_to_previous_version(self):
        old=BatchedInputs();new=BatchedInputs()
        before=invoke_v0_1_51(old,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.51')
        after=invoke_v0_1_52(new,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.52')
        self.assertEqual(old.store[(13,'company_memory')]['text'],new.store[(13,'company_memory')]['text'])
        for key in ('accepted_claim_count','required_section_coverage_count','research_incomplete'):
            self.assertEqual(before['outputs']['intelligence_dossier']['company_results'][0][key],
                             after['outputs']['intelligence_dossier']['company_results'][0][key])
        self.assertTrue(after['outputs']['intelligence_dossier']['publication_complete'])
        self.assertEqual(before['metrics']['agent_call_count'],after['metrics']['agent_call_count'])

    def test_every_active_role_exhaustion_is_typed_unresolved_with_one_call(self):
        for role in sorted(ACTIVE_ROLES):
            with self.subTest(role=role):
                source=ExhaustionInputs(role)
                wrapped=InvocationRecoveryInputs(source)
                with self.assertRaises(legacy.UnresolvedAgentResponse) as caught:
                    wrapped.invoke_agent(role,input={'company_id':13})
                self.assertEqual('provider_output_limit_reached',caught.exception.diagnostic['rule'])
                self.assertEqual(role,caught.exception.diagnostic['role'])
                self.assertEqual([(role,13)],source.dispatched)
                self.assertEqual([],source.mutables)
                self.assertEqual('affected_chunk_withheld_no_provider_retry',wrapped.invocation_issues[-1]['action'])

    def test_real_section_loops_contain_research_critic_and_synthesis_without_paid_backup(self):
        for role in ('portfolio_researcher','market_researcher','regulatory_risk_researcher',legacy.CRITIC_ROLE,legacy.SYNTHESIS_ROLE):
            with self.subTest(role=role):
                source=ExhaustionInputs(role)
                result=invoke_v0_1_52(source,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.52')
                self.assertEqual('success',result['status'])
                row=result['outputs']['intelligence_dossier']['company_results'][0]
                self.assertTrue(row['research_incomplete'])
                self.assertTrue(source.failed)
                self.assertNotIn(legacy.RESEARCH_RESOLVER_ROLE,[name for name,_ in source.dispatched])
                self.assertTrue(row['profile_document']['text'])

    def test_resolver_uses_only_source_owned_original_role(self):
        role=legacy.RESEARCH_RESOLVER_ROLE
        source=ExhaustionInputs(role);wrapped=InvocationRecoveryInputs(source)
        with self.assertRaises(legacy.UnresolvedAgentResponse) as caught:
            wrapped.invoke_agent(role,input={'company_id':13,'original_role':legacy.SYNTHESIS_ROLE})
        self.assertEqual(legacy.SYNTHESIS_ROLE,caught.exception.diagnostic['role'])
        source=ExhaustionInputs(role);wrapped=InvocationRecoveryInputs(source)
        with self.assertRaises(RuntimeAgentInvocationError):
            wrapped.invoke_agent(role,input={'company_id':13,'original_role':'untrusted'})
        self.assertEqual([(role,13)],source.dispatched)

    def test_unknown_authority_and_text_only_lookalikes_still_propagate(self):
        for cause in (None,'provider_execution_vertex_auth_failed','provider_execution_transport_failed'):
            class Rejected(BatchedInputs):
                def invoke_agent(self,role,*,input,on_error='raise'):
                    raise RuntimeAgentInvocationError('provider_execution_output_limit_reached',cause_code=cause)
            source=Rejected();wrapped=InvocationRecoveryInputs(source)
            with self.assertRaises(RuntimeAgentInvocationError):
                wrapped.invoke_agent('portfolio_researcher',input={'company_id':13})
            self.assertEqual([],source.mutables)

    def test_new_manifest_changes_only_budget_and_immutable_contract_versions(self):
        manifest=json.loads((ROOT/'nusaibah_pharma_company_intelligence_lab.asset.json').read_text(encoding='utf-8'))
        before=manifest['versions']['0.1.51'];after=deepcopy(manifest['versions']['0.1.52'])
        for role,agent in after['agents'].items():
            old=before['agents'][role]
            self.assertNotEqual(old['contract_version'],agent['contract_version'])
            self.assertEqual(agent['contract_version'],agent['definition']['chain']['version'])
            agent['definition']['chain']['version']=old['definition']['chain']['version']
            agent['contract_version']=old['contract_version']
            for index,step in enumerate(agent['definition']['chain']['steps']):
                self.assertEqual(64000,step['provider_policy']['generation_policy']['max_tokens'])
                step['provider_policy']['generation_policy']['max_tokens']=old['definition']['chain']['steps'][index]['provider_policy']['generation_policy']['max_tokens']
        self.assertEqual(before,after)


if __name__=='__main__':unittest.main()
