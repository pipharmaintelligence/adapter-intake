"""Content failure containment without authority or evidence fabrication."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from devtools.runtime_agent_invocation import RuntimeAgentInvocationError
try:
    from devtools.runtime_agent_invocation import _bridge_context, runtime_agent_invoker
except ImportError:
    _bridge_context = runtime_agent_invoker = None
from test_research_envelope_parity_v0_1_24 import ContractFollowingInputs
from test_orchestration_preview import _fake_citations
import legacy_preparation_helpers_v0_1_23 as legacy
from orchestration_v0_1_25 import invoke_v0_1_25, IndependentReviewRequiredError
from invocation_recovery_v0_1_25 import invocation_diagnostic


def failure(rule='agent_result_json_object_invalid', *, cause='provider_execution_vertex_response_invalid'):
    return RuntimeAgentInvocationError('agent_bridge_callback_failed', cause_code=cause,
        proof_failure_detail={
            'schema_version':'proof_failure_detail.v1', 'proof_kind':'agent_contract',
            'role':'provider', 'stage':'terminal_content', 'rule':rule, 'field':'content',
        })


class Inputs(ContractFollowingInputs):
    def __init__(self, role=None, pass_number=1, rule='agent_result_json_object_invalid', backup_failure=False):
        super().__init__()
        self.failed_role=role
        self.failed_pass=pass_number
        self.rule=rule
        self.backup_failure=backup_failure
        self.dispatched=[]

    def invoke_agent(self, role, *, input, on_error='raise'):
        self.dispatched.append((role,input['company_id']))
        if self.backup_failure and role=='research_response_resolver':
            raise failure()
        if role==self.failed_role and (input.get('portfolio_review') or {}).get('pass_number',1)==self.failed_pass:
            raise failure(self.rule)
        envelope=super().invoke_agent(role,input=input,on_error=on_error)
        if self.backup_failure and role=='portfolio_researcher':
            envelope['result']['content'][0]['value']['claims']='invalid-array'
        return envelope


def run(inputs):
    with patch.object(legacy,'_agent_citations',side_effect=_fake_citations):
        return invoke_v0_1_25(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.25')


class InvocationRecoveryTests(unittest.TestCase):
    def test_current_release_keeps_all_agent_and_skill_contracts(self):
        root=Path(__file__).resolve().parents[1]
        current=json.loads((root/'nusaibah_pharma_company_intelligence_lab.asset.json').read_text())
        previous=json.loads((root/'tests/fixtures/release-0.1.24/nusaibah_pharma_company_intelligence_lab.asset.json').read_text())
        self.assertEqual('0.1.25',current['default'])
        self.assertEqual(previous['execution'],current['execution'])
        self.assertEqual(previous['versions']['0.1.24'],current['versions']['0.1.25'])

    @unittest.skipIf(_bridge_context is None, 'Real IPC parity requires the actual runtime SDK; the stub CI has no transport.')
    def test_real_file_ipc_content_failure_retains_a_dossier(self):
        class Session:
            timeout_seconds=2.0
            def invoke(self, role, *, input):
                raise failure()
        with _bridge_context(Session()) as context:
            invoker=runtime_agent_invoker(context)
            class BridgeInputs(Inputs):
                def invoke_agent(self, role, *, input, on_error='raise'):
                    if role=='portfolio_researcher':
                        return invoker(role,input=input)
                    return super().invoke_agent(role,input=input,on_error=on_error)
            response=run(BridgeInputs())
        self.assertEqual('success',response['status'])
        self.assertEqual('incomplete',response['outputs']['intelligence_dossier']['business_result_state'])
        self.assertTrue(response['outputs']['intelligence_dossier']['agent_invocation_response_issues'])
        self.assertEqual(0,response['metrics']['memory_mutations_made'])

    def test_healthy_two_pass_path_and_no_mutations(self):
        response=run(Inputs())
        dossier=response['outputs']['intelligence_dossier']
        self.assertEqual('review_pending',dossier['business_result_state'])
        self.assertEqual([],dossier['agent_invocation_response_issues'])
        self.assertTrue(all([p['status'] for p in c['portfolio_review_trace']]==['validated','validated'] for c in dossier['company_results']))
        self.assertFalse(dossier['review_packet']['apply_authority'])
        self.assertEqual(0,response['metrics']['memory_mutations_made'])
        self.assertEqual(0,response['metrics']['methodology_learning_mutations_made'])

    def test_first_portfolio_failure_retains_completed_sibling_claims_and_annex(self):
        inputs=Inputs('portfolio_researcher')
        response=run(inputs)
        dossier=response['outputs']['intelligence_dossier']
        self.assertEqual('success',response['status'])
        self.assertEqual('incomplete',dossier['business_result_state'])
        for packet in dossier['review_packet']['companies']:
            self.assertGreater(len(packet['accepted_claims']),0)
            self.assertTrue(all(not c['claim_id'].startswith('portfolio_researcher:') for c in packet['accepted_claims']))
            self.assertTrue(packet['issues_annex']['items'])
            self.assertFalse(packet['memory_proposal']['mutation_eligible'])
        self.assertFalse(any(role=='research_response_resolver' for role,_ in inputs.dispatched))
        self.assertTrue(all(not issue['rejected_text_available'] for issue in dossier['agent_invocation_response_issues']))

    def test_reflection_failure_preserves_exact_first_pass_and_marks_incomplete(self):
        response=run(Inputs('portfolio_researcher',pass_number=2))
        for company in response['outputs']['intelligence_dossier']['company_results']:
            trace=company['portfolio_review_trace']
            self.assertEqual(['validated','unresolved'],[p['status'] for p in trace])
            self.assertEqual(trace[0]['result_sha256'],trace[1]['result_sha256'])
            self.assertTrue(company['research_incomplete'])

    def test_nonresearch_content_failure_is_incomplete_not_asset_failure(self):
        for role in ('memory_benchmark_reviewer','methodology_planner','strategic_analyst','evidence_critic','intelligence_synthesizer'):
            with self.subTest(role=role):
                response=run(Inputs(role))
                self.assertEqual('success',response['status'])
                self.assertEqual('incomplete',response['outputs']['intelligence_dossier']['business_result_state'])
                self.assertEqual(0,response['metrics']['memory_mutations_made'])

    def test_unavailable_original_json_does_not_invoke_factual_backup(self):
        inputs=Inputs('market_researcher')
        result=run(inputs)
        self.assertFalse(any(role=='research_response_resolver' for role,_ in inputs.dispatched))
        self.assertTrue(result['outputs']['intelligence_dossier']['agent_invocation_response_issues'])

    def test_existing_business_backup_failure_is_withheld_without_recursive_call(self):
        inputs=Inputs(backup_failure=True)
        response=run(inputs)
        self.assertEqual('incomplete',response['outputs']['intelligence_dossier']['business_result_state'])
        for company_id in inputs['variables']['company_ids']:
            self.assertEqual(1,sum(role=='research_response_resolver' and company==company_id for role,company in inputs.dispatched))

    def test_authority_policy_and_unknown_errors_still_propagate(self):
        for rule in ('agent_result_privileged_material_rejected','unknown_rule','agent_result_response_mode_unsupported'):
            with self.subTest(rule=rule):
                with self.assertRaises(RuntimeAgentInvocationError):
                    run(Inputs('portfolio_researcher',rule=rule))
        self.assertIsNone(invocation_diagnostic(failure(cause='provider_execution_authority_scope_mismatch'),role='portfolio_researcher'))
        old=RuntimeAgentInvocationError('agent_bridge_callback_failed',cause_code='provider_execution_vertex_response_invalid')
        self.assertIsNone(invocation_diagnostic(old,role='portfolio_researcher'))

    def test_apply_rejected_before_any_runtime_helpers(self):
        inputs=Inputs()
        inputs['variables']['memory_mode']='apply'
        with self.assertRaises(IndependentReviewRequiredError): run(inputs)
        self.assertEqual([],inputs.dispatched)
        self.assertEqual([],inputs.dynamic_skill_calls)


if __name__=='__main__': unittest.main()
