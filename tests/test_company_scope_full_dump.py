from __future__ import annotations

import ast
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_company_scope import ASSET, ROOT, contract, envelope, load, row

page_contract = load("scope_page_contract", "scope_page_contract.py")
page_adapter = load("full_dump_adapter", "company_scope_full_dump_adapter.py")


def native_page(records=None, *, final=False, page_index=0, record_offset=0):
    source = envelope(records if records is not None else [row(1001), row(1002)])
    source["exactness"] = "exact" if final else "partial"
    source["partial_reason"] = None if final else "more_pages_available"
    source["provenance"].update(input_mode="full_dump_async", page_index=page_index,
                                record_offset=record_offset)
    return source


def inputs(source=None):
    return {"variables": {"selection": "all_authorized"},
            "companies": source if source is not None else native_page()}


class CompanyScopeFullDumpTests(unittest.TestCase):
    def assert_code(self, code, function, *args):
        with self.assertRaises(contract.CompanyScopeError) as error:
            function(*args)
        self.assertEqual("company_scope_" + code, error.exception.code)
        self.assertEqual(error.exception.code, str(error.exception))

    def test_native_intermediate_page_preserves_partial_source_truth(self):
        source = native_page([row(1002), row(1001)])
        before = copy.deepcopy(source)
        response = page_adapter.CompanyScopeFullDumpAdapter().invoke(inputs(source), {})
        result = response["outputs"]["company_scope_page"]
        self.assertEqual("company_scope_page.v1", result["schema_version"])
        self.assertEqual([1002, 1001], [item["company_id"] for item in result["contexts"]])
        self.assertTrue(result["batch_complete"])
        self.assertFalse(result["source_exhausted"])
        self.assertIsNone(result["selection_complete"])
        self.assertEqual("current_page", result["completion_scope"])
        self.assertEqual("partial", result["source_exactness"])
        self.assertEqual("more_pages_available", result["source_partial_reason"])
        self.assertEqual(before, source)
        self.assertFalse(result["runtime_authority_verified"])
        self.assertEqual("resolved_page_only", result["validation_scope"])
        self.assertNotIn("company_scope_result", response["outputs"])

    def test_final_page_exhaustion_does_not_attest_prior_page_processing(self):
        result = page_contract.build_scope_page({"selection": "all_authorized"},
                    native_page([row(1003)], final=True, page_index=1, record_offset=2))
        self.assertTrue(result["batch_complete"])
        self.assertTrue(result["source_exhausted"])
        self.assertIsNone(result["selection_complete"])
        self.assertEqual({"page_index": 1, "record_offset": 2}, result["page"])
        self.assertNotIn("complete", result)

    def test_empty_terminal_page_is_valid_but_empty_continuation_is_rejected(self):
        for page_index, offset in ((0, 0), (1, 2)):
            result = page_contract.build_scope_page({"selection": "all_authorized"},
                native_page([], final=True, page_index=page_index, record_offset=offset))
            self.assertEqual([], result["contexts"])
            self.assertEqual(0, result["company_count"])
            self.assertTrue(result["source_exhausted"])
            self.assertIsNone(result["selection_complete"])
        self.assert_code("source_incomplete", page_contract.build_scope_page,
                         {"selection": "all_authorized"}, native_page([]))

    def test_only_explicit_all_authorized_selection_is_admitted(self):
        for variables in (None, [], {}, {"selection": "all"}, {"selection": True},
                          {"company_id": 1001}, {"company_ids": [1001]},
                          {"selection": "all_authorized", "company_id": 1001},
                          {"selection": "all_authorized", "corporate_id": 1},
                          {"selection": "all_authorized", "lake_id": "other"},
                          {"selection": "all_authorized", "max_company_ids": 10000},
                          {"selection": "all_authorized", "mode": "full_dump_async"}):
            with self.subTest(variables=variables):
                self.assert_code("selector_invalid", page_contract.build_scope_page,
                                 variables, None)

    def test_native_page_cannot_be_substituted_by_bounded_or_bare_input(self):
        for source in (None, [], envelope(), {"records": [row()]}):
            self.assert_code("source_invalid", page_contract.build_scope_page,
                             {"selection": "all_authorized"}, source)
        for name, value in (("input_mode", "bounded_query"), ("source", "direct"),
                            ("authority", "caller"), ("node_key", "another_node"),
                            ("lake_id", "https://private.invalid")):
            source = native_page()
            source["provenance"][name] = value
            self.assert_code("source_invalid", page_contract.build_scope_page,
                             {"selection": "all_authorized"}, source)

    def test_native_page_positions_and_page_count_are_strict(self):
        for name in ("page_index", "record_offset", "pages_read"):
            for value in (None, True, False, -1, "1", 1.0, [], {}, 2**63):
                source = native_page()
                source["provenance"][name] = value
                self.assert_code("source_invalid", page_contract.build_scope_page,
                                 {"selection": "all_authorized"}, source)
        for pages in (0, 2):
            source = native_page()
            source["provenance"]["pages_read"] = pages
            self.assert_code("source_invalid", page_contract.build_scope_page,
                             {"selection": "all_authorized"}, source)
        for index, offset in ((0, 1), (1, 0), (2, 1)):
            self.assert_code("source_invalid", page_contract.build_scope_page,
                {"selection": "all_authorized"}, native_page(page_index=index, record_offset=offset))

    def test_missing_or_extra_metadata_including_cursors_is_rejected(self):
        for key in ("page_index", "record_offset", "pages_read", "source", "lake_id"):
            source = native_page()
            del source["provenance"][key]
            self.assert_code("source_invalid", page_contract.build_scope_page,
                             {"selection": "all_authorized"}, source)
        for key in ("cursor", "next_cursor", "token", "provider_payload", "has_more"):
            for placement in ("top", "provenance"):
                source = native_page()
                target = source if placement == "top" else source["provenance"]
                target[key] = "PRIVATE_SENTINEL_DO_NOT_ECHO"
                self.assert_code("source_invalid", page_contract.build_scope_page,
                                 {"selection": "all_authorized"}, source)

    def test_caps_unknown_states_and_inconsistent_exactness_fail(self):
        for exactness, reason in (("partial", "client_pagination_cap_reached"),
                                 ("partial", "max_pages_reached"),
                                 ("partial", "max_rows_reached"),
                                 ("partial", "timeout_reached"),
                                 ("partial", "cursor_unavailable"),
                                 ("partial", None), ("unknown", None),
                                 ("exact", "more_pages_available")):
            source = native_page()
            source.update(exactness=exactness, partial_reason=reason)
            self.assert_code("source_incomplete", page_contract.build_scope_page,
                             {"selection": "all_authorized"}, source)

    def test_each_native_page_is_bounded_to_25_companies(self):
        records = [row(identifier) for identifier in range(1001, 1026)]
        result = page_contract.build_scope_page({"selection": "all_authorized"}, native_page(records))
        self.assertEqual(25, result["company_count"])
        self.assert_code("rows_invalid", page_contract.build_scope_page,
                         {"selection": "all_authorized"}, native_page(records + [row(1026)]))
        for count in (True, 25.0, -1, 0, 26):
            source = native_page(records)
            source["row_count"] = count
            self.assert_code("source_invalid", page_contract.build_scope_page,
                             {"selection": "all_authorized"}, source)

    def test_shared_company_validation_applies_to_native_pages(self):
        wrong_corporate = row(1002)
        wrong_corporate["corporate_id"] = 2
        unsafe = row(1002)
        unsafe["remember_token"] = "PRIVATE_SENTINEL_DO_NOT_ECHO"
        bad_name = row(1002)
        bad_name["company"] = ""
        for records, code in (([row(1001), row(1001)], "row_duplicate"),
                              ([row(1001), wrong_corporate], "corporate_scope_mismatch"),
                              ([row(1001), unsafe], "row_fields_invalid"),
                              ([row(1001), bad_name], "row_value_invalid"),
                              ([None], "rows_invalid")):
            self.assert_code(code, page_adapter.CompanyScopeFullDumpAdapter().invoke,
                             inputs(native_page(records)), {})

    def test_retry_output_is_deterministic_and_page_digest_binds_position(self):
        source = native_page()
        result = page_contract.build_scope_page({"selection": "all_authorized"}, source)
        self.assertEqual(result, page_contract.build_scope_page({"selection": "all_authorized"}, source))
        unhashed = {key: value for key, value in result.items() if key != "digest"}
        self.assertEqual(result["digest"], contract.canonical_digest(unhashed))
        next_position = copy.deepcopy(source)
        next_position["provenance"].update(page_index=1, record_offset=2)
        moved = page_contract.build_scope_page({"selection": "all_authorized"}, next_position)
        self.assertNotEqual(result["digest"], moved["digest"])
        self.assertEqual(result["contexts"], moved["contexts"])
        result["contexts"][0]["source"]["node_key"] = "Changed output"
        fresh = page_contract.build_scope_page({"selection": "all_authorized"}, source)
        self.assertEqual("companies", fresh["contexts"][0]["source"]["node_key"])

    def test_page_execution_is_stateless_and_does_not_invoke_runtime_helpers(self):
        class NoInvocationInputs(dict):
            def forbidden(self, *args, **kwargs):
                raise AssertionError("Scope projects one page only")
            invoke = invoke_agent = invoke_asset = invoke_tool = forbidden
        adapter = page_adapter.CompanyScopeFullDumpAdapter()
        request = NoInvocationInputs(inputs())
        first = adapter.invoke(request, {"input_page_continuation": "PRIVATE_SENTINEL_DO_NOT_ECHO"})
        last = adapter.invoke(inputs(native_page([row(1003)], final=True,
                                                 page_index=1, record_offset=2)), {})
        self.assertEqual(2, first["outputs"]["company_scope_page"]["company_count"])
        self.assertEqual(1, last["outputs"]["company_scope_page"]["company_count"])
        summary = first["outputs"]["company_scope_summary"]
        self.assertEqual("framework_owned", summary["selection_completion"])
        self.assertTrue(all(type(value) in (str, int, bool) for value in summary.values()))
        self.assertNotIn("Synthetic", json.dumps(summary))
        self.assertNotIn("1001", json.dumps(summary))
        for name in ("agent_call_count", "child_call_count", "adapter_query_call_count",
                     "mutable_dynamic_skill_call_count"):
            self.assertEqual(0, first["metrics"][name])
        self.assertEqual(first, adapter.invoke(request, {}))

    def test_roles_and_legacy_bounded_contract_remain_separate(self):
        for request in (None, [], {}, {"variables": {"selection": "all_authorized"}},
                        dict(inputs(), memory={})):
            self.assert_code("input_invalid", page_adapter.CompanyScopeFullDumpAdapter().invoke, request, {})
        self.assert_code("selector_invalid", contract.build_scope_result,
                         {"selection": "all_authorized"}, native_page())
        self.assert_code("source_incomplete", contract.build_scope_result,
                         {"company_ids": [1001, 1002]}, native_page())


class CompanyScopeFullDumpPackagingTests(unittest.TestCase):
    def test_manifest_has_distinct_versions_and_keeps_binding_authority(self):
        manifest = json.loads((ASSET / "company_scope.asset.json").read_text())
        self.assertEqual("0.1.1", manifest["default"])
        self.assertEqual({"0.1.0", "0.1.1"}, set(manifest["versions"]))
        self.assertFalse(manifest["versions"]["0.1.0"]["allow_resume"])
        current = manifest["versions"]["0.1.1"]
        self.assertTrue(current["allow_resume"])
        self.assertEqual({"required": True, "source": "binding", "shape": "object"}, current["inputs"]["companies"])
        self.assertEqual({"company_scope_page", "company_scope_summary"}, set(current["outputs"]))
        for forbidden in ("agents", "callable", "callable_assets", "runtime_tools", "runtime_skills"):
            self.assertNotIn(forbidden, current)

    def test_new_runtime_files_have_no_network_persistence_or_paging_loop(self):
        allowed = {"__future__", "typing", "adapters.base", "scope_contract", "scope_page_contract"}
        for filename in ("scope_page_contract.py", "company_scope_full_dump_adapter.py"):
            for node in ast.walk(ast.parse((ASSET / filename).read_text())):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertIn(alias.name, allowed)
                elif isinstance(node, ast.ImportFrom):
                    self.assertIn(node.module, allowed)
                elif isinstance(node, ast.While):
                    self.fail("Full-dump paging belongs to Assets/Core")
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        self.assertNotIn(node.func.attr, {"invoke", "invoke_agent", "invoke_asset",
                                                        "invoke_tool", "connect", "execute", "write_text"})
                    elif isinstance(node.func, ast.Name):
                        self.assertNotEqual("open", node.func.id)

    def test_both_version_imports_work_with_only_declared_runtime_files(self):
        for packaged in (False, True):
            with self.subTest(packaged=packaged), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "adapters").mkdir()
                (root / "adapters/__init__.py").write_text("")
                shutil.copy2(ROOT / "adapters/nusaibah/pharma_company_intelligence_lab/tests/stubs/adapters/base.py",
                             root / "adapters/base.py")
                destination = root
                prefix = ""
                if packaged:
                    destination = root / "adapters/intake/nusaibah/company_scope"
                    destination.mkdir(parents=True)
                    for folder in (destination, destination.parent, destination.parent.parent):
                        (folder / "__init__.py").write_text("")
                    prefix = "adapters.intake.nusaibah.company_scope."
                for filename in ("company_scope_adapter.py", "scope_contract.py",
                                 "company_scope_full_dump_adapter.py", "scope_page_contract.py"):
                    shutil.copy2(ASSET / filename, destination / filename)
                code = f"""
import importlib, json, sys
before = list(sys.path)
old = importlib.import_module({(prefix + 'company_scope_adapter')!r})
new = importlib.import_module({(prefix + 'company_scope_full_dump_adapter')!r})
assert before == sys.path
assert old.CompanyScopeAdapter.version == '0.1.0'
assert new.CompanyScopeFullDumpAdapter.version == '0.1.1'
legacy = old.CompanyScopeAdapter().invoke(json.loads({json.dumps({'variables': {'company_id': 1001}, 'companies': envelope()})!r}), {{}})
page = new.CompanyScopeFullDumpAdapter().invoke(json.loads({json.dumps(inputs())!r}), {{}})
assert legacy['outputs']['company_scope_result']['complete'] is True
assert page['outputs']['company_scope_page']['selection_complete'] is None
assert page['outputs']['company_scope_page']['source_exhausted'] is False
"""
                environment = os.environ.copy()
                environment.pop("PYTHONPATH", None)
                environment["PYTHONDONTWRITEBYTECODE"] = "1"
                result = subprocess.run([sys.executable, "-c", code], cwd=root, env=environment,
                                        capture_output=True, text=True, timeout=20)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_native_synthetic_fixture_is_not_promoted(self):
        fixture = json.loads((ASSET / "tests/fixtures/synthetic-full-dump-page.inputs.json").read_text())
        result = page_adapter.CompanyScopeFullDumpAdapter().invoke(fixture, {})
        self.assertTrue(result["outputs"]["company_scope_page"]["batch_complete"])
        promotion = (ASSET / "adapter.yaml").read_text()
        self.assertNotIn("synthetic-full-dump-page.inputs.json", promotion)
        self.assertIn("company_scope_adapter.py", promotion)
        self.assertIn("company_scope_full_dump_adapter.py", promotion)
        self.assertIn("scope_page_contract.py", promotion)
        self.assertIn("allow_raw_fixtures: false", promotion)


if __name__ == "__main__":
    unittest.main()
