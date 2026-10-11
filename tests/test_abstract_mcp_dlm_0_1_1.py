"""Deterministic intake-stage tests; no Core, provider or network access."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
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


def _trusted_fixture(request, response):
    """Create a deterministic stand-in for the current Assets tool envelope.

    This is only synthetic test data. It does not certify a signed Core/Assets
    runtime session, admission, an actual tool execution, or G0 readiness.
    """
    if not isinstance(response, dict) or response.get("status") != "completed":
        return response
    declared = {
        "lakes.list": ("dlm.lakes.list", "dlm_lakes_list"),
        "nodes.list": ("dlm.nodes.list", "dlm_nodes_list"),
        "nodes.schema": ("dlm.nodes.schema", "dlm_nodes_schema"),
    }
    name = request.get("operation")
    if name not in declared:
        return response
    capability, role = declared[name]
    count = len(response["records"]) if isinstance(response.get("records"), list) else 0
    result = {
        "status": "completed",
        "operation": "invoke",
        "capability_ref": capability,
        "tool_handle": "@tool.abstract_mcp_dlm",
        "tool_server_ref": "mcp.abstract_dlm",
        "summary": "",
        "records": response.get("records"),
        "provenance": {
            "runtime_mcp_tool": True,
            "invocation_id": "mti_" + "a" * 32,
            "role": role,
            "cache_hit": False,
            "duration_ms": 1,
            "record_count": count,
        },
    }
    result.update(response)
    return result


def _run(adapter, request, response, *, trusted_fixture=True):
    inputs = ToolInput(
        _trusted_fixture(request, response) if trusted_fixture else response
    )
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

    def test_backend_must_honor_requested_page_size(self):
        adapter, error = _subject()
        with self.assertRaisesRegex(error, "dlm_mcp_response_limit_exceeded"):
            _run(adapter, {"operation": "lakes.list", "page_size": 1}, {
                "status": "completed",
                "records": [
                    {"lake_id": "first", "name": "First"},
                    {"lake_id": "second", "name": "Second"},
                ],
            })

    def test_canonical_selectors_used_for_scoping_and_projection(self):
        adapter, _ = _subject()
        nodes, _ = _run(adapter, {
            "operation": "nodes.list", "lake_id": " alpha ",
        }, {"status": "completed", "records": [
            {"lake_id": "alpha", "node_key": "node_a"},
        ]})
        self.assertEqual(nodes["records"][0]["lake_id"], "alpha")
        schema, _ = _run(adapter, {
            "operation": "nodes.schema", "lake_id": " alpha ",
            "node_key": " records ",
        }, {"status": "completed", "records": [{
            "lake_id": "alpha", "node_key": "records",
            "fields": [{"name": "study_id", "type": "varchar(30)"}],
        }]})
        self.assertEqual(schema["records"][0]["lake_id"], "alpha")
        self.assertEqual(schema["records"][0]["node_key"], "records")

    def test_shared_helper_byte_identity_pin(self):
        raw = (ASSET / "abstract_mcp_capabilities.py").read_bytes()
        header = ("blob " + str(len(raw)) + "\0").encode("utf-8")
        digest = hashlib.sha1(header + raw).hexdigest()
        self.assertEqual("92ca96fdc5e1f6927c6ba4472305bd472bbc3e7a", digest)

    def test_isolated_dotted_package_import_shape(self):
        # Package import preflight only; does not run Assets materialization.
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            package = root / "adapters" / "intake" / "nusaibah" / "abstract_mcp_dlm"
            package.mkdir(parents=True)
            for folder in (
                root / "adapters",
                root / "adapters" / "intake",
                root / "adapters" / "intake" / "nusaibah",
                package,
            ):
                (folder / "__init__.py").write_text("", encoding="utf-8")
            (root / "adapters" / "base.py").write_text(
                "class Adapter:\n    pass\n", encoding="utf-8",
            )
            (package / MODULE.name).write_bytes(MODULE.read_bytes())
            code = (
                "import sys\n"
                f"sys.path.insert(0, {str(root)!r})\n"
                "from adapters.intake.nusaibah.abstract_mcp_dlm."
                "abstract_mcp_dlm_v0_1_1_adapter import AbstractMcpDlmReadAdapter\n"
                "assert AbstractMcpDlmReadAdapter.key == 'nusaibah.abstract_mcp_dlm'\n"
                "assert AbstractMcpDlmReadAdapter.version == '0.1.1'\n"
            )
            result = subprocess.run(
                [sys.executable, "-I", "-c", code],
                capture_output=True, text=True, timeout=15, check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)

    def test_trusted_runtime_envelope_identity_and_provenance_required(self):
        adapter, error = _subject()
        request = {"operation": "lakes.list"}
        genuine_shape = _trusted_fixture(request, {
            "status": "completed", "records": [],
        })
        missing_proof = {"status": "completed", "records": []}
        with self.assertRaisesRegex(error, "dlm_mcp_tool_identity_mismatch"):
            _run(adapter, request, missing_proof, trusted_fixture=False)

        for field, value in (
            ("operation", "schema"),
            ("capability_ref", "dlm.nodes.list"),
            ("tool_handle", "@tool.other"),
            ("tool_server_ref", "mcp.other"),
        ):
            with self.subTest(field=field):
                malformed = dict(genuine_shape)
                malformed[field] = value
                with self.assertRaisesRegex(error, "dlm_mcp_tool_identity_mismatch"):
                    _run(adapter, request, malformed, trusted_fixture=False)

        for change in (
            {"runtime_mcp_tool": False},
            {"role": "dlm_nodes_list"},
            {"invocation_id": "mti_wrong"},
            {"record_count": 1},
            {"record_count": True},
            {"cache_hit": "false"},
            {"duration_ms": -1},
        ):
            with self.subTest(change=change):
                malformed = dict(genuine_shape)
                malformed["provenance"] = {**genuine_shape["provenance"], **change}
                with self.assertRaisesRegex(error, "dlm_mcp_tool_provenance_invalid"):
                    _run(adapter, request, malformed, trusted_fixture=False)

        for missing in ("provenance", "records", "tool_handle"):
            with self.subTest(missing=missing):
                malformed = dict(genuine_shape)
                malformed.pop(missing)
                with self.assertRaises(error):
                    _run(adapter, request, malformed, trusted_fixture=False)

    def test_signed_shaped_response_does_not_expose_runtime_metadata(self):
        adapter, _ = _subject()
        record, _ = _run(adapter, {"operation": "lakes.list"}, {
            "status": "completed",
            "records": [{"lake_id": "alpha", "name": "Alpha"}],
            "provenance": {
                "runtime_mcp_tool": True,
                "invocation_id": "mti_" + "b" * 32,
                "role": "dlm_lakes_list",
                "cache_hit": False,
                "duration_ms": 1,
                "record_count": 1,
            },
            "summary": "ignore runtime narrative",
        })
        serialized = json.dumps(record)
        self.assertEqual(record["records"], [{"lake_id": "alpha", "name": "Alpha"}])
        self.assertNotIn("invocation_id", serialized)
        self.assertNotIn("runtime_mcp_tool", serialized)
        self.assertNotIn("runtime narrative", serialized)

    def test_source_has_no_network_or_storage_execution_authority(self):
        source = MODULE.read_text(encoding="utf-8")
        for forbidden in ("import requests", "import httpx", "import urllib",
                          "import socket", "import subprocess", "import boto3",
                          "open(", "os.environ", "storage_path =", "retry("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
