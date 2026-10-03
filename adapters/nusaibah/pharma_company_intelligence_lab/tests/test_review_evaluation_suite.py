from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
EVALUATION_ROOT = HERE / "evaluation"
SUITE_PATH = EVALUATION_ROOT / "review_evaluation_suite.v1.json"
TAXONOMY_PATH = EVALUATION_ROOT / "review_criticality_taxonomy.v1.json"

import sys
sys.path.insert(0, str(EVALUATION_ROOT))
from review_evaluation_status import evaluate_suite, evaluation_status, source_digest
from review_adjudication import (
    AdjudicationReceiptError,
    apply_adjudication_receipt,
    build_adjudication_receipt_template,
)
from review_baseline_measurement import (
    BaselineMeasurementError,
    assess_pinned_baseline_compatibility,
    build_measurement_template,
    evaluate_baseline_measurement,
)
from review_baseline_replay import (
    BaselineReplayError,
    build_replay_company_record,
    build_replay_inputs,
    replay_plan,
)

EXPECTED_BASELINE = {
    "asset_key": "nusaibah.pharma_company_intelligence_lab",
    "asset_version": "0.1.12",
    "runtime_version": "0.1.97",
    "intake_commit": "21cc6b39492cbd3c090de537a2ee27c599f0f0ec",
    "assets_promotion_head": "ba2db9b6af9dd4963634861e71335a0d313b8ec0",
    "assets_merge_commit": "7db8373b2a65a397c5ec01d41c3d440d9dbcd5b1",
    "core_lifetime_fix": "3d25123b6231954fb40c97097e957ea38a4a5ff3",
    "preview_run_uuid": "6e95802c-2336-47f5-b7c2-1e30476a0fef",
    "execution_seconds": 303,
    "factual_quality_measured": False,
    "cost_baseline_measured": False,
}

REQUIRED_STRATA = {
    "small_source",
    "medium_source",
    "oversized_source",
    "table",
    "footnote",
    "time_change",
    "jurisdiction_change",
    "conflicting_sources",
    "missing_evidence",
    "wrong_company_distractor",
    "ocr_gap",
    "source_prompt_injection",
    "boundary_spanning_claim",
    "overlap_duplicate",
    "changed_source_hash",
    "citation_laundering",
    "unsupported_paraphrase",
    "omitted_mandatory_requirement",
    "malformed_output",
    "truncation",
    "no_source_access",
    "preview_no_write",
    "timeout_cancellation",
    "final_synthesis_new_claim",
}

SAFE_EXPECTED_STATES = {"supported", "contradicted", "insufficient", "not_applicable"}
SAFE_CRITICALITY = {"noncritical", "high"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ReviewEvaluationSuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.suite = json.loads(SUITE_PATH.read_text(encoding="utf-8"))

    @staticmethod
    def _complete_measurement(suite: dict) -> dict:
        measurement = build_measurement_template(suite)
        for case, item in zip(suite["cases"], measurement["cases"], strict=True):
            expected_findings = case["candidate_expected_findings"]
            noncritical_expected = sum(
                finding["criticality"] == "noncritical"
                for finding in expected_findings
            )
            critical_expected = sum(
                finding["criticality"] == "high"
                for finding in expected_findings
            )
            item.update(
                {
                    "status": "measured",
                    "run_id": f"run:{case['case_id']}",
                    "reason_code": None,
                    "material_claim_count": max(1, len(expected_findings)),
                    "supported_material_claim_count": max(1, len(expected_findings)),
                    "noncritical_true_positive": noncritical_expected,
                    "noncritical_false_positive": 0,
                    "noncritical_false_negative": 0,
                    "critical_expected": critical_expected,
                    "critical_recovered": critical_expected,
                    "accepted_unsupported_high_impact": 0,
                    "truthful_incomplete": not case["candidate_expected_complete"],
                    "all_obligations_disposed": True,
                    "wrong_company_join_count": 0,
                    "unauthorized_write_count": 0,
                    "cap_overrun_count": 0,
                    "false_complete_count": 0,
                }
            )
        return measurement

    def test_baseline_is_exact_and_does_not_invent_usage_or_quality(self) -> None:
        self.assertEqual(self.suite["baseline"], EXPECTED_BASELINE)

        observations = self.suite["usage_observations"]
        for field in (
            "source_tokens",
            "input_characters",
            "answer_tokens",
            "thinking_tokens",
            "provider_reported_cost",
        ):
            self.assertIsNone(observations[field], field)

    def test_suite_has_24_cases_with_fixed_development_and_held_out_split(self) -> None:
        cases = self.suite["cases"]
        self.assertEqual(len(cases), 24)

        case_ids = [case["case_id"] for case in cases]
        self.assertEqual(len(case_ids), len(set(case_ids)))

        development = [case for case in cases if case["split"] == "development"]
        held_out = [case for case in cases if case["split"] == "held_out"]

        self.assertEqual(len(development), 16)
        self.assertEqual(len(held_out), 8)
        self.assertEqual(
            self.suite["split_policy"]["held_out_ids"],
            [case["case_id"] for case in held_out],
        )

    def test_oversized_case_is_genuinely_large(self) -> None:
        case = next(
            item
            for item in self.suite["cases"]
            if item["case_id"] == "document-oversized-017"
        )
        total_chars = sum(len(unit["text"]) for unit in case["source_units"])
        self.assertGreaterEqual(total_chars, 100_000)
        self.assertGreaterEqual(len(case["source_units"]), 20)

    def test_required_adversarial_strata_are_present(self) -> None:
        observed = {
            stratum
            for case in self.suite["cases"]
            for stratum in case["strata"]
        }
        self.assertFalse(REQUIRED_STRATA - observed)

    def test_case_identity_and_evidence_locators_are_self_consistent(self) -> None:
        for case in self.suite["cases"]:
            with self.subTest(case_id=case["case_id"]):
                self.assertEqual(
                    case["schema_version"],
                    "pharma_review_evaluation_case.v1",
                )
                self.assertIn(case["mode"], {"company_research", "document_review"})
                self.assertIn(case["split"], {"development", "held_out"})
                self.assertTrue(case["applicable_requirements"])

                source_units = case["source_units"]
                locators = [item["locator"] for item in source_units]
                self.assertEqual(len(locators), len(set(locators)))

                for finding in case["candidate_expected_findings"]:
                    self.assertIn(finding["expected_state"], SAFE_EXPECTED_STATES)
                    self.assertIn(finding["criticality"], SAFE_CRITICALITY)
                    self.assertTrue(finding["statement"].strip())
                    for locator in finding["supporting_locators"]:
                        self.assertIn(locator, locators)
                    for locator in finding["contradicting_locators"]:
                        self.assertIn(locator, locators)

    def test_criticality_taxonomy_is_explicit_and_not_self_certifying(self) -> None:
        taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            taxonomy["schema_version"],
            "pharma_review_criticality_taxonomy.v1",
        )
        self.assertIn(
            taxonomy["status"],
            {"proposed_for_domain_adjudication", "adjudicated"},
        )
        if taxonomy["status"] == "adjudicated":
            self.assertTrue(
                str(taxonomy["adjudication"]["assigned_domain_reviewer"]).strip()
            )
        self.assertIs(taxonomy["levels"]["high"]["blocking_when_unsupported"], True)
        self.assertIs(
            taxonomy["levels"]["noncritical"]["blocking_when_unsupported"],
            False,
        )

        class_ids = {
            item["class_id"]
            for item in taxonomy["levels"]["high"]["candidate_classes"]
        }
        self.assertEqual(
            class_ids,
            {
                "regulatory_status",
                "clinical_or_safety",
                "manufacturing_or_quality",
                "entity_identity",
                "review_completeness",
            },
        )

    def test_status_report_rejects_adjudication_without_named_reviewer(self) -> None:
        suite = json.loads(json.dumps(self.suite))
        taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))

        suite["status"] = "adjudicated"
        taxonomy["status"] = "adjudicated"
        suite["adjudication_policy"]["assigned_domain_reviewer"] = "Domain reviewer"
        taxonomy["adjudication"]["assigned_domain_reviewer"] = "Domain reviewer"

        for case in suite["cases"]:
            case["adjudication"] = {
                "status": "adjudicated",
                "primary_reviewer": None,
                "secondary_reviewer": None,
                "disagreement": False,
            }
            case["source_identity"]["digest_status"] = "frozen"
            case["source_identity"]["content_sha256"] = source_digest(case)

        report = evaluate_suite(suite, taxonomy)

        self.assertEqual(report["missing_primary_reviewer_count"], 24)
        self.assertIs(report["blockers"]["missing_primary_reviewer"], True)
        self.assertIs(report["wp1_contract_ready"], False)
        self.assertIs(report["wp2_unblocked"], False)

    def test_status_report_accepts_only_fully_adjudicated_frozen_suite(self) -> None:
        suite = json.loads(json.dumps(self.suite))
        taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))

        suite["status"] = "adjudicated"
        taxonomy["status"] = "adjudicated"
        suite["adjudication_policy"]["assigned_domain_reviewer"] = "Domain reviewer"
        taxonomy["adjudication"]["assigned_domain_reviewer"] = "Domain reviewer"
        suite["quality_threshold_policy"]["status"] = "calibrated"
        suite["quality_threshold_policy"]["calibrated_thresholds"] = {
            "factual_faithfulness_min": 0.98,
            "noncritical_precision_min": 0.95,
            "noncritical_recall_min": 0.95,
        }
        suite["quality_threshold_policy"]["calibration"]["assigned_domain_owner"] = (
            "Domain owner"
        )
        suite["quality_threshold_policy"]["calibration"]["decision_note"] = (
            "Synthetic test calibration decision."
        )

        for case in suite["cases"]:
            case["adjudication"]["status"] = "adjudicated"
            case["adjudication"]["primary_reviewer"] = "Domain reviewer"
            case["source_identity"]["digest_status"] = "frozen"
            case["source_identity"]["content_sha256"] = source_digest(case)

        report = evaluate_suite(suite, taxonomy)

        self.assertEqual(report["pending_domain_review_count"], 0)
        self.assertEqual(report["missing_primary_reviewer_count"], 0)
        self.assertEqual(report["invalid_frozen_digest_count"], 0)
        self.assertIs(report["domain_reviewer_assigned"], True)
        self.assertFalse(any(report["blockers"].values()))
        self.assertIs(report["wp1_contract_ready"], True)
        self.assertIs(report["baseline_measurement_ready"], False)
        self.assertIs(report["completion_blockers"]["baseline_measurement_missing_or_incomplete"], True)
        self.assertIs(report["wp1_complete"], False)
        self.assertIs(report["wp2_unblocked"], False)

    def test_status_report_keeps_wp2_blocked_until_adjudication_is_real(self) -> None:
        suite = json.loads(json.dumps(self.suite))
        taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))

        suite["status"] = "pending_domain_review"
        taxonomy["status"] = "proposed_for_domain_adjudication"
        suite["adjudication_policy"]["assigned_domain_reviewer"] = None
        taxonomy["adjudication"]["assigned_domain_reviewer"] = None
        suite["quality_threshold_policy"]["status"] = "pending_domain_calibration"
        suite["quality_threshold_policy"]["calibrated_thresholds"] = {
            "factual_faithfulness_min": None,
            "noncritical_precision_min": None,
            "noncritical_recall_min": None,
        }
        suite["quality_threshold_policy"]["calibration"]["assigned_domain_owner"] = None
        suite["quality_threshold_policy"]["calibration"]["decision_note"] = None

        for case in suite["cases"]:
            case["adjudication"] = {
                "status": "pending_domain_review",
                "primary_reviewer": None,
                "secondary_reviewer": None,
                "disagreement": False,
            }
            case["source_identity"]["digest_status"] = "pending_fixture_freeze"
            case["source_identity"]["content_sha256"] = None

        report = evaluate_suite(suite, taxonomy)

        self.assertEqual(report["case_count"], 24)
        self.assertEqual(report["development_count"], 16)
        self.assertEqual(report["held_out_count"], 8)
        self.assertEqual(report["candidate_complete_count"], 20)
        self.assertEqual(report["candidate_incomplete_count"], 4)
        self.assertEqual(report["adjudicated_count"], 0)
        self.assertEqual(report["pending_domain_review_count"], 24)
        self.assertIs(report["quality_thresholds_calibrated"], False)
        self.assertIs(report["blockers"]["quality_thresholds_not_calibrated"], True)
        self.assertIs(report["wp1_contract_ready"], False)
        self.assertIs(report["wp2_unblocked"], False)

    def test_status_report_unblocks_wp2_only_with_complete_validated_baseline(self) -> None:
        taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
        measurement = self._complete_measurement(self.suite)

        report = evaluate_suite(
            self.suite,
            taxonomy,
            baseline_measurement=measurement,
        )

        self.assertIs(report["wp1_contract_ready"], True)
        self.assertIs(report["baseline_measurement_ready"], True)
        self.assertIs(report["wp1_complete"], True)
        self.assertIs(report["wp2_unblocked"], True)
        self.assertFalse(any(report["completion_blockers"].values()))

    def test_completion_expectations_distinguish_complete_and_incomplete_cases(self) -> None:
        expected_incomplete = {
            "document-ocr-gap-014",
            "document-no-source-access-022",
            "document-output-failure-023",
            "document-budget-final-claim-024",
        }
        actual_incomplete = {
            case["case_id"]
            for case in self.suite["cases"]
            if case["candidate_expected_complete"] is False
        }
        self.assertEqual(actual_incomplete, expected_incomplete)
        for case in self.suite["cases"]:
            with self.subTest(case_id=case["case_id"]):
                self.assertIsInstance(case["candidate_expected_complete"], bool)
                self.assertTrue(case["completion_expectation_reason"].strip())

    def test_status_report_rejects_uncalibrated_quality_thresholds(self) -> None:
        suite = json.loads(json.dumps(self.suite))
        taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))

        suite["status"] = "adjudicated"
        taxonomy["status"] = "adjudicated"
        suite["adjudication_policy"]["assigned_domain_reviewer"] = "Domain reviewer"
        taxonomy["adjudication"]["assigned_domain_reviewer"] = "Domain reviewer"
        suite["quality_threshold_policy"]["status"] = "pending_domain_calibration"
        suite["quality_threshold_policy"]["calibrated_thresholds"] = {
            "factual_faithfulness_min": None,
            "noncritical_precision_min": None,
            "noncritical_recall_min": None,
        }
        suite["quality_threshold_policy"]["calibration"]["assigned_domain_owner"] = None
        suite["quality_threshold_policy"]["calibration"]["decision_note"] = None

        for case in suite["cases"]:
            case["adjudication"]["status"] = "adjudicated"
            case["adjudication"]["primary_reviewer"] = "Domain reviewer"
            case["source_identity"]["digest_status"] = "frozen"
            case["source_identity"]["content_sha256"] = source_digest(case)

        report = evaluate_suite(suite, taxonomy)

        self.assertIs(report["blockers"]["quality_thresholds_not_calibrated"], True)
        self.assertIs(report["wp1_contract_ready"], False)
        self.assertIs(report["wp2_unblocked"], False)

    def test_adjudication_receipt_template_is_bound_to_exact_inputs(self) -> None:
        taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
        receipt = build_adjudication_receipt_template(self.suite, taxonomy)

        self.assertEqual(len(receipt["cases"]), 24)
        self.assertTrue(receipt["suite_input_digest"].startswith("sha256:"))
        self.assertTrue(receipt["taxonomy_input_digest"].startswith("sha256:"))
        self.assertTrue(all(item["decision"] == "pending" for item in receipt["cases"]))

        changed_suite = json.loads(json.dumps(self.suite))
        changed_suite["cases"][0]["title"] += " changed"
        with self.assertRaises(AdjudicationReceiptError):
            apply_adjudication_receipt(changed_suite, taxonomy, receipt)

    def test_adjudication_receipt_requires_complete_human_and_calibration_decisions(self) -> None:
        taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
        receipt = build_adjudication_receipt_template(self.suite, taxonomy)

        with self.assertRaises(AdjudicationReceiptError):
            apply_adjudication_receipt(self.suite, taxonomy, receipt)

        receipt["reviewer"] = {
            "name": "Qualified reviewer",
            "qualification_basis": "Recorded pharma-domain qualification.",
        }
        receipt["taxonomy"] = {
            "decision": "approved",
            "notes": "Taxonomy reviewed and accepted.",
        }
        receipt["thresholds"] = {
            "decision": "approved",
            "domain_owner": "Domain owner",
            "decision_note": "Calibrated against the adjudicated evaluation design.",
            "factual_faithfulness_min": 0.98,
            "noncritical_precision_min": 0.95,
            "noncritical_recall_min": 0.95,
        }
        for item in receipt["cases"]:
            item["decision"] = "approved"
            item["notes"] = "Reviewed against source units and expected outcome."

        updated_suite, updated_taxonomy = apply_adjudication_receipt(
            self.suite,
            taxonomy,
            receipt,
        )
        report = evaluate_suite(updated_suite, updated_taxonomy)

        self.assertEqual(report["adjudicated_count"], 24)
        self.assertEqual(report["invalid_frozen_digest_count"], 0)
        self.assertIs(report["quality_thresholds_calibrated"], True)
        self.assertIs(report["wp1_contract_ready"], True)
        self.assertIs(report["baseline_measurement_ready"], False)
        self.assertIs(report["wp1_complete"], False)
        self.assertIs(report["wp2_unblocked"], False)

    def test_adjudication_receipt_requires_second_reviewer_for_disagreement(self) -> None:
        taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
        receipt = build_adjudication_receipt_template(self.suite, taxonomy)
        receipt["reviewer"] = {
            "name": "Qualified reviewer",
            "qualification_basis": "Recorded pharma-domain qualification.",
        }
        receipt["taxonomy"] = {
            "decision": "approved",
            "notes": "Taxonomy reviewed and accepted.",
        }
        receipt["thresholds"] = {
            "decision": "approved",
            "domain_owner": "Domain owner",
            "decision_note": "Calibration decision.",
            "factual_faithfulness_min": 0.98,
            "noncritical_precision_min": 0.95,
            "noncritical_recall_min": 0.95,
        }
        for item in receipt["cases"]:
            item["decision"] = "approved"
            item["notes"] = "Reviewed."
        receipt["cases"][0]["disagreement"] = True

        with self.assertRaises(AdjudicationReceiptError):
            apply_adjudication_receipt(self.suite, taxonomy, receipt)

    def test_pinned_baseline_cannot_directly_execute_adjudicated_fixture_suite(self) -> None:
        manifest_path = HERE.parent / "nusaibah_pharma_company_intelligence_lab.asset.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        version = manifest["versions"]["0.1.12"]

        report = assess_pinned_baseline_compatibility(self.suite, version)

        self.assertEqual(report["case_count"], 24)
        self.assertEqual(report["compatible_case_count"], 0)
        self.assertEqual(report["incompatible_case_count"], 24)
        self.assertIs(report["direct_fixture_execution_supported"], False)
        self.assertTrue(
            any(
                "document_review_input_contract_absent" in item["reason_codes"]
                for item in report["cases"]
            )
        )
        self.assertTrue(
            all(
                "live_company_selector_absent_from_fixture" in item["reason_codes"]
                for item in report["cases"]
            )
        )

    def test_baseline_measurement_stays_incomplete_for_incompatible_cases(self) -> None:
        measurement = build_measurement_template(self.suite)
        for item in measurement["cases"]:
            item["status"] = "not_executable"
            item["reason_code"] = "baseline_input_contract_incompatible"

        report = evaluate_baseline_measurement(self.suite, measurement)

        self.assertIs(report["measurement_complete"], False)
        self.assertEqual(report["measured_case_count"], 0)
        self.assertEqual(report["not_executable_case_count"], 24)
        self.assertIsNone(report["quality_metrics"])
        self.assertIsNone(report["quality_gate"])
        self.assertIsNone(report["controls_passed"])

    def test_baseline_measurement_rejects_edited_critical_expected_denominator(self) -> None:
        measurement = self._complete_measurement(self.suite)
        target_case = next(
            case
            for case in self.suite["cases"]
            if case["candidate_expected_complete"]
            and any(
                finding["criticality"] == "high"
                for finding in case["candidate_expected_findings"]
            )
        )
        target = next(
            item
            for item in measurement["cases"]
            if item["case_id"] == target_case["case_id"]
        )
        self.assertGreater(target["critical_expected"], 0)

        target["critical_expected"] = 0

        with self.assertRaisesRegex(
            BaselineMeasurementError,
            "critical_expected does not match adjudicated truth",
        ):
            evaluate_baseline_measurement(self.suite, measurement)

    def test_baseline_measurement_rejects_partial_or_stale_case_truth(self) -> None:
        measurement = build_measurement_template(self.suite)
        for item in measurement["cases"]:
            item["status"] = "not_executable"
            item["reason_code"] = "runtime_evidence_unavailable"

        measurement["cases"][0]["expected_complete"] = not measurement["cases"][0][
            "expected_complete"
        ]
        with self.assertRaises(BaselineMeasurementError):
            evaluate_baseline_measurement(self.suite, measurement)

    def test_replay_plan_exposes_only_company_cases_as_evaluation_replayable(self) -> None:
        plan = replay_plan(self.suite)

        self.assertEqual(plan["case_count"], 24)
        self.assertEqual(plan["replayable_case_count"], 11)
        self.assertEqual(plan["not_replayable_case_count"], 13)
        self.assertIs(plan["production_manifest_changed"], False)
        self.assertIs(plan["production_adapter_changed"], False)
        self.assertEqual(plan["purpose"], "evaluation_only")

        replayable = {
            item["case_id"]
            for item in plan["cases"]
            if item["replayable"]
        }
        self.assertEqual(
            replayable,
            {
                case["case_id"]
                for case in self.suite["cases"]
                if case["mode"] == "company_research"
            },
        )

        for item in plan["cases"]:
            if item["mode"] == "document_review":
                self.assertIn(
                    "document_review_input_contract_absent",
                    item["reason_codes"],
                )

    def test_replay_company_projection_preserves_all_source_units_without_truth(self) -> None:
        case = next(
            item
            for item in self.suite["cases"]
            if item["case_id"] == "company-medium-portfolio-002"
        )
        case_index = self.suite["cases"].index(case)

        record = build_replay_company_record(case, case_index=case_index)
        inputs = build_replay_inputs(case, case_index=case_index)

        self.assertEqual(record["evaluation_case_id"], case["case_id"])
        self.assertEqual(inputs["variables"]["memory_mode"], "preview")
        self.assertIs(inputs["variables"]["publish_dossier"], False)
        self.assertEqual(
            inputs["variables"]["company_ids"],
            [record["company_id"]],
        )
        self.assertEqual(inputs["companies"]["records"], [record])

        for index, unit in enumerate(case["source_units"], start=1):
            prefix = f"evaluation_source_{index:02d}"
            self.assertEqual(record[f"{prefix}_locator"], unit["locator"])
            self.assertEqual(record[f"{prefix}_text"], unit["text"])
            self.assertEqual(
                record[f"{prefix}_quality_flags"],
                unit["quality_flags"],
            )

        serialized = json.dumps(record, sort_keys=True)
        for finding in case["candidate_expected_findings"]:
            self.assertNotIn(finding["statement"], serialized)

    def test_replay_refuses_document_mode_and_large_projection_changes(self) -> None:
        document_case = next(
            item
            for item in self.suite["cases"]
            if item["mode"] == "document_review"
        )
        document_index = self.suite["cases"].index(document_case)
        with self.assertRaises(BaselineReplayError):
            build_replay_company_record(
                document_case,
                case_index=document_index,
            )

        oversized = next(
            item
            for item in self.suite["cases"]
            if item["case_id"] == "document-oversized-017"
        )
        oversized_index = self.suite["cases"].index(oversized)
        with self.assertRaises(BaselineReplayError):
            build_replay_company_record(
                oversized,
                case_index=oversized_index,
            )

    def test_source_digest_is_stable_and_depends_only_on_source_units(self) -> None:
        case = self.suite["cases"][0]
        digest = source_digest(case)

        self.assertRegex(digest, SHA256_RE)

        changed = json.loads(json.dumps(case))
        changed["title"] = "A changed display title must not alter source identity."
        self.assertEqual(source_digest(changed), digest)

        changed["source_units"][0]["text"] += " Changed source bytes."
        self.assertNotEqual(source_digest(changed), digest)

    def test_pending_domain_review_cannot_masquerade_as_adjudicated(self) -> None:
        suite = json.loads(json.dumps(self.suite))
        suite["status"] = "pending_domain_review"

        for case in suite["cases"]:
            case["adjudication"] = {
                "status": "pending_domain_review",
                "primary_reviewer": None,
                "secondary_reviewer": None,
                "disagreement": False,
            }
            case["source_identity"]["digest_status"] = "pending_fixture_freeze"
            case["source_identity"]["content_sha256"] = None

        self.assertEqual(suite["status"], "pending_domain_review")

        for case in suite["cases"]:
            with self.subTest(case_id=case["case_id"]):
                adjudication = case["adjudication"]
                self.assertEqual(adjudication["status"], "pending_domain_review")
                self.assertIsNone(adjudication["primary_reviewer"])
                self.assertIsNone(adjudication["secondary_reviewer"])
                self.assertIs(adjudication["disagreement"], False)

                source_identity = case["source_identity"]
                self.assertEqual(
                    source_identity["digest_status"],
                    "pending_fixture_freeze",
                )
                self.assertIsNone(source_identity["content_sha256"])

    def test_future_adjudicated_case_requires_frozen_digest_and_reviewers(self) -> None:
        for case in self.suite["cases"]:
            adjudication = case["adjudication"]
            if adjudication["status"] != "adjudicated":
                continue

            with self.subTest(case_id=case["case_id"]):
                self.assertTrue(str(adjudication["primary_reviewer"]).strip())
                if adjudication["disagreement"]:
                    self.assertTrue(str(adjudication["secondary_reviewer"]).strip())

                digest = case["source_identity"]["content_sha256"]
                self.assertIsInstance(digest, str)
                self.assertRegex(digest, SHA256_RE)
                self.assertEqual(case["source_identity"]["digest_status"], "frozen")

    def test_high_impact_cases_always_define_supported_evidence_or_abstention(self) -> None:
        for case in self.suite["cases"]:
            high_impact = any(
                finding["criticality"] == "high"
                for finding in case["candidate_expected_findings"]
            )
            if not high_impact and "high_impact_claim" not in case["strata"]:
                continue

            with self.subTest(case_id=case["case_id"]):
                supported = any(
                    finding["supporting_locators"]
                    for finding in case["candidate_expected_findings"]
                )
                self.assertTrue(supported or case["acceptable_abstention"])


if __name__ == "__main__":
    unittest.main()
