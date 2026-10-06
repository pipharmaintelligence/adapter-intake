from __future__ import annotations

import copy
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "adapters" / "nusaibah"
TOOL = ASSETS / "structured_review_toolkit"
PACKAGE = "_shared_review_toolkit_tests"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(TOOL)]
sys.modules[PACKAGE] = package


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ops = load_module(TOOL / "tool_operations.py", PACKAGE + ".tool_operations")
verification = sys.modules[PACKAGE + ".evidence_verification"]
tool_adapter = load_module(TOOL / "structured_review_toolkit_adapter.py", PACKAGE + ".adapter")


def fixture(kind: str = "company") -> tuple[dict, dict]:
    if kind == "company":
        entity, method, requirement = "synthetic-company:ficta", "demo.company-identity", "company.identity"
        text = "Ficta Therapeutics is a synthetic company."
    else:
        entity, method, requirement = "synthetic-policy:retention", "demo.policy-obligations", "policy.retention"
        text = "Synthetic audit records must be retained for 30 days."
    source = {"entity_id": entity, "source_id": "fixture-document", "source_version": "1",
              "extraction_version": "fixture-text-v1", "units": [{"locator": "p1", "text": text}]}
    policy = {"max_chars": 6000, "neighbor_units": 0}
    prepared = ops.prepare_sources({"source": source, "policy": policy})
    source_hash = prepared["inventory"]["source_hash"]
    span = {"ref": "e1", "entity_id": entity, "source_hash": source_hash,
            "locator": "p1", "start": 0, "end": len(text), "quote": text}
    finding = {"schema_version": "review_finding.v1", "finding_id": "f1", "entity_id": entity,
               "requirement_id": requirement, "section_id": "identity" if kind == "company" else "retention",
               "proposition_id": "fixture-fact", "polarity": "affirmed", "statement": text,
               "evidence_refs": ["e1"], "contradicting_evidence_refs": [], "evidence_state": "supported",
               "evidence_strength": "inspected_span", "observed_or_inferred": "observed", "date": None,
               "jurisdiction": None, "high_impact": False, "verification_reason": "Synthetic fixture assertion only."}
    verdict = {"schema_version": "review_semantic_verdict.v1", "finding_id": "f1", "evidence_refs": ["e1"],
               "input_digest": verification.finding_semantic_input_digest(finding, {"e1": {**span, "strength": "inspected_span"}}),
               "state": "supported", "verifier_id": "synthetic-fixture", "reason_code": "fixture_assertion"}
    coverage = [{"schema_version": "review_coverage.v1", "obligation_type": category,
                 "obligation_id": identifier, "status": "reviewed", "outcome": "supported",
                 "reason": "Synthetic structural fixture.", "task_ids": ["task1"]}
                for category, identifier in (("requirement", requirement), ("source_unit", "p1"))]
    result = {"schema_version": "review_result.v1", "scope_mode": "focused", "execution_state": "completed",
              "review_outcome": "review_complete", "coverage": coverage, "finding_ids": ["f1"],
              "limitations": ["Fixture verdict is not independent domain adjudication."], "persistence_state": "preview_only"}
    values = {"source": source, "policy": policy, "source_hash": source_hash, "evidence": [span],
              "findings": [finding], "semantic_verdicts": [verdict], "result": result}
    return values, {"ref": method, "version": "1.0.0", "requirements": [requirement]}


def request(values: dict, methodology: dict, operation: str = "assemble_preview") -> dict:
    return {"schema_version": "review_tool_request.v1", "operation": operation,
            "arguments": copy.deepcopy({**values, "methodology": methodology})}


def bind_fixture_verdicts(values: dict) -> None:
    index = {span["ref"]: {**span, "strength": "inspected_span"} for span in values["evidence"]}
    for finding, verdict in zip(values["findings"], values["semantic_verdicts"]):
        verdict["finding_id"] = finding["finding_id"]
        verdict["evidence_refs"] = list(finding["evidence_refs"])
        verdict["input_digest"] = verification.finding_semantic_input_digest(finding, index)


class SharedReviewToolkitTests(unittest.TestCase):
    def setUp(self):
        self.values, self.methodology = fixture()

    def evaluate(self, values=None):
        return ops.execute_operation(request(values or self.values, self.methodology))

    def test_same_tool_assembles_both_domains_without_domain_dispatch(self):
        for kind in ("company", "policy"):
            with self.subTest(kind=kind):
                values, method = fixture(kind)
                output = ops.execute_operation(request(values, method))
                self.assertEqual(values["findings"][0]["statement"], output["output"]["dossier"][0]["statement"])
                self.assertFalse(output["output"]["publication_allowed"])
                self.assertFalse(output["output"]["semantic_authority_verified"])
                self.assertFalse(output["output"]["external_truth_verified"])
                self.assertEqual(0, output["agent_call_count"])

    def test_six_operations_are_closed_and_unsupported_operation_rejected(self):
        self.assertEqual(6, len(ops.OPERATIONS))
        for operation in ("shell", "invoke_agent", [], "publish"):
            invalid = request(self.values, self.methodology)
            invalid["operation"] = operation
            with self.assertRaises(ops.ReviewToolError):
                ops.execute_operation(invalid)

    def test_all_data_operation_interfaces_reject_unrelated_operation_arguments(self):
        arguments = {**self.values, "methodology": self.methodology}
        schemas = {
            "prepare_sources": {"source", "policy"},
            "verify_findings": {"source", "policy", "source_hash", "methodology", "evidence", "findings", "semantic_verdicts"},
            "check_coverage": {"source", "policy", "source_hash", "methodology", "result"},
            "reconcile_findings": {"source", "policy", "source_hash", "methodology", "evidence", "findings", "semantic_verdicts"},
        }
        for operation, keys in schemas.items():
            value = {"schema_version": "review_tool_request.v1", "operation": operation,
                     "arguments": {key: arguments[key] for key in keys}}
            output = ops.execute_operation(value)
            self.assertEqual(operation, output["operation"])
            value["arguments"]["selected_memory_ids"] = []
            with self.assertRaises(ops.ReviewToolError):
                ops.execute_operation(value)

    def test_unsupported_schema_and_extra_fields_rejected(self):
        for update in ({"schema_version": "review_tool_request.v2"}, {"publication_allowed": True}):
            invalid = request(self.values, self.methodology)
            invalid.update(update)
            with self.assertRaises(ops.ReviewToolError):
                ops.execute_operation(invalid)

    def test_nested_authority_material_never_enters_tool(self):
        for key in ("credentials", "callback", "storage_path", "_obs_agent_bridge"):
            invalid = request(self.values, self.methodology)
            invalid["arguments"]["source"]["units"][0][key] = "forbidden-value"
            with self.assertRaisesRegex(ops.ReviewToolError, "authority_forbidden") as caught:
                ops.execute_operation(invalid)
            self.assertNotIn("forbidden-value", str(caught.exception))

    def test_non_json_and_nonfinite_numbers_rejected(self):
        for value in (float("nan"), float("inf"), object()):
            invalid = request(self.values, self.methodology)
            invalid["arguments"]["source"]["units"][0]["text"] = value
            with self.assertRaises(ops.ReviewToolError):
                ops.execute_operation(invalid)

    def test_input_byte_and_output_byte_caps_fail_without_truncation(self):
        invalid = request(self.values, self.methodology)
        invalid["arguments"]["source"]["units"][0]["text"] = "x" * ops.MAX_INPUT_BYTES
        with self.assertRaisesRegex(ops.ReviewToolError, "input_size_limit"):
            ops.execute_operation(invalid)
        with patch.object(ops, "MAX_RESULT_BYTES", 64):
            with self.assertRaisesRegex(ops.ReviewToolError, "result_size_limit"):
                self.evaluate()

    def test_unicode_chunk_amplification_hits_actual_result_byte_cap(self):
        source = copy.deepcopy(self.values["source"])
        source["units"] = [{"locator": f"p{i}", "text": "😀" * 700} for i in range(32)]
        with self.assertRaisesRegex(ops.ReviewToolError, "result_size_limit"):
            ops.execute_operation({"schema_version": "review_tool_request.v1", "operation": "prepare_sources",
                                   "arguments": {"source": source, "policy": {"max_chars": 6000, "neighbor_units": 4}}})

    def test_input_mutation_after_snapshot_does_not_change_hash_or_result(self):
        original = request(self.values, self.methodology)
        expected = copy.deepcopy(original)
        implementation = ops._EXECUTORS["assemble_preview"]
        def mutate(arguments):
            original["arguments"]["findings"][0]["statement"] = "Changed after snapshot"
            return implementation(arguments)
        with patch.dict(ops._EXECUTORS, {"assemble_preview": mutate}):
            output = ops.execute_operation(original)
        self.assertEqual(ops.stable_digest(expected), output["request_digest"])
        self.assertEqual(expected["arguments"]["findings"][0]["statement"], output["output"]["dossier"][0]["statement"])

    def test_boolean_chunk_limits_and_context_flags_are_rejected(self):
        for path in ("max_chars", "neighbor_units"):
            values = copy.deepcopy(self.values)
            values["policy"][path] = True
            with self.assertRaises(ops.ReviewToolError):
                self.evaluate(values)
        values = copy.deepcopy(self.values)
        values["source"]["units"][0]["context_only"] = "false"
        with self.assertRaises(ops.ReviewToolError):
            self.evaluate(values)

    def test_source_and_unit_limits_reject_before_partial_output(self):
        for text in ("x" * 6001, "x" * 24001):
            source = copy.deepcopy(self.values["source"])
            source["units"][0]["text"] = text
            with self.assertRaises(ValueError):
                ops.prepare_sources({"source": source, "policy": self.values["policy"]})
        source = copy.deepcopy(self.values["source"])
        source["units"] = [{"locator": f"p{i}", "text": "x"} for i in range(33)]
        with self.assertRaises(ops.ReviewToolError):
            ops.prepare_sources({"source": source, "policy": self.values["policy"]})

    def test_transitive_footnote_context_and_cycles_are_bounded_and_preserved(self):
        source = copy.deepcopy(self.values["source"])
        source["units"] = [{"locator": "row", "text": "value", "related_locators": ["header"]},
                           {"locator": "header", "text": "period", "related_locators": ["footnote"]},
                           {"locator": "footnote", "text": "qualification", "related_locators": ["row"]}]
        prepared = ops.prepare_sources({"source": source, "policy": self.values["policy"]})
        self.assertEqual(3, len(prepared["chunks"]))
        self.assertTrue(all(chunk["locators"] == ["row", "header", "footnote"] for chunk in prepared["chunks"]))

    def test_missing_or_inaccessible_required_structural_context_blocks(self):
        for related in ("missing", "header"):
            source = copy.deepcopy(self.values["source"])
            source["units"][0]["related_locators"] = [related]
            source["units"].append({"locator": "header", "text": "", "quality_flags": ["ocr_failed"]})
            with self.assertRaises(ValueError):
                ops.prepare_sources({"source": source, "policy": self.values["policy"]})

    def test_duplicate_source_locator_rejected(self):
        source = copy.deepcopy(self.values["source"])
        source["units"] *= 2
        with self.assertRaises(ValueError):
            ops.prepare_sources({"source": source, "policy": self.values["policy"]})

    def test_modified_source_digest_rejected(self):
        for changed in ("digest", "text", "version"):
            values = copy.deepcopy(self.values)
            if changed == "digest": values["source_hash"] = "0" * 64
            elif changed == "text": values["source"]["units"][0]["text"] += "changed"
            else: values["source"]["source_version"] = "2"
            with self.assertRaisesRegex(ops.ReviewToolError, "digest_mismatch"):
                self.evaluate(values)

    def test_exact_span_mismatch_and_boolean_offsets_rejected(self):
        for update in ({"quote": "invented"}, {"start": True}, {"end": 0}, {"locator": "unknown"}):
            values = copy.deepcopy(self.values)
            values["evidence"][0].update(update)
            with self.assertRaises(ops.ReviewToolError):
                self.evaluate(values)

    def test_unicode_span_offsets_use_original_python_character_indices(self):
        values = copy.deepcopy(self.values)
        text = "α😀e\u0301"
        values["source"]["units"][0]["text"] = text
        values["source_hash"] = ops.prepare_sources({"source": values["source"], "policy": values["policy"]})["inventory"]["source_hash"]
        values["evidence"][0].update(source_hash=values["source_hash"], end=len(text), quote=text)
        values["findings"][0]["statement"] = text
        span = {**values["evidence"][0], "strength": "inspected_span"}
        values["semantic_verdicts"][0]["input_digest"] = verification.finding_semantic_input_digest(values["findings"][0], {"e1": span})
        self.assertEqual(text, self.evaluate(values)["output"]["dossier"][0]["statement"])

    def test_cross_entity_finding_and_evidence_rejected(self):
        for field in ("findings", "evidence"):
            values = copy.deepcopy(self.values)
            values[field][0]["entity_id"] = "synthetic-company:other"
            with self.assertRaises(ops.ReviewToolError):
                self.evaluate(values)

    def test_context_only_units_cannot_become_primary_evidence(self):
        values = copy.deepcopy(self.values)
        values["source"]["units"][0]["context_only"] = True
        values["source_hash"] = ops.prepare_sources({"source": values["source"], "policy": values["policy"]})["inventory"]["source_hash"]
        values["evidence"][0]["source_hash"] = values["source_hash"]
        with self.assertRaisesRegex(ops.ReviewToolError, "evidence_locator_invalid"):
            self.evaluate(values)

    def test_duplicate_evidence_findings_or_verdicts_rejected(self):
        for field in ("evidence", "findings", "semantic_verdicts"):
            values = copy.deepcopy(self.values)
            values[field] *= 2
            with self.assertRaises(ops.ReviewToolError):
                self.evaluate(values)

    def test_missing_or_unbound_semantic_verdict_rejected(self):
        for field in ("missing", "digest", "statement"):
            values = copy.deepcopy(self.values)
            if field == "missing": values["semantic_verdicts"] = []
            elif field == "digest": values["semantic_verdicts"][0]["input_digest"] = "sha256:" + "0" * 64
            else: values["findings"][0]["statement"] = "Unsupported mutation"
            with self.assertRaises(ops.ReviewToolError):
                self.evaluate(values)

    def test_unknown_requirement_and_forged_high_impact_boolean_rejected(self):
        for update in ({"requirement_id": "other.requirement"}, {"high_impact": 1}):
            values = copy.deepcopy(self.values)
            values["findings"][0].update(update)
            with self.assertRaises(ops.ReviewToolError):
                self.evaluate(values)

    def test_inspected_evidence_cannot_be_mislabeled_as_memory_strength(self):
        for strength in ("reference_only", "memory_context"):
            values = copy.deepcopy(self.values)
            values["findings"][0]["evidence_strength"] = strength
            bind_fixture_verdicts(values)
            with self.assertRaisesRegex(ops.ReviewToolError, "strength_mismatch"):
                self.evaluate(values)

    def test_positive_supplied_verdict_cannot_upgrade_nonpositive_finding(self):
        for state in ("insufficient", "contradicted", "not_applicable"):
            values = copy.deepcopy(self.values)
            values["findings"][0]["evidence_state"] = state
            bind_fixture_verdicts(values)
            values["result"].update(execution_state="incomplete", review_outcome="review_incomplete", finding_ids=[])
            values["result"]["coverage"][0]["outcome"] = "insufficient"
            output = self.evaluate(values)["output"]
            self.assertEqual([], output["dossier"])
            self.assertEqual([], output["ledger"]["accepted_finding_ids"])
            self.assertEqual(["f1"], output["withheld_finding_ids"])

    def test_missing_duplicate_or_extra_coverage_is_rejected(self):
        for change in ("missing", "duplicate", "extra"):
            values = copy.deepcopy(self.values)
            if change == "missing": values["result"]["coverage"].pop()
            else:
                added = copy.deepcopy(values["result"]["coverage"][0])
                if change == "extra": added["obligation_id"] = "unknown"
                values["result"]["coverage"].append(added)
            with self.assertRaises(ops.ReviewToolError):
                self.evaluate(values)

    def test_unreviewed_coverage_cannot_claim_complete(self):
        values = copy.deepcopy(self.values)
        values["result"]["coverage"][0].update(status="unreviewed", outcome=None)
        with self.assertRaises(ops.ReviewToolError):
            self.evaluate(values)

    def test_insufficient_supported_and_false_gap_states_rejected(self):
        values = copy.deepcopy(self.values)
        values["result"]["coverage"][0]["outcome"] = "insufficient"
        with self.assertRaisesRegex(ops.ReviewToolError, "false_complete"):
            self.evaluate(values)
        values = copy.deepcopy(self.values)
        values["result"]["review_outcome"] = "review_complete_with_evidence_gaps"
        with self.assertRaisesRegex(ops.ReviewToolError, "false_gap_state"):
            self.evaluate(values)

    def test_terminal_execution_and_review_states_must_agree_in_both_directions(self):
        for state, outcome in (("completed", "failed"), ("completed", "blocked"),
                               ("completed", "review_incomplete"), ("incomplete", "failed")):
            values = copy.deepcopy(self.values)
            values["result"].update(execution_state=state, review_outcome=outcome)
            with self.assertRaises(ops.ReviewToolError):
                self.evaluate(values)

    def test_accepted_finding_cannot_use_unreviewed_or_not_applicable_obligations(self):
        for category in ("source_unit", "requirement"):
            for state, outcome in (("unreviewed", None), ("reviewed", "not_applicable")):
                values = copy.deepcopy(self.values)
                values["result"].update(execution_state="incomplete", review_outcome="review_incomplete")
                item = next(item for item in values["result"]["coverage"] if item["obligation_type"] == category)
                item.update(status=state, outcome=outcome)
                with self.assertRaisesRegex(ops.ReviewToolError, "coverage_mismatch"):
                    self.evaluate(values)

    def test_withheld_findings_cannot_hide_behind_another_supported_finding(self):
        values = copy.deepcopy(self.values)
        values["findings"].append({**values["findings"][0], "finding_id": "f2", "proposition_id": "other-fact"})
        values["semantic_verdicts"].append({**values["semantic_verdicts"][0], "state": "insufficient"})
        bind_fixture_verdicts(values)
        with self.assertRaisesRegex(ops.ReviewToolError, "gap_hidden"):
            self.evaluate(values)
        values["result"]["coverage"][0]["outcome"] = "insufficient"
        values["result"]["review_outcome"] = "review_complete_with_evidence_gaps"
        output = self.evaluate(values)["output"]
        self.assertEqual(1, output["gap_count"])
        self.assertEqual(["f2"], output["withheld_finding_ids"])
        self.assertEqual(["f1"], [item["finding_id"] for item in output["dossier"]])

    def test_date_jurisdiction_and_opposed_claims_block_complete_preview(self):
        for update in ({"date": "2026-01-01"}, {"jurisdiction": "fixture-country"}, {"polarity": "negated"}):
            values = copy.deepcopy(self.values)
            values["findings"].append({**values["findings"][0], "finding_id": "f2", **update})
            values["semantic_verdicts"].append(copy.deepcopy(values["semantic_verdicts"][0]))
            values["result"]["finding_ids"].append("f2")
            bind_fixture_verdicts(values)
            with self.assertRaisesRegex(ops.ReviewToolError, "unresolved_conflict"):
                self.evaluate(values)
    def test_mutation_and_final_finding_injection_rejected(self):
        for update in ({"persistence_state": "applied"}, {"finding_ids": ["f1", "new"]}):
            values = copy.deepcopy(self.values)
            values["result"].update(update)
            with self.assertRaises(ops.ReviewToolError):
                self.evaluate(values)

    def test_contradicted_verdict_remains_withheld_and_gaps_are_explicit(self):
        values = copy.deepcopy(self.values)
        values["semantic_verdicts"][0]["state"] = "contradicted"
        values["result"]["finding_ids"] = []
        values["result"]["review_outcome"] = "review_incomplete"
        values["result"]["execution_state"] = "incomplete"
        values["result"]["coverage"][0]["outcome"] = "contradicted"
        result = self.evaluate(values)["output"]
        self.assertEqual([], result["dossier"])
        self.assertEqual(["f1"], result["withheld_finding_ids"])

    def test_packet_selection_preserves_only_declared_memory_and_generic_rules(self):
        entity = self.values["source"]["entity_id"]
        arguments = {"entity_id": entity, "role": "identity-review", "requirement_ids": ["company.identity"],
                     "allowed_section_ids": ["identity"], "global_rules": {key: "Fixture rule" for key in (
                         "entity_isolation", "evidence_attribution", "uncertainty", "mutation_prohibition")},
                     "domain_rules": ["Synthetic identity only"], "memory_records": [
                         {"memory_id": "m1", "entity_id": entity, "text": "Relevant"},
                         {"memory_id": "m2", "entity_id": entity, "text": "Unrelated"}],
                     "evidence_refs": ["e1"], "selected_memory_ids": ["m1"], "omitted_context_reasons": ["m2 outside scope"]}
        output = ops.execute_operation({"schema_version": "review_tool_request.v1", "operation": "prepare_packet", "arguments": arguments})
        self.assertEqual(["m1"], [item["memory_id"] for item in output["output"]["packet"]["selected_memory"]])
        arguments["memory_records"][1]["entity_id"] = "other"
        with self.assertRaises(ops.ReviewToolError):
            ops.execute_operation({"schema_version": "review_tool_request.v1", "operation": "prepare_packet", "arguments": arguments})

    def test_packet_rejects_coerced_memory_identity_and_nonlist_rule_text(self):
        entity = self.values["source"]["entity_id"]
        valid = {"entity_id": entity, "role": "identity-review", "requirement_ids": ["company.identity"],
                 "allowed_section_ids": ["identity"], "global_rules": {key: "Fixture rule" for key in (
                     "entity_isolation", "evidence_attribution", "uncertainty", "mutation_prohibition")},
                 "domain_rules": [], "memory_records": [{"memory_id": "m1", "entity_id": entity, "text": "Relevant"}],
                 "evidence_refs": [], "selected_memory_ids": ["m1"], "omitted_context_reasons": []}
        for field in ("domain_rules", "omitted_context_reasons", "memory_id", "unselected_authority"):
            invalid = copy.deepcopy(valid)
            if field in {"domain_rules", "omitted_context_reasons"}: invalid[field] = "characters are not a list"
            elif field == "memory_id": invalid["memory_records"][0]["memory_id"] = None
            else: invalid["memory_records"].append({"memory_id": "m2", "entity_id": entity, "text": "Unselected", "api_key": "x"})
            with self.assertRaises(ops.ReviewToolError):
                ops.execute_operation({"schema_version": "review_tool_request.v1", "operation": "prepare_packet", "arguments": invalid})


class ConsumerContractTests(unittest.TestCase):
    def test_both_consumers_invoke_the_same_tool_with_their_own_methodology(self):
        for kind in ("company", "policy"):
            slug = kind + "_review_tools_demo"
            module = load_module(ASSETS / slug / (slug + "_adapter.py"), "_consumer_" + kind)
            calls = []
            values, method = fixture(kind)
            class Inputs(dict):
                def invoke_asset(self, role, *, variables, on_error):
                    calls.append((role, copy.deepcopy(variables), on_error))
                    return {"status": "success", "result": ops.execute_operation(variables)}
            output = module.SyntheticReviewToolsDemoAdapter().invoke(Inputs(variables=values), {})
            self.assertEqual(1, len(calls))
            self.assertEqual("review_toolkit", calls[0][0])
            self.assertEqual(method, calls[0][1]["arguments"]["methodology"])
            self.assertFalse(output["outputs"]["review_preview"]["output"]["semantic_authority_verified"])

    def test_consumers_fail_without_an_invoker_or_with_wrong_entity(self):
        module = load_module(ASSETS / "company_review_tools_demo/company_review_tools_demo_adapter.py", "_consumer_fail")
        values, _ = fixture("policy")
        with self.assertRaisesRegex(ValueError, "entity_scope_invalid"):
            module.SyntheticReviewToolsDemoAdapter().invoke({"variables": values}, {})
        values, _ = fixture()
        with self.assertRaises(AttributeError):
            module.SyntheticReviewToolsDemoAdapter().invoke({"variables": values}, {})

    def test_consumers_reject_wrong_request_digest_or_overstated_authority(self):
        for kind in ("company", "policy"):
            slug = kind + "_review_tools_demo"
            module = load_module(ASSETS / slug / (slug + "_adapter.py"), "_consumer_authority_" + kind)
            values, _ = fixture(kind)
            for field in ("request_digest", "validation_scope", "agent_call_count", "publication_allowed",
                          "semantic_authority_verified", "external_truth_verified"):
                class Inputs(dict):
                    def invoke_asset(self, role, *, variables, on_error):
                        result = ops.execute_operation(variables)
                        target = result["output"] if field in {"publication_allowed", "semantic_authority_verified", "external_truth_verified"} else result
                        target[field] = True
                        return {"status": "success", "result": result}
                with self.assertRaisesRegex(ValueError, "tool_result_invalid"):
                    module.SyntheticReviewToolsDemoAdapter().invoke(Inputs(variables=values), {})
    def test_declarations_pin_one_toolkit_and_keep_it_a_leaf(self):
        for slug in ("company_review_tools_demo", "policy_review_tools_demo"):
            manifest = json.loads((ASSETS / slug / (slug + ".asset.json")).read_text())
            dependency = manifest["versions"]["0.1.0"]["callable_assets"]["review_toolkit"]
            self.assertEqual("nusaibah.structured_review_toolkit", dependency["asset_key"])
            self.assertEqual("0.1.0", dependency["asset_version"])
        manifest = json.loads((TOOL / "structured_review_toolkit.asset.json").read_text())
        version = manifest["versions"]["0.1.0"]
        self.assertTrue(version["callable"]["enabled"])
        self.assertNotIn("callable_assets", version)
        self.assertNotIn("agents", version)

    def test_package_imports_do_not_modify_sys_path(self):
        before = list(sys.path)
        load_module(TOOL / "structured_review_toolkit_adapter.py", PACKAGE + ".adapter_again")
        self.assertEqual(before, sys.path)

    def test_helper_modules_define_no_runtime_adapter_subclasses(self):
        import ast
        for path in TOOL.glob("*.py"):
            if path.name.endswith("_adapter.py"):
                continue
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ClassDef):
                    self.assertFalse(any(isinstance(base, ast.Name) and base.id == "Adapter" for base in node.bases))


if __name__ == "__main__":
    unittest.main()
