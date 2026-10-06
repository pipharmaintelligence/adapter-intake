from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import test_supplied_source_review as old

ROOT = Path(__file__).resolve().parents[1]


def load(folder, filename, package_name):
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(folder)]
        sys.modules[package_name] = package
    name = package_name + "." + Path(filename).stem
    spec = importlib.util.spec_from_file_location(name, folder / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


review = load(ROOT, "supplied_source_quote_review.py", "_quote_review_tests")
tool = load(ROOT.parent / "structured_review_toolkit", "tool_operations_v0_1_1.py", "_quote_tool_tests")


class FakeInputs(old.FakeInputs):
    """Structural protocol double, not a factual-quality reviewer."""
    def __init__(self, initial=None, *, findings=True, transform=None, tool_transform=None):
        super().__init__(initial, findings=findings)
        self.transform_hook = transform
        self.tool_transform = tool_transform
        self.child_calls = []
        self.events = []

    def invoke_agent(self, role, *, input, on_error):
        response = super().invoke_agent(role, input=input, on_error=on_error)
        value = response["result"]["content"][0]["value"]
        if role != review.VERIFIER_ROLE:
            for req in value["requirements"]:
                for finding in req["findings"]:
                    for ref in finding["evidence"]:
                        ref.pop("start")
                        ref.pop("end")
        if self.transform_hook:
            value = self.transform_hook(role, input, value)
        with self.lock:
            self.events.append(input["task_stage"])
        return old.envelope(value)

    def invoke_asset(self, role, *, variables, on_error):
        assert role == review.TOOL_ROLE and on_error == "raise"
        self.child_calls.append(copy.deepcopy(variables))
        self.events.append("span_resolution")
        result = tool.execute_operation(variables)
        if self.tool_transform:
            result = self.tool_transform(variables, result)
        return {"status": "success", "result": result}


class QuoteReviewTests(unittest.TestCase):
    def test_specialists_select_quotes_then_one_child_resolves_before_verifiers(self):
        inputs = FakeInputs()
        result = review.run_review(inputs)
        self.assertEqual("supplied_source_review_result.v2", result["schema_version"])
        self.assertEqual(5, result["agent_call_count"])
        self.assertEqual(1, result["child_call_count"])
        self.assertEqual("review_complete", result["review_outcome"])
        self.assertEqual(["specialist_review"] * 3 + [
            "span_resolution", "chunk_evidence_verification", "global_consistency"], inputs.events)
        for _, packet in inputs.calls[:3]:
            self.assertEqual(["locator", "quote"], packet["response_contract"]["evidence_fields"])
            self.assertEqual("supplied_source_specialist.v2", packet["response_contract"]["schema_version"])
        review.validate_resolution_receipts(result, review.prepare_review(inputs))
        self.assertNotIn("Other Company", json.dumps(inputs.calls + inputs.child_calls))
        self.assertFalse(result["external_truth_verified"])

    def test_no_findings_still_has_one_empty_bounded_child_call_and_truthful_gaps(self):
        inputs = FakeInputs(findings=False)
        result = review.run_review(inputs)
        self.assertEqual("review_complete_with_evidence_gaps", result["review_outcome"])
        self.assertEqual((4, 1), (result["agent_call_count"], result["child_call_count"]))
        self.assertEqual([], inputs.child_calls[0]["arguments"]["requests"])
        review.validate_resolution_receipts(result, review.prepare_review(inputs))

    def test_nonzero_unicode_crlf_offsets_come_from_child_not_specialists(self):
        inputs = FakeInputs(transform=lambda role, packet, value: self.select_quote(
            role, value, "Ficta Therapeutics"))
        inputs["evaluation_case"]["records"][0]["source_units"][0]["text"] = "Before 😀\r\nFicta Therapeutics."
        result = review.run_review(inputs)
        for finding in result["accepted_findings"]:
            ref = finding["evidence"][0]
            self.assertEqual((10, 28), (ref["start"], ref["end"]))
        review.validate_resolution_receipts(result, review.prepare_review(inputs))

    @staticmethod
    def select_quote(role, value, quote):
        if role != review.VERIFIER_ROLE:
            for req in value["requirements"]:
                for finding in req["findings"]:
                    finding["evidence"][0]["quote"] = quote
        return value

    def test_missing_or_ambiguous_quote_blocks_before_semantic_verifier_without_retry(self):
        for text, quote, rule in (("abc", "missing", "quote_missing"), ("aaa", "aa", "quote_ambiguous")):
            inputs = FakeInputs(transform=lambda role, packet, value: self.select_quote(role, value, quote))
            inputs["evaluation_case"]["records"][0]["source_units"][0]["text"] = text
            with self.subTest(rule=rule), self.assertRaises(review.SourceReviewError) as caught:
                review.run_review(inputs)
            self.assertEqual("evidence_" + rule, caught.exception.proof_failure_detail["rule"])
            self.assertEqual("source_portfolio_reviewer", caught.exception.proof_failure_detail["role"])
            self.assertEqual(3, len(inputs.calls))
            self.assertEqual(1, len(inputs.child_calls))

    def test_old_specialist_version_or_model_offsets_rejected_before_child(self):
        for variant in ("schema", "offset"):
            def alter(role, packet, value):
                if role == "source_commercial_reviewer":
                    if variant == "schema":
                        value["schema_version"] = "supplied_source_specialist.v1"
                    else:
                        value["requirements"][0]["findings"][0]["evidence"][0]["start"] = 0
                return value
            inputs = FakeInputs(transform=alter)
            with self.subTest(variant=variant), self.assertRaises(review.SourceReviewError):
                review.run_review(inputs)
            self.assertEqual(3, len(inputs.calls))
            self.assertEqual([], inputs.child_calls)

    def test_rejected_batch_preserves_the_exact_specialist_role_without_quote_text(self):
        def alter(role, packet, value):
            return self.select_quote(role, value, "missing") if role == "source_commercial_reviewer" else value
        inputs = FakeInputs(transform=alter)
        with self.assertRaises(review.SourceReviewError) as caught:
            review.run_review(inputs)
        self.assertEqual("source_commercial_reviewer", caught.exception.proof_failure_detail["role"])
        self.assertEqual("evidence_quote_missing", caught.exception.proof_failure_detail["rule"])
        self.assertEqual(3, len(inputs.calls))
        self.assertEqual(1, len(inputs.child_calls))

    def test_typed_rejection_index_cannot_be_coerced_or_outside_request_batch(self):
        for index in (True, -1, 99, "0"):
            def alter(request, result):
                result["output"].update({"status": "rejected", "reason_code": "evidence_quote_missing",
                                         "rejected_request_index": index, "spans": []})
                return result
            with self.subTest(index=index), self.assertRaises(review.SourceReviewError) as caught:
                review.run_review(FakeInputs(tool_transform=alter))
            self.assertEqual("span_rejection_invalid", caught.exception.proof_failure_detail["rule"])

    def test_tampered_result_identity_authority_counts_and_request_digest_rejected(self):
        for field in ("toolkit_version", "request_digest", "validation_scope", "agent_call_count",
                      "mutable_call_count", "semantic_authority_verified", "source_digest"):
            def alter(request, result):
                target = result["output"] if field in {"semantic_authority_verified", "source_digest"} else result
                target[field] = True
                return result
            inputs = FakeInputs(tool_transform=alter)
            with self.subTest(field=field), self.assertRaises(review.SourceReviewError):
                review.run_review(inputs)
            self.assertEqual(3, len(inputs.calls))
            self.assertEqual(1, len(inputs.child_calls))

    def test_span_type_range_and_exact_slice_have_safe_specific_subreasons(self):
        for update, rule in (({"start": True}, "evidence_span_type_invalid"),
                             ({"end": "2"}, "evidence_span_type_invalid"),
                             ({"end": 9999}, "evidence_span_range_invalid"),
                             ({"start": 1}, "evidence_quote_mismatch")):
            def alter(request, result):
                result["output"]["spans"][0].update(update)
                return result
            inputs = FakeInputs(tool_transform=alter)
            with self.subTest(rule=rule), self.assertRaises(review.SourceReviewError) as caught:
                review.run_review(inputs)
            self.assertEqual(rule, caught.exception.proof_failure_detail["rule"])
            self.assertNotIn("Ficta", str(caught.exception))
            self.assertEqual(3, len(inputs.calls))

    def test_response_order_extra_spans_and_duplicate_spans_are_rejected(self):
        for variant in ("order", "extra", "duplicate"):
            def alter(request, result):
                spans = result["output"]["spans"]
                if variant == "order":
                    spans.reverse()
                elif variant == "extra":
                    spans.append(copy.deepcopy(spans[0]))
                else:
                    spans[1] = copy.deepcopy(spans[0])
                return result
            inputs = FakeInputs(tool_transform=alter)
            with self.subTest(variant=variant), self.assertRaises(review.SourceReviewError):
                review.run_review(inputs)
            self.assertEqual(3, len(inputs.calls))

    def test_missing_callable_helper_and_five_chunks_fail_before_any_agent(self):
        inputs = FakeInputs()
        inputs.invoke_asset = None
        with self.assertRaises(review.SourceReviewError):
            review.run_review(inputs)
        self.assertEqual([], inputs.calls)
        inputs = FakeInputs()
        inputs["evaluation_case"]["records"][0]["source_units"] = [
            {"locator": f"source:{i}", "entity_id": "ficta", "text": f"Evidence {i}."} for i in range(5)]
        with self.assertRaises(review.SourceReviewError):
            review.run_review(inputs)
        self.assertEqual([], inputs.calls)

    def test_four_chunks_obey_agent_and_child_ceilings(self):
        inputs = FakeInputs()
        inputs["evaluation_case"]["records"][0]["source_units"] = [
            {"locator": f"source:{i}", "entity_id": "ficta", "text": f"Evidence {i}."} for i in range(4)]
        result = review.run_review(inputs)
        self.assertEqual((17, 4), (result["agent_call_count"], result["child_call_count"]))
        self.assertEqual(4, result["plan"]["child_call_limit"])
        self.assertEqual(0, result["plan"]["repair_iterations"])
        review.validate_resolution_receipts(result, review.prepare_review(inputs))

    def test_sixteen_spans_per_chunk_and_no_more(self):
        def double(role, packet, value):
            if role != review.VERIFIER_ROLE:
                for req in value["requirements"]:
                    finding = req["findings"][0]
                    text = packet["source_chunk"]["units"][0]["text"]
                    finding["evidence"] = [{"locator": "source:identity", "quote": text[:5]},
                                           {"locator": "source:identity", "quote": text[6:18]}]
                    req["findings"].append(copy.deepcopy(finding))
            return value
        inputs = FakeInputs(transform=double)
        result = review.run_review(inputs)
        self.assertEqual(16, len(inputs.child_calls[0]["arguments"]["requests"]))
        review.validate_resolution_receipts(result, review.prepare_review(inputs))

    def test_deadline_after_child_prevents_verifier_and_no_repair(self):
        expired = False
        def alter(request, result):
            nonlocal expired
            expired = True
            return result
        inputs = FakeInputs(tool_transform=alter)
        with self.assertRaises(review.SourceReviewError) as caught:
            review.run_review(inputs, clock=lambda: 1800 if expired else 0)
        self.assertEqual("deadline_exceeded", caught.exception.proof_failure_detail["rule"])
        self.assertEqual((3, 1), (len(inputs.calls), len(inputs.child_calls)))

    def test_agent_budget_is_enforced_before_an_extra_call(self):
        inputs = FakeInputs()
        prepare = review.prepare_review
        def bounded(value):
            result = prepare(value)
            result["plan"]["logical_call_limit"] = 1
            return result
        with patch.object(review, "prepare_review", bounded):
            with self.assertRaises(review.SourceReviewError):
                review.run_review(inputs)
        self.assertEqual(1, len(inputs.calls))
        self.assertEqual([], inputs.child_calls)

    def test_exact_provenance_does_not_override_semantic_rejection(self):
        def alter(role, packet, value):
            if packet["task_stage"] == "chunk_evidence_verification":
                for verdict in value["verdicts"]:
                    verdict["state"] = "wrong_entity"
            return value
        inputs = FakeInputs(transform=alter)
        result = review.run_review(inputs)
        self.assertEqual([], result["accepted_findings"])
        self.assertEqual("review_complete_with_evidence_gaps", result["review_outcome"])
        self.assertEqual((4, 1), (result["agent_call_count"], result["child_call_count"]))
        review.validate_resolution_receipts(result, review.prepare_review(inputs))

    def test_legacy_invalid_span_still_rejected_under_021(self):
        def invalid(role, packet, value):
            if role == "source_commercial_reviewer":
                value["requirements"][0]["findings"][0]["evidence"][0]["start"] = True
            return value
        with self.assertRaises(old.review.SourceReviewError) as caught:
            old.review.run_review(old.FakeInputs(findings=True, transform=invalid))
        self.assertEqual("evidence_span_invalid", caught.exception.proof_failure_detail["rule"])


if __name__ == "__main__":
    unittest.main()
