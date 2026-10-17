"""Provider-free quality parity, independent packet failures and outcome evidence."""
from copy import deepcopy
from dataclasses import replace
import json
from hashlib import sha256
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(Path(__file__).parent)]
from test_profile_primary_v0_1_43 import DraftInputs
from test_grounded_profile_v0_1_40 import NativeInputs
import legacy_preparation_helpers_v0_1_23 as legacy
from orchestration_v0_1_50 import invoke_v0_1_50
from orchestration_v0_1_51 import invoke_v0_1_51
from critic_batches_v0_1_51 import factor,expand,SCHEMA
from devtools.runtime_business_outcome import validate_business_outcome,publication_status


class BatchedInputs(DraftInputs):
    corrupt_piece=False
    review_fault=None
    def __init__(self):
        super().__init__()
        self.batch_calls=[]
    def dynamic_skill(self,role,*,variables):
        handle=super().dynamic_skill(role,variables=variables)
        original=handle.apply
        def apply(changes,*,expected_digest):
            receipt=original(changes,expected_digest=expected_digest)
            # The historical fake used prose IDs. Keep production validation
            # strict and give this fixture a real-shaped ID in the SAME object
            # retained by its in-memory history.
            receipt.change_id='dynchg_'+sha256(str((handle.key,receipt.after_content_digest)).encode()).hexdigest()[:32]
            return receipt
        handle.apply=apply
        return handle
    def _single_invoke(self,role,*,input,on_error='raise'):
        return super().invoke_agent(role,input=input,on_error=on_error)
    def invoke_agent(self,role,*,input,on_error='raise'):
        if role!=legacy.CRITIC_ROLE or 'review_batch' not in input:
            return self._single_invoke(role,input=input,on_error=on_error)
        self.batch_calls.append(deepcopy(input))
        batch=input['review_batch'];reviews=[];envelope=None
        for index,piece in enumerate(batch['review_packets']):
            original=expand(batch['shared_review_fields'],piece['fields'])
            response=self._single_invoke(role,input=original,on_error=on_error)
            envelope=envelope or deepcopy(response)
            review=deepcopy(response['result']['content'][0]['value'])
            if self.corrupt_piece and len(self.batch_calls)==1 and index==0:
                review['company_id']=999999
            reviews.append({'packet_id':piece['packet_id'],'review':review})
        if self.review_fault and len(self.batch_calls)==1:
            if self.review_fault=='missing':reviews.pop(0)
            elif self.review_fault=='duplicate':reviews.append(deepcopy(reviews[0]))
            elif self.review_fault=='unknown':reviews[0]['packet_id']='unknown_piece'
        envelope['result']['content']=[{'type':'json','value':{
            'schema_version':SCHEMA,'company_id':input['company_id'],'role':role,
            'status':'completed','reviews':reviews}}]
        return envelope


class GroundedBatchedInputs(BatchedInputs):
    def _single_invoke(self,role,*,input,on_error='raise'):
        return NativeInputs.invoke_agent(self,role,input=input,on_error=on_error)


class DurableBatchedTests(unittest.TestCase):
    def setUp(self):
        guard=patch.object(socket.socket,'connect',side_effect=AssertionError('Unexpected network access'))
        guard.start();self.addCleanup(guard.stop)
    def run_fixture(self,inputs):
        return invoke_v0_1_51(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.51')
    def test_recursive_factoring_is_exact_for_all_evidence_and_negative_fields(self):
        values=[{'company_id':13,'evidence':{'quotes':['Exact Ω source.'],'claims':[{'id':'a','qualifier':'historical'}]},
                 'contract':{'same':'required','ids':['a']},'negative':{'contradictions':['A != B']}},
                {'company_id':13,'evidence':{'quotes':['Exact Ω source.'],'claims':[{'id':'b','qualifier':'uncertain'}]},
                 'contract':{'same':'required','ids':['b']},'negative':{'contradictions':['A != B']}}]
        shared,pieces=factor(values)
        self.assertEqual(values,[expand(shared,piece) for piece in pieces])
        self.assertLess(len(json.dumps([shared,pieces])),len(json.dumps(values)))
    def test_canonical_memory_and_all_coverage_match_previous_version_with_fewer_critic_calls(self):
        old=DraftInputs();control=invoke_v0_1_50(old,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.50')
        inputs=BatchedInputs();actual=self.run_fixture(inputs)
        row=actual['outputs']['intelligence_dossier']['company_results'][0]
        original=control['outputs']['intelligence_dossier']['company_results'][0]
        self.assertEqual(old.store[(13,'company_memory')]['text'],inputs.store[(13,'company_memory')]['text'])
        self.assertEqual(original['required_section_coverage_count'],row['required_section_coverage_count'])
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertTrue(row['skill_publication']['memory']['readback_verified'])
        self.assertTrue(row['skill_publication']['memory']['history_verified'])
        proof=row['critic_review_batching']
        self.assertGreater(proof['original_packet_count'],proof['planned_group_count'])
        self.assertLess(proof['batched_prompt_bound_chars'],proof['original_prompt_bound_chars'])
        self.assertEqual(3,row['agent_input_preflight']['max_parallel_calls'])
        self.assertEqual('published',publication_status(validate_business_outcome(actual['business_outcome'])))
        self.assertEqual('completed_published',actual['outputs']['intelligence_dossier']['status'])
        self.assertNotIn('markdown',json.dumps(actual['business_outcome']))
    def test_one_wrong_company_piece_does_not_discard_valid_sibling_reviews_or_research(self):
        inputs=BatchedInputs();inputs.corrupt_piece=True
        result=self.run_fixture(inputs)
        row=result['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['profile_document']['text'])
        self.assertTrue(row['research_incomplete'])
        self.assertIn('Unverified research',row['profile_document']['text'])
        self.assertTrue(any(outcome['status']=='validated' for outcome in row['section_enrichment_checks']))
        self.assertEqual(13,result['business_outcome']['subjects'][0]['subject_id'])
    def test_provider_grounded_evidence_citations_and_accepted_facts_match_previous_version(self):
        import devtools.agent_citation_view as view
        if not hasattr(view,'_validated_turns'):self.skipTest('Requires real SDK citation projection')
        old=NativeInputs();control=invoke_v0_1_50(old,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.50')
        inputs=GroundedBatchedInputs();actual=self.run_fixture(inputs)
        before=control['outputs']['intelligence_dossier']['company_results'][0]
        after=actual['outputs']['intelligence_dossier']['company_results'][0]
        self.assertGreater(after['accepted_claim_count'],0)
        self.assertEqual(before['accepted_claim_count'],after['accepted_claim_count'])
        self.assertEqual(old.store[(13,'company_memory')]['text'],inputs.store[(13,'company_memory')]['text'])
        self.assertIn('https://example.org/primary/',inputs.store[(13,'company_memory')]['text'])
        self.assertTrue(after['skill_publication']['publication_complete'])
    def test_missing_duplicate_and_unknown_review_ids_never_manufacture_coverage(self):
        for fault in ['missing','duplicate','unknown']:
            with self.subTest(fault=fault):
                inputs=BatchedInputs();inputs.review_fault=fault
                result=self.run_fixture(inputs)
                row=result['outputs']['intelligence_dossier']['company_results'][0]
                self.assertTrue(row['research_incomplete'])
                self.assertTrue(row['profile_document']['text'])
                self.assertTrue(any(item['status']=='validated' for item in row['section_enrichment_checks']))
                self.assertTrue(any(item['status']!='validated' for item in row['section_enrichment_checks']))

    def test_new_contract_changes_only_critic_instructions_and_reserves_finalization_time(self):
        manifest=json.loads((ROOT/'nusaibah_pharma_company_intelligence_lab.asset.json').read_text())
        before=manifest['versions']['0.1.50'];after=deepcopy(manifest['versions']['0.1.51'])
        self.assertEqual(2100,after['execution']['timeout_seconds'])
        after['execution']=before['execution']
        for role,agent in after['agents'].items():
            if role==legacy.CRITIC_ROLE:
                self.assertEqual('1.0.18',agent['contract_version'])
                step=agent['definition']['chain']['steps'][0]
                self.assertEqual(before['agents'][role]['definition']['chain']['steps'][0]['provider_policy'],step['provider_policy'])
                self.assertLessEqual(len(step['input']['text']),8192)
                after['agents'][role]=before['agents'][role]
        self.assertEqual(before,after)

    def test_candidate_rejection_is_independently_classified_and_does_not_mutate_memory(self):
        import retention_v0_1_50 as retention
        from devtools.preview_output_validator import PreviewOutputValidationError
        inputs=BatchedInputs();before=deepcopy(inputs.store)
        validator=retention.validate_preview_outputs
        def reject(value):
            if 'proposed_skills' in value:raise PreviewOutputValidationError('unsafe_runtime_value',())
            return validator(value)
        with patch.object(retention,'validate_preview_outputs',side_effect=reject):result=self.run_fixture(inputs)
        self.assertEqual(before,inputs.store)
        outcome=result['business_outcome'];self.assertEqual('withheld',publication_status(outcome))
        self.assertEqual('unsafe_runtime_value',outcome['subjects'][0]['admission_reason_code'])
        self.assertTrue(outcome['subjects'][0]['checks']['candidate_present'])
        self.assertFalse(outcome['subjects'][0]['checks']['candidate_admitted'])
        self.assertGreater(outcome['subjects'][0]['content_metrics']['candidate_byte_count'],0)
    def test_preview_remains_readonly_and_profile_capacity_is_unchanged(self):
        inputs=BatchedInputs();inputs['variables']['memory_mode']='preview';before=deepcopy(inputs.store)
        result=self.run_fixture(inputs)
        self.assertEqual(before,inputs.store)
        self.assertEqual('not_requested',publication_status(result['business_outcome']))
        self.assertEqual('completed_preview',result['outputs']['intelligence_dossier']['status'])
        from profile_research_v0_1_50 import MAX_PROFILE_CHARS,MAX_PROFILE_BYTES
        self.assertEqual(384000,MAX_PROFILE_CHARS);self.assertEqual(960*1024,MAX_PROFILE_BYTES)


if __name__=='__main__':unittest.main()
