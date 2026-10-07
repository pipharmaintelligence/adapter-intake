from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

import test_structured_review_toolkit as shared

base = shared.ops
ops = shared.load_module(shared.TOOL / "tool_operations_v0_1_1.py", shared.PACKAGE + ".tool_operations_v0_1_1")


def request(text="Before 😀\r\nExact evidence. After.", quote="Exact evidence.", entity="company"):
    material = {"entity_id": entity, "snapshot_id": "sha256:" + "a" * 64,
                "source_units": [{"locator": "source:1", "entity_id": entity,
                                  "text": text, "accessible": True}]}
    return {"schema_version": "review_tool_request.v1", "operation": "resolve_exact_spans",
            "arguments": {**material, "source_digest": base.stable_digest(material),
                          "requests": [{"request_id": "r1", "locator": "source:1", "quote": quote}]}}


def rebind(value):
    args = value["arguments"]
    args["source_digest"] = base.stable_digest({key: args[key] for key in (
        "entity_id", "snapshot_id", "source_units")})


class ExactSpanTests(unittest.TestCase):
    def test_unicode_crlf_and_two_domains_use_the_same_unique_literal_operation(self):
        for entity in ("company", "policy"):
            value = request(entity=entity)
            result = ops.execute_operation(value)
            span = result["output"]["spans"][0]
            self.assertEqual((10, 25), (span["start"], span["end"]))
            self.assertEqual("Exact evidence.", value["arguments"]["source_units"][0]["text"][10:25])
            self.assertFalse(result["output"]["semantic_authority_verified"])
            self.assertEqual((0, 0), (result["agent_call_count"], result["mutable_call_count"]))
            self.assertEqual("0.1.1", result["toolkit_version"])

    def test_old_version_still_has_six_operations_and_rejects_new_operation(self):
        self.assertEqual(6, len(base.OPERATIONS))
        self.assertEqual(7, len(ops.OPERATIONS))
        with self.assertRaisesRegex(base.ReviewToolError, "operation_not_supported"):
            base.execute_operation(request())
        values, method = shared.fixture()
        old = base.execute_operation(shared.request(values, method))
        new = ops.execute_operation(shared.request(values, method))
        self.assertEqual({**old, "toolkit_version": "0.1.1"}, new)

    def test_missing_repeated_and_overlapping_quotes_fail_without_fuzzy_matching(self):
        for text, quote, rule in (
            ("abc", "ABC", "quote_missing"), ("abc abc", "abc", "quote_ambiguous"),
            ("aaa", "aa", "quote_ambiguous"), ("e\u0301", "é", "quote_missing"),
            ("abc\r\nxyz", "abc\nxyz", "quote_missing"),
        ):
            with self.subTest(text=text):
                output = ops.execute_operation(request(text, quote))["output"]
                self.assertEqual(("rejected", "evidence_" + rule, []),
                                 (output["status"], output["reason_code"], output["spans"]))

    def test_no_whitespace_trimming_or_normalization(self):
        result = ops.execute_operation(request(" x ", " x "))
        self.assertEqual(" x ", result["output"]["spans"][0]["quote"])
        for quote in ("", " ", 1, True, [], "x" * 601):
            with self.subTest(quote_type=type(quote).__name__), self.assertRaisesRegex(
                    base.ReviewToolError, "quote_invalid"):
                ops.execute_operation(request(quote=quote))

    def test_unknown_wrong_entity_and_inaccessible_locators_are_rejected(self):
        for variant, reason in (("unknown", "locator_invalid"), ("entity", "entity_mismatch"),
                                ("inaccessible", "inaccessible")):
            value = request()
            if variant == "unknown":
                value["arguments"]["requests"][0]["locator"] = "missing"
            elif variant == "entity":
                value["arguments"]["source_units"][0]["entity_id"] = "other"
            else:
                value["arguments"]["source_units"][0]["accessible"] = False
            rebind(value)
            output = ops.execute_operation(value)["output"]
            self.assertEqual("rejected", output["status"])
            self.assertEqual("evidence_" + ("entity_mismatch" if variant == "entity" else
                             "inaccessible" if variant == "inaccessible" else "locator_invalid"),
                             output["reason_code"])

    def test_stale_snapshot_source_digest_fails_before_resolution(self):
        value = request()
        value["arguments"]["snapshot_id"] = "changed"
        with self.assertRaisesRegex(base.ReviewToolError, "digest_mismatch"):
            ops.execute_operation(value)

    def test_duplicate_locators_and_request_ids_and_extra_offsets_rejected(self):
        for variant in ("locator", "request", "offset", "authority"):
            value = request()
            if variant == "locator":
                value["arguments"]["source_units"] *= 2
                rebind(value)
            elif variant == "request":
                value["arguments"]["requests"] *= 2
            elif variant == "offset":
                value["arguments"]["requests"][0]["start"] = 0
            else:
                value["arguments"]["requests"][0]["api_key"] = "private"
            with self.subTest(variant=variant), self.assertRaises(base.ReviewToolError) as caught:
                ops.execute_operation(value)
            self.assertNotIn("private", str(caught.exception))

    def test_rejected_quote_does_not_hide_a_later_invalid_request_or_return_partial_spans(self):
        value = request()
        value["arguments"]["requests"].append({"request_id": "r2", "locator": "source:1", "quote": "missing"})
        self.assertEqual([], ops.execute_operation(value)["output"]["spans"])
        value["arguments"]["requests"][0]["quote"] = "missing"
        value["arguments"]["requests"][1]["start"] = 0
        with self.assertRaises(base.ReviewToolError):
            ops.execute_operation(value)

    def test_sixteen_requests_and_empty_batch_are_bounded(self):
        value = request()
        quote = value["arguments"]["requests"][0]
        value["arguments"]["requests"] = [{**quote, "request_id": f"r{i}"} for i in range(16)]
        self.assertEqual(16, len(ops.execute_operation(value)["output"]["spans"]))
        value["arguments"]["requests"].append({**quote, "request_id": "overflow"})
        with self.assertRaisesRegex(base.ReviewToolError, "collection_limit"):
            ops.execute_operation(value)
        value["arguments"]["requests"] = []
        self.assertEqual([], ops.execute_operation(value)["output"]["spans"])

    def test_source_collection_text_and_accessibility_types_are_bounded(self):
        for variant in ("count", "text", "total", "accessible", "duplicate"):
            value = request()
            unit = value["arguments"]["source_units"][0]
            if variant == "count":
                value["arguments"]["source_units"] = [{**unit, "locator": f"p{i}"} for i in range(33)]
            elif variant == "text":
                unit["text"] = "x" * 6001
            elif variant == "total":
                value["arguments"]["source_units"] = [{**unit, "locator": f"p{i}", "text": "x" * 6000}
                                                       for i in range(5)]
            elif variant == "accessible":
                unit["accessible"] = "true"
            else:
                value["arguments"]["source_units"] *= 2
            rebind(value)
            with self.subTest(variant=variant), self.assertRaises(base.ReviewToolError):
                ops.execute_operation(value)

    def test_invalid_unicode_bytes_input_output_and_depth_fail_safely(self):
        value = request(quote="\ud800")
        with self.assertRaisesRegex(base.ReviewToolError, "json_invalid"):
            ops.execute_operation(value)
        value = request(text="x" * base.MAX_INPUT_BYTES)
        with self.assertRaisesRegex(base.ReviewToolError, "input_size_limit"):
            ops.execute_operation(value)
        with patch.object(base, "MAX_RESULT_BYTES", 64):
            with self.assertRaisesRegex(base.ReviewToolError, "result_size_limit"):
                ops.execute_operation(request())
        value = request()
        nested = {}
        value["arguments"]["extra"] = nested
        for _ in range(14):
            nested["child"] = {}
            nested = nested["child"]
        with self.assertRaisesRegex(base.ReviewToolError, "depth_limit"):
            ops.execute_operation(value)

    def test_caller_mutation_cannot_change_the_validated_snapshot(self):
        value = request()
        expected = copy.deepcopy(value)
        resolver = ops.resolve_exact_spans
        def mutate(arguments):
            value["arguments"]["source_units"][0]["text"] = "changed"
            return resolver(arguments)
        with patch.object(ops, "resolve_exact_spans", mutate):
            result = ops.execute_operation(value)
        self.assertEqual(base.stable_digest(expected), result["request_digest"])
        self.assertEqual("Exact evidence.", result["output"]["spans"][0]["quote"])


if __name__ == "__main__":
    unittest.main()
