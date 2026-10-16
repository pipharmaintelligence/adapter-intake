"""Provider-free regression coverage for content, publication and concurrency."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import socket
import sys
from threading import Barrier, Lock
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]
import orchestration_v0_1_50 as orchestration
from agent_chunks_v0_1_47 import ChunkCoordinator
from memory_contract import MemoryCandidate, MEMORY_TARGET_SECTION
from profile_research_v0_1_50 import build_profile_candidate, MAX_PROFILE_CHARS
from profile_research_v0_1_45 import MAX_PROFILE_CHARS as OLD_PROFILE_CHARS
from retention_v0_1_50 import retain_dossier, REPORT_BYTES, OUTPUT_BYTES
from test_profile_primary_v0_1_43 import DraftInputs
from devtools.preview_output_validator import PreviewOutputValidationError
import retention_v0_1_50 as retention


class ContentBudgetTests(unittest.TestCase):
    def setUp(self):
        blocker = patch.object(socket.socket, 'connect', side_effect=AssertionError('Unexpected network access'))
        blocker.start()
        self.addCleanup(blocker.stop)

    def run_fixture(self, inputs):
        return orchestration.invoke_v0_1_50(inputs, asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.50')

    def test_oversized_diagnostics_do_not_change_memory_or_publication_receipts(self):
        control = DraftInputs()
        expected = self.run_fixture(control)
        inputs = DraftInputs()
        original = orchestration.prepare_report
        def padded(states, coordinator):
            original(states, coordinator)
            states[0]['result']['diagnostic_fixture'] = 'x' * (REPORT_BYTES + 1000)
        with patch.object(orchestration, 'prepare_report', side_effect=padded):
            actual = self.run_fixture(inputs)
        dossier = actual['outputs']['intelligence_dossier']
        row = dossier['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertEqual(control.store[(13, 'company_memory')]['text'], inputs.store[(13, 'company_memory')]['text'])
        self.assertTrue(row['skill_publication']['memory']['readback_verified'])
        self.assertTrue(row['skill_publication']['memory']['history_verified'])
        self.assertEqual(expected['metrics'], actual['metrics'])
        self.assertNotIn('diagnostic_fixture', row)
        self.assertFalse(dossier['report_retention']['candidate_truncated'])
        self.assertLess(len(json.dumps(dossier).encode()), OUTPUT_BYTES)

    def test_invalid_optional_report_field_does_not_veto_valid_candidate(self):
        inputs = DraftInputs()
        original = orchestration.prepare_report
        validator = retention.validate_preview_outputs
        def prepare(states, coordinator):
            original(states, coordinator)
            states[0]['result']['diagnostic_fixture'] = {'token': 'synthetic-rejected-value'}
        def validate(value):
            if 'diagnostic_fixture' in value.get('intelligence_dossier', {}):
                raise PreviewOutputValidationError('forbidden_field', ())
            validator(value)
        with patch.object(orchestration, 'prepare_report', side_effect=prepare), \
             patch.object(retention, 'validate_preview_outputs', side_effect=validate):
            row = self.run_fixture(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertNotIn('diagnostic_fixture', row)

    def test_unsafe_candidate_still_blocks_both_writes(self):
        inputs = DraftInputs()
        before = deepcopy(inputs.store)
        original = retention.validate_preview_outputs
        def reject_candidate(value):
            if 'proposed_skills' in value:
                raise PreviewOutputValidationError('unsafe_runtime_value', ())
            original(value)
        with patch.object(retention, 'validate_preview_outputs', side_effect=reject_candidate):
            row = self.run_fixture(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertFalse(row['skill_publication']['publication_complete'])
        self.assertEqual('withheld', row['skill_publication']['memory']['status'])
        self.assertEqual(before, inputs.store)

    def test_preview_still_makes_no_writes(self):
        inputs = DraftInputs()
        inputs['variables']['memory_mode'] = 'preview'
        before = deepcopy(inputs.store)
        result = self.run_fixture(inputs)
        self.assertEqual(before, inputs.store)
        self.assertEqual(0, result['metrics']['memory_mutations_made'])

    def test_profile_above_old_ceiling_preserves_every_distinct_statement(self):
        claims = [{'claim_id': f'draft{i}', 'section_id': 'company_profile',
                   'statement': f'Finding {i}: '+('Substantive synthetic company observation. ' * 12),
                   'citation_locators': [], 'verification_status': 'unverified', 'evidence_qualifiers': []}
                  for i in range(240)]
        candidate, metadata = build_profile_candidate(
            MemoryCandidate(13, MEMORY_TARGET_SECTION, '', ()), '', [], research=claims)
        self.assertGreater(len(candidate.markdown), OLD_PROFILE_CHARS)
        self.assertLess(len(candidate.markdown), MAX_PROFILE_CHARS)
        self.assertEqual(384000, MAX_PROFILE_CHARS)
        self.assertEqual(96000, OLD_PROFILE_CHARS)
        self.assertEqual([], metadata['omitted_facts'])
        self.assertEqual(240, len(metadata['paragraphs']))
        self.assertEqual((), candidate.fact_ids)

    def test_three_default_and_override_rejects_four(self):
        row = self.run_fixture(DraftInputs())['outputs']['intelligence_dossier']['company_results'][0]
        self.assertEqual(3, row['agent_input_preflight']['max_parallel_calls'])
        inputs = DraftInputs()
        inputs['variables']['agent_chunk_parallelism'] = 2
        row = self.run_fixture(inputs)['outputs']['intelligence_dossier']['company_results'][0]
        self.assertEqual(2, row['agent_input_preflight']['max_parallel_calls'])
        inputs['variables']['agent_chunk_parallelism'] = 4
        with self.assertRaisesRegex(ValueError, 'agent_parallelism_must_be_1_to_3'):
            self.run_fixture(inputs)

    def test_scheduler_really_overlaps_three_and_never_four(self):
        coordinator = ChunkCoordinator(parallelism=3)
        barrier = Barrier(3)
        lock = Lock()
        active = peak = 0
        def task(number):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            barrier.wait(timeout=5)
            with lock:
                active -= 1
            return number
        results = coordinator.parallel(list(range(6)), task)
        self.assertEqual(3, peak)
        self.assertEqual(list(range(6)), [r['value'] for r in results])

    def test_final_report_can_omit_copy_of_profile_without_changing_original_or_receipt(self):
        receipt = {'publication_complete': True, 'memory': {'status': 'applied', 'readback_verified': True}}
        source = {'company_results': [{'company_id': 13, 'skill_publication': receipt,
                                      'profile_document': {'text': 'x' * (REPORT_BYTES + 1)}}]}
        saved = deepcopy(source)
        result = retain_dossier(source)
        self.assertEqual(saved, source)
        self.assertEqual(receipt, result['company_results'][0]['skill_publication'])
        self.assertNotIn('profile_document', result['company_results'][0])
        self.assertEqual('complete_with_omissions', result['report_retention']['status'])

    def test_only_new_role_definitions_change_and_storage_roles_are_identical(self):
        manifest = json.loads((ROOT/'nusaibah_pharma_company_intelligence_lab.asset.json').read_text())
        old, new = manifest['versions']['0.1.49'], manifest['versions']['0.1.50']
        self.assertEqual(old['runtime_skills'], new['runtime_skills'])
        self.assertEqual(old['published_skills'], new['published_skills'])
        self.assertEqual(old['execution'], new['execution'])
        changed = {'portfolio_researcher', 'market_researcher', 'regulatory_risk_researcher',
                   'strategic_analyst', 'evidence_critic', 'intelligence_synthesizer'}
        for role, agent in new['agents'].items():
            if role not in changed:
                self.assertEqual(old['agents'][role], agent)
                continue
            self.assertNotEqual(old['agents'][role]['contract_version'], agent['contract_version'])
            self.assertEqual(agent['contract_version'], agent['definition']['chain']['version'])
            step = agent['definition']['chain']['steps'][0]
            self.assertIn('ROLE-SPECIFIC COVERAGE:', step['input']['text'])
            self.assertLessEqual(len(step['input']['text']), 8192)
            self.assertEqual(old['agents'][role]['definition']['chain']['steps'][0]['provider_policy'], step['provider_policy'])


if __name__ == '__main__':
    unittest.main()
