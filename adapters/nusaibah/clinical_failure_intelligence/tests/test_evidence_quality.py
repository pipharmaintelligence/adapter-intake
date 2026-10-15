"""Evidence identity and canonical consistency are not a semantic truth oracle."""
import unittest
from copy import deepcopy
from fakes import FakeInputs, example_inputs
from clinical_failure_intelligence.contracts import ContractError, parse_request, text_digest
from clinical_failure_intelligence.evidence import EvidenceLedger
from clinical_failure_intelligence.quality import normalize_items, review_items, validate_dependencies


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.raw = example_inputs(); self.request = parse_request(FakeInputs(self.raw))
        self.ledger = EvidenceLedger('CASE_SYN', '2025-02-01', self.raw['clinical_context']['evidence'])
    def test_exact_source_deduplication_has_alias(self):
        value = deepcopy(self.raw['clinical_context']['evidence'][0]); value['evidence_id'] = 'ALIAS'
        self.assertEqual('E_TRIAL', self.ledger.add(value)); self.assertEqual(['E_TRIAL'], self.ledger.refs(['ALIAS', 'E_TRIAL']))
        self.assertEqual(2, len(self.ledger.rows()))
    def test_conflicting_source_identity_rejected(self):
        value = deepcopy(self.raw['clinical_context']['evidence'][0]); value['text'] = 'Changed'
        with self.assertRaisesRegex(ContractError, 'collision'): self.ledger.add(value)
    def test_future_source_rejected(self):
        value = deepcopy(self.raw['clinical_context']['evidence'][0]); value['published_on'] = '2025-03-01'
        with self.assertRaisesRegex(ContractError, 'temporal_leak'): self.ledger.add(value)
    def test_source_digest_mismatch_rejected(self):
        value = deepcopy(self.raw['clinical_context']['evidence'][0]); value['declared_text_digest'] = text_digest('wrong')
        with self.assertRaisesRegex(ContractError, 'digest_mismatch'): self.ledger.add(value)
    def test_wrong_source_entity_rejected(self):
        value = deepcopy(self.raw['clinical_context']['evidence'][0]); value['subject_id'] = 'OTHER'
        with self.assertRaisesRegex(ContractError, 'subject_mismatch'): self.ledger.add(value)
    def test_unknown_evidence_never_materializes(self):
        with self.assertRaisesRegex(ContractError, 'ref_unknown'): self.ledger.refs(['INVENTED'])
    def test_undated_and_supplied_assertion_not_definitive(self):
        for field, value in [('published_on', None), ('source_type', 'supplied_assertion'), ('accessible_extent', 'supplied_assertion')]:
            raw = deepcopy(self.raw['clinical_context']['evidence'][0]); raw[field] = value
            ledger = EvidenceLedger('CASE_SYN', '2025-02-01', [raw])
            with self.assertRaisesRegex(ContractError, 'unverified'): ledger.assert_usable(['E_TRIAL'])
    def claims(self):
        return FakeInputs().role_payload('trial_researcher', {'task_id': 'research:0', 'assigned_obligation_ids': ['q'], 'evidence_packet': self.ledger.rows()})['items']
    def test_exact_span_is_not_semantic_review(self):
        valid, issues = self.ledger.validate_claims(self.claims(), stage_id='research:0')
        self.assertEqual([], issues); self.assertEqual('passage_checked', valid[0]['verification'])
        self.assertEqual('unreviewed', valid[0]['review_status'])
    def test_bad_span_isolated_from_valid_sibling(self):
        claims = self.claims(); claims[0]['source_spans'][0]['quote'] = 'not an exact quote'
        valid, issues = self.ledger.validate_claims(claims, stage_id='research:0')
        self.assertEqual(1, len(valid)); self.assertEqual(1, len(issues))
    def test_duplicate_claim_ids_rejected(self):
        claims = self.claims(); claims.append(deepcopy(claims[0]))
        with self.assertRaisesRegex(ContractError, 'duplicate'): self.ledger.validate_claims(claims, stage_id='a')
    def test_wrong_claim_entity_is_hard_failure(self):
        claims = self.claims(); claims[0]['subject_id'] = 'OTHER'
        with self.assertRaisesRegex(ContractError, 'subject_mismatch'): self.ledger.validate_claims(claims, stage_id='a')
    def test_same_quote_distinct_claims_not_deduplicated(self):
        claims = self.claims()[:1]; other = deepcopy(claims[0]); other['claim_id'] = 'distinct'; other['statement'] = 'A separately scoped claim'; claims.append(other)
        valid, issues = self.ledger.validate_claims(claims, stage_id='a')
        self.assertEqual(2, len(valid)); self.assertEqual([], issues)
    def items(self):
        fake = FakeInputs(); packet = {'task_id': 't', 'assigned_obligation_ids': ['q']}
        outcomes, _ = normalize_items(fake.role_payload('outcome_adjudicator', packet)['items'], 'outcome', self.request, self.ledger)
        hypotheses, _ = normalize_items(fake.role_payload('hypothesis_analyst', packet)['items'], 'hypothesis', self.request, self.ledger)
        return outcomes + hypotheses
    def decisions(self, items):
        return FakeInputs().role_payload('evidence_critic', {'task_id': 't', 'assigned_obligation_ids': ['q'], 'candidate_items': items})['items']
    def test_empty_critic_does_not_complete_review(self):
        result, issues = review_items(self.items(), [], self.ledger)
        self.assertTrue(issues); self.assertTrue(all(not x['accepted'] for x in result))
    def test_missing_one_review_preserves_siblings(self):
        items = self.items(); result, issues = review_items(items, self.decisions(items)[:-1], self.ledger)
        self.assertEqual(5, sum(x['accepted'] for x in result)); self.assertTrue(issues)
    def test_rejected_premise_invalidates_descendant(self):
        items = self.items(); decisions = self.decisions(items)
        next(x for x in decisions if x['item_id'] == 'outcome_primary_endpoint_result')['verdict'] = 'contradicted'
        result, issues = review_items(items, decisions, self.ledger)
        self.assertFalse(result[-1]['accepted']); self.assertEqual('inconclusive', result[-1]['verdict'])
        self.assertTrue(any(x['code'] == 'clinical_dependency_withheld' for x in issues))
    def test_definitive_hypothesis_requires_actual_evidence(self):
        items = self.items(); items[-1].update(proposed_verdict='supported', supporting_evidence_ids=[])
        result, issues = review_items(items, self.decisions(items), self.ledger)
        self.assertFalse(result[-1]['accepted']); self.assertTrue(issues)
    def test_false_scope_preservation_withholds_claim(self):
        items = self.items(); decisions = self.decisions(items); decisions[-1]['scope_preserved'] = False
        result, _ = review_items(items, decisions, self.ledger); self.assertFalse(result[-1]['accepted'])
    def test_critic_cannot_add_source_not_proposed_for_claim(self):
        items = self.items(); decisions = self.decisions(items); decisions[-1]['supporting_evidence_ids'] = ['E_TRIAL']
        result, issues = review_items(items, decisions, self.ledger); self.assertFalse(result[-1]['accepted']); self.assertTrue(issues)
    def test_unknown_and_duplicate_critic_ids_rejected(self):
        items = self.items(); decisions = self.decisions(items); decisions[0]['item_id'] = 'INVENTED'
        with self.assertRaisesRegex(ContractError, 'identity_invalid'): review_items(items, decisions, self.ledger)
        decisions = self.decisions(items); decisions.append(deepcopy(decisions[0]))
        with self.assertRaisesRegex(ContractError, 'identity_invalid'): review_items(items, decisions, self.ledger)
    def test_dependency_cycle_and_dangling_rejected(self):
        for reference in ('H_SYN', 'UNKNOWN'):
            items = self.items(); items[-1]['depends_on'] = [reference]
            with self.assertRaises(ContractError): validate_dependencies(items)
    def test_reason_taxonomy_not_model_extensible(self):
        row = FakeInputs().role_payload('hypothesis_analyst', {'task_id': 't', 'assigned_obligation_ids': ['q']})['items'][0]
        row['reason_code'] = 'arbitrary_new_rule'
        result, issues = normalize_items([row], 'hypothesis', self.request, self.ledger)
        self.assertEqual([], result); self.assertTrue(issues)
    def test_wrong_trial_cannot_support_outcome(self):
        row = FakeInputs().role_payload('outcome_adjudicator', {'task_id': 't', 'assigned_obligation_ids': ['q']})['items'][0]
        row['trial_ids'] = ['OTHER']
        with self.assertRaisesRegex(ContractError, 'trial_scope_mismatch'): normalize_items([row], 'outcome', self.request, self.ledger)
    def test_conflicting_outcomes_cannot_both_be_accepted(self):
        items = self.items(); other = deepcopy(items[1]); other['item_id'] = 'CONFLICT'; other['value'] = 'met'; items.append(other)
        result, issues = review_items(items, self.decisions(items), self.ledger)
        self.assertTrue(any(x['code'] == 'clinical_outcome_conflict' for x in issues))
        self.assertFalse(next(x for x in result if x['item_id'] == 'H_SYN')['accepted'])
    def test_refuted_hypothesis_requires_counterevidence(self):
        items = self.items(); items[-1]['proposed_verdict'] = 'refuted'
        result, issues = review_items(items, self.decisions(items), self.ledger)
        self.assertFalse(result[-1]['accepted']); self.assertTrue(issues)


if __name__ == '__main__': unittest.main()
