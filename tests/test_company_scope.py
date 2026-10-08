from __future__ import annotations

import ast
import copy
from dataclasses import FrozenInstanceError
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "adapters/nusaibah/company_scope"
PACKAGE = "_company_scope_tests"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ASSET)]
sys.modules[PACKAGE] = package


def load(name, filename):
    spec = importlib.util.spec_from_file_location(PACKAGE + "." + name, ASSET / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


contract = load("scope_contract", "scope_contract.py")
adapter_module = load("adapter", "company_scope_adapter.py")


def row(identifier=1001):
    return {"id": identifier, "company": f"Synthetic Company {identifier}", "corporate_id": 1}


def envelope(records=None):
    records = copy.deepcopy(records if records is not None else [row()])
    return {"records": records, "row_count": len(records), "exactness": "exact",
            "partial_reason": None,
            "provenance": {"source": "dlm_node", "authority": "dlm_node",
                           "lake_id": "synthetic_companies_lake", "node_key": "companies",
                           "pages_read": 1}}


class CompanyScopeContractTests(unittest.TestCase):
    def assert_code(self, expected, function, *args):
        with self.assertRaises(contract.CompanyScopeError) as error:
            function(*args)
        self.assertEqual("company_scope_" + expected, error.exception.code)
        self.assertEqual(error.exception.code, str(error.exception))

    def test_single_list_and_inclusive_range_normalize(self):
        for selector, expected, kind in (
            ({"company_id": 1001}, (1001,), "single"),
            ({"company_ids": [1002, 1001]}, (1002, 1001), "list"),
            ({"from_company_id": 1001, "to_company_id": 1003}, (1001, 1002, 1003), "range"),
            ({"from_company_id": 1001, "to_company_id": 1001}, (1001,), "range"),
        ):
            with self.subTest(selector=selector):
                request = contract.normalize_selector(selector)
                self.assertEqual(expected, request.company_ids)
                self.assertEqual(kind, request.selector_kind)

    def test_input_duplicates_are_stably_deduplicated(self):
        request = contract.normalize_selector({"company_ids": [1002, 1001, 1002, 1003, 1001]})
        self.assertEqual((1002, 1001, 1003), request.company_ids)
        self.assertEqual(2, request.duplicate_id_count)
        with self.assertRaises(FrozenInstanceError):
            request.selector_kind = "range"

    def test_identifier_types_are_strict(self):
        for value in (True, False, None, "1", 1.0, float("nan"), 0, -1, [], {}, 2**63):
            for selector in ({"company_id": value}, {"company_ids": [value]},
                             {"from_company_id": value, "to_company_id": 5},
                             {"from_company_id": 1, "to_company_id": value}):
                with self.subTest(value=value, selector=selector):
                    self.assert_code("identifier_invalid", contract.normalize_selector, selector)

    def test_missing_mixed_or_unrecognized_selector_fields_rejected(self):
        cases = (None, [], {}, {"company_id": 1, "company_ids": [1]},
                 {"company_id": 1, "from_company_id": 1, "to_company_id": 1},
                 {"company_ids": [1], "from_company_id": 1, "to_company_id": 1},
                 {"from_company_id": 1}, {"to_company_id": 1},
                 {"company_ids": []}, {"company_ids": (1,)},
                 {"company_id": 1, "active_only": True},
                 {"company_id": 1, "fields": ["company"]})
        for selector in cases:
            with self.subTest(selector=selector):
                self.assert_code("selector_invalid", contract.normalize_selector, selector)

    def test_caller_cannot_override_scope_limits_or_authority(self):
        for key, value in (("corporate_id", 1), ("corporate_id", 2),
                           ("max_company_ids", 10000), ("lake_id", "another_lake"),
                           ("node_key", "another_node"), ("selector", {"corporate_id": 2}),
                           ("runtime_authority_verified", True)):
            self.assert_code("selector_invalid", contract.normalize_selector,
                             {"company_id": 1001, key: value})

    def test_list_and_range_bounds_are_enforced_before_expansion(self):
        self.assertEqual(25, len(contract.normalize_selector({"company_ids": list(range(1, 26))}).company_ids))
        self.assertEqual(25, len(contract.normalize_selector({"from_company_id": 1, "to_company_id": 25}).company_ids))
        for selector in ({"company_ids": list(range(1, 27))}, {"company_ids": [1] * 26},
                         {"from_company_id": 1, "to_company_id": 26},
                         {"from_company_id": 1, "to_company_id": contract.MAX_COMPANY_ID}):
            self.assert_code("selector_limit_exceeded", contract.normalize_selector, selector)
        self.assert_code("range_invalid", contract.normalize_selector,
                         {"from_company_id": 10, "to_company_id": 1})

    def test_single_context_maps_only_actual_companies_fields(self):
        source = row()
        source.update(company="  Synthetic Unicode \u0623  ", address_line1="  First address ",
                      address_line2=None, headquarter=197, website="example.invalid",
                      updated_at="2026-10-08 10:30:00")
        result = contract.build_scope_result({"company_id": 1001}, envelope([source]))
        context = result["contexts"][0]
        self.assertEqual("company_context.v1", context["schema_version"])
        self.assertEqual("Synthetic Unicode \u0623", context["company_name"])
        self.assertEqual("First address", context["address_line1"])
        self.assertEqual(197, context["headquarters_country_id"])
        self.assertEqual("2026-10-08 10:30:00", context["source_updated_at"])
        self.assertTrue(result["complete"])
        self.assertEqual(1, result["corporate_id"])
        for unavailable in ("city", "country", "registration_number", "status", "remember_token"):
            self.assertNotIn(unavailable, context)

    def test_optional_fields_are_null_and_source_metadata_is_not_invented(self):
        context = contract.build_scope_result({"company_id": 1001}, envelope())["contexts"][0]
        for key in ("address_line1", "address_line2", "headquarters_country_id", "website", "source_updated_at"):
            self.assertIsNone(context[key])
        self.assertIsNone(context["source"]["retrieved_at"])
        self.assertIsNone(context["source"]["schema_version"])
        self.assertEqual("companies", context["source"]["node_key"])
        self.assertEqual("synthetic_companies_lake", context["source"]["lake_id"])

    def test_list_result_preserves_caller_order_and_source_input(self):
        source = envelope([row(1001), row(1003), row(1002)])
        before = copy.deepcopy(source)
        result = contract.build_scope_result({"company_ids": [1003, 1001, 1003, 1002]}, source)
        self.assertEqual([1003, 1001, 1002], result["requested_company_ids"])
        self.assertEqual([1003, 1001, 1002], [c["company_id"] for c in result["contexts"]])
        self.assertEqual(1, result["duplicate_id_count"])
        self.assertEqual(source, before)

    def test_range_result_requires_every_id(self):
        result = contract.build_scope_result({"from_company_id": 1001, "to_company_id": 1003},
                                            envelope([row(1003), row(1002), row(1001)]))
        self.assertEqual([1001, 1002, 1003], [c["company_id"] for c in result["contexts"]])
        self.assert_code("result_set_mismatch", contract.build_scope_result,
                         {"from_company_id": 1001, "to_company_id": 1003}, envelope([row(1001), row(1003)]))

    def test_zero_missing_and_extra_rows_fail_closed(self):
        for records in ([], [row(1002)], [row(1001), row(1002)]):
            self.assert_code("result_set_mismatch", contract.build_scope_result,
                             {"company_id": 1001}, envelope(records))
        self.assert_code("rows_invalid", contract.build_scope_result,
                         {"company_id": 1}, envelope([row(i) for i in range(1, 27)]))

    def test_duplicate_returned_rows_are_rejected(self):
        self.assert_code("row_duplicate", contract.build_scope_result,
                         {"company_id": 1001}, envelope([row(), row()]))

    def test_wrong_nullable_or_coerced_corporate_ids_are_rejected(self):
        for value in (2, 0, None, True, "1", 1.0):
            record = row()
            record["corporate_id"] = value
            self.assert_code("corporate_scope_mismatch", contract.build_scope_result,
                             {"company_id": 1001}, envelope([record]))

    def test_returned_ids_and_country_references_are_strict(self):
        for value in (True, "1001", 1001.0, 0, -1, None):
            for field in ("id", "headquarter"):
                if field == "headquarter" and value is None:
                    continue
                record = row()
                record[field] = value
                self.assert_code("identifier_invalid", contract.build_scope_result,
                                 {"company_id": 1001}, envelope([record]))

    def test_unknown_columns_including_sensitive_fields_are_rejected(self):
        for field in ("remember_token", "password", "user_id", "provider_payload", "description", "city"):
            record = row()
            record[field] = "PRIVATE_SENTINEL_DO_NOT_ECHO"
            self.assert_code("row_fields_invalid", contract.build_scope_result,
                             {"company_id": 1001}, envelope([record]))

    def test_required_fields_and_row_types_are_enforced(self):
        for field in ("id", "company", "corporate_id"):
            record = row()
            del record[field]
            self.assert_code("row_fields_invalid", contract.build_scope_result,
                             {"company_id": 1001}, envelope([record]))
        for record in (None, "not a row", []):
            self.assert_code("rows_invalid", contract.build_scope_result,
                             {"company_id": 1001}, envelope([record]))

    def test_strings_are_bounded_without_silent_truncation(self):
        for field, maximum in (("company", 512), ("address_line1", 4096),
                               ("address_line2", 4096), ("website", 2048), ("updated_at", 64)):
            for value in (True, 10, [], {}, "x" * (maximum + 1), "bad\x00value"):
                record = row()
                record[field] = value
                self.assert_code("row_value_invalid", contract.build_scope_result,
                                 {"company_id": 1001}, envelope([record]))
        for value in (None, "", "   "):
            record = row()
            record["company"] = value
            self.assert_code("row_value_invalid", contract.build_scope_result,
                             {"company_id": 1001}, envelope([record]))

    def test_partial_query_is_rejected_even_when_requested_rows_are_present(self):
        for changes in ({"exactness": "partial"}, {"partial_reason": "more_pages_available"},
                        {"exactness": "unknown"}):
            source = envelope()
            source.update(changes)
            self.assert_code("source_incomplete", contract.build_scope_result, {"company_id": 1001}, source)

    def test_incomplete_or_unknown_envelope_metadata_is_rejected(self):
        for value in ([row()], {"records": [row()]}, None):
            self.assert_code("source_invalid", contract.build_scope_result, {"company_id": 1001}, value)
        for count in (True, 1.0, -1, 0, 2):
            source = envelope()
            source["row_count"] = count
            self.assert_code("source_invalid", contract.build_scope_result, {"company_id": 1001}, source)
        source = envelope()
        source["token"] = "PRIVATE_SENTINEL_DO_NOT_ECHO"
        self.assert_code("source_invalid", contract.build_scope_result, {"company_id": 1001}, source)

    def test_source_identity_full_dump_or_extra_pages_are_rejected(self):
        for field, value in (("source", "direct"), ("authority", "caller"), ("node_key", "other_node"),
                             ("lake_id", "https://private.invalid/path"), ("lake_id", 1),
                             ("pages_read", 2), ("pages_read", True), ("pages_read", 0),
                             ("input_mode", "full_dump_async"), ("token", "PRIVATE_SENTINEL_DO_NOT_ECHO")):
            source = envelope()
            source["provenance"][field] = value
            self.assert_code("source_invalid", contract.build_scope_result, {"company_id": 1001}, source)
        source = envelope()
        source["provenance"]["input_mode"] = "bounded_query"
        self.assertTrue(contract.build_scope_result({"company_id": 1001}, source)["complete"])
        source = envelope()
        del source["provenance"]["node_key"]
        self.assert_code("source_invalid", contract.build_scope_result, {"company_id": 1001}, source)

    def test_context_and_result_digests_are_reproducible_and_content_bound(self):
        result = contract.build_scope_result({"company_id": 1001}, envelope())
        self.assertEqual(result, contract.build_scope_result({"company_id": 1001}, envelope()))
        for value in (result, result["contexts"][0]):
            unhashed = {key: item for key, item in value.items() if key != "digest"}
            encoded = json.dumps(unhashed, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":"), allow_nan=False).encode("utf-8")
            self.assertEqual("sha256:" + hashlib.sha256(encoded).hexdigest(), value["digest"])
        changed = row()
        changed["company"] = "Different Synthetic Name"
        self.assertNotEqual(result["contexts"][0]["digest"],
                            contract.build_scope_result({"company_id": 1001}, envelope([changed]))["contexts"][0]["digest"])
        # A copied provenance envelope is not cryptographic authorization.
        self.assertFalse(result["runtime_authority_verified"])
        self.assertEqual("resolved_rows_only", result["validation_scope"])

    def test_contexts_and_runs_do_not_share_mutable_state(self):
        source = envelope([row(1001), row(1002)])
        result = contract.build_scope_result({"company_ids": [1001, 1002]}, source)
        second_before = copy.deepcopy(result["contexts"][1])
        result["contexts"][0]["company_name"] = "Changed output"
        result["contexts"][0]["source"]["node_key"] = "Changed output"
        self.assertEqual(second_before, result["contexts"][1])
        fresh = contract.build_scope_result({"company_ids": [1001, 1002]}, source)
        self.assertEqual("Synthetic Company 1001", fresh["contexts"][0]["company_name"])
        self.assertEqual("companies", fresh["contexts"][0]["source"]["node_key"])

    def test_adapter_does_not_invoke_query_provider_child_or_mutation(self):
        class NoInvocationInputs(dict):
            def forbidden(self, *args, **kwargs):
                raise AssertionError("Scope must only consume prepared roles")
            invoke = invoke_agent = invoke_asset = invoke_tool = forbidden
        inputs = NoInvocationInputs(variables={"company_id": 1001}, companies=envelope())
        response = adapter_module.CompanyScopeAdapter().invoke(inputs, {})
        self.assertEqual("success", response["status"])
        self.assertEqual(0, response["metrics"]["agent_call_count"])
        self.assertEqual(0, response["metrics"]["child_call_count"])
        self.assertEqual(0, response["metrics"]["mutable_dynamic_skill_call_count"])
        self.assertEqual(0, response["metrics"]["adapter_query_call_count"])
        summary = response["outputs"]["company_scope_summary"]
        self.assertTrue(all(type(value) in (str, int, bool) for value in summary.values()))
        self.assertNotIn("Synthetic", json.dumps(summary))
        self.assertNotIn("1001", json.dumps(summary))
        self.assertFalse(summary["runtime_authority_verified"])

    def test_adapter_never_returns_partial_outputs_after_later_company_failure(self):
        bad = row(1002)
        bad["corporate_id"] = 2
        inputs = {"variables": {"company_ids": [1001, 1002]}, "companies": envelope([row(1001), bad])}
        self.assert_code("corporate_scope_mismatch", adapter_module.CompanyScopeAdapter().invoke, inputs, {})

    def test_adapter_rejects_extra_roles_and_invalid_variables_before_source_read(self):
        for inputs in (None, [], {}, {"variables": {"company_id": 1}},
                       {"variables": {"company_id": 1001}, "companies": envelope(), "memory": {}}):
            self.assert_code("input_invalid", adapter_module.CompanyScopeAdapter().invoke, inputs, {})
        self.assert_code("selector_invalid", adapter_module.CompanyScopeAdapter().invoke,
                         {"variables": {"company_id": 1001, "corporate_id": 2}, "companies": None}, {})


class CompanyScopePackagingTests(unittest.TestCase):
    def test_manifest_preserves_binding_ownership_and_has_no_agents_or_children(self):
        manifest = json.loads((ASSET / "company_scope.asset.json").read_text())
        self.assertEqual("nusaibah.company_scope", manifest["key"])
        version = manifest["versions"]["0.1.0"]
        self.assertEqual({"required": True, "source": "binding", "shape": "object"}, version["inputs"]["companies"])
        self.assertEqual({"company_scope_result", "company_scope_summary"}, set(version["outputs"]))
        for field in ("agents", "callable", "callable_assets", "runtime_tools", "runtime_skills"):
            self.assertNotIn(field, version)
        self.assertEqual(["local_worker"], manifest["execution"]["allowed_substrates"])
        self.assertEqual(60, manifest["execution"]["timeout_seconds"])
        dependencies = json.loads((ASSET / "adapter.dependencies.json").read_text())
        self.assertEqual({}, dependencies["dependencies"])
        self.assertFalse(dependencies["network"]["outbound_required"])

    def test_runtime_source_has_no_network_storage_provider_or_unbounded_loop(self):
        allowed_imports = {"__future__", "dataclasses", "hashlib", "json", "re", "typing",
                           "adapters.base", "scope_contract"}
        for filename in ("scope_contract.py", "company_scope_adapter.py"):
            tree = ast.parse((ASSET / filename).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertIn(alias.name, allowed_imports)
                elif isinstance(node, ast.ImportFrom):
                    self.assertIn(node.module, allowed_imports)
                elif isinstance(node, ast.While):
                    self.fail("Scope has no while/retry loops")
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, {"invoke_asset", "invoke_agent", "invoke_tool", "invoke", "execute", "connect"})

    def test_flat_and_packaged_imports_use_only_declared_promotion_files(self):
        for packaged in (False, True):
            with self.subTest(packaged=packaged), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "adapters").mkdir()
                (root / "adapters/__init__.py").write_text("", encoding="utf-8")
                shutil.copy2(ROOT / "adapters/nusaibah/pharma_company_intelligence_lab/tests/stubs/adapters/base.py",
                             root / "adapters/base.py")
                destination = root
                module = "company_scope_adapter"
                if packaged:
                    destination = root / "adapters/intake/nusaibah/company_scope"
                    destination.mkdir(parents=True)
                    for folder in (destination, destination.parent, destination.parent.parent):
                        (folder / "__init__.py").write_text("", encoding="utf-8")
                    module = "adapters.intake.nusaibah.company_scope.company_scope_adapter"
                for filename in ("company_scope_adapter.py", "scope_contract.py"):
                    shutil.copy2(ASSET / filename, destination / filename)
                inputs = {"variables": {"company_id": 1001}, "companies": envelope()}
                code = f"""
import importlib, json, sys
before = list(sys.path)
module = importlib.import_module({module!r})
assert before == sys.path
response = module.CompanyScopeAdapter().invoke(json.loads({json.dumps(inputs)!r}), {{}})
assert response['outputs']['company_scope_result']['company_count'] == 1
assert response['metrics']['agent_call_count'] == 0
"""
                env = os.environ.copy()
                env.pop("PYTHONPATH", None)
                env["PYTHONDONTWRITEBYTECODE"] = "1"
                result = subprocess.run([sys.executable, "-c", code], cwd=root, env=env,
                                        capture_output=True, text=True, timeout=20)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_synthetic_fixture_is_development_only_and_is_not_in_promotion_files(self):
        fixture = json.loads((ASSET / "tests/fixtures/synthetic-resolved.inputs.json").read_text())
        result = adapter_module.CompanyScopeAdapter().invoke(fixture, {})
        self.assertEqual(2, result["outputs"]["company_scope_result"]["company_count"])
        promotion = (ASSET / "adapter.yaml").read_text()
        self.assertNotIn("synthetic-resolved.inputs.json", promotion)
        self.assertNotIn("test_company_scope.py", promotion)
        self.assertIn("allow_raw_fixtures: false", promotion)


if __name__ == "__main__":
    unittest.main()
