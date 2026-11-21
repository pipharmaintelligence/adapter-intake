"""Synthetic contract tests for a standalone DLM lake search intake asset.

Tests do not reach Core, Assets, providers or ChatGPT; all authority is fake.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "adapters" / "nusaibah" / "dlm_lakes_search"
MODULE = ASSET / "dlm_lakes_search_adapter.py"


def _subject():
    # Intake CI does not install the full trusted Python runtime.
    source = MODULE.read_text(encoding="utf-8")
    source = source.replace("from adapters.base import Adapter", "class Adapter:\n    pass")
    namespace = {"__name__": "dlm_lakes_search_intake_test"}
    exec(compile(source, str(MODULE), "exec"), namespace)
    return namespace["DlmLakesKeywordSearchAdapter"](), namespace["DlmLakesSearchError"]


class FakeInputs(dict):
    """Synthetic helper implementing only the declared invoke_tool signature."""

    def __init__(self, result=None, failure=None):
        super().__init__()
        self.result, self.failure, self.calls = result, failure, []

    def invoke_tool(self, role, *, input, on_error):
        self.calls.append((role, input, on_error))
        if self.failure:
            raise self.failure
        return self.result


def _result(rows=None, **changes):
    rows = rows if rows is not None else [{"lake_id": "oncology_trials", "name": "Oncology 25%"}]
    value = {
        "status": "completed",
        "operation": "invoke",
        "capability_ref": "dlm.lakes.search",
        "tool_handle": "@tool.abstract_mcp_dlm",
        "tool_server_ref": "mcp.abstract_dlm",
        "records": rows,
        "provenance": {
            "runtime_mcp_tool": True,
            "role": "dlm_lakes_search",
            "invocation_id": "mti_" + "a" * 32,
            "record_count": len(rows),
            "cache_hit": False,
            "duration_ms": 7,
        },
    }
    value.update(changes)
    return value


class DlmLakesSearchContractTest(unittest.TestCase):
    def test_exact_public_request_maps_to_one_independent_trusted_role(self):
        adapter, _ = _subject()
        inp = FakeInputs(_result())
        inp["tool_request"] = {"operation": "lakes.search", "q": "  Oncology ", "page_size": 10}
        output = adapter.invoke(inp, {})["outputs"]["tool_results"]
        self.assertEqual([("dlm_lakes_search", {"text": "Oncology", "limit": 10}, "raise")], inp.calls)
        self.assertEqual("lakes.search", output["operation"])
        self.assertEqual("dlm_mcp_read.v1", output["schema_version"])
        self.assertEqual([{"lake_id": "oncology_trials", "name": "Oncology 25%"}], output["records"])
        self.assertNotIn("provenance", output)
        self.assertNotIn("has_more", output)
        self.assertEqual(1, output["record_count"])

    def test_empty_authorized_search_is_success_not_a_permission_proof(self):
        adapter, _ = _subject()
        inp = FakeInputs(_result(rows=[], has_more=False))
        inp["tool_request"] = {"operation": "lakes.search", "q": "oncology"}
        output = adapter.invoke(inp, {})["outputs"]["tool_results"]
        self.assertEqual([], output["records"])
        self.assertEqual(0, output["record_count"])
        self.assertFalse(output["has_more"])

    def test_partial_coverage_does_not_create_page_or_cursor(self):
        adapter, _ = _subject()
        inp = FakeInputs(_result(has_more=True))
        inp["tool_request"] = {"operation": "lakes.search", "q": "oncology"}
        output = adapter.invoke(inp, {})["outputs"]["tool_results"]
        self.assertTrue(output["truncated"])
        self.assertTrue(output["has_more"])
        self.assertNotIn("next_page", output)

    def test_invalid_public_requests_never_call_a_tool(self):
        adapter, error = _subject()
        cases = [
            {}, {"operation": "lakes.list", "q": "oncology"},
            {"operation": "lakes.search"}, {"operation": "lakes.search", "q": ""},
            {"operation": "lakes.search", "q": 12},
            {"operation": "lakes.search", "q": "oncology", "client_id": "other"},
            {"operation": "lakes.search", "q": "oncology", "limit": 20},
            {"operation": "lakes.search", "q": "oncology", "page_size": 51},
            {"operation": "lakes.search", "q": "oncology", "page_size": True},
            {"operation": "lakes.search", "q": "oncology", "page_size": "20"},
        ]
        for request in cases:
            with self.subTest(request=request):
                inp = FakeInputs()
                inp["tool_request"] = request
                with self.assertRaises(error):
                    adapter.invoke(inp, {})
                self.assertEqual([], inp.calls)

    def test_missing_or_failed_helper_never_fabricates_a_result(self):
        adapter, error = _subject()
        with self.assertRaisesRegex(error, "trusted_tool_unavailable"):
            adapter.invoke({"tool_request": {"operation": "lakes.search", "q": "oncology"}}, {})
        inp = FakeInputs(failure=RuntimeError("private upstream failure"))
        inp["tool_request"] = {"operation": "lakes.search", "q": "oncology"}
        with self.assertRaisesRegex(error, "tool_execution_failed") as ctx:
            adapter.invoke(inp, {})
        self.assertNotIn("private upstream failure", str(ctx.exception))

    def test_wrong_tool_identity_or_provenance_fails_closed(self):
        adapter, error = _subject()
        bad_results = [
            _result(capability_ref="dlm.lakes.list"),
            _result(tool_server_ref="other"),
            _result(operation="lakes.search"),
            _result(status="failed"),
            _result(provenance={"role": "dlm_lakes_search"}),
            _result(records=[{"lake_id": "bad/id", "name": "Wrong"}]),
            _result(records=[{"lake_id": "a", "name": "A"}, {"lake_id": "a", "name": "A"}]),
            _result(rows=[], has_more=True),
        ]
        for bad in bad_results:
            with self.subTest(bad=bad):
                inp = FakeInputs(bad)
                inp["tool_request"] = {"operation": "lakes.search", "q": "oncology"}
                with self.assertRaises(error):
                    adapter.invoke(inp, {})

    def test_role_and_remote_descriptor_remain_independent_of_immutable_asset(self):
        manifest = json.loads((ASSET / "dlm_lakes_search.asset.json").read_text())
        remote = json.loads((ASSET / "capabilities.v0.1.0.json").read_text())
        self.assertEqual("nusaibah.dlm_lakes_search", manifest["key"])
        self.assertEqual({"dlm_lakes_search"}, set(manifest["versions"]["0.1.0"]["runtime_tools"]))
        self.assertEqual("dlm.lakes.search",
            manifest["versions"]["0.1.0"]["runtime_tools"]["dlm_lakes_search"]["capability_ref"])
        self.assertEqual({"dlm.lakes.search"}, set(remote["capabilities"]))
        self.assertEqual("dlm_search_lakes", remote["capabilities"]["dlm.lakes.search"]["remote_mcp"]["tool_name"])
        self.assertEqual("templates_only", remote["publication_status"])
        original = ROOT / "adapters" / "nusaibah" / "abstract_mcp_dlm"
        self.assertTrue((original / "abstract_mcp_dlm_v0_1_2_adapter.py").exists())


if __name__ == "__main__":
    unittest.main()
