"""Provider-free source discovery and admission failure regressions."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from fakes import FakeInputs, example_inputs
from clinical_failure_intelligence.contracts import ContractError, parse_request
from clinical_failure_intelligence.evidence import EvidenceLedger
from clinical_failure_intelligence.policies import Budget, ExecutionPolicy
from clinical_failure_intelligence.research_sources import (
    query_plan, _admit_inspected, acquire_sources,
)


class DiscoveryContractTests(unittest.TestCase):
    def setUp(self):
        self.request = parse_request(FakeInputs())
        self.citation = SimpleNamespace(title="Synthetic source", locator="https://clinicaltrials.gov/study/NCT12345678")
        self.request["context"]["subject"]["trial_ids"] = ["NCT12345678"]
        self.inspection = SimpleNamespace(
            final_url="https://clinicaltrials.gov/study/NCT12345678",
            text="NCT12345678 was reported for Synthetic product Alpha. No outcome conclusion is given.",
            metadata={"published_on": "2025-01-20"}, title="Study record")

    def test_query_plan_deterministic_and_bounded(self):
        a = query_plan(self.request)
        self.assertEqual(a, query_plan(self.request))
        self.assertEqual(set(a), {"trial_researcher", "literature_researcher", "event_researcher"})
        self.assertTrue(all(len(s) <= 500 for s in a.values()))
        self.assertIn("NCT12345678", a["trial_researcher"])

    def test_inspected_registry_passage_still_requires_claim_review(self):
        value = _admit_inspected(self.inspection, self.citation, self.request)
        ledger = EvidenceLedger("CASE_SYN", "2025-02-01", [])
        ledger.add(value)
        self.assertEqual(len(ledger.rows()), 1)
        self.assertEqual(ledger.rows()[0]["verification"], "source_available")
        self.assertEqual(ledger.rows()[0]["source_type"], "trial_registry")
        self.assertEqual(ledger.rows()[0]["published_on"], "2025-01-20")

    def test_wrong_trial_rejected(self):
        self.inspection.final_url = "https://clinicaltrials.gov/study/NCT99999999"
        self.inspection.text = "Different trial and product."
        with self.assertRaisesRegex(ContractError, "scope_unverified"):
            _admit_inspected(self.inspection, self.citation, self.request)

    def test_future_publication_rejected(self):
        self.inspection.metadata = {"published_on": "2026-01-01"}
        with self.assertRaisesRegex(ContractError, "temporal_leak"):
            _admit_inspected(self.inspection, self.citation, self.request)

    def test_missing_source_text_rejected(self):
        self.inspection.text = ""
        with self.assertRaisesRegex(ContractError, "text_missing"):
            _admit_inspected(self.inspection, self.citation, self.request)

    def test_oversized_source_never_truncated_into_claim(self):
        self.inspection.text = "Synthetic product Alpha " * 700
        with self.assertRaisesRegex(ContractError, "partitioning"):
            _admit_inspected(self.inspection, self.citation, self.request)

    def test_without_reference_helper_does_not_use_network(self):
        fake = FakeInputs()
        ledger = EvidenceLedger("CASE_SYN", "2025-02-01", [])
        class FailIfCalled:
            def call(self, *args, **kwargs):
                raise AssertionError("must not invoke discovery")
        result = acquire_sources(fake, self.request, FailIfCalled(), Budget(ExecutionPolicy()), ledger, [])
        self.assertEqual(result, [{"code": "clinical_reference_capability_unavailable"}])
        self.assertEqual(ledger.rows(), [])


if __name__ == "__main__":
    unittest.main()
