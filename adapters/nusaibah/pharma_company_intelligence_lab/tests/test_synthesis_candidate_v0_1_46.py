"""Malformed presentation candidates must not erase independently usable research."""
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
from agent_chunks_v0_1_42 import ChunkCoordinator
from dossier_contract import render_empty_sections
from orchestration_v0_1_46 import invoke_v0_1_46
from profile_narrative_v0_1_46 import synthesize_packet
from test_grounded_profile_v0_1_40 import NativeInputs
from test_profile_primary_v0_1_43 import DraftInputs


def envelope(value):
    return {'status': 'completed', 'result': {
        'schema_version': 'agent_result.v1', 'kind': 'json',
        'content': [{'type': 'json', 'value': deepcopy(value)}],
    }}


def business():
    return {
        'schema_version': legacy.SYNTHESIS_SCHEMA_VERSION,
        'company_id': 13, 'role': legacy.SYNTHESIS_ROLE, 'status': 'completed',
        'sections': render_empty_sections(), 'residual_uncertainties': [],
        'memory_candidate': {'company_id': 13, 'markdown': 'Synthetic staging text.', 'fact_ids': []},
    }


class AgentFixture:
    def __init__(self, value):
        self.value = value
        self.calls = 0
        self.backups = 0
        self.recoveries = []

    def invoke_agent(self, *args, **kwargs):
        self.calls += 1
        return envelope(self.value)

    def invoke_response_resolver(self, *args, **kwargs):
        self.backups += 1
        return envelope(self.value)

    def record_response_recovery(self, **kwargs):
        self.recoveries.append(kwargs)


class MalformedSynthesis:
    """Keep the same invalid business response through its sole fake backup."""
    broken_sections = None

    def invoke_agent(self, role, *, input, on_error='raise'):
        if role == legacy.RESEARCH_RESOLVER_ROLE and input.get('original_role') == legacy.SYNTHESIS_ROLE:
            self.role_calls.append(role)
            self.agent_inputs.append((role, input['company_id'], deepcopy(input)))
            return envelope(input['invalid_response'])
        response = super().invoke_agent(role, input=input, on_error=on_error)
        if role == legacy.SYNTHESIS_ROLE:
            sections = set(input.get('packing_scope', {}).get('section_ids', []))
            if self.broken_sections is None or self.broken_sections.intersection(sections):
                response['result']['content'][0]['value']['memory_candidate'] = None
        return response


class MalformedDraftInputs(MalformedSynthesis, DraftInputs):
    pass


class MalformedVerifiedInputs(MalformedSynthesis, NativeInputs):
    pass


class SynthesisCandidateTests(unittest.TestCase):
    def setUp(self):
        # Neither the unit fixtures nor the full Skill fixture may reach a provider.
        self.network = patch.object(socket.socket, 'connect', side_effect=AssertionError('Unexpected network access'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def packet(self):
        return {'response_contract': legacy.response_contract_for_role(legacy.SYNTHESIS_ROLE, company_id=13)}

    def test_non_object_and_missing_candidates_use_one_backup_then_structured_issue(self):
        missing = object()
        for raw in (None, [], '', 'invalid', 7, True, missing):
            with self.subTest(candidate_type=type(raw).__name__):
                value = business()
                if raw is missing:
                    value.pop('memory_candidate')
                else:
                    value['memory_candidate'] = raw
                inputs = AgentFixture(value)
                with self.assertRaises(legacy.UnresolvedAgentResponse) as caught:
                    synthesize_packet(inputs, self.packet(), company_id=13)
                self.assertEqual(1, inputs.calls)
                self.assertEqual(1, inputs.backups)
                self.assertEqual('memory_candidate', caught.exception.diagnostic['field'])
                self.assertEqual('object_required', caught.exception.diagnostic['rule'])

    def test_empty_verified_fact_set_keeps_valid_object_without_backup(self):
        inputs = AgentFixture(business())
        _, candidate = synthesize_packet(inputs, self.packet(), company_id=13)
        self.assertEqual((), candidate.fact_ids)
        self.assertEqual(0, inputs.backups)

    def test_bad_chunk_does_not_erase_a_completed_sibling(self):
        valid, invalid = business(), business()
        invalid['memory_candidate'] = None
        coordinator = ChunkCoordinator(parallelism=2)
        items = [{'company_id': 13, 'value': value} for value in (valid, invalid)]
        outcomes = coordinator.parallel(items, lambda item: synthesize_packet(
            AgentFixture(item['value']), self.packet(), company_id=13))
        self.assertEqual(['completed', 'unresolved'], [row['status'] for row in outcomes])

    def test_unknown_runtime_failure_still_propagates_without_backup(self):
        inputs = AgentFixture(business())
        with patch.object(inputs, 'invoke_agent', side_effect=RuntimeError('fixture transport failure')):
            with self.assertRaisesRegex(RuntimeError, 'fixture transport failure'):
                synthesize_packet(inputs, self.packet(), company_id=13)
        self.assertEqual(0, inputs.backups)

    def test_wrong_company_does_not_become_a_valid_candidate(self):
        value = business()
        value['company_id'] = 999
        inputs = AgentFixture(value)
        with self.assertRaises(legacy.AgentContractValidationError):
            synthesize_packet(inputs, self.packet(), company_id=13)
        self.assertEqual(0, inputs.backups)

    def test_all_null_draft_candidates_still_publish_explicitly_unverified_research(self):
        inputs = MalformedDraftInputs()
        result = invoke_v0_1_46(inputs, asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.46')
        row = result['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'], row['skill_publication'])
        self.assertEqual(0, row['accepted_claim_count'])
        self.assertGreater(row['unverified_research_count'], 0)
        text = inputs.store[(13, 'company_memory')]['text']
        self.assertIn('**Unverified research.**', text)
        self.assertIn('Annex: Need Review', text)
        self.assertIn('Annex: Unverified Research', text)
        self.assertTrue(row['skill_publication']['memory']['readback_verified'])
        self.assertTrue(row['skill_publication']['memory']['history_verified'])
        self.assertNotIn(legacy.BENCHMARK_ROLE, inputs.role_calls)
        self.assertLessEqual(row['agent_input_preflight']['provider_dispatch_count'], 48)

    def test_all_null_verified_candidates_still_publish_reviewed_claim_fallback(self):
        import devtools.agent_citation_view as citation_view
        if not hasattr(citation_view, '_validated_turns'):
            self.skipTest('Native-grounding qualification requires the real runtime citation projection')
        inputs = MalformedVerifiedInputs()
        result = invoke_v0_1_46(inputs, asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.46')
        row = result['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'], row['skill_publication'])
        self.assertGreater(row['accepted_claim_count'], 0)
        self.assertTrue(row['section_enrichment']['paragraphs'])
        self.assertTrue(all(p['basis'] == 'original_research_prose_fallback'
                            for p in row['section_enrichment']['paragraphs']))
        self.assertTrue(all(p['verification_status'] == 'verified'
                            for p in row['section_enrichment']['paragraphs']))
        self.assertTrue(row['skill_publication']['memory']['readback_verified'])
        self.assertTrue(row['skill_publication']['memory']['history_verified'])
        self.assertIn('Annex: Need Review', inputs.store[(13, 'company_memory')]['text'])

    def test_release_reuses_exact_agent_storage_and_authority_contracts(self):
        manifest = json.loads((ROOT / 'nusaibah_pharma_company_intelligence_lab.asset.json').read_text())
        self.assertIn('0.1.46', manifest['versions'])
        self.assertEqual(manifest['versions']['0.1.45'], manifest['versions']['0.1.46'])


if __name__ == '__main__':
    unittest.main()
