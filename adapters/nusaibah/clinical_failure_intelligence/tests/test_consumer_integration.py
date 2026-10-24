"""Provider-free consumer tests; source adapters and live runtime are not exercised."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

from fakes import FakeInputs, CodedFailure, example_inputs
from test_source_bundle import case_inputs, bundle, entry, trial_result, metadata, abstract, terminology, NCT
from clinical_failure_intelligence.contracts import ContractError, canonical_bytes, digest, parse_request
from clinical_failure_intelligence.decision_outcome import finalize_output
from clinical_failure_intelligence.evidence import EvidenceLedger
from clinical_failure_intelligence.orchestration import run_analysis
from clinical_failure_intelligence.policies import Budget, ExecutionPolicy
from clinical_failure_intelligence.quality import normalize_items, review_items, OUTCOMES
from clinical_failure_intelligence.review_packets import critic_batches, scoped_review
from clinical_failure_intelligence.rendering import validate_result
from clinical_failure_intelligence.runtime_access import AgentRunner


class SourceAwareInputs(FakeInputs):
    """A deterministic model double driven by supplied evidence IDs, not providers."""
    def __init__(self, *, prepared=True, **kwargs):
        raw = case_inputs()
        raw["variables"]["supplementary_search"] = False
        raw["clinical_context"]["evidence"] = []
        if prepared:
            raw["clinical_evidence"] = bundle(entry(trial_result()), entry(metadata(), "pubmed"),
                entry(abstract(), "pubmed"), entry(terminology(), "umls", purpose="terminology"))
        super().__init__(raw, **kwargs)

    def role_payload(self, role, packet):
        payload = {"schema_version": "clinical_agent_response.v1", "task_id": packet["task_id"],
            "subject_id": "CASE_SYN", "role": role, "items": [], "followup_requests": [],
            "coverage": [{"obligation_id": key, "status": "completed"} for key in packet["assigned_obligation_ids"]]}
        if role.endswith("researcher"):
            for index, row in enumerate(packet["evidence_packet"]):
                body = row["text"]
                payload["items"].append({"claim_id": "CLAIM_" + str(index), "subject_id": "CASE_SYN",
                    "statement": "Synthetic source observation only.", "claim_kind": "observation",
                    "supporting_evidence_ids": [row["evidence_id"]], "contradicting_evidence_ids": [],
                    "source_spans": [{"evidence_id": row["evidence_id"], "start": 0,
                        "end": len(body), "quote": body, "text_digest": row["text_digest"]}]})
        elif role == "outcome_adjudicator":
            references = [e["evidence_id"] for e in packet["evidence_packet"]
                          if e.get("source_context", {}).get("evidence_use") == "posted_results"]
            for dimension in OUTCOMES:
                value = "not_met" if references and dimension == "primary_endpoint_result" else "unknown"
                payload["items"].append({"item_id": "OUT_" + dimension, "subject_id": "CASE_SYN",
                    "statement": "Synthetic outcome for fixture validation.", "dimension": dimension,
                    "value": value, "trial_ids": [NCT], "supporting_evidence_ids": references,
                    "contradicting_evidence_ids": [], "depends_on": []})
        elif role == "hypothesis_analyst":
            refs = [e["evidence_id"] for e in packet["evidence_packet"] if e["source_type"] == "original_research"]
            payload["items"] = [{"item_id": "H_SYN", "subject_id": "CASE_SYN",
                "statement": "Exposure remains a hypothesis in this synthetic case.",
                "supporting_evidence_ids": refs, "contradicting_evidence_ids": [],
                "depends_on": ["OUT_primary_endpoint_result"], "source_assertion_id": "SEED_SYN",
                "reason_code": "pk_pd_exposure_dose", "scope": "Synthetic regimen and trial only",
                "proposed_verdict": "inconclusive" if refs else "untested",
                "alternative_explanations": ["Population selection", "Target biology"],
                "validation_indicators": ["Measure exposure"],
                "falsification_condition": "Adequate exposure would challenge this explanation.", "lesson": None}]
        elif role == "evidence_critic":
            if packet.get("review_kind") == "product_memory_edits":
                payload["items"] = [{"edit_id": edit["edit_id"], "accepted": True, "scope_preserved": True,
                    "evidence_supported": True, "prior_content_preserved": True, "rationale": "Synthetic review."}
                    for edit in packet["candidate_edits"]]
            else:
                payload["items"] = [{"item_id": item["item_id"], "verdict": "accepted",
                    "supporting_evidence_ids": item["supporting_evidence_ids"],
                    "contradicting_evidence_ids": item["contradicting_evidence_ids"],
                    "scope_preserved": True, "rationale": "Synthetic review, not clinical proof."}
                    for item in packet["candidate_items"]]
        elif role == "product_memory_editor":
            payload["items"] = [{"edit_id": "EDIT_SYN", "operation": "add_section",
                "target_paragraph_id": None, "before_digest": None,
                "section_path": packet["memory_context"]["section_path"],
                "new_text": "A synthetic case observation with explicit uncertainty.",
                "supporting_item_ids": [item["item_id"] for item in packet["accepted_items"]],
                "rationale": "Synthetic new scoped paragraph."}]
        return payload


class ConsumerIntegrationTests(unittest.TestCase):
    def result(self, inputs=None):
        return run_analysis(inputs or FakeInputs())["outputs"]["clinical_intelligence"]

    def test_all_three_prepared_families_flow_through_actual_chain(self):
        fake = SourceAwareInputs()
        result = self.result(fake)
        self.assertTrue(result["evidence"])
        self.assertEqual(4, len(result["prepared_sources"]["sources"]))
        self.assertEqual(1, len(result["prepared_sources"]["terminology"]))
        self.assertEqual("preview", result["memory_update"]["status"])
        self.assertFalse(result["memory_update"]["write_attempted"])
        self.assertEqual("assessed", result["decision_summary"]["disposition"])
        self.assertEqual(8, len(fake.calls))
        self.assertEqual([("product_memory", {"product_id": "PRODUCT_SYN"})], fake.memory_calls)
        self.assertFalse(result["memory_update"]["class_extension"]["enabled"])
        validate_result(result)

    def test_all_three_prepared_families_preflight_has_zero_effects(self):
        class Strict(SourceAwareInputs):
            def invoke_agent(self, *args, **kwargs): raise AssertionError("No Agent preflight")
            def skill(self, *args, **kwargs): raise AssertionError("No Skill preflight")
            def dynamic_skill(self, *args, **kwargs): raise AssertionError("No memory preflight")
            def open_reference(self, *args, **kwargs): raise AssertionError("No HTTP preflight")
        fake = Strict(); fake["variables"]["preflight_only"] = True
        result = self.result(fake)
        self.assertEqual("preflight", result["quality"]["status"])
        self.assertEqual("not_assessed", result["decision_summary"]["disposition"])
        self.assertEqual(0, result["execution"]["logical_agent_calls"])
        self.assertEqual("not_requested", result["memory_update"]["status"])
        self.assertTrue(result["prepared_sources"]["terminology"])

    def test_wrong_prepared_identity_rejected_before_skill_or_agent(self):
        fake = SourceAwareInputs(); fake["clinical_evidence"]["product_id"] = "OTHER"
        with self.assertRaisesRegex(ContractError, "subject_mismatch"): self.result(fake)
        self.assertEqual([], fake.calls); self.assertEqual([], fake.memory_calls)

    def test_source_contract_declared_binding_only(self):
        root = Path(__file__).resolve().parents[1]
        m = json.loads((root / "clinical_failure_intelligence.asset.json").read_text())
        self.assertEqual("0.1.13", m["default"])
        inputs = m["versions"]["0.1.2"]["inputs"]
        self.assertEqual("binding", inputs["clinical_evidence"]["source"])
        self.assertFalse(inputs["clinical_evidence"]["required"])
        self.assertEqual("binding", inputs["clinical_context"]["source"])
        self.assertNotIn("callable_assets", m["versions"]["0.1.2"])

    def test_results_node_jsonl_record_output_is_opt_in_and_no_write(self):
        fake = SourceAwareInputs()
        default = run_analysis(fake)["outputs"]
        self.assertEqual({"clinical_intelligence"}, set(default))
        fake["variables"]["prepare_result_for_persistence"] = True
        outputs = run_analysis(fake)["outputs"]
        self.assertEqual({"clinical_intelligence", "clinical_intelligence_records"}, set(outputs))
        self.assertEqual({"records": [outputs["clinical_intelligence"]]}, outputs["clinical_intelligence_records"])
        line = json.dumps(outputs["clinical_intelligence_records"]["records"][0], separators=(",", ":")) + "\n"
        self.assertEqual(1, len(line.splitlines()))
        self.assertEqual(outputs["clinical_intelligence"], json.loads(line))
        self.assertEqual("not_attested", outputs["clinical_intelligence"]["persistence"]["status"])
        self.assertFalse(outputs["clinical_intelligence"]["memory_update"]["write_attempted"])
        root = Path(__file__).resolve().parents[1]
        from jsonschema import Draft202012Validator
        schema = json.loads((root / "tests/reference/clinical_intelligence.v1.schema.json").read_text())
        Draft202012Validator(schema).validate(json.loads(line))

    def test_persistence_record_intent_rejects_bad_type_and_preflight_without_side_effects(self):
        for value in ("true", 1, None):
            fake = SourceAwareInputs()
            fake["variables"]["prepare_result_for_persistence"] = value
            with self.assertRaisesRegex(ContractError, "clinical_persistence_prepare_flag_invalid"):
                self.result(fake)
            self.assertEqual([], fake.calls)
            self.assertEqual([], fake.memory_calls)
        fake = SourceAwareInputs()
        fake["variables"]["preflight_only"] = True
        fake["variables"]["prepare_result_for_persistence"] = True
        with self.assertRaisesRegex(ContractError, "clinical_persistence_preflight_forbidden"):
            self.result(fake)
        self.assertEqual([], fake.calls)
        self.assertEqual([], fake.memory_calls)

    def test_no_source_evidence_does_not_invent_failure_or_memory(self):
        fake = SourceAwareInputs(prepared=False)
        result = self.result(fake)
        self.assertEqual("needs_evidence", result["decision_summary"]["disposition"])
        self.assertTrue(all(row["value"] == "unknown" for row in result["case_assessments"]))
        self.assertEqual("no_change", result["memory_update"]["status"])
        self.assertFalse(result["memory_update"]["initialization_required"])
        self.assertNotIn("product_memory_editor", [role for role, _ in fake.calls])

    def test_supplied_terms_never_change_product_or_group_identity(self):
        fake = SourceAwareInputs()
        fake["clinical_context"]["subject"]["pharmacological_group_id"] = None
        result = self.result(fake)
        self.assertEqual("PRODUCT_SYN", result["subject"]["product_id"])
        self.assertIsNone(result["subject"]["pharmacological_group_id"])
        self.assertFalse(result["prepared_sources"]["terminology"][0]["clinical_equivalence_verified"])

    def test_supplementary_search_off_uses_no_reference_calls(self):
        class Strict(SourceAwareInputs):
            def open_reference(self, *args, **kwargs): raise AssertionError("No supplementary HTTP")
        result = self.result(Strict())
        self.assertEqual(0, result["execution"]["reference_reads"])

    def test_prepared_families_skip_redundant_grounded_discovery(self):
        class Search(SourceAwareInputs):
            def open_reference(self, *args, **kwargs): raise AssertionError("No native citation returned")
            def role_payload(self, role, packet):
                if packet.get("research_phase") == "source_discovery":
                    return {"schema_version": "clinical_agent_response.v1", "task_id": packet["task_id"],
                        "subject_id": "CASE_SYN", "role": role, "coverage": [
                            {"obligation_id": key, "status": "completed"} for key in packet["assigned_obligation_ids"]],
                        "items": [], "followup_requests": []}
                return super().role_payload(role, packet)
        fake = Search(); fake["variables"]["supplementary_search"] = True
        with patch("clinical_failure_intelligence.research_sources._provider_citations", return_value=()):
            result = self.result(fake)
        discovery_roles = [role for role, packet in fake.calls if packet.get("research_phase") == "source_discovery"]
        self.assertEqual(["event_researcher"], discovery_roles)
        self.assertTrue(result["evidence"])

    def test_multi_product_association_does_not_write_product_blame(self):
        fake = SourceAwareInputs()
        fake["clinical_context"]["source_event_metadata"] = {"events": [
            {"event_id": "EVENT_SYN", "all_product_ids": ["PRODUCT_SYN", "PRODUCT_OTHER"]}]}
        result = self.result(fake)
        self.assertTrue(result["case_assessments"])
        self.assertEqual("clinical_product_attribution_review_required", result["memory_update"]["reason"])
        self.assertEqual([], result["memory_update"]["operations"])
        self.assertNotIn("product_memory_editor", [role for role, _ in fake.calls])

    def test_graph_has_typed_entities_without_causality_or_cui_equivalence(self):
        result = self.result(SourceAwareInputs())
        relations = {edge["relation"] for edge in result["reason_graph"]["edges"]}
        self.assertTrue({"SUBJECT_PRODUCT", "SUBJECT_TRIAL", "SOURCE_RECORD", "TERM_CANDIDATE_FOR"} <= relations)
        self.assertNotIn("CAUSED_FAILURE", relations)
        self.assertTrue(all(node.get("clinical_equivalence_verified") is False
            for node in result["reason_graph"]["nodes"] if node["type"] == "terminology"))

    def test_business_and_memory_decisions_do_not_forge_receipts(self):
        result = self.result(SourceAwareInputs())
        self.assertIsNone(result["decision_summary"]["predictive_success_probability"])
        self.assertEqual("not_assessed", result["decision_summary"]["commercial_recommendation"])
        self.assertEqual("not_attested", result["memory_decision"]["journal_status"])
        self.assertTrue(result["memory_decision"]["candidate_present"])
        self.assertFalse(result["memory_decision"]["commit_observed"])
        result["memory_decision"]["commit_observed"] = True
        with self.assertRaisesRegex(ContractError, "not_attested"): validate_result(result)

    def test_report_compaction_does_not_change_canonical_science_or_delta(self):
        result = self.result(SourceAwareInputs())
        snapshot = deepcopy({key: result[key] for key in ("case_assessments", "hypothesis_results", "evidence", "memory_update")})
        with patch("clinical_failure_intelligence.decision_outcome.render_report", return_value="X" * 100000):
            compacted = finalize_output(result, max_bytes=80000)
        self.assertEqual("omitted_for_transport", compacted["presentation"]["report_status"])
        self.assertTrue(compacted["presentation"]["omitted_fields"])
        self.assertEqual(snapshot, {key: compacted[key] for key in snapshot})

    def test_canonical_oversize_is_not_silently_cut(self):
        result = self.result(SourceAwareInputs())
        evidence=deepcopy(result['evidence'])
        result=finalize_output(result,max_bytes=1000)
        self.assertEqual(evidence,result['evidence'])
        self.assertIn('clinical_canonical_result_size_warning',{x['code'] for x in result['quality']['issues']})

    def test_prepared_and_preflight_results_validate_json_schemas(self):
        from jsonschema import Draft202012Validator
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "tests/reference/clinical_intelligence.v1.schema.json").read_text())
        request_schema = json.loads((root / "tests/reference/analysis_request.v1.schema.json").read_text())
        for preflight in (False, True):
            fake = SourceAwareInputs(); fake["variables"]["preflight_only"] = preflight
            Draft202012Validator(request_schema).validate(dict(fake))
            Draft202012Validator(schema).validate(self.result(fake))

    def test_source_request_plan_is_not_execution(self):
        fake = SourceAwareInputs(prepared=False); fake["variables"]["preflight_only"] = True
        result = self.result(fake)
        self.assertTrue(result["source_request_plan"])
        self.assertTrue(all(row["execution"] == "not_requested" for row in result["source_request_plan"]))

    def test_no_implicit_apply_or_class_execution(self):
        fake = SourceAwareInputs(); fake["variables"]["memory_mode"] = "apply"
        with self.assertRaisesRegex(ContractError, "apply_not_admitted"): self.result(fake)
        self.assertEqual([], fake.calls)


class ReliabilityTests(unittest.TestCase):
    def test_typed_output_limit_contains_every_active_role_without_retry(self):
        module = ModuleType("devtools.runtime_agent_invocation")
        class TrustedFailure(RuntimeError):
            cause_code = "provider_execution_output_limit_reached"
        module.RuntimeAgentInvocationError = TrustedFailure
        with patch.dict(sys.modules, {"devtools.runtime_agent_invocation": module}):
            for role in ("trial_researcher", "literature_researcher", "event_researcher",
                         "outcome_adjudicator", "hypothesis_analyst", "evidence_critic", "product_memory_editor"):
                fake = FakeInputs(faults={role: TrustedFailure()})
                result = run_analysis(fake)["outputs"]["clinical_intelligence"]
                self.assertEqual(1, sum(r == role for r, _ in fake.calls), role)
                self.assertTrue(any(stage["code"] == "clinical_agent_output_exhausted"
                    for stage in result["execution"]["stages"]), role)
                self.assertFalse(result["memory_update"]["write_attempted"])
                self.assertEqual(0, result["execution"]["model_repair_calls"])

    def test_string_like_output_limit_is_not_trusted_sdk_failure(self):
        fake = FakeInputs(faults={"trial_researcher": CodedFailure(
            "agent_execution_provider_retry_exhausted", "provider_execution_output_limit_reached")})
        with self.assertRaisesRegex(ContractError, "runtime_blocked"):
            run_analysis(fake)

    def test_unknown_programming_or_authority_error_stays_hard(self):
        for error in (ValueError("programming problem"), CodedFailure("authority_revoked")):
            with self.assertRaisesRegex(ContractError, "runtime_blocked"):
                run_analysis(FakeInputs(faults={"event_researcher": error}))

    def test_duplicate_research_batch_preserves_other_research_and_result(self):
        def duplicate(payload, _):
            payload["items"].append(deepcopy(payload["items"][0])); return payload
        fake = FakeInputs(transforms={"trial_researcher": duplicate})
        result = run_analysis(fake)["outputs"]["clinical_intelligence"]
        self.assertTrue(result["research_claims"])
        self.assertTrue(any(issue["code"] == "clinical_claim_id_duplicate" for issue in result["quality"]["issues"]))

    def test_malformed_verdict_does_not_discard_valid_sibling(self):
        def malformed(payload, packet):
            if packet.get("review_kind") != "product_memory_edits":
                payload["items"][0]["scope_preserved"] = "yes"
            return payload
        result = run_analysis(FakeInputs(transforms={"evidence_critic": malformed}))["outputs"]["clinical_intelligence"]
        self.assertFalse(result["case_assessments"][0]["accepted"])
        self.assertTrue(result["case_assessments"][1]["accepted"])
        self.assertTrue(any(row["code"] == "clinical_critic_scope_invalid" for row in result["quality"]["issues"]))

    def test_critic_batching_preserves_ids_sources_and_dependency_context(self):
        raw = example_inputs(); request = parse_request(FakeInputs(raw))
        ledger = EvidenceLedger("CASE_SYN", "2025-02-01", raw["clinical_context"]["evidence"])
        fake = FakeInputs()
        packet = {"task_id": "synthetic", "assigned_obligation_ids": []}
        outcomes, _ = normalize_items(fake.role_payload("outcome_adjudicator", packet)["items"], "outcome", request, ledger)
        hypotheses, _ = normalize_items(fake.role_payload("hypothesis_analyst", packet)["items"], "hypothesis", request, ledger)
        items = outcomes + hypotheses
        batches = critic_batches(items, ledger.rows(), {"methodology": "shared"}, max_bytes=20000, max_items=2)
        self.assertEqual(3, len(batches))
        returned = []
        for batch in batches:
            returned.extend(fake.role_payload("evidence_critic", {**batch, **packet})["items"])
            known = {row["evidence_id"] for row in batch["evidence_packet"]}
            for row in batch["candidate_items"] + batch["dependency_context"]:
                self.assertTrue(set(row["supporting_evidence_ids"] + row["contradicting_evidence_ids"]) <= known)
        expected, _ = review_items(items, returned, ledger)
        actual, _ = scoped_review(items, returned, ledger)
        self.assertEqual(expected, actual)


if __name__ == "__main__": unittest.main()
