"""Deterministic intake-stage tests; no Core, provider or network access."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "adapters" / "nusaibah" / "abstract_mcp_dlm"
MODULE = ASSET / "abstract_mcp_dlm_v0_1_1_adapter.py"


def _subject():
    # The intake repository does not install pi-obs-python-runtime.
    # Exercise the actual class against an isolated Adapter test double.
    source = MODULE.read_text(encoding="utf-8")
    source = source.replace("from adapters.base import Adapter", "class Adapter:\n    pass")
    namespace = {"__name__": "dlm_mcp_intake_test"}
    exec(compile(source, str(MODULE), "exec"), namespace)
    return namespace["AbstractMcpDlmReadAdapter"](), namespace["DlmMcpReadError"]


class ToolInput(dict):
    """One injected local-only tool bridge; captures exact semantic fields."""

    def __init__(self, tool_result=None, *, error=None):
        super().__init__()
        self.tool_result = tool_result
        self.error = error
        self.calls = []

    def invoke_tool(self, role, *, input, on_error):
        self.calls.append((role, input, on_error))
        if self.error is not None:
            raise self.error
        return self.tool_result


def _run(adapter, request, response):
    inputs = ToolInput(response)
    inputs["tool_request"] = request
    value = adapter.invoke(inputs, {})
    return value["outputs"]["tool_results"], inputs.calls


class ReadOnlyMcpContractTest(unittest.TestCase):
    def test_current_version_intake_and_preserved_shared_manifest_contract(self):
        manifest = json.loads((ASSET / "abstract_mcp_dlm.asset.json").read_text())
        yaml = (ASSET / "adapter.yaml").read_text(encoding="utf-8")
        self.assertEqual("0.1.1", manifest["default"])
        self.assertEqual(["0.1.1"], list(manifest["versions"]))
        self.assertIn("adapter_module: abstract_mcp_dlm_v0_1_1_adapter.py", yaml)
        self.assertIn("  - abstract_mcp_capabilities.py", yaml)
        self.assertEqual({"tool_request"}, set(manifest["versions"]["0.1.1"]["inputs"]))
        self.assertEqual(
            {"dlm_lakes_list", "dlm_nodes_list", "dlm_nodes_schema"},
            set(manifest["versions"]["0.1.1"]["runtime_tools"]),
        )
        self.assertEqual(
            {"local_worker", "ecs"},
            set(manifest["execution"]["allowed_substrates"]),
        )

    def test_lakes_positive_allowlist_and_true_zero_records(self):
        adapter, _ = _subject()
        out, calls = _run(adapter, {"operation": "lakes.list", "page_size": 5}, {
            "status": "completed",
            "records": [{"lake_id": "safe-lake", "lake_name": "Safe Lake",
                         "storage_path": "not-output", "credentials": "not-output"}],
            "has_more": True,
        })
        self.assertEqual(out["records"], [{"lake_id": "safe-lake", "name": "Safe Lake"}])
        self.assertEqual(out["record_count"], 1)
        self.assertTrue(out["has_more"])
        self.assertEqual(calls, [("dlm_lakes_list", {"limit": 5}, "raise")])
        empty, _ = _run(adapter, {"operation": "lakes.list"}, {
            "status": "completed", "records": [],
        })
        self.assertEqual(empty["records"], [])
        self.assertEqual(empty["status"], "completed")

    def test_node_inventory_pagination_and_no_storage_projection(self):
        adapter, _ = _subject()
        result, calls = _run(adapter, {
            "operation": "nodes.list", "lake_id": "alpha", "page": 2,
            "page_size": 12, "q": "Cancer data",
        }, {"status": "completed", "records": [{
            "lake_id": "alpha", "node_key": "trial_records", "name": "Trial Records",
            "object_count": 3, "schema_status": "available",
            "storage_path": "not-output", "raw_provider_response": "not-output",
        }]})
        self.assertEqual(result["records"], [{
            "lake_id": "alpha", "node_key": "trial_records",
            "name": "Trial Records", "schema_status": "available",
            "object_count": 3,
        }])
        self.assertEqual(calls, [("dlm_nodes_list", {
            "limit": 12, "lake_id": "alpha", "page": 2, "search": "Cancer data",
        }, "raise")])

    def test_nested_schema_columns_preserved_without_extra_fields(self):
        adapter, _ = _subject()
        result, calls = _run(adapter, {
            "operation": "nodes.schema", "lake_id": "alpha", "node_key": "trial_records",
        }, {"status": "completed", "records": [{
            "lake_id": "alpha", "node_key": "trial_records",
            "schema_definition": {"columns": [
                {"column_name": "study_id", "data_type": "varchar(128)",
                 "nullable": False, "storage_path": "must-not-leak"},
                {"name": "year", "type": "integer"},
            ]},
            "private_metadata": "must-not-leak",
        }]})
        self.assertEqual(result["field_count"], 2)
        self.assertEqual(result["records"][0]["fields"], [
            {"name": "study_id", "type": "varchar(128)", "nullable": False},
            {"name": "year", "type": "integer"},
        ])
        self.assertEqual(calls, [("dlm_nodes_schema", {
            "lake_id": "alpha", "node_key": "trial_records",
        }, "raise")])
        self.assertNotIn("storage_path", json.dumps(result))

    def test_no_runtime_bridge_never_claims_success(self):
        adapter, error = _subject()
        with self.assertRaisesRegex(error, "dlm_mcp_trusted_tool_bridge_unavailable"):
            adapter.invoke({"tool_request": {"operation": "lakes.list"}}, {})

    def test_tool_exception_redacted_and_failure_status_rejected(self):
        adapter, error = _subject()
        subject = ToolInput(error=RuntimeError("private Core error should not leak"))
        subject["tool_request"] = {"operation": "lakes.list"}
        with self.assertRaisesRegex(error, "^dlm_mcp_tool_execution_failed$") as caught:
            adapter.invoke(subject, {})
        self.assertNotIn("private Core", str(caught.exception))
        for result in (None, {}, {"status": "failed", "records": []},
                       {"status": "partial", "records": []},
                       {"status": "completed"},
                       {"status": "completed", "records": None}):
            with self.subTest(result=result):
                with self.assertRaises(error):
                    _run(adapter, {"operation": "lakes.list"}, result)

    def test_operation_and_caller_authority_overrides_rejected(self):
        adapter, error = _subject()
        for request in (
            {"operation": "lakes.delete"},
            {"operation": "lakes.list", "client_id": "another"},
            {"operation": "lakes.list", "entity_key": "admin"},
            {"operation": "nodes.list", "lake_id": "alpha", "actor_id": "other"},
            {"operation": "nodes.schema", "lake_id": "alpha"},
            {"operation": "nodes.list", "lake_id": "bad/path"},
            {"operation": "lakes.list", "q": "https://invalid.test"},
            {"operation": "lakes.list", "page_size": True},
            {"operation": "lakes.list", "page_size": 51},
            {"operation": "nodes.list", "lake_id": "alpha", "page": 1001},
        ):
            with self.subTest(request=request):
                calls = ToolInput({"status": "completed", "records": []})
                calls["tool_request"] = request
                with self.assertRaises(error):
                    adapter.invoke(calls, {})
                self.assertEqual(calls.calls, [])

    def test_cross_lake_and_cross_node_data_rejected(self):
        adapter, error = _subject()
        with self.assertRaisesRegex(error, "dlm_mcp_scope_result_mismatch"):
            _run(adapter, {
                "operation": "nodes.list", "lake_id": "alpha",
            }, {"status": "completed", "records": [{"lake_id": "beta", "node_key": "node"}]})
        with self.assertRaisesRegex(error, "dlm_mcp_scope_result_mismatch"):
            _run(adapter, {
                "operation": "nodes.schema", "lake_id": "alpha", "node_key": "one",
            }, {"status": "completed", "records": [{
                "lake_id": "alpha", "node_key": "two",
                "columns": [{"name": "x", "type": "string"}],
            }]})

    def test_malformed_pagination_and_schema_fail_closed(self):
        adapter, error = _subject()
        with self.assertRaises(error):
            _run(adapter, {"operation": "lakes.list"}, {
                "status": "completed", "records": [], "has_more": "false",
            })
        with self.assertRaises(error):
            _run(adapter, {"operation": "nodes.schema", "lake_id": "alpha", "node_key": "x"}, {
                "status": "completed", "records": [{
                    "columns": [{"name": "x", "type": "string", "nullable": "maybe"}],
                }],
            })

    def test_result_limits_fail_instead_of_silent_truncation(self):
        adapter, error = _subject()
        with self.assertRaisesRegex(error, "dlm_mcp_response_limit_exceeded"):
            _run(adapter, {"operation": "lakes.list"}, {
                "status": "completed",
                "records": [{"lake_id": "a", "name": "A"}] * 51,
            })
        with self.assertRaisesRegex(error, "dlm_mcp_response_limit_exceeded"):
            _run(adapter, {
                "operation": "nodes.schema", "lake_id": "alpha", "node_key": "x",
            }, {"status": "completed", "records": [{
                "columns": [{"name": "column", "type": "varchar(20)"}] * 101,
            }]})

    def test_source_has_no_network_or_storage_execution_authority(self):
        source = MODULE.read_text(encoding="utf-8")
        for forbidden in ("import requests", "import httpx", "import urllib",
                          "import socket", "import subprocess", "import boto3",
                          "open(", "os.environ", "storage_path =", "retry("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
