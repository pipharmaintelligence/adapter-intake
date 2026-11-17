"""Provider-free lake/node record-envelope mapping regressions."""
import unittest
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parent))
from clinical_failure_intelligence.contracts import ContractError, parse_request
from clinical_failure_intelligence.source_events import normalize_event_records
from clinical_failure_intelligence.product_memory import case_path


def event(eid="79", *, products=None, indications=None, trials=None,
          event_date="2021-10-25", result="Failed"):
    return {"schema_version":"clinical_event_source.v1","event_id":eid,
        "event_date":event_date,"phase":None,"result_text":result,
        "screening_label":"reported_negative","source_sub_category_id":"4",
        "products":products if products is not None else [
            {"product_id":"913","product_name":"SYNTH_A","association_role":"unresolved"}],
        "indications":indications if indications is not None else [
            {"designation_id":"3026","designation_label":"Synthetic indication A"}],
        "trials":trials if trials is not None else [{"kind":"nct","value":"NCT03626545"}],
        "association_scope":"event_level_not_pairwise_attributed","quality_flags":[],
        "source":{"file":"synthetic.xlsx","sheet":"S","excel_row":2},
        "raw_fields":{"id":eid}}


def envelope(*rows):
    return {"records":list(rows),"provenance":{"source_ref":"aib_synthetic",
        "object_ref":"synthetic_object","access_mode":"file_object",
        "materializer_key":"json_object","format":"json",
        "complete":True,"record_count":len(rows),"sha256":"a"*64}}


def variables(eids=None,**overrides):
    value={"schema_version":"clinical_analysis_request.v1","request_id":"RQ_A",
        "analysis_mode":"mechanistic_case","subject_id":"CASE_A",
        "as_of_date":"2025-01-01","event_ids":eids or ["79"],
        "product_id":"913","memory_mode":"preview",
        "enable_pharmacological_class":False}
    value.update(overrides)
    return value


class SourceEventMappingTests(unittest.TestCase):
    def mapped(self,*rows,values=None):
        return normalize_event_records(values or variables(),envelope(*rows))

    def rejects(self,code,values,source):
        with self.assertRaises(ContractError) as e:
            normalize_event_records(values,source)
        self.assertEqual(code,e.exception.code)

    def test_selected_source_not_promoted_to_evidence(self):
        result=self.mapped(event())
        self.assertEqual(["79"],result["event_ids"])
        self.assertEqual("913",result["subject"]["product_id"])
        self.assertEqual(["NCT03626545"],result["subject"]["trial_ids"])
        self.assertIsNone(result["case_scope"]["regimen_id"])
        self.assertEqual([],result["evidence"])
        self.assertFalse(result["source_event_metadata"]["clinical_outcome_adjudicated"])
        self.assertNotIn("raw_fields",str(result))

    def test_original_context_still_accepted(self):
        from fakes import FakeInputs, example_inputs
        legacy=example_inputs()
        self.assertEqual(legacy["clinical_context"]["context_id"],
                         parse_request(FakeInputs(legacy))["context"]["context_id"])

    def test_bound_records_accepted_by_existing_role(self):
        parsed=parse_request({"variables":variables(),"clinical_context":envelope(event())})
        self.assertEqual("913",parsed["context"]["subject"]["product_id"])
        self.assertEqual("context_",parsed["context"]["context_id"][:8])

    def test_multi_product_requires_explicit_product_and_no_causal_ownership(self):
        row=event(products=[{"product_id":"913","product_name":"A"},
                            {"product_id":"442","product_name":"B"}])
        left=self.mapped(row)
        right=self.mapped(row,values=variables(product_id="442"))
        self.assertEqual("442",right["subject"]["product_id"])
        self.assertEqual(["913","442"],left["source_event_metadata"]["events"][0]["all_product_ids"])
        self.assertFalse(right["source_event_metadata"]["pairwise_attribution_verified"])

    def test_missing_product_selector_fails(self):
        v=variables();v.pop("product_id")
        self.rejects("clinical_id_invalid",v,envelope(event()))

    def test_indication_ambiguity_fails_closed(self):
        row=event(indications=[{"designation_id":"3026","designation_label":"A"},
                               {"designation_id":"3027","designation_label":"B"}])
        self.rejects("clinical_source_selector_ambiguous",variables(),envelope(row))
        self.assertEqual("B",self.mapped(row,values=variables(indication_id="3027"))["subject"]["indication"])

    def test_trial_ambiguity_fails_closed(self):
        row=event(trials=[{"kind":"nct","value":"NCT03626545"},
                          {"kind":"nct","value":"NCT03626546"}])
        self.rejects("clinical_source_trial_selector_ambiguous",variables(),envelope(row))
        self.assertEqual(["NCT03626546"],
            self.mapped(row,values=variables(trial_id="NCT03626546"))["subject"]["trial_ids"])

    def test_missing_trial_uses_event_scope_without_fake_nct(self):
        result=self.mapped(event(trials=[]))
        self.assertEqual([],result["subject"]["trial_ids"])
        self.assertEqual("79",result["case_scope"]["event_id"])
        self.assertIn("Event 79 trial unreported",
                      case_path({"context":result}))
        self.assertIn("Regimen unreported",case_path({"context":result}))

    def test_study_name_is_not_nct(self):
        result=self.mapped(event(trials=[{"kind":"study_name","value":"SYNTH-STUDY"}]))
        self.assertEqual([],result["subject"]["trial_ids"])
        self.assertEqual(["SYNTH-STUDY"],
            result["source_event_metadata"]["events"][0]["study_name_leads"])

    def test_same_case_events_preserve_both_sources(self):
        result=self.mapped(event(),event("80",event_date="2022-01-01"),
                            values=variables(["79","80"]))
        self.assertEqual(2,len(result["source_assertions"]))

    def test_mixed_trial_batch_is_rejected(self):
        self.rejects("clinical_source_mixed_case_requires_split",
            variables(["79","80"]),
            envelope(event(),event("80",trials=[{"kind":"nct","value":"NCT03626546"}])))

    def test_two_unreported_trials_are_separate_event_scopes(self):
        self.rejects("clinical_source_unreported_trial_requires_single_event",
            variables(["79","80"]),envelope(event(trials=[]),event("80",trials=[])))

    def test_missing_event_not_empty_result(self):
        self.rejects("clinical_source_event_missing",variables(["999"]),envelope(event()))

    def test_source_count_and_completeness_are_required(self):
        original=envelope(event())
        for field,value,code in [
            ("complete",False,"clinical_source_incomplete"),
            ("record_count",2,"clinical_source_count_mismatch")]:
            candidate=envelope(event())
            candidate["provenance"][field]=value
            self.rejects(code,variables(),candidate)

    def test_duplicate_event_ids_fail(self):
        self.rejects("clinical_source_event_duplicate",variables(),
            envelope(event(),event()))

    def test_future_event_fails(self):
        self.rejects("clinical_source_event_future",variables(),
            envelope(event(event_date="2026-12-01")))

    def test_positive_sounding_source_remains_unreviewed(self):
        result=self.mapped(event(result="A significant primary endpoint was achieved"))
        self.assertFalse(result["source_event_metadata"]["clinical_outcome_adjudicated"])
        self.assertEqual([],result["evidence"])

    def test_cohort_inference_not_derived_from_selected_negatives(self):
        self.rejects("clinical_source_case_mode_required",
            variables(analysis_mode="cohort_pattern"),envelope(event()))

    def test_source_with_privileged_field_fails(self):
        candidate=envelope(event());candidate["provenance"]["credentials"]="not admitted"
        self.rejects("clinical_authority_material_forbidden",variables(),candidate)

    def test_nonrequested_row_is_not_forwarded(self):
        result=self.mapped(event(),event("80"))
        self.assertEqual(["79"],result["event_ids"])
        self.assertEqual(1,len(result["source_event_metadata"]["events"]))

    def test_missing_indication_fails(self):
        self.rejects("clinical_source_indication_unresolved",variables(),
            envelope(event(indications=[])))


if __name__=="__main__":
    unittest.main()
