"""Clinical consumer of the pinned UMLS 0.1.1 output, not receipt authentication."""
from copy import deepcopy
import unittest
from fakes import FakeInputs
from test_source_bundle import case_inputs, terminology, entry, bundle
from clinical_failure_intelligence.contracts import ContractError, parse_request, digest
from clinical_failure_intelligence.source_bundle import prepare_bundle


class UmlsConsumerTests(unittest.TestCase):
    def normalize(self,value):
        return prepare_bundle(bundle(entry(value,'umls',purpose='terminology')),parse_request(FakeInputs(case_inputs())))
    def test_attestation_preserved_without_inventing_release_or_clinical_authority(self):
        value=self.normalize(terminology())
        term=value['terminology'][0]
        receipt=value['sources'][0]['runtime_fetch_attestation']
        self.assertTrue(term['query_attested'])
        self.assertEqual(receipt['fetch_id'],term['fetch_id'])
        self.assertIsNone(term['release'])
        self.assertFalse(term['clinical_equivalence_verified'])
        self.assertFalse(term['may_support_outcome'])
        self.assertEqual([],value['evidence'])
        self.assertEqual({'returned_count':1,'truncated':None},value['sources'][0]['coverage'])
    def test_full_fetch_count_is_not_confused_with_projected_count(self):
        value=terminology()
        value['provenance']['runtime_fetch_evidence'].update(record_count=2,response_digest='sha256:'+'2'*64)
        value['completeness']['truncated']=True
        result=self.normalize(value)
        self.assertEqual(2,result['sources'][0]['runtime_fetch_attestation']['record_count'])
        self.assertEqual(1,len(result['terminology']))
    def test_unattested_missing_malformed_or_mismatched_receipt_rejected(self):
        for mutate in (
            lambda v:v.update(query_attested=False),
            lambda v:v['provenance'].pop('runtime_fetch_evidence'),
            lambda v:v['provenance']['runtime_fetch_evidence'].update(unknown=True),
            lambda v:v['provenance']['runtime_fetch_evidence'].update(record_count=True),
            lambda v:v['provenance']['runtime_fetch_evidence'].update(record_count=0),
            lambda v:v['provenance']['runtime_fetch_evidence'].update(completed_at_utc='2026-02-30T01:00:00.000Z'),
            lambda v:v['query'].update(text='unrelated'),
            lambda v:v['provenance']['runtime_fetch_evidence'].update(response_digest='unverified'),
        ):
            value=terminology();mutate(value)
            with self.subTest(value=value),self.assertRaises(ContractError):self.normalize(value)
    def test_source_vocabulary_selectors_preserve_order(self):
        value=terminology()
        value['query']['sources']=['SYNTH','OTHER']
        value['provenance']['runtime_fetch_evidence']['effective_selectors_digest']=digest([
            {'string':value['query']['text'],'searchType':'exact','sabs':'SYNTH,OTHER'}])
        self.assertTrue(self.normalize(value)['terminology'][0]['query_attested'])
    def test_old_producer_cannot_supply_new_contract(self):
        supplied=entry(terminology(),'umls',purpose='terminology')
        supplied['asset_version']='0.1.0'
        with self.assertRaisesRegex(ContractError,'contract_mismatch'):
            prepare_bundle(bundle(supplied),parse_request(FakeInputs(case_inputs())))
