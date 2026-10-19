"""Closed request and terminal response contracts; no live runtime."""
import json
import math
import unittest
from copy import deepcopy
from fakes import FakeInputs, example_inputs
from clinical_failure_intelligence.contracts import ContractError, parse_request, strict_object, canonical_bytes
from clinical_failure_intelligence.runtime_access import decode_terminal


class ContractTests(unittest.TestCase):
    def test_request_modes_preserve_source_assertions(self):
        for mode in ('mechanistic_case', 'cohort_pattern'):
            raw = example_inputs(mode)
            self.assertEqual(raw['clinical_context']['source_assertions'], parse_request(FakeInputs(raw))['context']['source_assertions'])
    def test_parse_makes_detached_copy(self):
        raw = example_inputs(); out = parse_request(FakeInputs(raw))
        out['context']['subject']['product_name'] = 'Changed'
        self.assertNotEqual(raw['clinical_context']['subject']['product_name'], 'Changed')
    def test_missing_and_extra_input_roles_rejected(self):
        for edit in ('missing', 'extra'):
            raw = example_inputs()
            if edit == 'missing': raw.pop('clinical_context')
            else: raw['override'] = {}
            with self.assertRaises(ContractError): parse_request(FakeInputs(raw))
    def test_apply_rejected_before_agent_or_memory(self):
        from clinical_failure_intelligence.orchestration import run_analysis
        raw = example_inputs(); raw['variables']['memory_mode'] = 'apply'; fake = FakeInputs(raw)
        with self.assertRaisesRegex(ContractError, 'apply_not_admitted'): run_analysis(fake)
        self.assertEqual([], fake.calls); self.assertEqual([], fake.memory_calls)
    def test_wrong_subject_rejected(self):
        raw = example_inputs(); raw['clinical_context']['subject']['subject_id'] = 'OTHER'
        with self.assertRaisesRegex(ContractError, 'subject_mismatch'): parse_request(FakeInputs(raw))
    def test_wrong_event_set_rejected(self):
        raw = example_inputs(); raw['clinical_context']['event_ids'] = ['OTHER']
        with self.assertRaisesRegex(ContractError, 'event_scope_mismatch'): parse_request(FakeInputs(raw))
    def test_bad_or_missing_dates_rejected(self):
        for date in ('2025-02-30', 'yesterday', None):
            raw = example_inputs(); raw['variables']['as_of_date'] = date
            with self.assertRaises(ContractError): parse_request(FakeInputs(raw))
    def test_case_needs_product_and_indication(self):
        for field in ('product_id', 'indication'):
            raw = example_inputs(); raw['clinical_context']['subject'][field] = None
            with self.assertRaisesRegex(ContractError, 'subject_incomplete'): parse_request(FakeInputs(raw))
    def test_unknown_request_fields_are_not_execution_configuration(self):
        raw = example_inputs(); raw['variables']['max_agent_calls'] = 999
        with self.assertRaises(ContractError): parse_request(FakeInputs(raw))
    def test_seed_duplicates_and_malformed_lists_rejected(self):
        raw = example_inputs(); seeds = raw['clinical_context']['source_assertions']; seeds.append(deepcopy(seeds[0]))
        with self.assertRaisesRegex(ContractError, 'seed_duplicate'): parse_request(FakeInputs(raw))
        raw = example_inputs(); raw['clinical_context']['source_assertions'][0]['example_drugs'] = 'not-list'
        with self.assertRaises(ContractError): parse_request(FakeInputs(raw))
    def test_authority_fields_rejected_recursively(self):
        for key in ('authorization', 'credentials', 'provider_state', 'raw_obs_response'):
            with self.assertRaisesRegex(ContractError, 'authority_material'): canonical_bytes({'nested': [{key: 'synthetic'}]})
    def test_nonfinite_and_nonjson_rejected(self):
        for value in (math.nan, math.inf, {'unsupported'}):
            with self.assertRaises(ContractError): canonical_bytes({'value': value})
    def test_complete_wrappers_only(self):
        for value in ('{"a":1}', '```json\n{"a":1}\n```', json.dumps('{"a":1}')):
            self.assertEqual({'a': 1}, strict_object(value))
        for value in ('prefix {"a":1}', '{"a":', '[1,2]', 'null'):
            with self.assertRaises(ContractError): strict_object(value)
    def test_duplicate_json_keys_and_nan_rejected(self):
        for value in ('{"a":1,"a":2}', '{"nested":{"x":1,"x":2}}', '{"a":NaN}'):
            with self.assertRaises(ContractError): strict_object(value)
    def test_typed_json_and_text_keep_safe_metadata(self):
        for kind in ('json', 'text'):
            payload = {'a': 'value'}
            block = {'type': 'json', 'value': payload} if kind == 'json' else {'type': 'text', 'text': json.dumps(payload)}
            out, metadata = decode_terminal({'status': 'completed', 'result': {'schema_version': 'agent_result.v1',
                'kind': kind, 'content': [block], 'model': 'synthetic', 'provider_metadata': {'turns': []}}})
            self.assertEqual(payload, out); self.assertEqual('synthetic', metadata['model'])
            self.assertEqual({'turns': []}, metadata['provider_metadata'])
    def test_nonterminal_multiple_blocks_and_wrong_kind_rejected(self):
        base = {'status': 'completed', 'result': {'schema_version': 'agent_result.v1', 'kind': 'json', 'content': [{'type': 'json', 'value': {}}]}}
        variants = []
        v = deepcopy(base); v['status'] = 'pending'; variants.append(v)
        v = deepcopy(base); v['result']['content'] *= 2; variants.append(v)
        v = deepcopy(base); v['result']['kind'] = 'text'; variants.append(v)
        for value in variants:
            with self.assertRaises(ContractError): decode_terminal(value)
    def test_container_values_in_enum_positions_rejected_safely(self):
        for field in ('analysis_mode', 'memory_mode'):
            raw = example_inputs(); raw['variables'][field] = []
            with self.assertRaises(ContractError): parse_request(FakeInputs(raw))


if __name__ == '__main__': unittest.main()
