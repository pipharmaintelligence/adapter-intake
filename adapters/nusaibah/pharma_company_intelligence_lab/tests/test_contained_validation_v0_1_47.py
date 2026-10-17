"""Exercise real validators through final Skill write/readback, without providers."""
from copy import deepcopy
import json
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

import legacy_preparation_helpers_v0_1_23 as legacy
from agent_chunks_v0_1_47 import ChunkCoordinator, BUSINESS_VALIDATION_ERRORS
from research_diagnostics_v0_1_17 import ResearchContractValidationError
from research_response_contract_v0_1_26 import ResearchResponseContractError
from candidate_validation_v0_1_21 import CandidateContractError
from agent_response_recovery_v0_1_40 import AgentResponseDiagnosticError
from orchestration_v0_1_47 import invoke_v0_1_47
from test_profile_primary_v0_1_43 import DraftInputs
from test_grounded_profile_v0_1_40 import NativeInputs
from test_synthesis_candidate_v0_1_46 import envelope, MalformedSynthesis


def invoke(inputs):
    return invoke_v0_1_47(inputs, asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.47')


class ChangedRepairInputs(DraftInputs):
    """The initial invalid enum triggers the real sole repair and real guard."""
    changed_field = 'inference'
    broken_roles = {'regulatory_risk_researcher'}

    def __init__(self):
        super().__init__()
        self.originals = {}
        self.repair_counts = {}

    def invoke_agent(self, role, *, input, on_error='raise'):
        if role == legacy.RESEARCH_RESOLVER_ROLE and input.get('original_role') in self.broken_roles:
            owner = input['original_role']
            self.role_calls.append(role)
            self.repair_counts[owner] = self.repair_counts.get(owner, 0) + 1
            repaired = deepcopy(input['invalid_response'])
            repaired['claims'][0]['confidence'] = 'low'
            changes = {'inference': True, 'statement': 'Fabricated replacement research.',
                       'as_of_date': '2099-01-01', 'citation_locators': ['https://example.org/replaced'],
                       'evidence_qualifiers': ['Invented qualifier'], 'semantic_context': None}
            repaired['claims'][0][self.changed_field] = changes[self.changed_field]
            return envelope(repaired)
        response = super().invoke_agent(role, input=input, on_error=on_error)
        if role in self.broken_roles:
            value = response['result']['content'][0]['value']
            if value['claims']:
                self.originals[role] = deepcopy(value)
                value['claims'][0]['confidence'] = 'INVALID'
        return response


class ContainedValidationTests(unittest.TestCase):
    def setUp(self):
        blocker = patch.object(socket.socket, 'connect', side_effect=AssertionError('Unexpected network access'))
        blocker.start()
        self.addCleanup(blocker.stop)

    def assert_published(self, inputs, result):
        dossier = result['outputs']['intelligence_dossier']
        self.assertTrue(dossier['execution_complete'])
        row = dossier['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'], row['skill_publication'])
        receipt = row['skill_publication']['memory']
        self.assertTrue(receipt['readback_verified'])
        self.assertTrue(receipt['history_verified'])
        text = inputs.store[(13, 'company_memory')]['text']
        self.assertIn('Annex: Need Review', text)
        self.assertEqual(row['profile_document']['text'].strip(),
            inputs.dynamic_skill('company_memory', variables={'company_id':'13'}).section_text('Current Public Research').strip())
        self.assertLessEqual(row['agent_input_preflight']['provider_dispatch_count'], 48)
        self.assertLessEqual(row['agent_input_preflight']['observed_peak_parallel_calls'], 2)
        return row

    def test_observed_inference_repair_failure_preserves_siblings_and_publishes(self):
        inputs = ChangedRepairInputs()
        row = self.assert_published(inputs, invoke(inputs))
        diagnostics = [o['diagnostic'] for o in row['agent_input_preflight']['outcomes'] if o['status']=='unresolved']
        self.assertTrue(any(d['stage']=='research_repair' and d['field']=='claims_inference'
                            and d['rule']=='repair_changed_evidence' for d in diagnostics), diagnostics)
        self.assertEqual({'regulatory_risk_researcher':1}, inputs.repair_counts)
        self.assertGreater(row['unverified_research_count'], 0)
        self.assertNotIn('Fabricated replacement research.', inputs.store[(13,'company_memory')]['text'])

    def test_changed_evidence_types_are_rejected_locally_by_real_repair_guards(self):
        for field in ('statement', 'as_of_date', 'citation_locators', 'evidence_qualifiers'):
            with self.subTest(field=field):
                inputs = ChangedRepairInputs(); inputs.changed_field = field
                row = self.assert_published(inputs, invoke(inputs))
                self.assertTrue(row['unresolved_agent_responses'])
                expected = 'claims.'+field if field in {'citation_locators','evidence_qualifiers'} else 'claims_'+field
                diagnostics=[o['diagnostic'] for o in row['agent_input_preflight']['outcomes'] if o['status']=='unresolved']
                diagnostics.extend(t['diagnostic'] for t in row['agent_response_recovery_trace'] if isinstance(t.get('diagnostic'),dict))
                self.assertTrue(any(d['field']==expected and d['rule']=='repair_changed_evidence' for d in diagnostics),diagnostics)
                self.assertEqual({'regulatory_risk_researcher':1}, inputs.repair_counts)
                self.assertNotIn('Fabricated replacement research.', inputs.store[(13,'company_memory')]['text'])

    def test_simultaneous_research_repair_and_null_synthesis_keep_memory_publication(self):
        class Mixed(MalformedSynthesis, ChangedRepairInputs):
            pass
        inputs = Mixed()
        row = self.assert_published(inputs, invoke(inputs))
        self.assertGreater(row['unverified_research_count'], 0)
        self.assertTrue(row['research_incomplete'])

    def test_every_concrete_business_exception_keeps_exact_diagnostic_and_order(self):
        errors = [
            ResearchContractValidationError(role='regulatory_risk_researcher', stage='research_repair', field='claims_inference', rule='repair_changed_evidence'),
            ResearchResponseContractError(role='market_researcher', field='claims', rule='bounded_list_required'),
            AgentResponseDiagnosticError(role=legacy.CRITIC_ROLE, field='claim_reviews', rule='array_required'),
            legacy.AgentResponseDiagnosticError(role=legacy.SYNTHESIS_ROLE, field='sections', rule='array_required'),
            CandidateContractError(field='memory_candidate.fact_ids', rule='candidate_fact_id_unknown'),
        ]
        self.assertEqual(set(BUSINESS_VALIDATION_ERRORS), {type(e) for e in errors})
        for error in errors:
            with self.subTest(error=type(error).__module__):
                engine=ChunkCoordinator()
                items=[{'company_id':13,'value':'before'}, {'company_id':13,'value':error}, {'company_id':13,'value':'after'}]
                def run(item):
                    if isinstance(item['value'], Exception): raise item['value']
                    return item['value']
                outcomes=engine.parallel(items,run)
                self.assertEqual(['completed','unresolved','completed'],[o['status'] for o in outcomes])
                self.assertEqual(error.proof_failure_detail,outcomes[1]['diagnostic'])
                self.assertEqual('before',outcomes[0]['value']); self.assertEqual('after',outcomes[2]['value'])
                self.assertEqual(0,engine.calls)

    def test_one_research_chunk_preserves_verified_siblings_in_the_same_role(self):
        import devtools.agent_citation_view as view
        if not hasattr(view,'_validated_turns'): self.skipTest('Requires real runtime citation projection')
        class Broken(NativeInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                if role=='portfolio_researcher' and input.get('packing_scope',{}).get('section_ids')==['company_profile']:
                    raise ResearchContractValidationError(role=role,stage='research_repair',field='claims_inference',rule='repair_changed_evidence')
                return super().invoke_agent(role,input=input,on_error=on_error)
        inputs=Broken(); row=self.assert_published(inputs,invoke(inputs))
        self.assertGreater(row['accepted_claim_count'],0)
        self.assertTrue(any(o['status']=='unresolved' for o in row['agent_input_preflight']['outcomes']))
        self.assertTrue(any(o['status']=='completed' and 'product_portfolio_intelligence' in o['section_ids'] for o in row['agent_input_preflight']['outcomes']))

    def test_all_research_rejected_preserves_existing_memory_and_returns_continuation(self):
        class Broken(DraftInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                if role in legacy.RESEARCH_ROLES:
                    raise ResearchContractValidationError(role=role,stage='research_repair',field='claims_inference',rule='repair_changed_evidence')
                return super().invoke_agent(role,input=input,on_error=on_error)
        inputs=Broken(); before=inputs.store[(13,'company_memory')]['text']
        dossier=invoke(inputs)['outputs']['intelligence_dossier']; row=dossier['company_results'][0]
        self.assertTrue(dossier['execution_complete']); self.assertTrue(dossier['continuation_allowed'])
        self.assertEqual(before,inputs.store[(13,'company_memory')]['text'])
        self.assertEqual(0,row['accepted_claim_count'])
        self.assertEqual(0,row['unverified_research_count'])
        self.assertTrue(row['unresolved_agent_responses'])
        self.assertNotIn(legacy.SYNTHESIS_ROLE,inputs.role_calls)

    def test_runtime_authority_and_programming_errors_are_not_converted_to_content_issues(self):
        from devtools.runtime_agent_invocation import RuntimeAgentInvocationError
        errors=[RuntimeAgentInvocationError('agent_execution_provider_member_refresh_mismatch'),
                legacy.AgentContractValidationError('pharma_agent_runtime_envelope_invalid','fixture'),
                ValueError('unknown implementation defect'), TypeError('unknown implementation defect'),
                RuntimeError('storage failure')]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                def fail(_): raise error
                with self.assertRaises(type(error)):
                    ChunkCoordinator().parallel([{'company_id':13}],fail)

    def test_malformed_model_field_matrix_keeps_independent_research(self):
        # Actual model envelopes, validators, resolver exhaustion and publication;
        # no mocked validation result or fake publication receipt.
        cases={
            'regulatory_risk_researcher':['claims','sections','uncertainties'],
            legacy.CRITIC_ROLE:['claim_reviews','future_guidance','citation_coverage','unsupported_claim_ids'],
            legacy.SYNTHESIS_ROLE:['memory_candidate','sections','residual_uncertainties'],
            legacy.STRATEGIC_ROLE:['implications','risks'],
        }
        for owner,fields in cases.items():
            for field in fields:
                for raw in (None, [], {}, 7, 'invalid'):
                    with self.subTest(role=owner,field=field,value=raw):
                        class Broken(DraftInputs):
                            def invoke_agent(self,role,*,input,on_error='raise'):
                                if role==legacy.RESEARCH_RESOLVER_ROLE and input.get('original_role')==owner:
                                    self.role_calls.append(role)
                                    return envelope(input['invalid_response'])
                                response=super().invoke_agent(role,input=input,on_error=on_error)
                                if role==owner:
                                    response['result']['content'][0]['value'][field]=deepcopy(raw)
                                return response
                        inputs=Broken()
                        self.assert_published(inputs,invoke(inputs))

    def test_release_contracts_and_existing_synthesis_fix_are_preserved(self):
        manifest=json.loads((ROOT/'nusaibah_pharma_company_intelligence_lab.asset.json').read_text())
        self.assertIn('0.1.47',manifest['versions'])
        self.assertEqual(manifest['versions']['0.1.46'],manifest['versions']['0.1.47'])


if __name__=='__main__': unittest.main()
