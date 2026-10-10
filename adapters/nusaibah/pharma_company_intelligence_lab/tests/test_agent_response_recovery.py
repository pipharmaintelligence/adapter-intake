from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

import test_orchestration_preview as orchestration
import test_iteration_limits as limits
import test_memory_apply_contract as mutation
import agent_response_recovery_v0_1_17 as recovery

adapter = orchestration.adapter_module


class BackupInputs(orchestration.FakeInputs):
    def __init__(self, failed_role, *, change_verdict=False, wrapper=None):
        super().__init__()
        self.failed_role = failed_role
        self.change_verdict = change_verdict
        self.wrapper = wrapper
        self.failed = False

    def invoke_agent(self, role, *, input, on_error="raise"):
        if role == adapter.RESEARCH_RESOLVER_ROLE:
            self.agent_calls.append((role, input["company_id"]))
            self.agent_inputs.append((role, input["company_id"], deepcopy(input)))
            value = deepcopy(input["invalid_response"])
            if self.change_verdict:
                value["unmet_plan_requirements"] = []
                value["recommendation"] = "pass"
            if self.wrapper:
                value = self.wrapper(json.dumps(value))
            return {"status": "completed", "result": {"schema_version": "agent_result.v1", "kind": "json",
                    "content": [{"type": "json", "value": value}]}}
        envelope = super().invoke_agent(role, input=input, on_error=on_error)
        if role == self.failed_role and input["company_id"] == 13 and not self.failed:
            self.failed = True
            value = envelope["result"]["content"][0]["value"]
            missing = {
                adapter.PLANNER_ROLE: "priority_rationale", adapter.STRATEGIC_ROLE: "implications",
                adapter.CRITIC_ROLE: "unmet_plan_requirements", adapter.SYNTHESIS_ROLE: "memory_candidate",
                adapter.BENCHMARK_ROLE: "results",
            }[role]
            del value[missing]
        return envelope


class AgentResponseRecoveryTests(unittest.TestCase):
    def run_preview(self, inputs):
        with patch.object(adapter, "_agent_citations", side_effect=orchestration._fake_citations):
            return adapter.NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(inputs, {})

    def test_every_nonresearch_role_gets_one_backup_then_batch_continues_without_approval(self):
        for role in (adapter.PLANNER_ROLE, adapter.STRATEGIC_ROLE, adapter.CRITIC_ROLE,
                     adapter.SYNTHESIS_ROLE, adapter.BENCHMARK_ROLE):
            with self.subTest(role=role):
                inputs = BackupInputs(role, wrapper=lambda text: "'''" + text + "'''")
                inputs["variables"]["retain_review_packet"] = True
                result = self.run_preview(inputs)
                dossier = result["outputs"]["intelligence_dossier"]
                first, second = dossier["company_results"]
                self.assertTrue(first["agent_schema_incomplete"])
                self.assertFalse(first["quality_gate_passed"])
                self.assertFalse(first["memory_mutation_eligible"])
                self.assertFalse(second["agent_schema_incomplete"])
                self.assertEqual(Counter(inputs.agent_calls)[(adapter.RESEARCH_RESOLVER_ROLE, 13)], 1)
                self.assertEqual(first["agent_response_resolver_call_count"], 1)
                self.assertEqual(dossier["business_result_state"], "incomplete")
                self.assertFalse(any(name.endswith("_update") for name, _ in inputs.dynamic_skill_calls))
                packet = dossier["review_packet"]
                withheld = packet["companies"][0]
                self.assertIsNone(withheld["critic"])
                self.assertIsNone(withheld["memory_proposal"]["replacement_text"])
                self.assertFalse(withheld["memory_proposal"]["mutation_eligible"])
                body = {key: value for key, value in packet.items() if key != "packet_sha256"}
                self.assertEqual(packet["packet_sha256"], "sha256:" + sha256(adapter.canonical_bytes(body)).hexdigest())
                repair_input = next(payload for name, _, payload in inputs.agent_inputs if name == adapter.RESEARCH_RESOLVER_ROLE)
                self.assertEqual(repair_input["original_role"], role)
                self.assertEqual(repair_input["original_invocation_ordinal"], 1)
                self.assertEqual(repair_input["repair_scope"], "business_json_format_only")

    def test_backup_cannot_invent_missing_critic_approval_fields(self):
        result = self.run_preview(BackupInputs(adapter.CRITIC_ROLE, change_verdict=True))
        first = result["outputs"]["intelligence_dossier"]["company_results"][0]
        self.assertTrue(first["agent_schema_incomplete"])
        self.assertEqual(first["unresolved_agent_responses"][0]["rule"], "repair_changed_business_content")

    def test_incomplete_company_withholds_all_its_writes_without_stopping_other_company_or_output(self):
        inputs = BackupInputs(adapter.CRITIC_ROLE)
        inputs["variables"].update(memory_mode="apply", publish_dossier=True)
        with patch.object(adapter, "_apply_company_memory", return_value={"memory_update_status": "applied"}) as memory_apply, \
             patch.object(adapter, "_apply_company_methodology", return_value={"methodology_learning_update_status": "applied"}) as methodology_apply:
            result = self.run_preview(inputs)
        self.assertEqual([call.args[1]["company_id"] for call in memory_apply.call_args_list], [59])
        self.assertEqual([call.kwargs["company_id"] for call in methodology_apply.call_args_list], [59])
        dossier = result["outputs"]["intelligence_dossier"]
        self.assertEqual(dossier["publication_state"], "runtime_output_ready_for_output_policy")
        self.assertEqual(dossier["business_result_state"], "incomplete")
        first, second = dossier["company_results"]
        self.assertEqual(first["memory_update_status"], "withheld_incomplete")
        self.assertEqual(first["methodology_learning_update_status"], "withheld_incomplete")
        self.assertIsNone(first["benchmark_improvement_count"])
        self.assertEqual(second["memory_update_status"], "applied")

    def test_committed_benchmark_failure_is_reported_after_write_and_gets_only_one_backup(self):
        candidate = adapter.MemoryCandidate(company_id=13, target_section=adapter.MEMORY_TARGET_SECTION,
                                            markdown="Updated grounded memory.", fact_ids=("claim-1",))
        mutable = mutation.FakeMutableMemory()
        class CommittedInputs(mutation.FakeInputs):
            def __init__(self):
                super().__init__(mutable, mutation.FakeFreshMemory(candidate))
                self.agent_calls = []
            def invoke_agent(self, role, *, input, on_error="raise"):
                self.agent_calls.append(role)
                value = {"schema_version": adapter.BENCHMARK_SCHEMA_VERSION, "company_id": 13,
                         "role": adapter.BENCHMARK_ROLE, "status": "completed"}
                return {"status": "completed", "result": {"schema_version": "agent_result.v1", "kind": "json",
                        "content": [{"type": "json", "value": value}]}}
        runtime = CommittedInputs()
        with self.assertRaises(recovery.UnresolvedAgentResponse) as caught:
            adapter._apply_company_memory(limits.bounded(runtime, mode="apply"), mutation._state(candidate))
        self.assertEqual(mutable.expected_digest_seen, mutation.BEFORE)
        self.assertEqual(runtime.agent_calls, [adapter.BENCHMARK_ROLE, adapter.RESEARCH_RESOLVER_ROLE])
        self.assertEqual(caught.exception.code, "pharma_agent_business_schema_invalid")
        self.assertEqual(caught.exception.proof_failure_detail["role"], adapter.BENCHMARK_ROLE)

    def test_wrapped_responses_for_every_original_role_need_zero_backup_calls(self):
        class WrappedInputs(orchestration.FakeInputs):
            def invoke_agent(self, role, *, input, on_error="raise"):
                envelope = super().invoke_agent(role, input=input, on_error=on_error)
                value = envelope["result"]["content"][0]["value"]
                envelope["result"]["content"][0]["value"] = "'''```json\n" + json.dumps(value) + "\n```'''"
                return envelope
        result = self.run_preview(WrappedInputs())
        self.assertEqual(result["metrics"]["agent_response_resolver_call_count"], 0)
        self.assertEqual(result["metrics"]["logical_agent_invocations"], 24)
        for company in result["outputs"]["intelligence_dossier"]["company_results"]:
            self.assertFalse(company["agent_schema_incomplete"])
            self.assertTrue(company["agent_response_recovery_trace"])

    def test_known_enum_and_array_cleanup_is_deterministic_and_preserves_negative_verdict(self):
        contract = adapter.response_contract_for_role(adapter.CRITIC_ROLE, company_id=13)
        original = {"recommendation": " FAIL ", "citation_coverage": {"status": " INSUFFICIENT ", "notes": "same"},
                    "unsupported_claim_ids": "claim-1"}
        cleaned = recovery.formatting_normal_form(original, contract)
        self.assertEqual(cleaned["recommendation"], "fail")
        self.assertEqual(cleaned["citation_coverage"]["status"], "insufficient")
        self.assertEqual(cleaned["unsupported_claim_ids"], ["claim-1"])
        recovery.require_preserved_business(original, cleaned, contract=contract, role=adapter.CRITIC_ROLE)
        cleaned["recommendation"] = "pass"
        with self.assertRaises(recovery.AgentResponseDiagnosticError):
            recovery.require_preserved_business(original, cleaned, contract=contract, role=adapter.CRITIC_ROLE)

    def test_malformed_section_identity_reaches_diagnostics_instead_of_cleanup_typeerror(self):
        contract = adapter.response_contract_for_role(adapter.SYNTHESIS_ROLE, company_id=13)
        payload = {"sections": [{"section_id": [], "subsections": []}]}
        self.assertEqual(recovery.formatting_normal_form(payload, contract)["sections"][0]["section_id"], [])

    def test_backup_cannot_change_memory_facts_or_coverage_decisions(self):
        for role, original, repaired in (
            (adapter.SYNTHESIS_ROLE, {"memory_candidate": {"markdown": "Grounded fact", "fact_ids": ["f1"]}},
             {"memory_candidate": {"markdown": "Invented fact", "fact_ids": ["f1"]}}),
            (adapter.BENCHMARK_ROLE, {"results": [{"question_id": "q1", "coverage": "not_covered", "evidence_basis": "Absent"}]},
             {"results": [{"question_id": "q1", "coverage": "covered", "evidence_basis": "Absent"}]}),
        ):
            with self.subTest(role=role), self.assertRaises(recovery.AgentResponseDiagnosticError):
                recovery.require_preserved_business(original, repaired, contract=adapter.response_contract_for_role(role, company_id=13), role=role)

    def test_one_repair_reservation_cannot_be_reused_or_recursively_repair_the_backup(self):
        runtime = limits.RecordingRuntime()
        bounded = limits.bounded(runtime)
        with self.assertRaises(adapter.AgentContractValidationError):
            bounded.invoke_agent(adapter.RESEARCH_RESOLVER_ROLE, input={"company_id": 13})
        bounded.invoke_agent(adapter.STRATEGIC_ROLE, input={"company_id": 13})
        bounded.invoke_response_resolver(original_role=adapter.STRATEGIC_ROLE, input={"company_id": 13})
        with self.assertRaises(adapter.AgentContractValidationError):
            bounded.invoke_response_resolver(original_role=adapter.STRATEGIC_ROLE, input={"company_id": 13})
        with self.assertRaises(adapter.AgentContractValidationError):
            bounded.invoke_response_resolver(original_role=adapter.RESEARCH_RESOLVER_ROLE, input={"company_id": 13})
        self.assertEqual(len(runtime.calls), 2)

    def test_failed_backup_consumes_its_reservation_and_never_retries(self):
        runtime = limits.RecordingRuntime()
        bounded = limits.bounded(runtime)
        bounded.invoke_agent(adapter.STRATEGIC_ROLE, input={"company_id": 13})
        runtime.fail = True
        with self.assertRaisesRegex(RuntimeError, "synthetic invocation"):
            bounded.invoke_response_resolver(original_role=adapter.STRATEGIC_ROLE, input={"company_id": 13})
        with self.assertRaises(adapter.AgentContractValidationError):
            bounded.invoke_response_resolver(original_role=adapter.STRATEGIC_ROLE, input={"company_id": 13})
        self.assertEqual(len(runtime.calls), 2)

    def test_json_parser_rejects_ambiguous_prose_duplicate_keys_and_incomplete_objects(self):
        for text in ('Prose {"x":1}', '{"x":1,"x":2}', '```json\n{"x":1}', "'''{'x':1}'''",
                     '```json\n{"x":NaN}\n```', '```json\n[]\n```'):
            with self.subTest(text=text), self.assertRaises(recovery.AgentResponseDiagnosticError) as caught:
                recovery.parse_business_json(text, role=adapter.STRATEGIC_ROLE)
            self.assertNotIn(text, str(caught.exception))
            self.assertEqual(caught.exception.proof_failure_detail["field"], "content")

    def test_invalid_research_backup_json_is_withheld_without_retry(self):
        class InvalidBackup(limits.RecordingRuntime):
            def invoke_agent(self, role, *, input, on_error="raise"):
                self.calls.append((role, input["company_id"]))
                return {"status": "completed", "result": {"schema_version": "agent_result.v1", "kind": "json",
                        "content": [{"type": "json", "value": '```json\n{"company_id":13'}]}}
        runtime = InvalidBackup()
        bounded = limits.bounded(runtime)
        bounded.invoke_agent("portfolio_researcher", input={"company_id": 13})
        initial = adapter.ResearchContractValidationError(role="portfolio_researcher", stage="research_payload",
                                                          field="claims_confidence", rule="enum_invalid")
        payload, repairs, diagnostic = adapter._repair_research_response(
            bounded, value={"company_id": 13}, role="portfolio_researcher", company_id=13, initial_error=initial)
        self.assertIsNone(payload)
        self.assertEqual(repairs, [])
        self.assertEqual(diagnostic["field"], "content")
        self.assertEqual(runtime.calls, [("portfolio_researcher", 13), (adapter.RESEARCH_RESOLVER_ROLE, 13)])


if __name__ == "__main__":
    unittest.main()
