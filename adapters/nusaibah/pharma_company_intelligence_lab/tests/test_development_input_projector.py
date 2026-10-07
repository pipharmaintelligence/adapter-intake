from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

EVALUATION_ROOT = Path(__file__).resolve().parent / "evaluation"
sys.path.insert(0, str(EVALUATION_ROOT))
import project_development_inputs as projector

CASE_IDS = ["company-small-identity-001", "company-wrong-entity-005",
            "company-source-injection-006", "company-missing-evidence-007",
            "company-conflicting-dates-003"]


class PoisonTruth(dict):
    def __getitem__(self, key):
        raise AssertionError("Evaluation truth must never be accessed.")

    def get(self, key, default=None):
        raise AssertionError("Evaluation truth must never be accessed.")


class DevelopmentProjectorTests(unittest.TestCase):
    def test_scoped_candidate_uses_new_identity_and_method_without_changing_source_inputs(self):
        suite, suite_hash = projector.load_snapshot(projector.candidate.SUITE_PATH)
        old_bindings, old_hash = projector.load_snapshot(EVALUATION_ROOT / "development_input_bindings.v2.json")
        bindings, binding_hash = projector.load_snapshot(EVALUATION_ROOT / "development_input_bindings.v3.json")
        old_report, old_outputs = projector.project_batch(suite, old_bindings, CASE_IDS,
            suite_sha256=suite_hash, binding_sha256=old_hash, candidate_version="0.2.2")
        report, outputs = projector.project_batch(suite, bindings, CASE_IDS,
            suite_sha256=suite_hash, binding_sha256=binding_hash, candidate_version="0.2.3")
        self.assertEqual(old_outputs, outputs)
        self.assertEqual("nusaibah.pharma_company_intelligence_lab_evaluation:0.2.3", report["candidate_identity"])
        self.assertNotEqual(old_report["cases"][0]["plan"]["methodology_digest"], report["cases"][0]["plan"]["methodology_digest"])
        self.assertEqual([5, 5, 5, 5, 9], [c["plan"]["logical_call_limit"] for c in report["cases"]])
        self.assertEqual([1, 1, 1, 1, 2], [c["plan"]["child_call_limit"] for c in report["cases"]])
        self.assertFalse(report["execution_allowed"])
        self.assertEqual(0, report["provider_invocations"])
        self.assertFalse(report["wp1_complete"])
        with self.assertRaisesRegex(projector.ProjectionError, "candidate_identity_mismatch"):
            projector.project_batch(suite, old_bindings, CASE_IDS,
                suite_sha256=suite_hash, binding_sha256=old_hash, candidate_version="0.2.3")

    def test_scoped_candidate_cli_selects_its_own_bindings_and_preserves_historical_default(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = projector.main(["--case-id", CASE_IDS[0], "--candidate-version", "0.2.3"])
        report = json.loads(output.getvalue())
        self.assertEqual(0, code)
        self.assertEqual("prepared", report["status"])
        self.assertEqual(0, report["provider_invocations"])
        self.assertEqual("0.2.1", projector.candidate.CANDIDATE_ASSET_VERSION)

    def test_explicit_quote_candidate_uses_new_bindings_and_plan_without_changing_inputs(self):
        suite, suite_hash = projector.load_snapshot(projector.candidate.SUITE_PATH)
        bindings, binding_hash = projector.load_snapshot(EVALUATION_ROOT / "development_input_bindings.v2.json")
        report, outputs = projector.project_batch(suite, bindings, CASE_IDS,
            suite_sha256=suite_hash, binding_sha256=binding_hash, candidate_version="0.2.2")
        old_bindings, old_hash = projector.load_snapshot(projector.BINDINGS_PATH)
        old_report, old_outputs = projector.project_batch(suite, old_bindings, CASE_IDS,
            suite_sha256=suite_hash, binding_sha256=old_hash)
        self.assertEqual(old_outputs, outputs)
        self.assertEqual("nusaibah.pharma_company_intelligence_lab_evaluation:0.2.2",
                         report["candidate_identity"])
        self.assertEqual([1, 1, 1, 1, 2], [c["plan"]["child_call_limit"] for c in report["cases"]])
        self.assertTrue(all(c["plan"]["schema_version"] == "supplied_source_plan.v2" for c in report["cases"]))
        self.assertNotEqual(old_report["cases"][0]["plan"]["methodology_digest"],
                            report["cases"][0]["plan"]["methodology_digest"])
        self.assertFalse(report["execution_allowed"])
        with self.assertRaisesRegex(projector.ProjectionError, "candidate_identity_mismatch"):
            projector.project_batch(suite, bindings, CASE_IDS, suite_sha256=suite_hash,
                                    binding_sha256=binding_hash)

    def test_quote_candidate_cli_selects_version_specific_bindings_without_providers(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = projector.main(["--case-id", CASE_IDS[0], "--candidate-version", "0.2.2"])
        report = json.loads(output.getvalue())
        self.assertEqual(0, code)
        self.assertEqual("prepared", report["status"])
        self.assertEqual(0, report["provider_invocations"])
        self.assertFalse(report["wp1_complete"])

    def setUp(self):
        self.suite, self.suite_hash = projector.load_snapshot(projector.candidate.SUITE_PATH)
        self.bindings, self.binding_hash = projector.load_snapshot(projector.BINDINGS_PATH)

    def project(self, ids=None):
        return projector.project_batch(self.suite, self.bindings, ids or CASE_IDS,
                                        suite_sha256=self.suite_hash,
                                        binding_sha256=self.binding_hash)

    def case(self, case_id):
        return next(case for case in self.suite["cases"] if case["case_id"] == case_id)

    def refreeze_source(self, case_id):
        case = self.case(case_id)
        digest = hashlib.sha256(json.dumps(case["source_units"], ensure_ascii=False,
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        case["source_identity"]["content_sha256"] = digest
        next(b for b in self.bindings["bindings"] if b["case_id"] == case_id)["source_sha256"] = digest

    def cli(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = projector.main(args)
        return result, json.loads(output.getvalue())

    def test_real_finite_set_is_prepared_but_not_admitted_or_measured(self):
        report, outputs = self.project()
        self.assertEqual(report["status"], "prepared")
        self.assertEqual(report["expected_case_ids"], CASE_IDS)
        self.assertEqual(len(outputs), 5)
        self.assertEqual([c["chunk_count"] for c in report["cases"]], [1, 1, 1, 1, 2])
        self.assertEqual([c["excluded_entity_count"] for c in report["cases"]], [1, 1, 0, 0, 0])
        self.assertEqual([c["plan"]["logical_call_limit"] for c in report["cases"]], [5, 5, 5, 5, 9])
        for field in ("execution_allowed", "baseline_comparable", "wp1_complete", "wp2_unblocked"):
            self.assertIs(report[field], False)
        self.assertEqual(report["provider_invocations"], 0)

    def test_output_is_deterministic_and_hashes_exact_bytes(self):
        report, outputs = self.project()
        self.assertEqual((report, outputs), self.project())
        for receipt in report["cases"]:
            payload = outputs[receipt["inputs_file"]]
            self.assertEqual(receipt["inputs_sha256"], hashlib.sha256(payload).hexdigest())
            self.assertEqual(receipt["inputs_size_bytes"], len(payload))

    def test_truth_is_not_accessed_or_exported(self):
        expected = self.project()[1]
        for case_id in CASE_IDS:
            case = self.case(case_id)
            for field in ("candidate_expected_findings", "acceptable_abstention",
                          "candidate_expected_complete", "completion_expectation_reason",
                          "applicable_requirements", "strata", "title"):
                case[field] = PoisonTruth()
            case["adjudication"]["review_notes"] = "SECRET-REVIEW-NOTES"
        self.suite["quality_threshold_policy"] = PoisonTruth()
        report, outputs = self.project()
        self.assertEqual(outputs, expected)
        encoded = projector.encode(report) + b"".join(outputs.values())
        for value in (b"candidate_expected", b"criticality", b"acceptable_abstention",
                      b"SECRET-REVIEW-NOTES", b"primary_reviewer", b"review_notes"):
            self.assertNotIn(value, encoded)

    def test_source_text_and_locator_sets_preserved_with_wrong_entity_exclusion(self):
        _, outputs = self.project()
        for case_id in CASE_IDS:
            fixture = self.case(case_id)
            inputs = json.loads(outputs[f"{case_id}.inputs.json"])
            record = inputs["evaluation_case"]["records"][0]
            self.assertEqual(list(inputs), ["evaluation_case", "variables"])
            for original, projected in zip(fixture["source_units"], record["source_units"]):
                self.assertEqual(original["text"], projected["text"])
                self.assertEqual(original["locator"], projected["locator"])
                self.assertEqual(original.get("related_locators", []), projected["related_locators"])
                self.assertNotIn("quality_flags", projected)
                if set(original["quality_flags"]) & projector.candidate.WRONG_ENTITY_FLAGS:
                    self.assertNotEqual(record["entity_id"], projected["entity_id"])
            projector.candidate.validate_inputs_against_fixture(fixture, inputs)

    def test_preserves_inaccessible_sources_and_related_context(self):
        case = self.case(CASE_IDS[0])
        case["source_units"].insert(1, {"locator": "company:2", "text": "Qualifier.",
            "quality_flags": [], "related_locators": ["company:1"]})
        case["source_units"].append({"locator": "company:3", "text": "",
                                   "quality_flags": ["inaccessible"]})
        self.refreeze_source(CASE_IDS[0])
        report, outputs = self.project([CASE_IDS[0]])
        self.assertEqual(report["cases"][0]["chunk_count"], 2)
        self.assertEqual(report["cases"][0]["inaccessible_count"], 1)
        units = json.loads(next(iter(outputs.values())))["evaluation_case"]["records"][0]["source_units"]
        self.assertEqual(units[1]["related_locators"], ["company:1"])
        self.assertIs(units[-1]["accessible"], False)
        self.assertEqual(units[-1]["text"], "")

    def test_held_out_rejected_before_source_or_adjudication_access(self):
        case = self.case(CASE_IDS[0])
        case["split"] = "held_out"
        case["source_units"] = PoisonTruth()
        case["adjudication"] = PoisonTruth()
        with self.assertRaisesRegex(projector.ProjectionError, "development_only"):
            self.project([CASE_IDS[0]])

    def test_unknown_and_duplicate_case_ids_rejected(self):
        for ids, reason in ((["unknown-case"], "fixture_identity_invalid"),
                            ([CASE_IDS[0], CASE_IDS[0]], "duplicate_case")):
            with self.subTest(ids=ids), self.assertRaisesRegex(projector.ProjectionError, reason):
                self.project(ids)

    def test_batch_limit_and_path_identity_rejected(self):
        for ids, reason in ((["case"] * 17, "case_count_invalid"),
                            (["../unsafe"], "case_identity_invalid")):
            with self.subTest(ids=ids), self.assertRaisesRegex(projector.ProjectionError, reason):
                self.project(ids)

    def test_unbound_development_case_rejected(self):
        self.bindings["bindings"] = self.bindings["bindings"][1:]
        with self.assertRaisesRegex(projector.ProjectionError, "case_binding_missing"):
            self.project()

    def test_suite_binding_and_source_drift_rejected(self):
        variants = [("suite_hash", "suite_digest_mismatch"),
                    ("source_text", "fixture_validation_rejected"),
                    ("binding_source", "binding_source_digest_mismatch"),
                    ("candidate", "candidate_identity_mismatch")]
        for variant, reason in variants:
            with self.subTest(variant=variant):
                self.setUp()
                if variant == "suite_hash": self.suite_hash = "a" * 64
                if variant == "source_text": self.case(CASE_IDS[0])["source_units"][0]["text"] += " changed"
                if variant == "binding_source": self.bindings["bindings"][0]["source_sha256"] = "a" * 64
                if variant == "candidate": self.bindings["candidate_identity"] += "-other"
                with self.assertRaisesRegex(projector.ProjectionError, reason): self.project()

    def test_binding_cannot_inject_truth_or_approval(self):
        for mutate in (lambda b: b.update({"expected_findings": []}),
                       lambda b: b["bindings"][0].update({"criticality": "high"}),
                       lambda b: b.update({"decision_status": "approved"})):
            with self.subTest(mutate=mutate):
                self.setUp()
                mutate(self.bindings)
                with self.assertRaises(projector.ProjectionError): self.project()

    def test_non_synthetic_source_rejected(self):
        self.case(CASE_IDS[0])["source_identity"]["source_id"] = "real:company"
        with self.assertRaisesRegex(projector.ProjectionError, "synthetic_source_identity_required"):
            self.project()

    def test_non_executable_case_kept_in_batch_and_no_partial_export(self):
        self.case(CASE_IDS[0])["mode"] = "document_review"
        report, outputs = self.project()
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(len(report["cases"]), 5)
        self.assertEqual(report["ready_case_count"], 4)
        self.assertEqual(report["cases"][0]["projection_status"], "not_executable")
        self.assertEqual(outputs, {})

    def test_context_and_chunk_overflow_block_instead_of_truncating(self):
        case = self.case(CASE_IDS[0])
        case["source_units"] = [{"locator": f"source:{i}", "text": "Evidence.",
                                "quality_flags": []} for i in range(5)]
        self.refreeze_source(CASE_IDS[0])
        report, outputs = self.project()
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["cases"][0]["reason_codes"], ["candidate_input_preflight_rejected"])
        self.assertFalse(outputs)

    def test_cli_preflight_writes_nothing_and_stdout_contains_no_source_values(self):
        code, report = self.cli(["--case-id", CASE_IDS[0]])
        self.assertEqual(code, 0)
        self.assertIs(report["inputs_exported"], False)
        self.assertNotIn("Ficta", json.dumps(report))
        self.assertNotIn("headquarters", json.dumps(report))

    def test_export_manifest_and_files_match_and_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "batch"
            args = ["--case-id", CASE_IDS[0], "--output-dir", str(destination)]
            code, report = self.cli(args)
            self.assertEqual(code, 0)
            manifest = json.loads((destination / "projection-manifest.json").read_bytes())
            self.assertEqual(report, manifest)
            original = (destination / f"{CASE_IDS[0]}.inputs.json").read_bytes()
            code, report = self.cli(args)
            self.assertEqual(code, 2)
            self.assertEqual(report["reason_code"], "output_already_exists")
            self.assertEqual(original, (destination / f"{CASE_IDS[0]}.inputs.json").read_bytes())

    def test_export_inside_repository_blocked(self):
        report, outputs = self.project()
        with self.assertRaisesRegex(projector.ProjectionError, "output_inside_source_checkout"):
            projector.export_batch(EVALUATION_ROOT / "generated-inputs", report, outputs)

    def test_blocked_batch_creates_no_directory(self):
        self.case(CASE_IDS[0])["mode"] = "document_review"
        with tempfile.TemporaryDirectory() as root:
            suite_path = Path(root) / "suite.json"
            binding_path = Path(root) / "bindings.json"
            suite_path.write_bytes(projector.encode(self.suite))
            self.bindings["suite_byte_sha256"] = [projector.sha256(suite_path.read_bytes())]
            binding_path.write_bytes(projector.encode(self.bindings))
            destination = Path(root) / "batch"
            code, report = self.cli(["--suite", str(suite_path), "--bindings", str(binding_path),
                                    "--case-id", CASE_IDS[0], "--output-dir", str(destination)])
            self.assertEqual(code, 2)
            self.assertEqual(report["status"], "blocked")
            self.assertFalse(destination.exists())

    def test_malformed_json_and_io_errors_do_not_echo_values(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "private-name.json"
            path.write_text('{"private-secret-value":', encoding="utf-8")
            for suite_path in (path, Path(root) / "secret-missing-file.json"):
                code, report = self.cli(["--case-id", CASE_IDS[0], "--suite", str(suite_path)])
                self.assertEqual(code, 2)
                self.assertNotIn("secret", json.dumps(report))

    def test_strict_bounded_json_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "input.json"
            for payload in (b'{"a":1,"a":2}', b'{"a":NaN}', b"x" * (projector.MAX_FILE_BYTES + 1)):
                path.write_bytes(payload)
                with self.subTest(payload=payload[:20]), self.assertRaises(projector.ProjectionError):
                    projector.load_snapshot(path)
            payload = b'\xef\xbb\xbf{"x":"unchanged"}\r\n'
            path.write_bytes(payload)
            value, digest = projector.load_snapshot(path)
            self.assertEqual(value, {"x": "unchanged"})
            self.assertEqual(digest, hashlib.sha256(payload).hexdigest())

    def test_reviewed_lf_and_crlf_byte_variants_produce_identical_inputs(self):
        payload = projector.candidate.SUITE_PATH.read_bytes().replace(b"\r\n", b"\n")
        expected = self.project()[1]
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "suite.json"
            for raw in (payload, payload.replace(b"\n", b"\r\n")):
                path.write_bytes(raw)
                suite, digest = projector.load_snapshot(path)
                report, outputs = projector.project_batch(suite, self.bindings, CASE_IDS,
                    suite_sha256=digest, binding_sha256=self.binding_hash)
                self.assertEqual(outputs, expected)
                self.assertEqual(report["suite_sha256"], hashlib.sha256(raw).hexdigest())

    def test_file_loaded_once_and_no_provider_helper_is_used(self):
        opened = []
        original_open = Path.open

        def record_open(path, *args, **kwargs):
            opened.append(path)
            return original_open(path, *args, **kwargs)

        with mock.patch.object(projector.candidate.SOURCE_REVIEW, "run_review",
                               side_effect=AssertionError("No runtime execution")), \
             mock.patch.object(Path, "open", new=record_open):
            code, _ = self.cli(["--case-id", CASE_IDS[0]])
            self.assertEqual(code, 0)
        self.assertEqual(opened, [projector.candidate.SUITE_PATH, projector.BINDINGS_PATH])


if __name__ == "__main__":
    unittest.main()
