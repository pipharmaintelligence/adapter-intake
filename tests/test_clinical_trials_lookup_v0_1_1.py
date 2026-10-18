"""Reference-based results and advisory 2 MiB sizing; no provider calls."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import unittest
from test_clinical_trials_lookup import ASSET, FakeInputs, STUDY, search_page, module as legacy

spec = importlib.util.spec_from_file_location("clinical_lookup_v011", ASSET / "clinical_trials_lookup_v0_1_1_adapter.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def invoke(study, operation="results_get"):
    inputs = FakeInputs({"records": [study]})
    inputs["variables"] = {"operation": operation, "nct_id": "NCT01234567"}
    return module.ClinicalTrialsLookupAdapter().invoke(inputs, {})["outputs"]["trial_result"]


def dereference(record, ref):
    value = record
    for token in ref["json_pointer"][1:].split("/"):
        value = value[token.replace("~1", "/").replace("~0", "~")]
    digest = "sha256:" + hashlib.sha256(module._json(value)).hexdigest()
    if digest != ref["content_digest"]:
        raise AssertionError("Reference digest mismatch")
    return value


class ClinicalTrialsLookupV011Tests(unittest.TestCase):
    def test_all_publication_templates_accept_size_diagnostics(self):
        from jsonschema import Draft202012Validator
        definitions = json.loads((ASSET / "capabilities.v0.1.1.json").read_text())["capabilities"]
        for capability in definitions.values():
            operation = capability["operation"]
            variables = {"operation": operation}
            if operation == "study_search":
                variables["text"] = "Synthetic"
            elif operation == "study_batch":
                variables["nct_ids"] = ["NCT01234567"]
            elif operation != "describe":
                variables["nct_id"] = "NCT01234567"
            response = search_page(STUDY) if operation in {"study_search", "study_batch"} else {"records": [STUDY]}
            inputs = FakeInputs(response)
            inputs["variables"] = variables
            result = module.ClinicalTrialsLookupAdapter().invoke(inputs, {})["outputs"]["trial_result"]
            errors = [e.validator for e in Draft202012Validator(capability["remote_mcp"]["output_schema"]).iter_errors({"trial_result": result})]
            self.assertEqual([], errors, operation)

    def test_results_retains_native_study_once_and_references_exact_arrays(self):
        study = deepcopy(STUDY)
        study["resultsSection"]["participantFlowModule"]["groups"] = [{"id": "FLOW_1", "title": "Flow group"}]
        result = invoke(study)
        record = result["records"][0]
        self.assertEqual(study, record["registry_study"])
        self.assertNotIn("results_outcome_measures", record)
        self.assertNotIn("results_group_modules", record)
        self.assertEqual(study["resultsSection"]["outcomeMeasuresModule"]["outcomeMeasures"],
                         dereference(record, record["results_outcome_measures_ref"]))
        self.assertEqual(study["resultsSection"]["participantFlowModule"]["groups"],
                         dereference(record, record["results_group_module_refs"]["participantFlowModule"]["groups"]))
        self.assertEqual("posted", result["results_state"])
        self.assertEqual(len(module._json(result)), result["size_policy"]["result_bytes"])

    def test_reference_tokens_escape_native_module_and_field_names(self):
        study = deepcopy(STUDY)
        study["resultsSection"]["extension/a"] = {"named~Groups": [{"id": "GROUP_1"}]}
        result = invoke(study)
        record = result["records"][0]
        ref = record["results_group_module_refs"]["extension/a"]["named~Groups"]
        self.assertIn("extension~1a/named~0Groups", ref["json_pointer"])
        self.assertEqual([{"id": "GROUP_1"}], dereference(record, ref))

    def test_over_two_mib_warns_without_dropping_fields_or_failing(self):
        study = deepcopy(STUDY)
        text = "أ" * 1_100_000
        study["protocolSection"]["descriptionModule"]["briefSummary"] = text
        result = invoke(study, "study_get")
        self.assertEqual(text, result["records"][0]["registry_study"]["protocolSection"]["descriptionModule"]["briefSummary"])
        self.assertTrue(result["size_policy"]["threshold_exceeded"])
        self.assertEqual(2 * 1024 * 1024, result["size_policy"]["warning_threshold_bytes"])
        self.assertEqual(len(module._json(result)), result["size_policy"]["result_bytes"])
        self.assertEqual("clinical_trials_result_size_warning", result["warnings"][0]["code"])

    def test_realistic_result_over_old_cap_succeeds_without_warning(self):
        study = deepcopy(STUDY)
        study["resultsSection"]["outcomeMeasuresModule"]["outcomeMeasures"][0]["description"] = "x" * 310_000
        result = invoke(study)
        self.assertFalse(result["size_policy"]["threshold_exceeded"])
        self.assertEqual([], result["warnings"])
        self.assertEqual(study["resultsSection"], result["records"][0]["registry_study"]["resultsSection"])

    def test_legacy_version_and_convenience_contract_remain_available(self):
        inputs = FakeInputs({"records": [STUDY]})
        inputs["variables"] = {"operation": "results_get", "nct_id": "NCT01234567"}
        result = legacy.ClinicalTrialsLookupAdapter().invoke(inputs, {})["outputs"]["trial_result"]
        self.assertEqual("0.1.0", legacy.ClinicalTrialsLookupAdapter.version)
        self.assertIn("results_outcome_measures", result["records"][0])
        self.assertEqual("0.1.1", module.ClinicalTrialsLookupAdapter.version)
        manifest = json.loads((ASSET / "clinical_trials_lookup_v0_1_1.asset.json").read_text())
        self.assertEqual(16 * 1024 * 1024, manifest["versions"]["0.1.1"]["callable"]["max_result_bytes"])

    def test_missing_results_do_not_create_dangling_references(self):
        study = deepcopy(STUDY)
        study.pop("resultsSection")
        study["hasResults"] = False
        result = invoke(study)
        self.assertEqual("not_posted", result["results_state"])
        self.assertIsNone(result["records"][0]["results_outcome_measures_ref"])
        self.assertEqual({}, result["records"][0]["results_group_module_refs"])

    def test_no_match_is_distinct_from_invalid_or_wrong_identity(self):
        empty = FakeInputs({"records": []})
        empty["variables"] = {"operation": "study_get", "nct_id": "NCT01234567"}
        result = module.ClinicalTrialsLookupAdapter().invoke(empty, {})["outputs"]["trial_result"]
        self.assertEqual("no_match", result["status"])
        self.assertEqual(0, result["record_count"])
        for variables in ({"operation": "study_get"}, {"operation": "study_get", "nct_id": "invalid"}):
            inputs = FakeInputs({"records": []})
            inputs["variables"] = variables
            with self.assertRaisesRegex(ValueError, "clinical_trials_nct_id_invalid"):
                module.ClinicalTrialsLookupAdapter().invoke(inputs, {})
            self.assertEqual([], inputs.calls)
        for returned_id, code in ((None, "clinical_trials_nct_id_invalid"),
                                  ("NCT07654321", "clinical_trials_detail_identity_mismatch")):
            study = deepcopy(STUDY)
            study["protocolSection"]["identificationModule"]["nctId"] = returned_id
            with self.assertRaisesRegex(ValueError, code):
                invoke(study)

    def test_unknown_results_and_malformed_response_never_become_no_match(self):
        study = deepcopy(STUDY)
        study.pop("resultsSection")
        result = invoke(study)
        self.assertEqual("not_present_in_record", result["results_state"])
        malformed = FakeInputs({"records": None})
        malformed["variables"] = {"operation": "study_get", "nct_id": "NCT01234567"}
        with self.assertRaisesRegex(ValueError, "clinical_trials_runtime_source_shape_invalid"):
            module.ClinicalTrialsLookupAdapter().invoke(malformed, {})


if __name__ == "__main__":
    unittest.main()
