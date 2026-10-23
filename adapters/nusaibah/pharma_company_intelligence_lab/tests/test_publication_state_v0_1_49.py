"""Exercise retention-to-publication with no providers and synthetic Skill I/O."""
from copy import deepcopy
from pathlib import Path
import socket
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]
import automatic_publication_v0_1_45 as previous
from automatic_publication_v0_1_49 import publish_company
from continuation_v0_1_43 import admit_retention
from orchestration_v0_1_49 import invoke_v0_1_49
from test_profile_primary_v0_1_43 import DraftInputs


class PublicationStateTests(unittest.TestCase):
    def setUp(self):
        blocker = patch.object(socket.socket, 'connect', side_effect=AssertionError('Unexpected network access'))
        blocker.start()
        self.addCleanup(blocker.stop)

    def assert_withheld(self, publication):
        self.assertFalse(publication['publication_complete'])
        self.assertTrue(publication['continuation_allowed'])
        self.assertFalse(publication['required_mutation'])
        for name in ('memory', 'methodology'):
            receipt = publication[name]
            self.assertEqual('withheld', receipt['status'])
            self.assertEqual('enrichment_unresolved', receipt['reason'])
            self.assertFalse(receipt['write_attempted'])
            self.assertFalse(receipt['readback_verified'])
            self.assertIsNone(receipt['change_id'])

    def test_incomplete_result_precedes_empty_candidate_and_no_enrichment(self):
        for no_enrichment in (False, True):
            state = {'company_id': 62, 'incomplete_schema_preview': True,
                     'no_supported_enrichment': no_enrichment,
                     'memory_candidate': SimpleNamespace(fact_ids=()),
                     'result': {'research_incomplete': True}}
            with patch.object(previous, 'read_company_memory') as memory, \
                 patch.object(previous, 'load_methodology_learning') as methodology, \
                 patch.object(previous, '_apply_section') as apply, \
                 patch.object(previous, 'initialize_section') as initialize:
                self.assert_withheld(publish_company(object(), state))
                for call in (memory, methodology, apply, initialize):
                    call.assert_not_called()

    def test_real_retention_compaction_cannot_crash_or_write(self):
        state = {'company_id': 62, 'memory_candidate': SimpleNamespace(fact_ids=()),
                 'result': {'company_id': 62, 'section_enrichment': {}, 'fixture_text': 'x' * 500000}}
        sibling = {'company_id': 63, 'result': {'company_id': 63, 'accepted_claim_count': 1}}
        sibling_before = deepcopy(sibling['result'])
        admit_retention([state, sibling], SimpleNamespace(proof=lambda: {}),
                        SimpleNamespace(observations=[], invocation_issues=[]))
        self.assertTrue(state['incomplete_schema_preview'])
        self.assertNotIn('section_enrichment', state['result'])
        self.assertFalse(state['result']['retention_admission']['candidate_truncated'])
        self.assertEqual(sibling_before, {k: v for k, v in sibling['result'].items()
                                         if k != 'agent_input_preflight'})
        self.assert_withheld(publish_company(object(), state))

    def test_complete_orchestration_continues_after_retention_with_zero_writes(self):
        inputs = DraftInputs()
        before = deepcopy(inputs.store)

        def bounded_retention(states, coordinator, forwarded):
            return admit_retention(states, coordinator, forwarded, maximum=4096)

        with patch('orchestration_v0_1_49.admit_retention', side_effect=bounded_retention):
            result = invoke_v0_1_49(inputs, asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.49')
        dossier = result['outputs']['intelligence_dossier']
        self.assertEqual('success', result['status'])
        self.assertTrue(dossier['execution_complete'])
        self.assertTrue(dossier['continuation_allowed'])
        self.assertFalse(dossier['publication_complete'])
        self.assertEqual('enrichment_ready_or_partial', dossier['business_result_state'])
        self.assert_withheld(dossier['company_results'][0]['skill_publication'])
        self.assertEqual(before, inputs.store)
        self.assertEqual([], inputs.mutables)
        self.assertEqual(0, result['metrics']['memory_mutations_made'])
        self.assertEqual(0, result['metrics']['methodology_learning_mutations_made'])

    def test_ordinary_state_still_publishes_and_verifies_readback_and_history(self):
        inputs = DraftInputs()
        result = invoke_v0_1_49(inputs, asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.49')
        publication = result['outputs']['intelligence_dossier']['company_results'][0]['skill_publication']
        self.assertTrue(publication['publication_complete'])
        for name in ('memory', 'methodology'):
            self.assertTrue(publication[name]['readback_verified'])
            self.assertTrue(publication[name]['history_verified'])

    def test_unmarked_state_delegates_without_reclassifying_write_failure(self):
        state = {'company_id': 62}
        failed = {'publication_complete': False, 'memory': {'status': 'apply_failed_or_unconfirmed'}}
        with patch.object(previous, 'publish_company', return_value=failed) as publish:
            self.assertIs(failed, publish_company(object(), state))
            publish.assert_called_once()
        self.assertNotIn('continuation_allowed', failed)


if __name__ == '__main__':
    unittest.main()
