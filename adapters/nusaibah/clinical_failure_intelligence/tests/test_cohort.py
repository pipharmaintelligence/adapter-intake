"""Reported percentages cannot create a missing cohort denominator."""
import unittest
from copy import deepcopy
from fakes import example_cohort
from clinical_failure_intelligence.contracts import ContractError
from clinical_failure_intelligence.cohort import compute_statistics, run_approved_test


class CohortTests(unittest.TestCase):
    def result(self, cohort=None):
        return compute_statistics(cohort if cohort is not None else example_cohort(), as_of_date='2025-02-01')
    def test_known_and_unknown_denominators_separate(self):
        a, b = self.result()['groups']
        self.assertEqual((1, 2, 1, .5), (a['numerator'], a['denominator'], a['unknown_count'], a['estimate']))
        self.assertEqual((1, 1, 1), (b['numerator'], b['denominator'], b['unknown_count']))
    def test_failure_only_no_success_inference(self):
        c = example_cohort(); c['selection'] = 'failure_only'; self.assertEqual('not_run', self.result(c)['status'])
    def test_missing_denominator_no_estimate(self):
        c = example_cohort(); c['denominator_complete'] = False; self.assertEqual('not_run', self.result(c)['status'])
    def test_absent_cohort_explicit(self):
        self.assertEqual('not_run', compute_statistics(None, as_of_date='2025-02-01')['status'])
    def test_duplicate_events_do_not_inflate_denominator(self):
        c = example_cohort(); c['rows'].append(deepcopy(c['rows'][0])); result = self.result(c)
        self.assertEqual(1, result['duplicate_rows_removed']); self.assertEqual(2, result['groups'][0]['denominator'])
    def test_conflicting_unit_records_not_cherry_picked(self):
        c = example_cohort(); row = deepcopy(c['rows'][0]); row['outcome'] = 'failure'; c['rows'].append(row)
        self.assertEqual('not_run', self.result(c)['status'])
    def test_overlapping_group_membership_rejected(self):
        c = example_cohort(); row = deepcopy(c['rows'][0]); row['group'] = 'overall'; c['rows'].append(row)
        self.assertEqual('not_run', self.result(c)['status'])
    def test_zero_known_outcomes_not_zero_success(self):
        c = example_cohort(); c['rows'] = c['rows'][2:3]
        self.assertIsNone(self.result(c)['groups'][0]['estimate']); self.assertEqual('not_run', self.result(c)['status'])
    def test_attribute_prevalence_has_own_denominator(self):
        c = example_cohort(); c['metric'] = 'attribute_prevalence'; c['rows'][0]['attribute'] = True; c['rows'][1]['attribute'] = False
        a = self.result(c)['groups'][0]; self.assertEqual((1, 2, 1), (a['numerator'], a['denominator'], a['unknown_count']))
    def test_future_window_and_invalid_grain_blocked(self):
        for field, value in [('window_end', '2026-01-01'), ('unit_of_analysis', 'random_news_rows')]:
            c = example_cohort(); c[field] = value
            with self.assertRaises(ContractError): self.result(c)
    def test_inferential_statistics_never_invented(self):
        result = self.result(); self.assertIsNone(result['p_value']); self.assertIsNone(result['confidence_interval'])
        self.assertEqual('not_run', run_approved_test()['status'])
    def test_empty_cohort_has_no_estimate(self):
        c = example_cohort(); c['rows'] = []; self.assertEqual([], self.result(c)['groups'])
        self.assertEqual('not_run', self.result(c)['status'])


if __name__ == '__main__': unittest.main()
