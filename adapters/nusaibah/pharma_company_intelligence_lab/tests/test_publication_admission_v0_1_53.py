"""Provider-free selective redaction, evidence downgrade and publication parity."""
from dataclasses import replace
from pathlib import Path
import json
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]

import unittest
from importlib.util import find_spec
from memory_contract import MemoryCandidate, MEMORY_TARGET_SECTION
from publication_admission_v0_1_53 import preflight_publication
from methodology_learning_v0_1_42 import build_methodology_learning_proposal, read_guidance, fingerprint
from automatic_publication_v0_1_53 import diagnostic
from devtools.dynamic_skill_runtime import DynamicSkillRuntimeError
from test_durable_batched_v0_1_51 import BatchedInputs
from orchestration_v0_1_52 import invoke_v0_1_52
from orchestration_v0_1_53 import invoke_v0_1_53
import orchestration_v0_1_53 as current




def state(text, methodology=None):
    return {'company_id':13, 'memory_candidate':MemoryCandidate(13, MEMORY_TARGET_SECTION, text, ('f1','f2')),
        'methodology_learning_candidate':methodology, 'before_target_text':'', 'candidate_changed':True,
        'result':{'section_enrichment':{'paragraphs':[
            {'section_number':1,'paragraph':1,'section_id':'company_profile','claim_ids':['f1'],'verification_status':'verified'},
            {'section_number':1,'paragraph':2,'section_id':'company_profile','claim_ids':['f2'],'verification_status':'verified'}],
            'added_fact_ids':['f1','f2'], 'unverified_research':[]},
            'profile_document':{'text':text}}}


class PublicationAdmissionTests(unittest.TestCase):
    def setUp(self):
        if find_spec('devtools.business_text_redaction') is None:
            self.skipTest('Real runtime 0.1.123 qualification required; intake stubs cannot prove redaction.')
        blocker = patch.object(socket.socket, 'connect', side_effect=AssertionError('unexpected network'))
        blocker.start()
        self.addCleanup(blocker.stop)

    def test_only_changed_paragraph_loses_its_attestation_and_useful_sibling_survives(self):
        text = ('<!-- profile_paragraph: 1:1; verification: verified -->\n'
            'Original evidence has Bearer test-only-token.\n\n<!-- enrichment_fact: f1 -->\n'
            '<!-- profile_paragraph: 1:2; verification: verified -->\n'
            'Independent complete evidence remains intact.\n\n<!-- enrichment_fact: f2 -->\n')
        value = state(text)
        preflight_publication([value])
        safe = value['memory_candidate']
        assert safe.fact_ids == ('f2',)
        assert 'test-only-token' not in safe.markdown and '[redacted]' in safe.markdown
        assert 'Independent complete evidence remains intact.' in safe.markdown
        assert '1:1; verification: unverified' in safe.markdown
        assert '1:2; verification: verified' in safe.markdown
        assert 'enrichment_fact: f1' not in safe.markdown and 'enrichment_fact: f2' in safe.markdown
        assert value['result']['memory_admission']['status'] == 'ready'
        assert value['result']['profile_document']['text'] == safe.markdown
        assert value['result']['redaction_affected_claim_count'] == 1


    def test_guidance_remains_structured_and_its_identity_matches_redacted_content(self):
        feedback = [{'section_id':'company_profile','subsection_id':None,'observation':'Retain useful advice.',
            'next_action':'Inspect api_key=test-only before checking official filings.',
            'success_check':'Use official evidence.','origin':'section_critic'}]
        proposal = build_methodology_learning_proposal('', feedback=feedback)
        value = state('Useful complete research.', proposal.candidate)
        preflight_publication([value])
        safe = value['methodology_learning_candidate']
        rows = read_guidance(safe)
        assert len(rows) == 1 and 'test-only' not in safe
        original = {key:item for key,item in rows[0].items() if key not in {'schema_version','guidance_id'}}
        assert rows[0]['guidance_id'] == fingerprint(original)
        assert rows[0]['observation'] == feedback[0]['observation']
        assert '[redacted]' in rows[0]['next_action']
        assert value['result']['memory_admission']['status'] == 'ready'
        assert 'test-only' not in json.dumps(value['result']['publication_redactions'])

    def test_escaped_sensitive_guidance_keeps_its_structural_contract(self):
        for sensitive in ['password="test only value"', 'aws_access_key_id=test-only',
                          '"C:/private folder/key.txt"', r'C:\private\key.txt',
                          'https://example.org/?X-Amz-Signature=test-only']:
            with self.subTest(sensitive_type=sensitive.split('=')[0]):
                feedback = [{'section_id':'company_profile','subsection_id':None,
                    'observation':'Keep this independent observation.',
                    'next_action':'Before ' + sensitive + ' after.',
                    'success_check':'Use official evidence.','origin':'section_critic'}]
                proposal = build_methodology_learning_proposal('', feedback=feedback)
                value = state('Useful complete research.', proposal.candidate)
                preflight_publication([value])
                rows = read_guidance(value['methodology_learning_candidate'])
                assert len(rows) == 1
                assert rows[0]['observation'] == feedback[0]['observation']
                assert 'Before ' in rows[0]['next_action'] and ' after.' in rows[0]['next_action']
                assert 'test-only' not in rows[0]['next_action'] and 'private' not in rows[0]['next_action']
                assert value['result']['memory_admission']['status'] == 'ready'


    def test_safe_candidates_keep_exact_bytes_and_do_not_gain_redaction_receipts(self):
        text = "The company retains rights (excluding select Asia-Pacific territories). Evidence comes from filings."
        value = state(text)
        preflight_publication([value])
        assert value['memory_candidate'].markdown == text
        assert value['memory_candidate'].fact_ids == ('f1','f2')
        assert 'publication_redactions' not in value['result']


    def test_core_initialization_rejection_keeps_original_safe_stage_and_unknown_outcome(self):
        proof = dict(schema_version='proof_failure_detail.v1',proof_kind='dynamic_skill_initialization',
            request_stage='complete',http_status=503,reason_code=None,retry_after_seconds=30,
            outcome_unknown=True,attempt_count=1,upload_id=7,operation_id='op1')
        error = DynamicSkillRuntimeError('dynamic_skill_initialization_core_request_rejected',proof_failure_detail=proof)
        safe = diagnostic(error)
        assert safe['proof_failure_detail'] == proof and safe['reconciliation_required'] is True
        assert safe['failure_code'] == error.code


    def test_actual_orchestration_keeps_safe_publication_and_agent_call_counts(self):
        before_inputs = BatchedInputs(); after_inputs = BatchedInputs()
        before = invoke_v0_1_52(before_inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.52')
        after = invoke_v0_1_53(after_inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.53')
        assert after['outputs']['intelligence_dossier']['publication_complete']
        for role in ['company_memory','company_methodology']:
            assert before_inputs.store[(13,role)]['text'] == after_inputs.store[(13,role)]['text']
        assert before['metrics']['agent_call_count'] == after['metrics']['agent_call_count']

    def test_actual_publication_uses_the_redacted_candidate_without_another_agent_call(self):
        original = current.finalize_profiles
        def inject(states, coordinator):
            original(states, coordinator)
            for value in states:
                candidate = value['memory_candidate']
                # Simulate one sensitive generated annotation after synthesis.
                text = candidate.markdown
                marker = '<!-- profile_paragraph:'
                start = text.index(marker)
                end = text.index('-->', start) + 3
                text = text[:end] + '\nBearer test-only-token. ' + text[end:]
                value['memory_candidate'] = replace(candidate, markdown=text)
        source = BatchedInputs()
        baseline = invoke_v0_1_52(BatchedInputs(),asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.52')
        with patch.object(current, 'finalize_profiles', side_effect=inject):
            after = invoke_v0_1_53(source,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.53')
        row = after['outputs']['intelligence_dossier']['company_results'][0]
        assert row['skill_publication']['publication_complete']
        text = source.store[(13,'company_memory')]['text']
        assert 'test-only-token' not in text and '[redacted]' in text
        assert row['publication_redactions']['memory']['redaction_count'] == 1
        assert row['memory_admission']['exact_candidate_validated']
        assert after['metrics']['agent_call_count'] == baseline['metrics']['agent_call_count']
