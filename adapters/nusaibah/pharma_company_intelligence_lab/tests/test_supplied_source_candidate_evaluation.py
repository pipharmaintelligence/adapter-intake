from __future__ import annotations

import copy
import contextlib
import io
import importlib
import json
import sys
import tempfile
import types
import unittest
from unittest import mock
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVALUATION_ROOT = HERE / "evaluation"
sys.path.insert(0, str(EVALUATION_ROOT))

import supplied_source_candidate_evaluation as candidate


def quote_candidate_retained(*, supported=True, version="0.2.2"):
    engine = candidate._source_contract(version)
    tool_folder = EVALUATION_ROOT.parents[2] / "structured_review_toolkit"
    name = "_candidate_exact_span_test_tool"
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [str(tool_folder)]
        sys.modules[name] = package
    tool = importlib.import_module(name + ".tool_operations_v0_1_1")
    wrapper = importlib.import_module(engine.__package__ +
        ".nusaibah_pharma_company_intelligence_lab_evaluation_v" + version.replace(".", "_") + "_adapter")
    class Inputs(dict):
        def invoke_agent(self, role, *, input, on_error):
            contract = input["response_contract"]
            value = {key: contract[key] for key in (
                "schema_version", "entity_id", "snapshot_id", "chunk_id", "role", "status")}
            if role != engine.VERIFIER_ROLE:
                value["requirements"] = []
                for requirement in contract["requirement_ids_in_order"]:
                    findings = []
                    if requirement == "company_identity":
                        unit = input["source_chunk"]["units"][0]
                        findings = [{"statement": unit["text"],
                                     "evidence": [{"locator": unit["locator"], "quote": unit["text"]}]}]
                    value["requirements"].append({"requirement_id": requirement,
                        "disposition": "findings" if findings else "no_evidence", "findings": findings})
            else:
                value["verdicts"] = [{**item, "state": "supported" if supported else "insufficient"}
                                     for item in contract["verdicts_in_order"]]
                value["coverage"] = [{**item, "reviewed": True, "unrepresented_evidence": False}
                                    for item in contract["coverage_in_order"]]
            return {"status": "completed", "result": {"schema_version": "agent_result.v1",
                "kind": "json", "content": [{"type": "json", "value": value}], "citations": []}}
        def invoke_asset(self, role, *, variables, on_error):
            return {"status": "success", "result": tool.execute_operation(variables)}
    adapter_name = "NusaibahPharmaCompanyIntelligenceLabEvaluationV" + version.replace(".", "") + "Adapter"
    response = getattr(wrapper, adapter_name)().invoke(Inputs(inputs()), {})
    return {"schema_version": "adapter_preview_result.v1",
            "run_uuid": "0455965f-eaf3-4f73-8bc2-9d21a7cdbc93",
            "asset_identity": candidate.CANDIDATE_ASSET_KEY + ":" + version, "outputs": response["outputs"]}


class QuoteCandidateEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.suite = suite()
        self.case = fixture_case()
        self.inputs = inputs()
        self.context = candidate.validate_inputs_against_fixture(
            self.case, self.inputs, candidate_version="0.2.2")
        self.retained = quote_candidate_retained()

    def validate(self, retained=None):
        return candidate.validate_retained_result(self.case, self.context, retained or self.retained)

    def test_new_version_template_and_offline_score_are_bound_to_exact_new_contract(self):
        context = self.validate()
        review = ready_review(self.suite, self.case, context)
        self.assertEqual("0.2.2", review["candidate_asset"]["asset_version"])
        report = candidate.evaluate_candidate_case(self.suite, self.case, self.context, context, review,
            inputs_file_sha256="1" * 64, retained_file_sha256="2" * 64)
        self.assertEqual("evaluated", report["case_status"])
        self.assertEqual("0.2.2", candidate.safe_status(report)["asset_version"])
        self.assertFalse(report["frozen_wp1_baseline_completed"])
        self.assertEqual(1, context["result"]["child_call_count"])

    def test_old_selector_or_borrowed_plan_cannot_score_new_result(self):
        old_context = candidate.validate_inputs_against_fixture(self.case, self.inputs)
        with self.assertRaises(candidate.CandidateEvaluationError):
            candidate.validate_retained_result(self.case, old_context, self.retained)
        broken = copy.deepcopy(self.retained)
        broken["outputs"]["evaluation_result"]["plan"] = old_context["prepared_review"]["plan"]
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "finite plan"):
            self.validate(broken)

    def test_missing_tampered_reordered_or_unbound_receipt_blocks_scoring(self):
        for variant in ("missing", "digest", "offset", "quote", "request_id", "chunk"):
            broken = copy.deepcopy(self.retained)
            result = broken["outputs"]["evaluation_result"]
            receipts = result["span_resolution_receipts"]
            if variant == "missing":
                receipts.clear()
            elif variant == "digest":
                receipts[0]["result"]["request_digest"] = "0" * 64
            elif variant == "offset":
                receipts[0]["result"]["output"]["spans"][0]["start"] = True
            elif variant == "quote":
                receipts[0]["result"]["output"]["spans"][0]["quote"] = "fabricated"
            elif variant == "request_id":
                receipts[0]["result"]["output"]["spans"][0]["request_id"] += "-other"
            else:
                receipts[0]["chunk_id"] = "wrong"
            with self.subTest(variant=variant), self.assertRaises(candidate.CandidateEvaluationError):
                self.validate(broken)

    def test_withheld_findings_still_require_resolved_evidence_accounting(self):
        retained = quote_candidate_retained(supported=False)
        context = self.validate(retained)
        self.assertEqual([], context["result"]["accepted_findings"])
        retained["outputs"]["evaluation_result"]["span_resolution_receipts"][0]["result"]["output"]["spans"] = []
        with self.assertRaises(candidate.CandidateEvaluationError):
            self.validate(retained)

    def test_child_count_and_scalar_summary_are_bound_and_bool_counts_rejected(self):
        for variant in ("summary", "count", "bool"):
            broken = copy.deepcopy(self.retained)
            if variant == "summary":
                broken["outputs"]["evaluation_summary"]["child_call_count"] = 0
            else:
                value = True if variant == "bool" else 2
                broken["outputs"]["evaluation_result"]["child_call_count"] = value
                broken["outputs"]["evaluation_summary"]["child_call_count"] = value
            with self.subTest(variant=variant), self.assertRaises(candidate.CandidateEvaluationError):
                self.validate(broken)

    def test_batches_cannot_mix_candidate_versions_or_methods(self):
        context = self.validate()
        review = ready_review(self.suite, self.case, context)
        first = candidate.evaluate_candidate_case(self.suite, self.case, self.context, context, review,
            inputs_file_sha256="1" * 64, retained_file_sha256="2" * 64)
        for variant in ("version", "method"):
            second = copy.deepcopy(first)
            second["case_id"] = "another"
            if variant == "version":
                second["candidate_asset"]["asset_version"] = "0.2.1"
            else:
                second["candidate_methodology_digest"] = "sha256:" + "0" * 64
            with self.subTest(variant=variant), self.assertRaises(candidate.CandidateEvaluationError):
                candidate.aggregate_candidate_reports([first, second],
                    expected_case_ids=[first["case_id"], second["case_id"]])

    def test_quote_version_cli_emits_bound_pending_review_without_provider_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, value in (("suite", self.suite), ("inputs", self.inputs), ("retained", self.retained)):
                (root / (name + ".json")).write_text(json.dumps(value), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code = candidate.main(["--candidate-version", "0.2.2", "--suite", str(root / "suite.json"),
                    "--case-id", self.case["case_id"], "--inputs", str(root / "inputs.json"),
                    "--retained-result", str(root / "retained.json"),
                    "--emit-review-template", str(root / "review.json")])
            self.assertEqual(0, code)
            review = candidate.load_json(root / "review.json")
            self.assertEqual("0.2.2", review["candidate_asset"]["asset_version"])
            self.assertEqual("pending_review", review["case_status"])


class RoleScopedCandidateEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.suite, self.case, self.inputs = suite(), fixture_case(), inputs()
        self.context = candidate.validate_inputs_against_fixture(self.case, self.inputs, candidate_version="0.2.3")
        self.retained = quote_candidate_retained(version="0.2.3")

    def validate(self, retained=None):
        return candidate.validate_retained_result(self.case, self.context, retained or self.retained)

    def test_scoped_candidate_receipt_and_quality_score_bind_to_the_distinct_method_and_asset(self):
        retained_context = self.validate()
        review = ready_review(self.suite, self.case, retained_context)
        self.assertEqual("0.2.3", review["candidate_asset"]["asset_version"])
        report = candidate.evaluate_candidate_case(self.suite, self.case, self.context, retained_context, review,
            inputs_file_sha256="1" * 64, retained_file_sha256="2" * 64)
        self.assertEqual("evaluated", report["case_status"])
        self.assertEqual("0.2.3", candidate.safe_status(report)["asset_version"])
        self.assertEqual(1, report["review_counts"]["matched_expected_count"])
        self.assertFalse(report["frozen_wp1_baseline_completed"])
        self.assertNotEqual(candidate._source_contract("0.2.2").digest(candidate._source_contract("0.2.2").METHOD),
                            report["candidate_methodology_digest"])

    def test_historical_identity_plan_and_review_cannot_be_relabelled_as_scoped_evidence(self):
        old_context = candidate.validate_inputs_against_fixture(self.case, self.inputs, candidate_version="0.2.2")
        with self.assertRaises(candidate.CandidateEvaluationError):
            candidate.validate_retained_result(self.case, old_context, self.retained)
        broken = copy.deepcopy(self.retained)
        broken["outputs"]["evaluation_result"]["plan"] = old_context["prepared_review"]["plan"]
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "finite plan"):
            self.validate(broken)
        scoped_context = self.validate()
        review = ready_review(self.suite, self.case, scoped_context)
        review["candidate_asset"]["asset_version"] = "0.2.2"
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "asset identity"):
            candidate.evaluate_candidate_case(self.suite, self.case, self.context, scoped_context, review,
                inputs_file_sha256="1" * 64, retained_file_sha256="2" * 64)

    def test_scoped_candidate_still_rejects_missing_or_tampered_exact_span_receipts(self):
        for variant in ("missing", "digest", "offset"):
            broken = copy.deepcopy(self.retained)
            receipts = broken["outputs"]["evaluation_result"]["span_resolution_receipts"]
            if variant == "missing":
                receipts.clear()
            elif variant == "digest":
                receipts[0]["result"]["request_digest"] = "0" * 64
            else:
                receipts[0]["result"]["output"]["spans"][0]["start"] = True
            with self.subTest(variant=variant), self.assertRaises(candidate.CandidateEvaluationError):
                self.validate(broken)

    def test_scoped_cli_emits_only_pending_review_until_independent_attestation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, value in (("suite", self.suite), ("inputs", self.inputs), ("retained", self.retained)):
                (root / (name + ".json")).write_text(json.dumps(value), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code = candidate.main(["--candidate-version", "0.2.3", "--suite", str(root / "suite.json"),
                    "--case-id", self.case["case_id"], "--inputs", str(root / "inputs.json"),
                    "--retained-result", str(root / "retained.json"),
                    "--emit-review-template", str(root / "review.json")])
            self.assertEqual(0, code)
            review = candidate.load_json(root / "review.json")
            self.assertEqual("0.2.3", review["candidate_asset"]["asset_version"])
            self.assertEqual("pending_review", review["case_status"])
            self.assertIsNone(review["reviewer"]["name"])


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
    prepared = candidate.SOURCE_REVIEW.prepare_review(inputs())
    quote = "Ficta Therapeutics is a synthetic company."
    finding_id = "sha256:" + "b" * 64
    snapshot_id = prepared["snapshot_id"]
    chunk_id = prepared["chunks"][0]["chunk_id"]
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
        "plan": prepared["plan"],
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
    finding = result["accepted_findings"][0]
    material = {key: finding[key] for key in (
        "entity_id", "snapshot_id", "chunk_id", "role", "requirement_id", "ordinal", "statement", "evidence",
    )}
    finding_id = candidate._canonical_digest(material)
    finding["finding_id"] = finding_id
    finding["verification"] = {
        "finding_id": finding_id, "state": "supported",
        "input_digest": candidate._canonical_digest({
            "finding": {**material, "finding_id": finding_id},
            "source_units": prepared["chunks"][0]["units"],
            "methodology_digest": prepared["plan"]["methodology_digest"],
        }),
    }
    finding["global_verification"] = {
        "finding_id": finding_id, "state": "supported",
        "input_digest": candidate._canonical_digest({
            **material, "finding_id": finding_id, "verification": finding["verification"],
        }),
    }
    result["coverage"][0]["finding_ids"] = [finding_id]
    result["coverage"][0]["accepted_finding_ids"] = [finding_id]
    for role, requirements in candidate.SOURCE_REVIEW.ROLES.items():
        for requirement in requirements:
            if requirement == "company_identity":
                continue
            result["coverage"].append({
                "chunk_id": chunk_id, "primary_locator": "source:identity", "role": role,
                "requirement_id": requirement, "finding_ids": [], "specialist_disposition": "no_evidence",
                "reviewed": True, "unrepresented_evidence": False, "accepted_finding_ids": [],
                "evidence_state": "insufficient",
            })
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
        pending_review["case_id"] = "candidate-test-002"
        pending_review["metric_case"] = None
        pending_review["quality_metrics"] = None
        aggregate = candidate.aggregate_candidate_reports(
            [evaluated, pending_review], expected_case_ids=["candidate-test-001", "candidate-test-002"],
        )
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

    def test_missing_coverage_cannot_claim_complete_accounting(self):
        broken = copy.deepcopy(self.retained)
        broken["outputs"]["evaluation_result"]["coverage"] = []
        broken["outputs"]["evaluation_result"]["accepted_findings"] = []
        broken["outputs"]["evaluation_summary"]["accepted_finding_count"] = 0
        with self.assertRaises(candidate.CandidateEvaluationError):
            candidate.validate_retained_result(self.case, self.input_context, broken)

    def test_declared_call_budget_cannot_bypass_candidate_limit(self):
        broken = copy.deepcopy(self.retained)
        broken["outputs"]["evaluation_result"]["plan"]["logical_call_limit"] = 100
        broken["outputs"]["evaluation_result"]["agent_call_count"] = 99
        broken["outputs"]["evaluation_summary"]["agent_call_count"] = 99
        with self.assertRaises(candidate.CandidateEvaluationError):
            candidate.validate_retained_result(self.case, self.input_context, broken)

    def test_snapshot_must_be_derived_from_exact_input(self):
        broken = copy.deepcopy(self.retained)
        result = broken["outputs"]["evaluation_result"]
        result["snapshot_id"] = "sha256:" + "0" * 64
        result["plan"]["snapshot_id"] = result["snapshot_id"]
        result["accepted_findings"][0]["snapshot_id"] = result["snapshot_id"]
        with self.assertRaises(candidate.CandidateEvaluationError):
            candidate.validate_retained_result(self.case, self.input_context, broken)

    def test_verifier_digest_must_bind_to_the_actual_finding(self):
        broken = copy.deepcopy(self.retained)
        broken["outputs"]["evaluation_result"]["accepted_findings"][0]["verification"]["input_digest"] = "sha256:" + "0" * 64
        with self.assertRaises(candidate.CandidateEvaluationError):
            candidate.validate_retained_result(self.case, self.input_context, broken)

    def test_one_observed_claim_cannot_recover_two_expected_findings(self):
        self.case["candidate_expected_findings"].append({
            **self.case["candidate_expected_findings"][0], "finding_id": "f2",
        })
        review = ready_review(self.suite, self.case, self.retained_context)
        review["expected_finding_decisions"].append({
            **review["expected_finding_decisions"][0], "expected_finding_id": "f2",
        })
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "reciprocal"):
            self.evaluate(review)

    def test_supported_additional_claim_does_not_recover_missed_truth(self):
        review = ready_review(self.suite, self.case, self.retained_context)
        review["expected_finding_decisions"][0].update(
            decision="missed", observed_finding_id=None,
        )
        review["observed_finding_decisions"][0].update(
            decision="supported_additional", expected_finding_id=None,
        )
        report = self.evaluate(review)
        self.assertEqual(report["quality_metrics"]["noncritical_recall"], 0.0)
        self.assertEqual(report["quality_metrics"]["noncritical_precision"], 1.0)

    def test_usage_requires_explicit_matching_run_identity(self):
        review = ready_review(self.suite, self.case, self.retained_context)
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "run"):
            self.evaluate(review, usage={"execution_evidence": {"status": "available"}})

    def test_held_out_truth_cannot_be_opened_without_a_freeze_contract(self):
        self.case["split"] = "held_out"
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "Held-out"):
            candidate.find_fixture(self.suite, self.case["case_id"])

    def test_duplicate_batch_cases_cannot_inflate_finite_coverage(self):
        report = self.evaluate(ready_review(self.suite, self.case, self.retained_context))
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "duplicate"):
            candidate.aggregate_candidate_reports(
                [report, copy.deepcopy(report)], expected_case_ids=[self.case["case_id"]],
            )

    def test_freeform_usage_status_cannot_leak_into_safe_projection(self):
        review = ready_review(self.suite, self.case, self.retained_context)
        usage = {
            "run_uuid": self.retained_context["run_uuid"],
            "execution_evidence": {"status": "available", "usage_status": "source secret text"},
        }
        status = candidate.safe_status(self.evaluate(review, usage=usage))
        self.assertNotIn("source secret text", json.dumps(status))

    def test_duplicate_coverage_rows_fail_closed(self):
        broken = copy.deepcopy(self.retained)
        rows = broken["outputs"]["evaluation_result"]["coverage"]
        rows.append(copy.deepcopy(rows[0]))
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "obligation"):
            candidate.validate_retained_result(self.case, self.input_context, broken)

    def test_zero_calls_cannot_claim_a_completed_review(self):
        broken = copy.deepcopy(self.retained)
        broken["outputs"]["evaluation_result"]["agent_call_count"] = 0
        broken["outputs"]["evaluation_summary"]["agent_call_count"] = 0
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "call count"):
            candidate.validate_retained_result(self.case, self.input_context, broken)

    def test_boolean_counts_cannot_masquerade_as_integers(self):
        for field in ("mutable_call_count", "chunk_count"):
            broken = copy.deepcopy(self.retained)
            broken["outputs"]["evaluation_summary"][field] = False if field == "mutable_call_count" else True
            with self.subTest(field=field), self.assertRaises(candidate.CandidateEvaluationError):
                candidate.validate_retained_result(self.case, self.input_context, broken)

    def test_finding_identity_cannot_be_reused_for_changed_statement(self):
        broken = copy.deepcopy(self.retained)
        broken["outputs"]["evaluation_result"]["accepted_findings"][0]["statement"] = "An invented statement."
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "exact material"):
            candidate.validate_retained_result(self.case, self.input_context, broken)

    def test_global_verdict_must_bind_the_locally_verified_finding(self):
        broken = copy.deepcopy(self.retained)
        broken["outputs"]["evaluation_result"]["accepted_findings"][0]["global_verification"]["input_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "global_verification digest"):
            candidate.validate_retained_result(self.case, self.input_context, broken)

    def test_empty_citation_does_not_establish_evidence(self):
        broken = copy.deepcopy(self.retained)
        broken["outputs"]["evaluation_result"]["accepted_findings"][0]["evidence"][0].update(start=0, end=0, quote="")
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "source span"):
            candidate.validate_retained_result(self.case, self.input_context, broken)

    def test_review_receipt_binds_candidate_method_separately_from_fixture_method(self):
        review = ready_review(self.suite, self.case, self.retained_context)
        self.assertNotEqual(review["methodology_digest"], review["candidate_methodology_digest"])
        review["candidate_methodology_digest"] = review["methodology_digest"]
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "candidate methodology"):
            self.evaluate(review)

    def test_batch_cannot_omit_a_declared_case(self):
        report = self.evaluate(ready_review(self.suite, self.case, self.retained_context))
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "declared case set"):
            candidate.aggregate_candidate_reports(
                [report], expected_case_ids=[self.case["case_id"], "missing-case"],
            )

    def test_batch_rejects_mixed_suite_digests(self):
        report = self.evaluate(ready_review(self.suite, self.case, self.retained_context))
        other = copy.deepcopy(report)
        other["case_id"] = "other-case"
        other["suite_input_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(candidate.CandidateEvaluationError, "suite identity"):
            candidate.aggregate_candidate_reports(
                [report, other], expected_case_ids=[self.case["case_id"], "other-case"],
            )

    def test_find_fixture_requires_frozen_adjudication_provenance(self):
        for section, field, value in (
            ("adjudication", "primary_reviewer", ""),
            ("source_identity", "digest_status", "pending"),
        ):
            changed = copy.deepcopy(self.suite)
            changed["cases"][0][section][field] = value
            with self.subTest(field=field), self.assertRaises(candidate.CandidateEvaluationError):
                candidate.find_fixture(changed, self.case["case_id"])

    def test_cli_emits_bound_pending_review_status(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, value in (("suite", self.suite), ("inputs", self.inputs), ("retained", self.retained)):
                (root / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = candidate.main([
                    "--suite", str(root / "suite.json"), "--case-id", self.case["case_id"],
                    "--inputs", str(root / "inputs.json"), "--retained-result", str(root / "retained.json"),
                    "--emit-review-template", str(root / "review.json"),
                    "--safe-status-output", str(root / "status.json"),
                ])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["case_status"], "pending_review")
            receipt = candidate.load_json(root / "review.json")
            self.assertEqual(receipt["candidate_methodology_digest"], self.retained_context["result"]["plan"]["methodology_digest"])
            self.assertEqual(candidate.load_json(root / "status.json")["case_status"], "pending_review")

    def test_cli_rejects_held_out_without_emitting_truth_template(self):
        held_out = copy.deepcopy(self.suite)
        held_out["cases"][0]["split"] = "held_out"
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "suite.json").write_text(json.dumps(held_out), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = candidate.main([
                    "--suite", str(root / "suite.json"), "--case-id", self.case["case_id"],
                    "--inputs", str(root / "absent.json"), "--retained-result", str(root / "absent.json"),
                    "--emit-review-template", str(root / "review.json"),
                ])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(output.getvalue())["case_status"], "blocked")
            self.assertFalse((root / "review.json").exists())

    def test_cli_binds_the_bytes_validated_before_a_file_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, value in (("suite", self.suite), ("inputs", self.inputs), ("retained", self.retained)):
                (root / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
            original_sha = candidate.hashlib.sha256((root / "inputs.json").read_bytes()).hexdigest()
            validate = candidate.validate_retained_result

            def change_input_after_validation(*args):
                result = validate(*args)
                (root / "inputs.json").write_text('{"changed":true}', encoding="utf-8")
                return result

            with mock.patch.object(candidate, "validate_retained_result", side_effect=change_input_after_validation):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = candidate.main([
                        "--suite", str(root / "suite.json"), "--case-id", self.case["case_id"],
                        "--inputs", str(root / "inputs.json"), "--retained-result", str(root / "retained.json"),
                        "--emit-review-template", str(root / "review.json"),
                    ])
            self.assertEqual(code, 0)
            self.assertEqual(candidate.load_json(root / "review.json")["inputs_file_sha256"], original_sha)


if __name__ == "__main__":
    unittest.main()
