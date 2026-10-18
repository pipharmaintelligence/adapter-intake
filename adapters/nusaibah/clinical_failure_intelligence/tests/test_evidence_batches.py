"""Lossless source admission, bounded model packets and truthful deferred coverage."""
from copy import deepcopy
import unittest

from fakes import FakeInputs, example_inputs
from test_source_bundle import bundle, case_inputs, entry, trial_result
from clinical_failure_intelligence.contracts import ContractError, canonical_bytes, digest, parse_request
from clinical_failure_intelligence.evidence_batches import evidence_batches, closed_packet
from clinical_failure_intelligence.orchestration import run_analysis
from clinical_failure_intelligence.policies import Budget, ExecutionPolicy
from clinical_failure_intelligence.runtime_access import AgentRunner


class EvidenceBatchTests(unittest.TestCase):
    def test_large_bundle_warns_and_retains_every_complete_window(self):
        inputs = case_inputs()
        inputs["clinical_context"]["evidence"] = []
        result = trial_result()
        result["records"][0]["registry_study"]["protocolSection"]["contactsLocationsModule"] = {"locations": [
            {"facility": str(i), "details": "x" * 11000}
            for i in range(200)]
        }
        inputs["clinical_evidence"] = bundle(entry(result))
        inputs["variables"]["preflight_only"] = True
        inputs["variables"]["memory_mode"] = "off"
        response = run_analysis(inputs)
        output = response["outputs"]["clinical_intelligence"]
        self.assertEqual("success", response["status"])
        self.assertGreaterEqual(len(output["evidence"]), 200)
        self.assertTrue(any(r["source_context"]["source_pointer"].endswith("/locations/199") for r in output["evidence"]))
        self.assertEqual([], output["prepared_sources"]["omissions"])
        self.assertTrue(any(x["code"] == "clinical_source_bundle_size_warning" for x in output["quality"]["issues"]))
        self.assertTrue(any(x["code"] == "clinical_result_size_warning" for x in output["quality"]["issues"]))
        self.assertEqual(0, output["execution"]["logical_agent_calls"])

    def test_locations_never_displace_outcomes_or_safety(self):
        inputs = case_inputs()
        source = trial_result()
        study = source["records"][0]["registry_study"]
        study["protocolSection"]["contactsLocationsModule"] = {"locations": [
            {"facility": str(i), "details": "x" * 2000} for i in range(100)]}
        inputs["clinical_evidence"] = bundle(entry(source))
        prepared = parse_request(inputs)["prepared_sources"]
        self.assertEqual([], prepared["omissions"])
        uses = {r["source_context"]["evidence_use"] for r in prepared["evidence"]}
        self.assertTrue({"posted_results", "safety_results"} <= uses)
        chunks = evidence_batches(prepared["evidence"], lambda rows: {"evidence": rows}, max_bytes=24000)
        first = {r["source_context"]["evidence_use"] for r in chunks[0]}
        self.assertTrue({"posted_results", "safety_results"} <= first)
        self.assertEqual(len(prepared["evidence"]), sum(map(len, chunks)))
        self.assertTrue(all(len(canonical_bytes({"evidence": chunk})) <= 24000 for chunk in chunks))

    def test_full_agent_wrapper_and_utf8_bytes_are_budgeted(self):
        request = parse_request(example_inputs())
        runner = AgentRunner(FakeInputs(), Budget(ExecutionPolicy(max_packet_bytes=16000)))
        rows = [{"evidence_id": "E_" + str(i), "text": "أ" * 1800} for i in range(12)]
        def packet(chunk):
            return runner.packet("trial_researcher", request, task_id="batch:sizing", obligations=["research"],
                packet_data={"methodology": "common context" * 100, "evidence_packet": chunk})
        chunks = evidence_batches(rows, packet, max_bytes=16000)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(rows, [row for chunk in chunks for row in chunk])
        self.assertTrue(all(len(canonical_bytes(packet(chunk))) <= 16000 for chunk in chunks))

    def test_many_outcomes_do_not_displace_safety_from_first_packet(self):
        rows = [{"evidence_id": use + str(i), "text": "x" * 12000,
                 "source_context": {"evidence_use": use}}
                for use in ("posted_results", "safety_results") for i in range(10)]
        chunks = evidence_batches(rows, lambda chunk: {"evidence_packet": chunk}, max_bytes=50000)
        self.assertEqual({"posted_results", "safety_results"},
                         {r["source_context"]["evidence_use"] for r in chunks[0]})
        self.assertEqual({r["evidence_id"] for r in rows},
                         {r["evidence_id"] for chunk in chunks for r in chunk})
        self.assertTrue(all(len(canonical_bytes({"evidence_packet": chunk})) <= 50000 for chunk in chunks))

    def test_claims_keep_cross_batch_premises_and_counterevidence(self):
        inventory = [{"evidence_id": "A", "text": "support"}, {"evidence_id": "B", "text": "counter"}]
        claim = {"supporting_evidence_ids": ["A"], "contradicting_evidence_ids": ["B"]}
        packet = closed_packet(inventory[:1], inventory, [claim], {})
        self.assertEqual({"A", "B"}, {r["evidence_id"] for r in packet["evidence_packet"]})
        self.assertEqual([claim], packet["research_claims"])
        self.assertEqual(0, packet["evidence_scope"]["not_assigned_count"])

    def test_analysis_keeps_outcome_dependency_premises(self):
        inventory = [{"evidence_id": key, "text": key} for key in ("A", "B", "C")]
        assessments = [
            {"item_id": "O1", "supporting_evidence_ids": ["A"], "contradicting_evidence_ids": [], "depends_on": ["O2"]},
            {"item_id": "O2", "supporting_evidence_ids": ["B"], "contradicting_evidence_ids": ["C"], "depends_on": []}]
        packet = closed_packet(inventory[:1], inventory, [], {"case_assessments": assessments})
        self.assertEqual(assessments, packet["case_assessments"])
        self.assertEqual({"A", "B", "C"}, {r["evidence_id"] for r in packet["evidence_packet"]})

    def test_unfittable_atomic_closure_defers_without_an_agent_call(self):
        fake = FakeInputs()
        runner = AgentRunner(fake, Budget())
        request = parse_request(example_inputs())
        stage = runner.call("outcome_adjudicator", request, task_id="oversize:closure", obligations=["outcome"],
            packet_data={"evidence_packet": [{"evidence_id": "E_" + str(i)} for i in range(65)]})
        self.assertEqual("deferred", stage.status)
        self.assertEqual("clinical_packet_requires_partitioning", stage.code)
        self.assertEqual([], fake.calls)

    def test_large_analysis_dispatches_bounded_batches_and_reports_deferred_work(self):
        raw = example_inputs()
        raw["variables"]["memory_mode"] = "off"
        for i in range(20):
            raw["clinical_context"]["evidence"].append({**raw["clinical_context"]["evidence"][0],
                "evidence_id": "EX_" + str(i), "source_id": "SOURCE_" + str(i), "text": "x" * 9000})
        class EmptyResearchers(FakeInputs):
            def role_payload(self, role, packet):
                payload = super().role_payload(role, packet)
                if role.endswith("researcher"):
                    payload["items"] = []
                return payload
        fake = EmptyResearchers(raw)
        output = run_analysis(fake, policy=ExecutionPolicy(max_packet_bytes=32000))["outputs"]["clinical_intelligence"]
        self.assertTrue(fake.calls)
        self.assertTrue(all(len(canonical_bytes(packet)) <= 32000 for _, packet in fake.calls))
        self.assertLessEqual(output["execution"]["logical_agent_calls"], 12)
        batches = output["execution"]["evidence_batches"]
        self.assertTrue(any(r["role"] == "outcome_adjudicator" and r["batch_count"] > 1 for r in batches))
        self.assertTrue(any(r["role"] == "hypothesis_analyst" and r["batch_count"] > 1 for r in batches))
        self.assertTrue(any(r["status"] == "deferred" for r in batches))
        self.assertEqual("partial", output["quality"]["status"])
        self.assertEqual(22, len(output["evidence"]))

    def test_new_lookup_references_are_checked_without_fetching(self):
        inputs = case_inputs()
        source = trial_result()
        record = source["records"][0]
        measures = record["registry_study"]["resultsSection"]["outcomeMeasuresModule"]["outcomeMeasures"]
        record.update(results_reference_schema="clinical_trials_results_refs.v1", results_group_module_refs={},
            results_outcome_measures_ref={"json_pointer": "/registry_study/resultsSection/outcomeMeasuresModule/outcomeMeasures",
                                         "content_digest": digest(measures)})
        selected = entry(source)
        selected["asset_version"] = "0.1.1"
        inputs["clinical_evidence"] = bundle(selected)
        self.assertEqual("normalized", parse_request(inputs)["prepared_sources"]["status"])
        for pointer in ("/registry_study/resultsSection/missing", "/registry_study/resultsSection/~2invalid"):
            altered = deepcopy(inputs)
            result = altered["clinical_evidence"]["sources"][0]["result"]
            result["records"][0]["results_outcome_measures_ref"]["json_pointer"] = pointer
            altered["clinical_evidence"]["sources"][0]["result_digest"] = digest(result)
            with self.assertRaisesRegex(ContractError, "result_reference_invalid"):
                parse_request(altered)


if __name__ == "__main__":
    unittest.main()
