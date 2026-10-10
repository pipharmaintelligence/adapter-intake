from __future__ import annotations

import json
from pathlib import Path
import unittest

import test_supplied_source_quote_review as fixtures

ROOT = Path(__file__).resolve().parents[1].parent / "pharma_company_context_review"
review = fixtures.load(ROOT, "company_context_review.py", "_context_review_tests")
scope = fixtures.load(ROOT.parent / "company_scope", "scope_contract.py", "_context_scope_tests")


def handoff():
    companies = {"records": [{"id": 13, "company": "Synthetic Contract Company", "corporate": 1,
                             "address_line1": "Registered office, Example Street", "headquarter": 7}],
                 "row_count": 1, "exactness": "exact", "partial_reason": None,
                 "provenance": {"source": "dlm_node", "authority": "dlm_node", "lake_id": "synthetic_lake",
                                "node_key": "companies", "pages_read": 1}}
    return {"company_context": {"value": scope.build_scope_result({"company_id": 13}, companies),
        "provenance": {"source": "retained_asset_output", "authority": "core_artifact",
            "run_uuid": "b707a865-610b-41a0-9c67-07059b1e8af3", "asset_identity": review.SCOPE_IDENTITY,
            "output_role": "company_scope_result", "checksum_sha256": "a" * 64}},
        "variables": {"execution_purpose": review.PURPOSE}}


def identity_only(role, packet, value):
    if role != review.scoped.VERIFIER_ROLE:
        for requirement in value["requirements"]:
            if requirement["requirement_id"] != "company_identity":
                requirement.update(disposition="no_evidence", findings=[])
    return value


class CompanyContextReviewTests(unittest.TestCase):
    def test_one_retained_context_runs_specialists_toolkit_and_verifiers_without_queries(self):
        inputs = fixtures.FakeInputs(handoff(), findings=True, transform=identity_only)
        result = review.run_review(inputs)
        self.assertFalse(result["synthetic"])
        self.assertFalse(result["publication_allowed"])
        self.assertFalse(result["external_truth_verified"])
        self.assertEqual((5, 1, 0), (result["agent_call_count"], result["child_call_count"], result["mutable_call_count"]))
        self.assertEqual(["company_identity"], [f["requirement_id"] for f in result["accepted_findings"]])
        self.assertEqual("review_complete_with_evidence_gaps", result["review_outcome"])
        self.assertEqual("company-13", result["entity_id"])
        self.assertEqual(0, result["plan"]["repair_iterations"])
        self.assertEqual(5, result["plan"]["logical_call_limit"])
        review.scoped.validate_resolution_receipts(result, review.prepare_review(inputs))
        self.assertEqual(["specialist_review"] * 3 + ["span_resolution", "chunk_evidence_verification", "global_consistency"], inputs.events)
        self.assertNotIn("country_name", json.dumps(inputs.calls))
        self.assertNotIn("evaluation_case", inputs)

    def test_report_record_retains_literal_business_urls_under_existing_sdk(self):
        try:
            from devtools.response_validator import validate_response
        except ModuleNotFoundError as exc:
            if exc.name not in {"devtools", "devtools.response_validator"}:
                raise
            self.skipTest("Installed SDK qualification: intake CI uses dependency-free stubs")
        inputs = fixtures.FakeInputs(handoff(), findings=True, transform=identity_only)
        result = review.run_review(inputs)
        result["accepted_findings"][0]["claim"] = "Website recorded as https://company.example.test"
        validate_response({"response_version": "1", "status": "success",
                           "outputs": {"evaluation_result": {"record": result}}})
        adapter = fixtures.load(ROOT, "pharma_company_context_review_adapter.py", "_context_adapter_test")
        response = adapter.NusaibahPharmaCompanyContextReviewAdapter().invoke(
            fixtures.FakeInputs(handoff(), findings=True, transform=identity_only), {})
        self.assertEqual("company_context_review_result.v1", response["outputs"]["evaluation_result"]["record"]["schema_version"])
        validate_response(response)

    def test_absent_findings_are_retained_as_truthful_gaps(self):
        inputs = fixtures.FakeInputs(handoff(), findings=False)
        result = review.run_review(inputs)
        self.assertEqual([], result["accepted_findings"])
        self.assertEqual(4, result["agent_call_count"])
        self.assertTrue(all(x["specialist_disposition"] == "no_evidence" for x in result["coverage"]))

    def test_invalid_or_tampered_context_aborts_before_any_helper(self):
        def invalid_count(value): value["company_context"]["value"]["company_count"] = 2
        def bad_digest(value): value["company_context"]["value"]["records"][0]["company_name"] = "Other company"
        def wrong_origin(value): value["company_context"]["provenance"]["asset_identity"] = "example.other:0.1.0"
        def raw(value): value["company_context"] = value["company_context"]["value"]
        for mutate in (invalid_count, bad_digest, wrong_origin, raw):
            inputs = fixtures.FakeInputs(handoff())
            mutate(inputs)
            with self.subTest(mutate=mutate.__name__), self.assertRaises(review.scoped.SourceReviewError):
                review.run_review(inputs)
            self.assertEqual([], inputs.calls)
            self.assertEqual([], inputs.child_calls)

    def test_old_synthetic_version_and_manifest_contracts_remain_unchanged(self):
        manifest = json.loads((ROOT / "pharma_company_context_review.asset.json").read_bytes())
        legacy = json.loads((ROOT.parent / "pharma_company_intelligence_lab_evaluation" / "nusaibah_pharma_company_intelligence_lab_evaluation.asset.json").read_bytes())
        self.assertEqual("0.2.3", legacy["default"])
        self.assertEqual({"evaluation_case", "variables"}, set(legacy["versions"]["0.2.3"]["inputs"]))
        self.assertEqual({"company_context", "variables"}, set(manifest["versions"]["0.1.0"]["inputs"]))
        self.assertEqual({"asset_identity": review.SCOPE_IDENTITY, "output_role": "company_scope_result"},
                         manifest["versions"]["0.1.0"]["inputs"]["company_context"]["retained_output"])
        # The historical tests separately pin byte hashes; this test proves no input relaxation.
        with self.assertRaises(review.scoped.SourceReviewError):
            review.scoped.prepare_review(handoff())
        self.assertEqual("supplied_source_methodology.v3", review.scoped.METHOD["schema_version"])
