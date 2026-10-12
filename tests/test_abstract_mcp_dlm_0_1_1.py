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
    source = source.replace("from .mcp_read_resolution_v0_1_1 import", "from mcp_read_resolution_v0_1_1 import")
    namespace = {"__name__": "dlm_mcp_intake_test"}
    sys.path.insert(0, str(ASSET))
    try:
        exec(compile(source, str(MODULE), "exec"), namespace)
    finally:
        sys.path.remove(str(ASSET))
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
        self.assertEqual({"tool_request", "variables"}, set(manifest["versions"]["0.1.1"]["inputs"]))
        self.assertTrue(manifest["versions"]["0.1.1"]["inputs"]["tool_request"]["required"])
        self.assertFalse(manifest["versions"]["0.1.1"]["inputs"]["variables"]["required"])
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

    def test_list_pagination_preserves_known_and_unknown_continuation(self):
        adapter, _ = _subject()
        first, _ = _run(adapter, {"operation": "lakes.list", "page_size": 1}, {
            "status": "completed",
            "records": [{"lake_id": "alpha", "name": "Alpha"}],
            "has_more": True,
        })
        self.assertEqual(1, first["page_size"])
        self.assertTrue(first["has_more"])
        self.assertTrue(first["truncated"])
        self.assertNotIn("next_page", first)

        unknown, _ = _run(adapter, {"operation": "lakes.list"}, {
            "status": "completed", "records": [],
        })
        self.assertEqual([], unknown["records"])
        self.assertNotIn("has_more", unknown)
        self.assertNotIn("truncated", unknown)

        nodes, _ = _run(adapter, {
            "operation": "nodes.list", "lake_id": "alpha", "page": 2, "page_size": 1,
        }, {
            "status": "completed",
            "records": [{"lake_id": "alpha", "node_key": "n1"}],
            "has_more": True,
        })
        self.assertEqual(2, nodes["page"])
        self.assertEqual(3, nodes["next_page"])
        self.assertTrue(nodes["has_more"])

    def test_empty_node_list_is_valid_but_empty_schema_is_not(self):
        adapter, error = _subject()
        empty_nodes, _ = _run(adapter, {
            "operation": "nodes.list", "lake_id": "alpha",
        }, {"status": "completed", "records": [], "has_more": False})
        self.assertEqual([], empty_nodes["records"])
        self.assertFalse(empty_nodes["has_more"])

        with self.assertRaisesRegex(error, "dlm_mcp_schema_unavailable"):
            _run(adapter, {
                "operation": "nodes.schema", "lake_id": "alpha", "node_key": "missing",
            }, {"status": "completed", "records": []})

    def test_inconsistent_pagination_fails_closed(self):
        adapter, error = _subject()
        for request, response in (
            ({"operation": "lakes.list"}, {"status": "completed", "records": [], "has_more": True}),
            ({"operation": "nodes.schema", "lake_id": "alpha", "node_key": "x"},
             {"status": "completed", "records": [{"fields": [{"name": "id", "type": "integer"}]}], "has_more": False}),
        ):
            with self.subTest(request=request):
                with self.assertRaisesRegex(error, "dlm_mcp_pagination_invalid"):
                    _run(adapter, request, response)

    def test_misspelled_lake_returns_suggestion_not_silent_selection(self):
        adapter, _ = _subject()
        class SearchInput(ToolInput):
            def invoke_tool(self, role, *, input, on_error):
                self.calls.append((role, input, on_error))
                if "q" in input:
                    return _trusted_fixture({"operation": "lakes.list"}, {
                        "status": "completed", "records": [], "has_more": False,
                    })
                return _trusted_fixture({"operation": "lakes.list"}, {
                    "status": "completed",
                    "records": [{"lake_id": "hyper", "lake_name": "Hyper"}],
                    "has_more": False,
                })
        inputs = SearchInput()
        inputs["tool_request"] = {"operation": "lakes.list", "q": "hyser"}
        lookup = adapter.invoke(inputs, {})["outputs"]["tool_results"]["lookup"]
        self.assertEqual("suggestions", lookup["status"])
        self.assertTrue(lookup["requires_confirmation"])
        self.assertNotIn("resolved_id", lookup)
        self.assertEqual("Hyper", lookup["candidates"][0]["name"])
        self.assertEqual(2, len(inputs.calls))

    def test_exact_search_selects_id_only_when_supported(self):
        adapter, _ = _subject()
        result, _ = _run(adapter, {"operation": "lakes.list", "q": "hyper"}, {
            "status": "completed", "has_more": False,
            "records": [{"lake_id": "hyper", "name": "Hyper"}],
        })
        self.assertEqual("exact", result["lookup"]["status"])
        self.assertEqual("hyper", result["lookup"]["resolved_id"])
        self.assertFalse(result["lookup"]["requires_confirmation"])

    def test_partial_coverage_never_claims_absence(self):
        adapter, _ = _subject()
        class PartialInput(ToolInput):
            def invoke_tool(self, role, *, input, on_error):
                self.calls.append((role, input, on_error))
                return _trusted_fixture({"operation": "lakes.list"}, {
                    "status": "completed", "records": [], "has_more": False,
                }) if "q" in input else _trusted_fixture({"operation": "lakes.list"}, {
                    "status": "completed", "has_more": True,
                    "records": [{"lake_id": "alpha", "name": "Alpha"}],
                })
        inputs = PartialInput()
        inputs["tool_request"] = {"operation": "lakes.list", "q": "hyser"}
        result = adapter.invoke(inputs, {})["outputs"]["tool_results"]["lookup"]
        self.assertEqual("unresolved", result["status"])
        self.assertEqual("partial", result["coverage"])

    def test_discovery_failure_does_not_fabricate_not_found(self):
        adapter, _ = _subject()
        class FailingInput(ToolInput):
            def invoke_tool(self, role, *, input, on_error):
                self.calls.append((role, input, on_error))
                if "q" not in input:
                    raise RuntimeError("confidential downstream failure")
                return _trusted_fixture({"operation": "lakes.list"}, {
                    "status": "completed", "records": [], "has_more": False,
                })
        inputs = FailingInput()
        inputs["tool_request"] = {"operation": "lakes.list", "q": "hyser"}
        result = adapter.invoke(inputs, {})["outputs"]["tool_results"]["lookup"]
        self.assertEqual("unresolved", result["status"])
        self.assertEqual("discovery_unavailable", result["source"])
        self.assertNotIn("confidential", json.dumps(result))

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
            helper = ASSET / "mcp_read_resolution_v0_1_1.py"
            (package / helper.name).write_bytes(helper.read_bytes())
            code = (
                "import sys\n"
                f"sys.path.insert(0, {str(root)!r})\n"
                "from adapters.intake.nusaibah.abstract_mcp_dlm."
                "abstract_mcp_dlm_v0_1_1_adapter import AbstractMcpDlmReadAdapter\n"
                "assert AbstractMcpDlmReadAdapter.key == 'nusaibah.abstract_mcp_dlm'\n"
                "assert AbstractMcpDlmReadAdapter.version == '0.1.1'\n"
                f"sys.path.insert(0, {str(package)!r})\n"
                "from abstract_mcp_dlm_v0_1_1_adapter import AbstractMcpDlmReadAdapter as FlatAdapter\n"
                "assert FlatAdapter.key == AbstractMcpDlmReadAdapter.key\n"
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



class ReusableReadResolutionTest(unittest.TestCase):
    def test_both_assets_invocation_id_shapes_and_malformed_ids(self):
        adapter, error = _subject()
        request = {"operation": "lakes.list"}
        for identity in ("mti_" + "a" * 32, "mti_11111111-1111-4111-8111-111111111111"):
            response = _trusted_fixture(request, {"status": "completed", "records": []})
            response["provenance"]["invocation_id"] = identity
            out, _ = _run(adapter, request, response, trusted_fixture=False)
            self.assertEqual("completed", out["status"])
        for identity in ("mti_" + "A" * 32, "mti_123", "mti_" + "g" * 32,
                         "mti_111111111111-4111-8111-111111111111", "mti_" + "a" * 32 + "\n"):
            response = _trusted_fixture(request, {"status": "completed", "records": []})
            response["provenance"]["invocation_id"] = identity
            with self.subTest(identity=identity), self.assertRaisesRegex(error, "tool_provenance_invalid"):
                _run(adapter, request, response, trusted_fixture=False)

    def test_callable_filters_preserve_the_prepared_scope_and_original_request(self):
        adapter, _ = _subject()
        request = {"operation": "nodes.list", "lake_id": "lake-7"}
        inputs = ToolInput(_trusted_fixture(request, {"status": "completed", "records": []}))
        inputs.update(tool_request=request, variables={"q": "Trials", "page": 2, "page_size": 5})
        out = adapter.invoke(inputs, {})["outputs"]["tool_results"]
        self.assertEqual([("dlm_nodes_list", {
            "lake_id": "lake-7", "search": "Trials", "page": 2, "limit": 5,
        }, "raise")], inputs.calls)
        self.assertEqual({"operation": "nodes.list", "lake_id": "lake-7"}, request)
        self.assertEqual(2, out["page"])

    def test_callable_variables_cannot_supply_scope_authority_or_conflicting_filters(self):
        adapter, error = _subject()
        for variables in ({"lake_id": "other"}, {"node_key": "other"},
                          {"operation": "lakes.list"}, {"role": "admin"},
                          {"profile": {}}, {"q": "different"}, None, []):
            inputs = ToolInput()
            inputs.update(tool_request={"operation": "nodes.list", "lake_id": "lake-7", "q": "Trials"},
                          variables=variables)
            with self.subTest(variables=variables), self.assertRaises(error):
                adapter.invoke(inputs, {})
            self.assertEqual([], inputs.calls)
        with self.assertRaisesRegex(error, "input_roles_invalid"):
            adapter.invoke({"variables": {"q": "Trials"}}, {})

    def test_name_normalization_handles_unicode_punctuation_and_resource_nouns(self):
        adapter, _ = _subject()
        out, _ = _run(adapter, {"operation": "lakes.list", "q": "ＬＡＫＥ  Hyper"}, {
            "status": "completed", "has_more": False,
            "records": [{"lake_id": "lake-7", "name": "Hyper_Lake"}],
        })
        self.assertEqual("exact", out["lookup"]["status"])
        self.assertEqual("lake-7", out["lookup"]["resolved_id"])

    def test_generic_profile_resolves_an_unrelated_resource_with_its_own_contract(self):
        adapter, _ = _subject()
        namespace = adapter.invoke.__globals__
        ReadContract, NameProfile = namespace["ReadContract"], namespace["NameProfile"]
        resolve = namespace["resolve_names"]
        contract = ReadContract("project_find", "projects.list", "@tool.projects", "mcp.projects", 5)
        profile = NameProfile("project_id", ("project_id", "name"), ignored_nouns=("project",))
        calls = []
        def envelope(records, more=False):
            return {"status": "completed", "operation": "invoke", "records": records,
                    "capability_ref": contract.capability_ref, "tool_handle": contract.tool_handle,
                    "tool_server_ref": contract.tool_server_ref, "has_more": more,
                    "provenance": {"runtime_mcp_tool": True, "role": contract.role,
                                   "invocation_id": "mti_" + "b" * 32,
                                   "record_count": len(records), "cache_hit": False, "duration_ms": 0}}
        def invoke(role, *, input, on_error):
            calls.append((role, input, on_error))
            return envelope([{"project_id": "prj-17", "name": "Hyper", "credentials": "hidden"}])
        project = lambda rows, scope: [{"project_id": row["project_id"], "name": row["name"]} for row in rows]
        lookup = resolve(query="Hyser", records=[], result=envelope([]), contract=contract,
                         profile=profile, invoke_tool=invoke, project=project,
                         fallback_input={"workspace_id": "ws-2", "limit": 5}, error=RuntimeError)
        self.assertEqual([("project_find", {"workspace_id": "ws-2", "limit": 5}, "raise")], calls)
        self.assertEqual("suggestions", lookup["status"])
        self.assertTrue(lookup["requires_confirmation"])
        self.assertEqual({"project_id": "prj-17", "name": "Hyper", "match_type": "close_spelling"},
                         lookup["candidates"][0])
        self.assertNotIn("lake", json.dumps(lookup))
        self.assertNotIn("credentials", json.dumps(lookup))
        bad = envelope([{"project_id": "prj-17", "name": "Hyper"}])
        bad["capability_ref"] = "projects.delete"
        lookup = resolve(query="Hyser", records=[], result=envelope([]), contract=contract,
                         profile=profile, invoke_tool=lambda *args, **kwargs: bad, project=project,
                         fallback_input={"workspace_id": "ws-2", "limit": 5}, error=RuntimeError)
        self.assertEqual("unresolved", lookup["status"])
        self.assertEqual([], lookup["candidates"])

    def test_name_normalization_cannot_resolve_a_different_id_with_unknown_coverage(self):
        adapter, _ = _subject()
        for query, confirmation in (("Hyper", True), ("lake_Hyper", False)):
            out, _ = _run(adapter, {"operation": "lakes.list", "q": query}, {
                "status": "completed", "records": [{"lake_id": "lake_Hyper", "name": "Hyper"}],
            })
            self.assertEqual("exact", out["lookup"]["status"])
            self.assertEqual(confirmation, out["lookup"]["requires_confirmation"])
            if confirmation:
                self.assertNotIn("resolved_id", out["lookup"])
            else:
                self.assertEqual("lake_Hyper", out["lookup"]["resolved_id"])

    def test_reuse_contract_keeps_prepared_request_required_and_public_schema_stable(self):
        manifest = json.loads((ASSET / "abstract_mcp_dlm.asset.json").read_text())
        contract = manifest["versions"]["0.1.1"]["callable"]
        self.assertEqual({"enabled": True, "result_key": "tool_results", "result_shape": "object",
                          "max_result_bytes": 65536, "timeout_seconds": 120}, contract)
        metadata = json.loads((ASSET / "capabilities.v0.1.1.json").read_text())
        for capability in metadata["capabilities"].values():
            self.assertEqual({"tool_request"}, set(capability["remote_mcp"]["input_schema"]["properties"]))
        self.assertIn("  - mcp_read_resolution_v0_1_1.py", (ASSET / "adapter.yaml").read_text())


class DiscoveryOrchestrationPackageTest(unittest.TestCase):
    PLUGIN_ROOT = ROOT / "plugins" / "dms-dlm-discovery"
    SKILL_ROOT = PLUGIN_ROOT / "skills" / "dlm-discovery-orchestration"

    def metadata(self):
        return json.loads(
            (ASSET / "capabilities.v0.1.1.json").read_text(
                encoding="utf-8",
            )
        )

    def test_adapter_execution_has_no_chatgpt_skill_dependency(self):
        manifest = json.loads((ASSET / "abstract_mcp_dlm.asset.json").read_text())
        version = manifest["versions"]["0.1.1"]
        self.assertNotIn("skills", version)
        self.assertNotIn("published_skills", version)
        self.assertFalse((ASSET / "skills" / "dlm-discovery-orchestration").exists())
        yaml = (ASSET / "adapter.yaml").read_text(encoding="utf-8")
        self.assertIn("  - capabilities.v0.1.1.json", yaml)
        self.assertIn("reviewed_support_files:\n  - capabilities.v0.1.1.json", yaml)
        self.assertNotIn("optional_files:\n  - README.md\n  - capabilities.v0.1.1.json", yaml)
        metadata = self.metadata()
        self.assertNotIn("skill_ref", metadata)
        self.assertNotIn("skill_version", metadata)

    def test_chatgpt_plugin_owns_a_contained_instruction_package(self):
        plugin = json.loads((self.PLUGIN_ROOT / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual("dms-dlm-discovery", plugin["name"])
        self.assertEqual("1.1.0", plugin["version"])
        self.assertEqual(
            "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
            plugin["$schema"],
        )
        self.assertNotIn("skills", plugin)  # portable hosts use the fixed skills/ location
        self.assertNotIn("mcpServers", plugin)
        self.assertNotIn("apps", plugin)
        self.assertFalse((self.PLUGIN_ROOT / "mcp.json").exists())
        self.assertFalse((self.PLUGIN_ROOT / ".app.json").exists())
        interface = plugin["extensions"]["com.openai"]["interface"]
        self.assertLessEqual(len(interface["shortDescription"]), 30)
        markdown = (self.SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(markdown.startswith("---\nname: dlm-discovery-orchestration\n"))
        self.assertIn("description:", markdown.split("---", 2)[1])
        self.assertIn("not an Assets execution dependency", markdown)
        self.assertNotIn("references/capabilities.v0.1.1.json", markdown)
        self.assertEqual(
            {"README.md", "plugin.json", "skills/dlm-discovery-orchestration/SKILL.md",
             "skills/mcp-resource-discovery/SKILL.md"},
            {path.relative_to(self.PLUGIN_ROOT).as_posix()
             for path in self.PLUGIN_ROOT.rglob("*") if path.is_file()},
        )

    def test_metadata_has_exact_capability_and_role_parity(self):
        manifest = json.loads((ASSET / "abstract_mcp_dlm.asset.json").read_text())
        roles = manifest["versions"]["0.1.1"]["runtime_tools"]
        metadata = self.metadata()
        self.assertEqual("nusaibah.abstract_mcp_dlm", metadata["asset_key"])
        self.assertEqual("0.1.1", metadata["asset_version"])
        self.assertEqual("templates_only", metadata["publication_status"])
        self.assertEqual(
            {"dlm.lakes.list", "dlm.nodes.list", "dlm.nodes.schema"},
            set(metadata["capabilities"]),
        )
        for capability, definition in metadata["capabilities"].items():
            role = definition["tool_role"]
            self.assertEqual(capability, roles[role]["capability_ref"])
        self.assertEqual(
            {"dlm_list_lakes", "dlm_list_nodes", "dlm_get_node_schema"},
            {definition["remote_mcp"]["tool_name"]
             for definition in metadata["capabilities"].values()},
        )

    def test_descriptors_respect_the_current_assets_projection_budget(self):
        def depth(value):
            if isinstance(value, dict):
                return max((1 + depth(item) for item in value.values()), default=0)
            if isinstance(value, list):
                return max((1 + depth(item) for item in value), default=0)
            return 0

        for definition in self.metadata()["capabilities"].values():
            with self.subTest(capability=definition["operation"]):
                remote = definition["remote_mcp"]
                self.assertGreater(len(remote["description"]), 0)
                self.assertLessEqual(len(remote["description"]), 240)
                for field in ("input_schema", "output_schema"):
                    self.assertLessEqual(
                        len(json.dumps(remote[field]).encode("utf-8")), 32768,
                    )
                    self.assertLessEqual(depth(remote[field]), 12)

    def test_public_schemas_use_only_the_real_adapter_selectors_and_limits(self):
        adapter, _ = _subject()
        contract = adapter.invoke.__globals__
        for definition in self.metadata()["capabilities"].values():
            operation = definition["operation"]
            schema = definition["remote_mcp"]["input_schema"]
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(["tool_request"], schema["required"])
            self.assertEqual({"tool_request"}, set(schema["properties"]))
            request = schema["properties"]["tool_request"]
            self.assertFalse(request["additionalProperties"])
            self.assertEqual(
                contract["_ALLOWED_KEYS"][operation], set(request["properties"]),
            )
            self.assertEqual(
                [operation], request["properties"]["operation"]["enum"],
            )
            if operation != "nodes.schema":
                self.assertEqual(
                    contract["MAX_PAGE_SIZE"],
                    request["properties"]["page_size"]["maximum"],
                )
            if operation == "nodes.list":
                self.assertIn("lake_id", request["required"])
                self.assertEqual(
                    contract["MAX_PAGE"], request["properties"]["page"]["maximum"],
                )
            if operation == "nodes.schema":
                self.assertEqual(
                    {"operation", "lake_id", "node_key"}, set(request["required"]),
                )

    def test_output_descriptors_expose_lookup_in_the_registered_asset_result(self):
        for capability in ("dlm.lakes.list", "dlm.nodes.list"):
            output = self.metadata()["capabilities"][capability]["remote_mcp"]["output_schema"]
            self.assertEqual(["tool_results"], output["required"])
            result = output["properties"]["tool_results"]
            lookup = result["properties"]["lookup"]
            self.assertFalse(lookup["additionalProperties"])
            self.assertIn("requires_confirmation", lookup["required"])
            self.assertIn("coverage", lookup["required"])
            self.assertEqual(3, lookup["properties"]["candidates"]["maxItems"])
            self.assertEqual(
                {"exact", "suggestions", "ambiguous", "no_match", "unresolved"},
                set(lookup["properties"]["status"]["enum"]),
            )
            candidate = lookup["properties"]["candidates"]["items"]
            self.assertIn("lake_id", candidate["required"])
            if capability == "dlm.nodes.list":
                self.assertIn("node_key", candidate["required"])
            else:
                self.assertNotIn("next_page", result["properties"])
        schema = self.metadata()["capabilities"]["dlm.nodes.schema"]["remote_mcp"]["output_schema"]
        fields = schema["properties"]["tool_results"]["properties"]["records"]["items"]["properties"]["fields"]
        self.assertEqual(100, fields["maxItems"])

    def test_confirmed_lake_and_node_chain_uses_returned_identifiers(self):
        # The simulated user confirmation is a conversational boundary, not
        # an adapter permission field or automatic selection by the runtime.
        adapter, _ = _subject()
        class LakeSearchInput(ToolInput):
            def invoke_tool(self, role, *, input, on_error):
                self.calls.append((role, input, on_error))
                rows = [] if "q" in input else [
                    {"lake_id": "lake-7", "name": "Hyper"},
                ]
                return _trusted_fixture({"operation": "lakes.list"}, {
                    "status": "completed", "records": rows, "has_more": False,
                })
        search = LakeSearchInput()
        search["tool_request"] = {
            "operation": "lakes.list", "q": "Hyser", "page_size": 20,
        }
        found = adapter.invoke(search, {})["outputs"]["tool_results"]["lookup"]
        self.assertTrue(found["requires_confirmation"])
        self.assertNotIn("resolved_id", found)
        self.assertEqual(["dlm_lakes_list", "dlm_lakes_list"], [
            call[0] for call in search.calls
        ])
        selected_lake = found["candidates"][0]  # simulated user: "Yes, Hyper"
        self.assertEqual("Hyper", selected_lake["name"])
        nodes, calls = _run(adapter, {
            "operation": "nodes.list", "lake_id": selected_lake["lake_id"],
            "q": "Trials", "page": 1, "page_size": 20,
        }, {
            "status": "completed", "has_more": False,
            "records": [{"lake_id": "lake-7", "node_key": "node-9", "name": "Trials"}],
        })
        self.assertEqual("lake-7", calls[0][1]["lake_id"])
        selected_node = nodes["lookup"]
        self.assertFalse(selected_node["requires_confirmation"])
        self.assertEqual("node-9", selected_node["resolved_id"])
        schema, calls = _run(adapter, {
            "operation": "nodes.schema", "lake_id": selected_lake["lake_id"],
            "node_key": selected_node["resolved_id"],
        }, {
            "status": "completed",
            "records": [{"lake_id": "lake-7", "node_key": "node-9",
                         "fields": [{"name": "study_id", "type": "integer"}]}],
        })
        self.assertEqual(("dlm_nodes_schema", {
            "lake_id": "lake-7", "node_key": "node-9",
        }, "raise"), calls[0])
        self.assertEqual("node-9", schema["records"][0]["node_key"])


if __name__ == "__main__":
    unittest.main()

