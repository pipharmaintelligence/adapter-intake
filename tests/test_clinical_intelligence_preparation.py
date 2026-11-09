"""Adversarial pure fixtures for the proposed clinical preparation contracts."""
import importlib.util
import copy
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("clinical_preparation_check", ROOT / "tools/check_clinical_preparation.py")
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


def fixture(name):
    return json.loads((CHECK.DESIGN / "examples" / (name + ".json")).read_text(encoding="utf-8"))


class ClinicalPreparationContractTests(unittest.TestCase):
    def rejected(self, kind, value, code=None):
        with self.assertRaises(CHECK.DraftContractError) as caught:
            CHECK.validate(kind, value)
        if code:
            self.assertEqual(str(caught.exception), code)

    def test_all_draft_schemas_are_valid_and_references_are_offline(self):
        self.assertEqual(7, len(CHECK.SCHEMAS))
        for schema in CHECK.SCHEMAS.values():
            CHECK.Draft202012Validator.check_schema(schema)
            self.assertTrue(schema["$id"].startswith("urn:dms-ai:clinical-preparation:"))

    def test_all_synthetic_examples_validate(self):
        cases = {
            "complete-snapshot.scope": "class-scope", "selected-subset.scope": "class-scope",
            "class-review.request": "gateway-request", "retained-assessment.handoff": "assessment-handoff",
            "existing-review.request": "gateway-request", "neutral-assessment.request": "gateway-request",
            "status.request": "gateway-request", "readback.request": "gateway-request", "blocked.gateway-response": "gateway-response",
            "complete-snapshot.review": "class-review", "incomplete-subset.review": "class-review",
            "accepted.gateway-response": "gateway-response", "partial.gateway-response": "gateway-response",
            "oversized-snapshot.gateway-response": "gateway-response",
            "describe-capabilities.request": "gateway-request", "read-guidance.request": "gateway-request",
            "capabilities.guidance-response": "gateway-response", "unavailable.guidance-response": "gateway-response",
        }
        for name, kind in cases.items():
            with self.subTest(name=name):
                CHECK.validate(kind, fixture(name))

    def test_complete_execution_does_not_require_complete_science(self):
        report = fixture("complete-snapshot.review")
        self.assertTrue(report["coverage"]["execution_complete"])
        self.assertFalse(report["coverage"]["evidence_complete"])
        self.assertFalse(report["coverage"]["scientific_review_complete"])
        self.assertEqual(3, report["coverage"]["missing_product_count"])
        CHECK.validate("class-review", report)

    def test_missing_identity_can_remain_for_governed_resolution(self):
        request = fixture("class-review.request")
        for key in ("supplied_identity_context", "molecule_ids", "pharmacological_class_ids", "scope_mode"):
            request.pop(key)
        request["scope_mode"] = "all_known_in_snapshot"
        CHECK.validate("gateway-request", request)

    def test_selected_molecules_cases_and_products_are_supported(self):
        for field, values in (("molecule_ids", ["SYNTH_MOLECULE_A"]), ("molecule_names", ["Synthetic molecule A"]),
                              ("product_ids", ["SYNTH_PRODUCT_A"]),
                              ("selected_cases", fixture("selected-subset.scope")["selected_cases"][:1])):
            request = fixture("class-review.request")
            request.pop("molecule_ids")
            request[field] = values
            CHECK.validate("gateway-request", request)

    def test_subset_requires_explicit_selection(self):
        request = fixture("class-review.request")
        request.pop("molecule_ids")
        self.rejected("gateway-request", request)

    def test_public_authority_and_payload_fields_are_rejected(self):
        for field in ("source_ref", "complete", "binding_id", "lake_id", "node_id", "client_id", "actor_id",
                      "approved", "provider", "model", "raw_assessment", "ruleset", "output_destination"):
            with self.subTest(field=field):
                request = fixture("class-review.request")
                request[field] = "SYNTH_FORBIDDEN"
                self.rejected("gateway-request", request)

    def test_supplied_mapping_does_not_cross_class_boundary(self):
        request = fixture("class-review.request")
        request["supplied_identity_context"][0]["pharmacological_class_id"] = "SYNTH_CLASS_Y"
        self.rejected("gateway-request", request, "supplied_context_cross_class")

    def test_cross_class_frozen_member_rejected(self):
        scope = fixture("complete-snapshot.scope")
        scope["membership"]["eligible_products"][0]["pharmacological_class_id"] = "SYNTH_CLASS_Y"
        self.rejected("class-scope", scope, "cross_class_membership")

    def test_molecule_mismatch_cannot_be_hidden_by_matching_product(self):
        scope = fixture("selected-subset.scope")
        scope["selected_products"][0]["molecule_id"] = "SYNTH_OTHER_MOLECULE"
        self.rejected("class-scope", scope, "selected_member_identity_mismatch")

    def test_incomplete_membership_can_be_reported_but_not_claimed_complete(self):
        scope = fixture("selected-subset.scope")
        scope["membership"]["unresolved"] = [{"semantic_ref": "SYNTH_UNKNOWN", "reason_code": "ambiguous_identity"}]
        self.rejected("class-scope", scope, "complete_membership_has_unresolved_identity")
        scope["membership"]["complete"] = False
        CHECK.validate("class-scope", scope)

    def test_all_known_cannot_omit_an_eligible_member(self):
        scope = fixture("complete-snapshot.scope")
        scope["selected_products"].pop()
        self.rejected("class-scope", scope, "all_known_selection_incomplete")

    def test_no_silent_legacy_group_alias(self):
        scope = fixture("selected-subset.scope")
        scope["legacy_class_mapping"] = {"pharmacological_class_id": "SYNTH_CLASS_Y",
                                          "pharmacological_group_id": "SYNTH_GROUP", "source_ref": "SYNTH_CROSSWALK"}
        self.rejected("class-scope", scope, "legacy_mapping_class_mismatch")

    def test_duplicate_semantic_ids_rejected_even_when_rows_differ(self):
        scope = fixture("selected-subset.scope")
        scope["selected_products"][1]["product_id"] = scope["selected_products"][0]["product_id"]
        self.rejected("class-scope", scope, "duplicate_semantic_identity")

    def test_retained_handoff_preserves_required_lineage(self):
        for field in ("producer", "retained_result", "reason_graph_ref", "methodology", "evidence_sources", "model_revision"):
            handoff = fixture("retained-assessment.handoff")
            handoff.pop(field)
            with self.subTest(field=field):
                self.rejected("assessment-handoff", handoff)

    def test_bad_digest_and_wrong_case_rejected(self):
        handoff = fixture("retained-assessment.handoff")
        handoff["retained_result"]["content_digest"] = "sha256:unverified"
        self.rejected("assessment-handoff", handoff)
        handoff = fixture("retained-assessment.handoff")
        handoff["case"]["product_id"] = "SYNTH_PRODUCT_OTHER"
        self.rejected("assessment-handoff", handoff, "assessment_case_identity_mismatch")

    def test_partial_assessment_is_not_relabeled_accepted(self):
        handoff = fixture("retained-assessment.handoff")
        handoff["quality"] = "accepted"
        self.rejected("assessment-handoff", handoff)

    def test_producer_quality_crosswalk_preserves_original_status(self):
        for source_status, normalized in (("completed", "accepted"), ("partial", "partial"),
                                           ("preflight", "deferred"), ("deferred", "deferred"), ("future_status", "unknown")):
            with self.subTest(source_status=source_status):
                handoff = fixture("retained-assessment.handoff")
                handoff["producer_quality"]["status"] = source_status
                handoff["quality"] = normalized
                before = copy.deepcopy(handoff)
                CHECK.validate("assessment-handoff", handoff)
                self.assertEqual(handoff, before)
                self.assertFalse(handoff["producer_quality"]["scientific_accuracy_certified"])

    def test_accepted_handoff_can_preserve_unresolved_scientific_questions(self):
        handoff = fixture("retained-assessment.handoff")
        handoff["producer_quality"]["status"] = "completed"
        handoff["quality"] = "accepted"
        CHECK.validate("assessment-handoff", handoff)
        self.assertTrue(handoff["unresolved_reason_codes"])
        self.assertFalse(handoff["producer_quality"]["external_truth_verified"])

    def test_source_scientific_flags_cannot_be_upgraded(self):
        for field, value in (("scientific_accuracy_certified", True), ("external_truth_verified", True),
                             ("automated_review_only", False)):
            handoff = fixture("retained-assessment.handoff")
            handoff["producer_quality"][field] = value
            self.rejected("assessment-handoff", handoff)

    def test_verification_failure_unknown_and_staleness_preserve_distinct_states(self):
        for field, value, expected in (("retained_integrity", "failed", "blocked"),
                                       ("retained_integrity", "unavailable", "blocked"),
                                       ("retained_integrity", "unverified", "unknown"),
                                       ("identity", "conflict", "blocked"), ("identity", "unresolved", "unknown"),
                                       ("structure", "invalid", "blocked"), ("structure", "unverified", "unknown"),
                                       ("freshness", "outdated", "outdated"), ("freshness", "unknown", "unknown")):
            with self.subTest(field=field, value=value):
                handoff = fixture("retained-assessment.handoff")
                handoff["producer_quality"]["status"] = "completed"
                handoff["verification"][field] = value
                handoff["quality"] = expected
                CHECK.validate("assessment-handoff", handoff)
                handoff["quality"] = "accepted"
                self.rejected("assessment-handoff", handoff)

    def test_unknown_source_cannot_be_reclassified_as_completed(self):
        handoff = fixture("retained-assessment.handoff")
        handoff["producer_quality"]["status"] = "future_status"
        handoff["quality"] = "partial"
        self.rejected("assessment-handoff", handoff, "handoff_quality_crosswalk_mismatch")

    def bounded_scope(self):
        scope = fixture("complete-snapshot.scope")
        rows = [{"product_id": "SYNTH_PRODUCT_" + str(i), "molecule_id": "SYNTH_MOLECULE_" + str(i),
                 "pharmacological_class_id": "SYNTH_CLASS_X"} for i in range(128)]
        scope["membership"]["eligible_products"] = copy.deepcopy(rows)
        scope["selected_products"] = rows
        scope["selected_cases"] = [{"case_ref": "SYNTH_CASE_" + str(i), "product_id": row["product_id"],
            "indication_ref": "SYNTH_INDICATION", "trial_refs": ["SYNTH_TRIAL_" + str(i)]} for i, row in enumerate(rows)]
        for key in ("eligible_product_count", "selected_product_count", "selected_case_count"):
            scope["extent"][key] = 128
        return scope

    def test_exact_128_member_and_case_boundary_is_representable(self):
        CHECK.validate("class-scope", self.bounded_scope())

    def test_each_129_item_array_exceeds_the_draft_contract(self):
        for path in (("membership", "eligible_products"), ("selected_products",), ("selected_cases",)):
            scope = self.bounded_scope()
            rows = scope
            for key in path:
                rows = rows[key]
            rows.append(copy.deepcopy(rows[-1]))
            self.rejected("class-scope", scope)
            validator = CHECK.Draft202012Validator(CHECK.SCHEMAS["class-scope"], registry=CHECK.REGISTRY)
            self.assertTrue(any(error.validator == "maxItems" and tuple(error.absolute_path) == path
                                for error in validator.iter_errors(scope)))

    def test_truncated_128_item_prefix_cannot_hide_129_known_entities(self):
        for field in ("eligible_product_count", "selected_product_count", "selected_case_count"):
            scope = self.bounded_scope()
            scope["extent"][field] = 129
            self.rejected("class-scope", scope)

    def test_truncation_and_unqualified_pagination_flags_rejected(self):
        for field in ("truncated", "pagination_applied"):
            scope = self.bounded_scope()
            scope["extent"][field] = True
            self.rejected("class-scope", scope)

    def test_unknown_extent_cannot_be_complete_inventory(self):
        for field in ("eligible_product_count", "selected_case_count"):
            scope = fixture("complete-snapshot.scope")
            scope["extent"][field] = None
            self.rejected("class-scope", scope, "complete_scope_extent_unknown")
        scope["case_inventory_complete"] = False
        CHECK.validate("class-scope", scope)

    def test_overflow_response_is_blocked_before_launch(self):
        response = fixture("oversized-snapshot.gateway-response")
        CHECK.validate("gateway-response", response)
        for field, value in (("status", "completed"), ("run_ref", "SYNTH_RUN"), ("next_action", "poll")):
            mutated = copy.deepcopy(response)
            mutated[field] = value
            self.rejected("gateway-response", mutated)

    def test_overflow_response_requires_observed_overflow(self):
        response = fixture("oversized-snapshot.gateway-response")
        response["scope_limit"]["observed_eligible_product_count"] = 128
        response["scope_limit"]["observed_selected_product_count"] = 128
        self.rejected("gateway-response", response, "scope_limit_overflow_not_observed")

    def test_deferred_and_unknown_coverage_counts_are_not_accepted_counts(self):
        for state, product_field in (("deferred", "deferred_product_count"), ("unknown", "unknown_product_count")):
            coverage = fixture("complete-snapshot.review")["coverage"]
            coverage["product_dispositions"][2]["state"] = state
            coverage["product_with_partial_assessment_count"] = 0
            coverage[product_field] = 1
            coverage["case_dispositions"][2]["state"] = state
            coverage["partial_case_count"] = 0
            coverage[state + "_case_count"] = 1
            CHECK.validate("coverage", coverage)
            self.assertEqual(2, coverage["product_with_accepted_assessment_count"])

    def test_subset_generalization_is_rejected(self):
        report = fixture("incomplete-subset.review")
        report["coverage"]["class_generalization_supported"] = True
        self.rejected("class-review", report)

    def test_denominator_and_disposition_drift_rejected(self):
        report = fixture("complete-snapshot.review")
        report["coverage"]["product_with_accepted_assessment_count"] += 1
        self.rejected("class-review", report, "product_denominator_mismatch")
        report = fixture("complete-snapshot.review")
        report["coverage"]["product_dispositions"][0]["product_id"] = "SYNTH_PRODUCT_OTHER"
        self.rejected("class-review", report, "product_coverage_scope_mismatch")

    def test_unknown_denominator_cannot_support_complete_membership(self):
        report = fixture("complete-snapshot.review")
        report["coverage"]["inventory_member_count"] = None
        self.rejected("class-review", report, "complete_membership_denominator_unknown")

    def test_case_missing_from_join_rejected(self):
        report = fixture("complete-snapshot.review")
        report["coverage"]["case_dispositions"][0]["case_ref"] = "SYNTH_OTHER_CASE"
        self.rejected("class-review", report, "case_coverage_scope_mismatch")

    def test_accepted_product_cannot_hide_partial_case(self):
        report = fixture("complete-snapshot.review")
        report["coverage"]["case_dispositions"][0]["state"] = "partial"
        report["coverage"]["completed_case_count"] -= 1
        report["coverage"]["partial_case_count"] += 1
        self.rejected("class-review", report, "accepted_product_has_incomplete_cases")

    def test_incomplete_source_and_science_flags_rejected(self):
        for key in ("evidence_complete", "scientific_review_complete"):
            report = fixture("complete-snapshot.review")
            report["coverage"][key] = True
            self.rejected("class-review", report)

    def test_missing_critic_and_comparability_block_generalization(self):
        report = fixture("complete-snapshot.review")
        report["coverage"]["class_generalization_supported"] = True
        self.rejected("class-review", report)

    def eligible_review(self):
        """Structurally eligible synthetic case; never proves scientific truth."""
        report = fixture("complete-snapshot.review")
        coverage = report["coverage"]
        for field in CHECK.COMPLETENESS:
            coverage[field] = True
        coverage["class_generalization_supported"] = True
        for field in CHECK.PRODUCT_COUNTS.values():
            coverage[field] = 0
        coverage["product_with_accepted_assessment_count"] = 6
        for state in ("partial", "deferred", "missing", "blocked", "outdated"):
            coverage[state + "_case_count"] = 0
        coverage["completed_case_count"] = 6
        for row in coverage["product_dispositions"]:
            row["state"] = "accepted"
        for row in coverage["case_dispositions"]:
            row["state"] = "completed"
        for row in coverage["evidence_coverage_by_source"]:
            row["complete"] = True
        report["comparability"] = "established"
        report["independent_critic"] = {"status": "passed", "review_ref": "SYNTH_CRITIC", "unresolved_finding_refs": []}
        report["assessment_refs"] = [{"assessment_ref": "SYNTH_ASSESSMENT_" + str(index), "handoff_ref": "SYNTH_HANDOFF_" + str(index),
            "product_id": case["product_id"], "case_ref": case["case_ref"], "content_digest": "sha256:" + "e" * 64,
            "quality": "accepted"} for index, case in enumerate(report["class_scope"]["selected_cases"])]
        report["findings"] = [{"finding_ref": "SYNTH_FINDING", "scope": "class", "interpretation": "supported",
            "product_ids": ["SYNTH_PRODUCT_A"], "evidence_refs": ["SYNTH_EVIDENCE"],
            "reason_graph_refs": ["SYNTH_GRAPH"], "summary": "Synthetic structural acceptance example only."}]
        report["strata"] = [{"stratum_ref": "SYNTH_STRATUM", "product_ids": ["SYNTH_PRODUCT_A"],
            "indication_ref": "SYNTH_INDICATION", "trial_refs": ["SYNTH_TRIAL_A"], "regimen_ref": "SYNTH_REGIMEN",
            "comparator_ref": "SYNTH_COMPARATOR", "endpoint_ref": "SYNTH_ENDPOINT", "population_ref": "SYNTH_POPULATION",
            "phase_ref": "SYNTH_PHASE", "mechanism_ref": "SYNTH_MECHANISM", "evidence_as_of_date": "2026-11-08"}]
        return report

    def test_structurally_eligible_generalization_is_representable(self):
        CHECK.validate("class-review", self.eligible_review())

    def test_each_completeness_dimension_independently_blocks_generalization(self):
        for field in CHECK.COMPLETENESS:
            for value in (False, None):
                with self.subTest(field=field, value=value):
                    report = self.eligible_review()
                    report["coverage"][field] = value
                    self.rejected("class-review", report)

    def test_critic_case_inventory_and_comparability_independently_gate_generalization(self):
        for key, value in (("status", "pending"), ("status", "challenged"),
                           ("review_ref", None), ("unresolved_finding_refs", ["SYNTH_UNRESOLVED"])):
            report = self.eligible_review()
            report["independent_critic"][key] = value
            self.rejected("class-review", report)
        report = self.eligible_review()
        report["comparability"] = "heterogeneous"
        self.rejected("class-review", report)
        report = self.eligible_review()
        report["class_scope"]["case_inventory_complete"] = False
        self.rejected("class-review", report)

    def test_fully_reviewed_subset_still_cannot_generalize(self):
        report = self.eligible_review()
        report["class_scope"]["scope_mode"] = "selected_subset"
        self.rejected("class-review", report)

    def test_completed_case_requires_matching_accepted_retained_reference(self):
        report = fixture("complete-snapshot.review")
        report["assessment_refs"] = []
        self.rejected("class-review", report, "completed_case_retained_assessment_missing")
        report = fixture("complete-snapshot.review")
        report["assessment_refs"][0]["product_id"] = "SYNTH_PRODUCT_OTHER"
        self.rejected("class-review", report, "assessment_reference_outside_case_scope")

    def test_supported_class_finding_cannot_bypass_generalization_gate(self):
        report = fixture("incomplete-subset.review")
        report["findings"] = [{"finding_ref": "SYNTH_FINDING", "scope": "class", "interpretation": "supported",
            "product_ids": ["SYNTH_PRODUCT_A"], "evidence_refs": ["SYNTH_EVIDENCE"],
            "reason_graph_refs": ["SYNTH_GRAPH"], "summary": "Synthetic adversarial claim."}]
        self.rejected("class-review", report, "unsupported_class_finding")

    def test_skill_apply_and_write_flags_rejected(self):
        for flag in ("apply_authorized", "write_attempted"):
            report = fixture("incomplete-subset.review")
            report["skill_improvement"][flag] = True
            self.rejected("class-review", report)

    def test_public_status_and_readback_use_only_run_ref(self):
        for operation in ("get_status", "get_result"):
            request = {"schema_version": "clinical_gateway_request.draft.v1", "operation": operation, "run_ref": "SYNTH_RUN"}
            CHECK.validate("gateway-request", request)
            request["actor_id"] = "SYNTH_ACTOR"
            self.rejected("gateway-request", request)

    def test_accepted_response_preserves_run_identity_without_result(self):
        response = fixture("accepted.gateway-response")
        response["run_ref"] = None
        self.rejected("gateway-response", response)

    def test_accepted_run_has_clear_poll_action(self):
        response = fixture("accepted.gateway-response")
        response["next_action"] = "none"
        self.rejected("gateway-response", response)
        response = fixture("accepted.gateway-response")
        response["reports"] = [{"report_ref": "SYNTH_REPORT", "report_version": "0.0.1"}]
        self.rejected("gateway-response", response)

    def test_completed_transport_can_still_report_partial_science(self):
        response = fixture("partial.gateway-response")
        response["status"] = "completed"
        CHECK.validate("gateway-response", response)
        self.assertFalse(response["coverage"]["scientific_review_complete"])

    def test_public_projection_rejects_internal_authority_and_raw_payloads(self):
        for field in ("producer_run", "retained_result", "raw_assessment", "binding_id", "storage_path", "credential"):
            response = fixture("partial.gateway-response")
            response[field] = "SYNTH_FORBIDDEN"
            self.rejected("gateway-response", response)

    def test_subset_public_response_cannot_claim_class_generalization(self):
        response = fixture("partial.gateway-response")
        response["coverage"]["class_generalization_supported"] = True
        self.rejected("gateway-response", response)

    def test_invalid_date_rejected(self):
        request = fixture("class-review.request")
        request["as_of_date"] = "2026-99-99"
        self.rejected("gateway-request", request)


if __name__ == "__main__":
    unittest.main()
