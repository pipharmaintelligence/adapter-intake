"""Real recovery budgets, validation and publication; synthetic provider/Skill I/O."""
from copy import deepcopy
import json
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch, Mock
from threading import Lock
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]
import legacy_preparation_helpers_v0_1_23 as legacy
from orchestration_v0_1_48 import invoke_v0_1_48
from test_profile_primary_v0_1_43 import DraftInputs
from test_synthesis_candidate_v0_1_46 import envelope
import test_contained_validation_v0_1_47 as previous
from research_response_contract_v0_1_26 import RESEARCH_SCHEMA_VERSION
from invocation_recovery_v0_1_48 import BoundedRecoveryInputs
from devtools.trusted_runtime_callable_child_bridge import RuntimeCallableBridgeError


class WrongSchema(DraftInputs):
    alter_business = False
    bad_identity = False

    def __init__(self):
        super().__init__()
        self.schema_repairs = 0

    def invoke_agent(self, role, *, input, on_error='raise'):
        if role == legacy.RESEARCH_RESOLVER_ROLE and input.get('repair_instruction', '').startswith('Correct schema_version only'):
            self.schema_repairs += 1
            self.role_calls.append(role)
            value = deepcopy(input['invalid_response'])
            value['schema_version'] = RESEARCH_SCHEMA_VERSION
            if self.alter_business:
                value['uncertainties'] = ['Invented replacement uncertainty.']
            return envelope(value)
        response = super().invoke_agent(role, input=input, on_error=on_error)
        if role == 'regulatory_risk_researcher':
            response['result']['content'][0]['value']['schema_version'] = 'wrong_schema.v1'
            if self.bad_identity:
                response['result']['content'][0]['value']['company_id'] = 999
        return response


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        blocker = patch.object(socket.socket, 'connect', side_effect=AssertionError('Unexpected network access'))
        blocker.start(); self.addCleanup(blocker.stop)

    def invoke(self, inputs):
        return invoke_v0_1_48(inputs, asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.48')

    def test_wrong_schema_uses_existing_budget_then_publishes(self):
        inputs = WrongSchema()
        row = previous.ContainedValidationTests.assert_published(self, inputs, self.invoke(inputs))
        self.assertGreater(inputs.schema_repairs, 0)
        self.assertTrue(any(t['status'] == 'schema_echo_repaired' for t in row['agent_response_recovery_trace']))
        self.assertEqual(len(inputs.role_calls), row['agent_input_preflight']['provider_dispatch_count'])
        self.assertFalse(any(d.get('rule') == 'schema_version' for d in row['unresolved_agent_responses']))

    def test_repair_cannot_change_business_content(self):
        inputs = WrongSchema(); inputs.alter_business = True
        result = self.invoke(inputs)
        row = previous.ContainedValidationTests.assert_published(self, inputs, result)
        self.assertNotIn('Invented replacement uncertainty.', json.dumps(result))
        self.assertTrue(row['research_incomplete'])
        self.assertTrue(any(t.get('diagnostic', {}).get('rule') == 'repair_changed_business_content'
                            for t in row['agent_response_recovery_trace']))

    def test_wrong_identity_does_not_spend_schema_repair(self):
        inputs = WrongSchema(); inputs.bad_identity = True
        self.invoke(inputs)
        self.assertEqual(0, inputs.schema_repairs)

    def test_existing_changed_evidence_guard_still_keeps_valid_siblings(self):
        inputs = previous.ChangedRepairInputs()
        previous.ContainedValidationTests.assert_published(self, inputs, self.invoke(inputs))

    def test_preflight_uses_current_toolkit_without_agents_or_writes(self):
        inputs = DraftInputs()
        inputs['variables'].update(memory_mode='preview', preflight_only=True)
        writes_before = deepcopy(inputs.store)
        result = self.invoke(inputs)
        self.assertTrue(result['outputs']['intelligence_dossier']['company_results'][0]['toolkit_spans_verified'])
        self.assertEqual([], inputs.role_calls)
        self.assertEqual(writes_before, inputs.store)
        self.assertEqual(0, result['metrics']['agent_call_count'])

    def span_inputs(self, failures, *, deadline=1000, used=0):
        bounded = object.__new__(BoundedRecoveryInputs)
        bounded._source_lock = Lock(); bounded._source_toolkit_calls = used
        bounded._runtime_inputs = Mock()
        bounded._runtime_inputs.invoke_asset.side_effect = failures
        bounded.coordinator = SimpleNamespace(publication_reserve_seconds=300, clock=lambda: 0, deadline=deadline)
        return bounded

    def test_only_confirmed_pure_tool_timeouts_retry_within_same_call_budget(self):
        timeout = RuntimeCallableBridgeError('direct_runtime_callable_execution_timed_out')
        bounded = self.span_inputs([timeout, timeout, {'status':'success'}])
        with patch('invocation_recovery_v0_1_48.time.sleep') as sleep:
            self.assertEqual({'status':'success'}, bounded.invoke_asset('review_toolkit', variables={'operation':'resolve_exact_spans'}))
        self.assertEqual([5, 10], [c.args[0] for c in sleep.call_args_list])
        self.assertEqual(3, bounded._source_toolkit_calls)

    def test_tool_retry_never_replays_unknown_failures_or_spends_publication_reserve(self):
        for role, code, deadline, used in (
            ('other', 'direct_runtime_callable_execution_timed_out', 1000, 0),
            ('review_toolkit', 'direct_runtime_callable_execution_failed', 1000, 0),
            ('review_toolkit', 'direct_runtime_callable_execution_timed_out', 330, 0),
            ('review_toolkit', 'direct_runtime_callable_execution_timed_out', 1000, 31),
        ):
            with self.subTest(role=role, code=code, deadline=deadline, used=used):
                bounded = self.span_inputs([RuntimeCallableBridgeError(code)], deadline=deadline, used=used)
                with patch('invocation_recovery_v0_1_48.time.sleep') as sleep, self.assertRaises(RuntimeCallableBridgeError):
                    bounded.invoke_asset(role, variables={'operation':'resolve_exact_spans'})
                self.assertEqual(1, bounded._runtime_inputs.invoke_asset.call_count)
                sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()
