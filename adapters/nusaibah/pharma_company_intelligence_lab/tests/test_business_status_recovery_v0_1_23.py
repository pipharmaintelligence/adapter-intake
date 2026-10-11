from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import legacy_preparation_helpers_v0_1_21 as historical
import legacy_preparation_helpers_v0_1_23 as legacy
from nusaibah_pharma_company_intelligence_lab_v0_1_23_adapter import NusaibahPharmaCompanyIntelligenceLabV023Adapter
from orchestration_v0_1_23 import IndependentReviewRequiredError, invoke_v0_1_23
from research_execution_v0_1_23 import _repair_research_response_v0_1_23
from test_orchestration_preview import _fake_citations
from test_orchestration_v0_1_21 import V021Inputs


IDENTITY = 'nusaibah.pharma_company_intelligence_lab:0.1.23'


class StatusInputs(V021Inputs):
    def __init__(self, role, status='incomplete', *, reflection_only=False, fault=None):
        super().__init__()
        self.bad_role = role
        self.bad_status = status
        self.reflection_only = reflection_only
        self.fault = fault
        self.original_bad_values = []
        self['variables']['retain_review_packet'] = True
        if reflection_only:
            self['variables']['portfolio_review_passes'] = 2

    def invoke_agent(self, role, *, input=None, on_error='raise'):
        envelope = super().invoke_agent(role, input=input, on_error=on_error)
        value = envelope['result']['content'][0]['value']
        if role == self.bad_role and value['company_id'] == 13:
            if self.reflection_only and input['portfolio_review']['pass_number'] != 2:
                return envelope
            value['status'] = self.bad_status
            if self.fault == 'company':
                value['company_id'] = 999
            elif self.fault == 'role':
                value['role'] = 'wrong_role'
            elif self.fault == 'runtime':
                envelope['status'] = 'failed'
            self.original_bad_values.append(value)
        return envelope


def run(inputs):
    with patch.object(legacy, '_agent_citations', side_effect=_fake_citations):
        return invoke_v0_1_23(inputs, asset_identity=IDENTITY)


class BusinessStatusRecoveryV023Tests(unittest.TestCase):
    def test_non_completed_business_status_retains_each_role_and_continues_next_company(self):
        roles = (legacy.BENCHMARK_ROLE, legacy.PLANNER_ROLE, *legacy.RESEARCH_ROLES,
                 legacy.STRATEGIC_ROLE, legacy.CRITIC_ROLE, legacy.SYNTHESIS_ROLE)
        for role in roles:
            with self.subTest(role=role):
                inputs = StatusInputs(role)
                response = run(inputs)
                dossier = response['outputs']['intelligence_dossier']
                first, second = dossier['company_results']
                self.assertEqual('success', response['status'])
                self.assertTrue(first['research_incomplete'])
                self.assertEqual('review_pending', second['business_result_state'])
                self.assertGreater(second['accepted_claim_count'], 0)
                trace = first['agent_response_recovery_trace']
                diagnostics = [item['diagnostic'] for item in trace if item.get('diagnostic')]
                self.assertTrue(any(d['role'] == role and d['field'] == 'status'
                                    and d['rule'] == 'business_status_not_completed' for d in diagnostics))
                self.assertTrue(all(v['status'] == 'incomplete' for v in inputs.original_bad_values))
                self.assertEqual(0, first['agent_response_resolver_call_count'])
                self.assertFalse(dossier['review_packet']['apply_authority'])
                self.assertEqual(0, response['metrics']['memory_mutations_made'])
                self.assertEqual(0, response['metrics']['methodology_learning_mutations_made'])

    def test_invalid_research_status_preserves_valid_sibling_research(self):
        inputs = StatusInputs('portfolio_researcher')
        response = run(inputs)
        packet = response['outputs']['intelligence_dossier']['review_packet']['companies'][0]
        self.assertGreater(len(packet['accepted_claims']), 0)
        self.assertFalse(any(c['claim_id'].startswith('portfolio_researcher:') for c in packet['accepted_claims']))
        self.assertTrue(any(c['claim_id'].startswith('market_researcher:') for c in packet['accepted_claims']))
        self.assertTrue(any(c['claim_id'].startswith('regulatory_risk_researcher:') for c in packet['accepted_claims']))
        self.assertFalse(packet['memory_proposal']['mutation_eligible'])

    def test_invalid_reflection_retains_the_first_validated_pass_and_stops(self):
        inputs = StatusInputs('portfolio_researcher', reflection_only=True)
        response = run(inputs)
        first = response['outputs']['intelligence_dossier']['company_results'][0]
        self.assertEqual(['validated', 'unresolved'], [p['status'] for p in first['portfolio_review_trace']])
        self.assertEqual(first['portfolio_review_trace'][0]['result_sha256'], first['portfolio_review_trace'][1]['result_sha256'])
        self.assertGreater(first['portfolio_review_trace'][1]['claim_count'], 0)
        self.assertTrue(first['research_incomplete'])

    def test_status_missing_invalid_type_or_failure_never_becomes_completed(self):
        for status in (None, {}, 'failed', 'success', 'Completed'):
            with self.subTest(status=status):
                inputs = StatusInputs('market_researcher', status)
                response = run(inputs)
                self.assertTrue(response['outputs']['intelligence_dossier']['company_results'][0]['research_incomplete'])
                self.assertTrue(all(v['status'] == status for v in inputs.original_bad_values))

    def test_all_research_statuses_unresolved_skip_dependent_paid_stages(self):
        class Inputs(V021Inputs):
            def invoke_agent(self, role, *, input=None, on_error='raise'):
                envelope = super().invoke_agent(role, input=input, on_error=on_error)
                value = envelope['result']['content'][0]['value']
                if role in legacy.RESEARCH_ROLES and value['company_id'] == 13:
                    value['status'] = 'incomplete'
                return envelope
        inputs = Inputs()
        inputs['variables']['retain_review_packet'] = True
        response = run(inputs)
        first = response['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(first['research_incomplete'])
        self.assertEqual(0, first['accepted_claim_count'])
        self.assertFalse(any(company == 13 and role in (legacy.STRATEGIC_ROLE, legacy.CRITIC_ROLE,
            legacy.SYNTHESIS_ROLE, legacy.RESEARCH_RESOLVER_ROLE) for role, company, _ in inputs.agent_inputs))

    def test_runtime_failure_and_company_role_mismatch_remain_strict(self):
        for fault, code in (('runtime', 'pharma_agent_runtime_envelope_invalid'),
                            ('company', 'pharma_agent_company_id_invalid'),
                            ('role', 'pharma_agent_role_invalid')):
            with self.subTest(fault=fault):
                with self.assertRaises(legacy.AgentContractValidationError) as raised:
                    run(StatusInputs('portfolio_researcher', fault=fault))
                self.assertEqual(code, raised.exception.code)

    def test_backup_non_completed_status_retains_one_issue_without_second_call(self):
        class Inputs:
            def __init__(self): self.calls = 0; self.trace = []
            def record_response_recovery(self, **entry): self.trace.append(entry)
            def invoke_response_resolver(self, **kwargs):
                self.calls += 1
                value = copy.deepcopy(kwargs['input']['invalid_response'])
                value['status'] = 'incomplete'
                return {'status': 'completed', 'result': {'schema_version': 'agent_result.v1',
                    'kind': 'json', 'content': [{'type': 'json', 'value': value}]}}
        inputs = Inputs()
        value = {'company_id': 13, 'role': legacy.STRATEGIC_ROLE, 'status': 'completed',
                 'schema_version': legacy.STRATEGIC_SCHEMA_VERSION, 'sections': []}
        envelope = {'status': 'completed', 'result': {'schema_version': 'agent_result.v1',
                    'kind': 'json', 'content': [{'type': 'json', 'value': value}]}}
        def invalid(_): raise ValueError('fixture invalid field')
        contract = {'schema_version': legacy.STRATEGIC_SCHEMA_VERSION, 'required_fields': list(value)}
        with self.assertRaises(legacy.UnresolvedAgentResponse) as raised:
            legacy._validated_agent_response(inputs, envelope, role=legacy.STRATEGIC_ROLE,
                company_id=13, contract=contract, validator=invalid)
        self.assertEqual(1, inputs.calls)
        self.assertEqual('status', raised.exception.diagnostic['field'])
        self.assertEqual('business_status_not_completed', raised.exception.diagnostic['rule'])

    def test_research_backup_non_completed_status_is_withheld_after_one_call(self):
        class Inputs:
            def __init__(self): self.calls = 0; self.trace = []
            def record_response_recovery(self, **entry): self.trace.append(entry)
            def invoke_response_resolver(self, **kwargs):
                self.calls += 1
                value = copy.deepcopy(kwargs['input']['invalid_response'])
                value['status'] = 'incomplete'
                return {'status': 'completed', 'result': {'schema_version': 'agent_result.v1',
                    'kind': 'json', 'content': [{'type': 'json', 'value': value}]}}
        inputs = Inputs()
        value = {'company_id': 13, 'role': 'portfolio_researcher', 'status': 'completed',
                 'schema_version': 'pharma_research_agent.v2', 'sections': [], 'claims': [], 'uncertainties': []}
        error = SimpleNamespace(proof_failure_detail={'schema_version': 'proof_failure_detail.v1',
            'proof_kind': 'agent_contract', 'role': 'portfolio_researcher',
            'stage': 'research_payload', 'rule': 'fixture_invalid', 'field': 'sections'})
        repaired, repairs, diagnostic = _repair_research_response_v0_1_23(inputs, value=value,
            role='portfolio_researcher', company_id=13, initial_error=error)
        self.assertIsNone(repaired)
        self.assertEqual([], repairs)
        self.assertEqual('business_status_not_completed', diagnostic['rule'])
        self.assertEqual(1, inputs.calls)

    def test_historical_extractor_retains_its_strict_status_behavior(self):
        envelope = {'status': 'completed', 'result': {'schema_version': 'agent_result.v1',
                    'kind': 'json', 'content': [{'type': 'json', 'value': {
                        'company_id': 13, 'role': 'portfolio_researcher',
                        'status': 'incomplete', 'schema_version': 'pharma_research_agent.v2'}}]}}
        with self.assertRaises(historical.AgentContractValidationError) as raised:
            historical.extract_agent_json(envelope, expected_role='portfolio_researcher',
                company_id=13, expected_schema_version='pharma_research_agent.v2')
        self.assertEqual('pharma_agent_status_invalid', raised.exception.code)

    def test_manifest_reuses_exact_agent_budgets_and_apply_rejected_before_calls(self):
        previous = json.loads((ROOT/'tests/fixtures/release-0.1.22/nusaibah_pharma_company_intelligence_lab.asset.json').read_text())
        current = json.loads((ROOT/'tests/fixtures/release-0.1.23/nusaibah_pharma_company_intelligence_lab.asset.json').read_text())
        self.assertEqual(previous['versions']['0.1.22'], current['versions']['0.1.23'])
        inputs = V021Inputs()
        inputs['variables']['memory_mode'] = 'apply'
        with self.assertRaises(IndependentReviewRequiredError):
            NusaibahPharmaCompanyIntelligenceLabV023Adapter().invoke(inputs, {})
        self.assertEqual([], inputs.agent_calls)
        self.assertEqual([], inputs.dynamic_skill_calls)


if __name__ == '__main__':
    unittest.main()
