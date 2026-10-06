from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVALUATION_ROOT = HERE / "evaluation"
sys.path.insert(0, str(EVALUATION_ROOT))

import supplied_source_candidate_evaluation as candidate


def fixture_case() -> dict:
    source_units = [
        {
            "locator": "source:identity",
            "text": "Ficta Therapeutics is a synthetic company.",
            "quality_flags": [],
        },
        {
            "locator": "source:distractor",
            "text": "Other Company has a product.",
            "quality_flags": ["wrong_entity_distractor"],
        },
    ]
    source_digest = candidate.hashlib.sha256(
        json.dumps(
            source_units,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "pharma_review_evaluation_case.v1",
        "source_identity": {
            "source_id": "synthetic:test",
            "source_version": "synthetic.v1",
            "content_sha256": source_digest,
            "digest_status": "frozen",
        },
        "methodology_identity": {
            "skill_ref": "nusaibah.pharma-intelligence-methodology",
            "skill_version": "1.0.0",
            "skill_digest": "sha256:" + "a" * 64,
        },
        "adjudication": {
            "status": "adjudicated",
            "primary_reviewer": "Reviewer",
            "secondary_reviewer": None,
            "disagreement": False,
            "review_notes": "Approved.",
        },
        "case_id": "candidate-test-001",
        "mode": "company_research",
        "split": "development",
        "title": "Candidate test",
        "strata": ["small_source", "company_isolation"],
        "source_units": source_units,
        "applicable_requirements": ["company_profile.identity"],
        "candidate_expected_findings": [
            {
                "finding_id": "f1",
                "statement": "Ficta Therapeutics is a synthetic company.",
                "expected_state": "supported",
                "criticality": "noncritical",
                "supporting_locators": ["source:identity"],
                "contradicting_locators": [],
            }
        ],
        "acceptable_abstention": [],
        "candidate_expected_complete": True,
        "completion_expectation_reason": "Direct identity evidence is present.",
    }


def suite() -> dict:
    return {
        "schema_version": "pharma_review_evaluation_suite.v1",
        "suite_id": "suite.test.v1",
        "cases": [fixture_case()],
    }


def inputs() -> dict:
    return {
        "variables": {"execution_purpose": "supplied_source_review"},
        "evaluation_case": {
            "records": [
                {
                    "case_id": "candidate-test-001",
                    "mode": "supplied_source_review",
                    "synthetic": True,
                    "entity_id": "ficta",
                    "entity_name": "Ficta Therapeutics",
                    "source_units": [
                        {
                            "locator": "source:identity",
                            "entity_id": "ficta",
                            "text": "Ficta Therapeutics is a synthetic company.",
                        },
                        {
                            "locator": "source:distractor",
                            "entity_id": "other",
                            "text": "Other Company has a product.",
                        },
                    ],
                }
            ]
        },
    }


def retained() -> dict:
    quote = "Ficta Therapeutics is a synthetic company."
    finding_id = "sha256:" + "b" * 64
    snapshot_id = "sha256:" + "c" * 64
    chunk_id = "sha256:" + "d" * 64
    result = {
        "schema_version": "supplied_source_review_result.v1",
        "case_id": "candidate-test-001",
        "entity_id": "ficta",
        "snapshot_id": snapshot_id,
        "execution_state": "completed",
        "review_outcome": "review_complete_with_evidence_gaps",
        "scope": "focused_company_review",
        "synthetic": True,
        "preview_only": True,
        "baseline_comparable": False,
        "external_truth_verified": False,
        "publication_allowed": False,
        "plan": {
            "schema_version": "supplied_source_plan.v1",
            "snapshot_id": snapshot_id,
            "methodology_id": "supplied_source_methodology.v1",
            "methodology_digest": "sha256:" + "e" * 64,
            "chunk_ids": [chunk_id],
            "roles": [
                "source_portfolio_reviewer",
                "source_commercial_reviewer",
                "source_regulatory_reviewer",
            ],
            "verifier_role": "source_evidence_verifier",
            "logical_call_limit": 5,
            "max_concurrency": 3,
            "deadline_seconds": 1800,
            "repair_iterations": 0,
            "plan_digest": "sha256:" + "f" * 64,
        },
        "source_inventory": [
            {
                "locator": "source:identity",
                "disposition": "reviewed",
                "chunk_id": chunk_id,
            },
            {
                "locator": "source:distractor",
                "disposition": "excluded_by_entity",
            },
        ],
        "coverage": [
            {
                "chunk_id": chunk_id,
                "primary_locator": "source:identity",
                "role": "source_portfolio_reviewer",
                "requirement_id": "company_identity",
                "finding_ids": [finding_id],
                "specialist_disposition": "findings",
                "reviewed": True,
                "unrepresented_evidence": False,
                "accepted_finding_ids": [finding_id],
                "evidence_state": "supported",
            }
        ],
        "accepted_findings": [
            {
                "entity_id": "ficta",
                "snapshot_id": snapshot_id,
                "chunk_id": chunk_id,
                "role": "source_portfolio_reviewer",
                "requirement_id": "company_identity",
                "ordinal": 0,
                "statement": "Ficta Therapeutics is a synthetic company.",
                "evidence": [
                    {
                        "locator": "source:identity",
                        "start": 0,
                        "end": len(quote),
                        "quote": quote,
                    }
                ],
                "finding_id": finding_id,
                "verification": {
                    "finding_id": finding_id,
                    "input_digest": "sha256:" + "1" * 64,
                    "state": "supported",
                },
                "global_verification": {
                    "finding_id": finding_id,
                    "input_digest": "sha256:" + "2" * 64,
                    "state": "supported",
                },
                "provenance_strength": "inspected_supplied_span",
                "external_truth_verified": False,
            }
        ],
        "withheld_findings": [],
        "agent_call_count": 5,
        "mutable_call_count": 0,
        "limitations": [],
    }
    summary = {
        "review_outcome": result["review_outcome"],
        "agent_call_count": 5,
        "mutable_call_count": 0,
        "execution_state": "completed",
        "preview_only": True,
        "publication_allowed": False,
        "baseline_comparable": False,
        "external_truth_verified": False,
        "schema_version": "pharma_supplied_source_review_summary.v1",
        "accepted_finding_count": 1,
        "withheld_finding_count": 0,
        "chunk_count": 1,
    }
    return {
        "schema_version": "adapter_preview_result.v1",
        "run_uuid": "60017bb0-56c7-4abf-be7e-51eb7fd4c7a2",
        "asset_identity": candidate.CANDIDATE_ASSET_IDENTITY,
        "outputs": {
            "evaluation_result": result,
            "evaluation_summary": summary,
        },
    }


def ready_review(
    suite_value: dict,
    case: dict,
    retained_context: dict,
) -> dict:
    review = candidate.build_review_template(
        suite_value,
        case,
        retained_context,
        inputs_file_sha256="1" * 64,
        retained_file_sha256="2" * 64,
    )
    finding_id = next(iter(retained_context["accepted_by_id"]))
    review["reviewer"] = {
        "name": "Independent Reviewer",
        "qualification_basis": "Qualified pharma-domain reviewer",
    }
    review["expected_finding_decisions"] = [
        {
            "expected_finding_id": "f1",
            "decision": "matched",
            "observed_finding_id": finding_id,
            "notes": "Meaning matches the adjudicated identity fact.",
        }
    ]
    review["observed_finding_decisions"] = [
        {
            "observed_finding_id": finding_id,
            "decision": "matched_expected",
            "expected_finding_id": "f1",
            "criticality": "noncritical",
            "notes": "Supported by the exact supplied span.",
        }
    ]
    review["fixture_obligations"] = [
        {
            "requirement_id": "company_profile.identity",
            "disposed": True,
            "notes": "Identity obligation was reviewed.",
        }
    ]
    review["truthful_incomplete"] = False
    review["case_status"] = "evaluated"
    review["status_reason"] = None
    review["notes"] = "Independent review complete."
    return review


class CandidateEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = suite()
        self.case = candidate.find_fixture(self.suite, "candidate-test-001")
        self.inputs = inputs()
        self.input_context = candidate.validate_inputs_against_fixture(self.case, self.inputs)
        self.retained = retained()
        self.retained_context = candidate.validate_retained_result(
            self.case,
            self.input_context,
            self.retained,
        )

    def evaluate(self, review: dict, usage=None) -> dict:
        return candidate.evaluate_candidate_case(
            self.suite,
            self.case,
            self.input_context,
            self.retained_context,
            review,
            inputs_file_sha256="1" * 64,
            retained_file_sha256="2" * 64,
            usage_payload=usage,
        )

    def test_valid_evaluated_case_scores_against_independent_mapping(self):
        report = self.evaluate(ready_review(self.suite, self.case, self.retained_context))
        self.assertEqual(report["case_status"], "evaluated")
        self.assertEqual(report["quality_metrics"]["noncritical_precision"], 1.0)
        self.assertEqual(report["quality_metrics"]["noncritical_recall"], 1.0)
        self.assertEqual(report["metric_case"]["accepted_unsupported_high_impact"], 0)
        self.assertFalse(report["frozen_wp1_baseline_completed"])

    def test_summary_mismatch_fails_closed(self):
        broken = copy.deepcopy(self.retained)
        broken["outputs"]["evaluation_summary"]["accepted_finding_count"] = 0
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "evaluation_summary"):
            candidate.validate_retained_result(self.case, self.input_context, broken)

    def test_truth_field_leakage_in_inputs_fails_closed(self):
        broken = copy.deepcopy(self.inputs)
        broken["evaluation_case"]["records"][0]["expected_findings"] = []
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "fields"):
            candidate.validate_inputs_against_fixture(self.case, broken)

    def test_wrong_company_projection_as_target_fails_closed(self):
        broken = copy.deepcopy(self.inputs)
        broken["evaluation_case"]["records"][0]["source_units"][1]["entity_id"] = "ficta"
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "Wrong-company"):
            candidate.validate_inputs_against_fixture(self.case, broken)

    def test_wrong_company_citation_fails_closed(self):
        broken = copy.deepcopy(self.retained)
        finding = broken["outputs"]["evaluation_result"]["accepted_findings"][0]
        finding["evidence"] = [{
            "locator": "source:distractor",
            "start": 0,
            "end": len("Other Company has a product."),
            "quote": "Other Company has a product.",
        }]
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "wrong-company"):
            candidate.validate_retained_result(self.case, self.input_context, broken)

    def test_citation_offset_mismatch_fails_closed(self):
        broken = copy.deepcopy(self.retained)
        broken["outputs"]["evaluation_result"]["accepted_findings"][0]["evidence"][0]["end"] -= 1
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "source span"):
            candidate.validate_retained_result(self.case, self.input_context, broken)

    def test_review_mapping_must_cover_every_expected_finding(self):
        review = ready_review(self.suite, self.case, self.retained_context)
        review["expected_finding_decisions"] = []
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "truth set"):
            self.evaluate(review)

    def test_review_mapping_must_cover_every_observed_finding(self):
        review = ready_review(self.suite, self.case, self.retained_context)
        review["observed_finding_decisions"] = []
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "accepted finding set"):
            self.evaluate(review)

    def test_unsupported_high_impact_claim_is_counted(self):
        review = ready_review(self.suite, self.case, self.retained_context)
        finding_id = next(iter(self.retained_context["accepted_by_id"]))
        review["expected_finding_decisions"][0] = {
            "expected_finding_id": "f1",
            "decision": "missed",
            "observed_finding_id": None,
            "notes": "The observed claim does not semantically match the expected finding.",
        }
        review["observed_finding_decisions"][0] = {
            "observed_finding_id": finding_id,
            "decision": "unsupported",
            "expected_finding_id": None,
            "criticality": "high",
            "notes": "Independent reviewer found no support for this accepted claim.",
        }
        report = self.evaluate(review)
        self.assertEqual(report["metric_case"]["accepted_unsupported_high_impact"], 1)
        self.assertEqual(report["quality_metrics"]["accepted_unsupported_high_impact"], 1)

    def test_pending_review_preserves_case_without_inventing_metrics(self):
        review = candidate.build_review_template(
            self.suite,
            self.case,
            self.retained_context,
            inputs_file_sha256="1" * 64,
            retained_file_sha256="2" * 64,
        )
        review["status_reason"] = "Independent semantic review has not been completed."
        report = self.evaluate(review)
        self.assertEqual(report["case_status"], "pending_review")
        self.assertIsNone(report["quality_metrics"])
        self.assertIsNone(report["metric_case"])

    def test_document_fixture_is_explicitly_not_executable(self):
        document_case = copy.deepcopy(self.case)
        document_case["mode"] = "document_review"
        status = candidate.assess_fixture_compatibility(document_case)
        self.assertEqual(status["status"], "not_executable")
        self.assertIn("candidate_mode_not_supported", status["reason_codes"])

    def test_usage_must_belong_to_same_run(self):
        review = ready_review(self.suite, self.case, self.retained_context)
        usage = {
            "run_uuid": "11111111-1111-1111-1111-111111111111",
            "execution_evidence": {
                "status": "available",
                "usage_status": "provider_reported",
            },
        }
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "different run"):
            self.evaluate(review, usage=usage)

    def test_usage_preserves_unknown_values_as_null(self):
        review = ready_review(self.suite, self.case, self.retained_context)
        usage = {
            "run_uuid": self.retained_context["run_uuid"],
            "execution_evidence": {
                "status": "available",
                "usage_status": "provider_reported",
                "receipt_count": 5,
                "usage": {"input_tokens": 100, "output_tokens": 20},
            },
        }
        report = self.evaluate(review, usage=usage)
        self.assertEqual(report["usage"]["receipt_count"], 5)
        self.assertEqual(report["usage"]["usage"]["input_tokens"], 100)
        self.assertIsNone(report["usage"]["usage"]["thought_tokens"])

    def test_safe_status_contains_counts_not_source_or_finding_text(self):
        report = self.evaluate(ready_review(self.suite, self.case, self.retained_context))
        status = candidate.safe_status(report)
        encoded = json.dumps(status)
        self.assertTrue(status["safe"])
        self.assertFalse(status["values_included"])
        self.assertNotIn("Ficta Therapeutics is a synthetic company", encoded)
        self.assertNotIn("statement", encoded)

    def test_batch_keeps_blocked_and_pending_cases_visible(self):
        evaluated = self.evaluate(ready_review(self.suite, self.case, self.retained_context))
        pending_review = copy.deepcopy(evaluated)
        pending_review["case_status"] = "pending_review"
        pending_review["metric_case"] = None
        pending_review["quality_metrics"] = None
        aggregate = candidate.aggregate_candidate_reports([evaluated, pending_review])
        self.assertEqual(aggregate["case_count"], 2)
        self.assertEqual(aggregate["status_counts"]["evaluated"], 1)
        self.assertEqual(aggregate["status_counts"]["pending_review"], 1)
        self.assertFalse(aggregate["all_cases_evaluated"])
        self.assertIsNone(aggregate["quality_gate"])

    def test_template_is_bound_to_exact_suite_and_files(self):
        review = candidate.build_review_template(
            self.suite,
            self.case,
            self.retained_context,
            inputs_file_sha256="1" * 64,
            retained_file_sha256="2" * 64,
        )
        self.assertEqual(review["suite_input_digest"], candidate._canonical_digest(self.suite))
        self.assertEqual(review["inputs_file_sha256"], "1" * 64)
        self.assertEqual(review["retained_result_file_sha256"], "2" * 64)
        self.assertEqual(review["case_status"], "pending_review")


if __name__ == "__main__":
    unittest.main()
