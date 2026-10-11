from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import legacy_preparation_helpers_v0_1_23 as legacy
from orchestration_v0_1_23 import IndependentReviewRequiredError, invoke_v0_1_23
from orchestration_v0_1_24 import (
    BUSINESS_FIELDS, RESEARCH_ROLES, _ResearchContractInputs,
    complete_research_contract, invoke_v0_1_24,
)
from research_claim_pipeline_v0_1_21 import research_response_contract_for_role_v0_1_21
from test_orchestration_preview import _fake_citations
from test_orchestration_v0_1_21 import V021Inputs


class ContractFollowingInputs(V021Inputs):
    """Emit envelope literals only when the producer contract declares them.

    Evidence fixtures are unchanged. This exposes instructions/validator drift
    independently of the older handwritten fixture's completed/v2 envelope.
    """

    def __init__(self):
        super().__init__()
        self['variables'].update(retain_review_packet=True, portfolio_review_passes=2)

    def invoke_agent(self, role, *, input, on_error='raise'):
        envelope = super().invoke_agent(role, input=input, on_error=on_error)
        if role in RESEARCH_ROLES:
            value = envelope['result']['content'][0]['value']
            for field in ('schema_version', 'status'):
                definition = input['response_contract'].get(field)
                if isinstance(definition, dict) and 'required_value' in definition:
                    value[field] = definition['required_value']
                else:
                    value.pop(field, None)
            envelope['result']['text'] = json.dumps(value)
        return envelope


def run(inputs, *, old=False):
    with patch.object(legacy, '_agent_citations', side_effect=_fake_citations):
        method = invoke_v0_1_23 if old else invoke_v0_1_24
        return method(inputs, asset_identity='nusaibah.pharma_company_intelligence_lab:' + ('0.1.23' if old else '0.1.24'))


class ResearchEnvelopeParityV024Tests(unittest.TestCase):
    def test_contract_following_formatter_reproduces_old_gap_and_new_full_two_pass_preview(self):
        old = run(ContractFollowingInputs(), old=True)
        self.assertEqual('incomplete', old['outputs']['intelligence_dossier']['business_result_state'])
        self.assertTrue(all(row['accepted_claim_count'] == 0 for row in old['outputs']['intelligence_dossier']['company_results']))
        inputs = ContractFollowingInputs()
        response = run(inputs)
        dossier = response['outputs']['intelligence_dossier']
        self.assertEqual('review_pending', dossier['business_result_state'])
        for row in dossier['company_results']:
            self.assertGreater(row['accepted_claim_count'], 0)
            self.assertEqual(['validated', 'validated'], [p['status'] for p in row['portfolio_review_trace']])
        self.assertEqual(8, len(dossier['research_response_observations']))
        self.assertTrue(all(h['business_status_class'] == 'completed' and h['business_schema_matches'] for h in dossier['research_response_observations']))
        self.assertFalse(dossier['review_packet']['apply_authority'])
        self.assertEqual(0, response['metrics']['memory_mutations_made'])
        self.assertEqual(0, response['metrics']['methodology_learning_mutations_made'])

    def test_complete_contract_preserves_all_original_field_and_evidence_bounds(self):
        for role in RESEARCH_ROLES:
            for company_id in (13, 14):
                with self.subTest(role=role, company_id=company_id):
                    original = research_response_contract_for_role_v0_1_21(role=role, company_id=company_id)
                    before = copy.deepcopy(original)
                    completed = complete_research_contract(original)
                    self.assertEqual(before, original)
                    self.assertEqual(before, {k: completed[k] for k in before})
                    self.assertEqual(list(BUSINESS_FIELDS), completed['required_fields'])
                    self.assertEqual('completed', completed['status']['required_value'])
                    self.assertEqual('pharma_research_agent.v2', completed['schema_version']['required_value'])
                    self.assertFalse(completed['additional_response_fields_allowed'])
                    completed['claims']['max_items'] = -1
                    self.assertEqual(before, original)

    def test_nonresearch_calls_and_runtime_capabilities_pass_through(self):
        class Inputs(dict):
            def __init__(self): super().__init__(); self.calls = []
            def invoke_agent(self, role, *, input, on_error):
                self.calls.append((role, input, on_error)); return {'unchanged': True}
            def skill(self, selector): return selector
            def dynamic_skill(self, role, **kwargs): return (role, kwargs)
        inputs = Inputs()
        proxy = _ResearchContractInputs(inputs)
        payload = {'company_id': 14, 'response_contract': {'status': 'completed'}}
        self.assertEqual({'unchanged': True}, proxy.invoke_agent('evidence_critic', input=payload, on_error='raise'))
        self.assertIs(payload, inputs.calls[0][1])
        self.assertEqual('fixed', proxy.skill('fixed'))
        self.assertEqual(('memory', {'variables': {'company_id': '14'}}), proxy.dynamic_skill('memory', variables={'company_id': '14'}))
        self.assertEqual([], proxy.observations)

    def test_research_backup_receives_full_contract_without_mutating_original_input(self):
        class Inputs(dict):
            def invoke_agent(self, role, *, input, on_error): self.seen = input; return {}
        inputs = Inputs()
        proxy = _ResearchContractInputs(inputs)
        payload = {'company_id': 14, 'original_role': 'market_researcher',
                   'repair_scope': 'research_business_json', 'response_contract': {'claims': {'max_items': 16}}}
        before = copy.deepcopy(payload)
        proxy.invoke_agent('research_response_resolver', input=payload)
        self.assertEqual(before, payload)
        self.assertEqual(list(BUSINESS_FIELDS), inputs.seen['response_contract']['required_fields'])
        self.assertEqual('completed', inputs.seen['response_contract']['status']['required_value'])

    def test_returned_negative_missing_or_invalid_status_is_never_rewritten_or_retried(self):
        missing = object()
        for status, classification in ((missing, 'missing'), (None, 'invalid_type'), ('incomplete', 'incomplete'),
                                       ('failed', 'failed'), ('success', 'success'), ('RAW_PRIVATE_SENTINEL', 'other_string')):
            with self.subTest(classification=classification):
                class Inputs(ContractFollowingInputs):
                    def invoke_agent(self, role, *, input, on_error='raise'):
                        envelope = super().invoke_agent(role, input=input, on_error=on_error)
                        if role == 'market_researcher':
                            value = envelope['result']['content'][0]['value']
                            if status is missing: value.pop('status')
                            else: value['status'] = status
                        return envelope
                inputs = Inputs()
                response = run(inputs)
                dossier = response['outputs']['intelligence_dossier']
                self.assertTrue(all(row['research_incomplete'] for row in dossier['company_results']))
                self.assertTrue(all(row['memory_update_status'] == 'withheld_incomplete' for row in dossier['company_results']))
                self.assertFalse(any(role == legacy.RESEARCH_RESOLVER_ROLE for role, _ in inputs.agent_calls))
                observations = [h for h in dossier['research_response_observations'] if h['role'] == 'market_researcher']
                self.assertTrue(all(h['business_status_class'] == classification for h in observations))
                self.assertNotIn('RAW_PRIVATE_SENTINEL', json.dumps(observations))

    def test_runtime_failure_and_wrong_identity_remain_strict(self):
        for fault, code in (('runtime', 'pharma_agent_runtime_envelope_invalid'),
                            ('company', 'pharma_agent_company_id_invalid'), ('role', 'pharma_agent_role_invalid')):
            with self.subTest(fault=fault):
                class Inputs(ContractFollowingInputs):
                    def invoke_agent(self, role, *, input, on_error='raise'):
                        envelope = super().invoke_agent(role, input=input, on_error=on_error)
                        if role == 'portfolio_researcher':
                            if fault == 'runtime': envelope['status'] = 'failed'
                            else: envelope['result']['content'][0]['value']['company_id' if fault == 'company' else 'role'] = 999 if fault == 'company' else 'wrong_role'
                        return envelope
                with self.assertRaises(legacy.AgentContractValidationError) as raised:
                    run(Inputs())
                self.assertEqual(code, raised.exception.code)

    def test_apply_still_rejected_before_any_helper_or_provider_call(self):
        inputs = ContractFollowingInputs()
        inputs['variables']['memory_mode'] = 'apply'
        with self.assertRaises(IndependentReviewRequiredError): run(inputs)
        self.assertEqual([], inputs.agent_calls)
        self.assertEqual([], inputs.dynamic_skill_calls)

    def test_manifest_preserves_exact_agent_definitions_skill_references_and_budgets(self):
        previous = json.loads((ROOT/'tests/fixtures/release-0.1.23/nusaibah_pharma_company_intelligence_lab.asset.json').read_text())
        current = json.loads((ROOT/'tests/fixtures/release-0.1.24/nusaibah_pharma_company_intelligence_lab.asset.json').read_text())
        self.assertEqual(previous['versions']['0.1.23'], current['versions']['0.1.24'])
        self.assertEqual(previous['execution'], current['execution'])
        self.assertEqual('0.1.24', current['default'])


if __name__ == '__main__': unittest.main()
