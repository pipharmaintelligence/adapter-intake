from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import test_orchestration_preview as orchestration
from test_orchestration_preview import FakeInputs, FirstRunMethodologyInputs, _fake_citations
import research_diagnostics_v0_1_17 as diagnostic
import portfolio_review_v0_1_17 as configuration
import test_iteration_limits as limits

adapter = orchestration.adapter_module


class RepairInputs(FakeInputs):
    def __init__(self, *, resolver_invalid=False, resolver_changes_evidence=False, failed_pass=1):
        super().__init__()
        self.resolver_invalid = resolver_invalid
        self.resolver_changes_evidence = resolver_changes_evidence
        self.failed_pass = failed_pass

    def invoke_agent(self, role, *, input, on_error="raise"):
        if role == adapter.RESEARCH_RESOLVER_ROLE:
            company_id = input["company_id"]
            self.agent_calls.append((role, company_id))
            self.agent_inputs.append((role, company_id, deepcopy(input)))
            value = deepcopy(input["invalid_response"])
            value["claims"][0]["confidence"] = "unknown" if self.resolver_invalid else "low"
            if self.resolver_changes_evidence:
                value["claims"][0]["statement"] = "Invented replacement claim."
            return {"status": "completed", "result": {"schema_version": "agent_result.v1", "kind": "json",
                    "content": [{"type": "json", "value": value}]}}
        envelope = super().invoke_agent(role, input=input, on_error=on_error)
        if role == "portfolio_researcher" and input["portfolio_review"]["pass_number"] == self.failed_pass:
            envelope["result"]["content"][0]["value"]["claims"][0]["confidence"] = "unknown"
        return envelope


class PortfolioReflectionTests(unittest.TestCase):
    def run_preview(self, inputs):
        with patch.object(adapter, "_agent_citations", side_effect=_fake_citations):
            return adapter.NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(inputs, {})

    def companies(self, result):
        return result["outputs"]["intelligence_dossier"]["company_results"]

    def test_total_passes_one_two_three_repeat_only_portfolio_with_no_writes(self):
        for passes in (1, 2, 3):
            with self.subTest(passes=passes):
                inputs = FakeInputs(); inputs["variables"]["portfolio_review_passes"] = passes
                result = self.run_preview(inputs)
                counts = Counter(inputs.agent_calls)
                for company_id in (13, 59):
                    self.assertEqual(counts[("portfolio_researcher", company_id)], passes)
                    for role in ("market_researcher", "regulatory_risk_researcher", "strategic_analyst", "evidence_critic", "intelligence_synthesizer"):
                        self.assertEqual(counts[(role, company_id)], 1)
                self.assertEqual(len(inputs.agent_calls), 2 * (11 + passes))
                self.assertEqual(result["metrics"]["search_enabled_agent_invocations"], 2 * (2 + passes))
                self.assertEqual(result["metrics"]["research_resolver_agent_call_count"], 0)
                self.assertEqual(result["metrics"]["memory_mutations_made"], 0)
                self.assertFalse(any(role.endswith("_update") for role, _ in inputs.dynamic_skill_calls))
                for row in self.companies(result):
                    self.assertEqual(row["portfolio_review_pass_count"], passes)
                    self.assertEqual(row["portfolio_reflection_pass_count"], passes - 1)
                    trace = row["portfolio_review_trace"]
                    self.assertIsNone(trace[0]["previous_result_sha256"])
                    for previous, current in zip(trace, trace[1:]):
                        self.assertEqual(current["previous_result_sha256"], previous["result_sha256"])
                for role, company_id, payload in inputs.agent_inputs:
                    if role == "portfolio_researcher":
                        self.assertIn("verify therapeutic areas first", payload["learned_methodology"])
                        previous = payload["portfolio_review"]["previous_result"]
                        if previous is not None:
                            self.assertEqual(previous["company_id"], company_id)
                            self.assertTrue(previous["citation_sources"])
                            self.assertTrue(all(str(company_id) in claim["statement"] for claim in previous["claims"]))

    def test_absent_learned_methodology_is_valid_for_all_passes(self):
        inputs = FirstRunMethodologyInputs(); inputs["variables"]["portfolio_review_passes"] = 3
        result = self.run_preview(inputs)
        self.assertEqual(result["status"], "success")
        for role, _, payload in inputs.agent_inputs:
            if role in adapter.RESEARCH_ROLES:
                self.assertEqual(payload["learned_methodology"], "")
        self.assertTrue(all(not trace["learned_methodology_used"] for row in self.companies(result)
                            for trace in row["portfolio_review_trace"]))

    def test_invalid_pass_count_stops_before_any_runtime_helper(self):
        for value in (0, 4, -1, True, "2", 2.0, None, [], {}):
            inputs = FakeInputs(); inputs["variables"]["portfolio_review_passes"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                adapter.NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(inputs, {})
            self.assertEqual(inputs.agent_calls, [])
            self.assertEqual(inputs.dynamic_skill_calls, [])
        self.assertEqual(configuration.portfolio_review_passes({}), 1)

    def test_deterministic_cleanup_needs_no_resolver_call(self):
        original = orchestration._agent_value
        def reordered(role, company_id, payload):
            value = original(role, company_id, payload)
            if role in adapter.RESEARCH_ROLES:
                value["sections"].reverse()
                value["claims"][0]["confidence"] = "HIGH"
            return value
        with patch.object(orchestration, "_agent_value", side_effect=reordered):
            result = self.run_preview(FakeInputs())
        self.assertEqual(result["metrics"]["logical_agent_invocations"], 24)
        self.assertEqual(result["metrics"]["research_resolver_agent_call_count"], 0)
        self.assertGreater(result["metrics"]["research_response_repair_count"], 0)

    def test_registered_resolver_repairs_once_then_reflection_continues(self):
        inputs = RepairInputs(); inputs["variables"]["portfolio_review_passes"] = 3
        result = self.run_preview(inputs)
        self.assertEqual(len(inputs.agent_calls), 30)  # 28 planned + 2 company repairs
        self.assertEqual(result["metrics"]["research_resolver_agent_call_count"], 2)
        self.assertEqual(result["metrics"]["incomplete_research_company_count"], 0)
        for role, _, payload in inputs.agent_inputs:
            if role == adapter.RESEARCH_RESOLVER_ROLE:
                self.assertEqual(payload["failed_contract"]["field"], "claims_confidence")
                self.assertEqual(payload["failed_contract"]["rule"], "enum_invalid")
                self.assertNotIn("existing_company_memory", payload)
        self.assertTrue(all(row["portfolio_review_pass_count"] == 3 for row in self.companies(result)))

    def test_unrepaired_response_is_withheld_and_other_research_continues(self):
        original = orchestration._agent_value
        def honest_critic(role, company_id, payload):
            value = original(role, company_id, payload)
            if role == "evidence_critic":
                no_evidence = payload["research_evidence"]["no_evidence_research_roles"]
                value["unmet_plan_requirements"] = [
                    {"requirement_id": item["requirement_id"], "disposition": "unresolved_evidence", "notes": "Response was withheld."}
                    for item in payload["planner_requirements"] if item["role"] in no_evidence
                ]
            return value
        for changed_evidence, mode in ((False, "preview"), (True, "preview"), (False, "apply")):
            inputs = RepairInputs(resolver_invalid=not changed_evidence, resolver_changes_evidence=changed_evidence)
            inputs["variables"].update(portfolio_review_passes=3, retain_review_packet=True, memory_mode=mode)
            with patch.object(orchestration, "_agent_value", side_effect=honest_critic):
                result = self.run_preview(inputs)
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["metrics"]["incomplete_research_company_count"], 2)
            self.assertEqual(result["metrics"]["memory_mutations_made"], 0)
            self.assertEqual(Counter(inputs.agent_calls)[("portfolio_researcher", 13)], 1)
            for row in self.companies(result):
                self.assertTrue(row["research_incomplete"])
                self.assertFalse(row["memory_mutation_eligible"])
                self.assertIn("portfolio_researcher", row["no_evidence_research_roles"])
                self.assertEqual(len(row["unresolved_research_responses"]), 1)
            packet = result["outputs"]["intelligence_dossier"]["review_packet"]
            self.assertTrue(all(not row["memory_proposal"]["mutation_eligible"] for row in packet["companies"]))
            self.assertTrue(all(row["methodology_proposal"]["replacement_text"] is None for row in packet["companies"]))
            self.assertFalse(any(role.endswith("_update") for role, _ in inputs.dynamic_skill_calls))
            self.assertEqual(result["outputs"]["intelligence_dossier"]["business_result_state"], "incomplete")

        inputs = RepairInputs(resolver_invalid=True)
        inputs["variables"].update(publish_dossier=True, memory_mode="apply")
        with patch.object(orchestration, "_agent_value", side_effect=honest_critic):
            result = self.run_preview(inputs)
        dossier = result["outputs"]["intelligence_dossier"]
        self.assertEqual(dossier["business_result_state"], "incomplete")
        self.assertEqual(dossier["publication_state"], "runtime_output_ready_for_output_policy")
        self.assertTrue(dossier["publication_requested"])
        self.assertTrue(all(row["research_incomplete"] for row in dossier["company_results"]))
        self.assertFalse(any(role.endswith("_update") for role, _ in inputs.dynamic_skill_calls))

    def test_company_with_no_market_evidence_needs_explicit_critic_dispositions(self):
        original = orchestration._agent_value
        def sparse_company(role, company_id, payload):
            value = original(role, company_id, payload)
            if role == "market_researcher":
                value["claims"] = []
                value["uncertainties"] = ["No public market evidence was found."]
                for section in value["sections"]:
                    for sub in section["subsections"]:
                        sub["content"] = diagnostic.EVIDENCE_GAP_TEXT
            elif role == "evidence_critic":
                value["unmet_plan_requirements"] = [
                    {"requirement_id": item["requirement_id"], "disposition": "unresolved_evidence", "notes": "No market evidence."}
                    for item in payload["planner_requirements"] if item["role"] == "market_researcher"
                ]
            return value
        def citations(result):
            return () if result["content"][0]["value"]["role"] == "market_researcher" else _fake_citations(result)
        with patch.object(orchestration, "_agent_value", side_effect=sparse_company), patch.object(adapter, "_agent_citations", side_effect=citations):
            result = adapter.NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(FakeInputs(), {})
        self.assertTrue(all(row["no_evidence_research_roles"] == ["market_researcher"] for row in self.companies(result)))
        self.assertTrue(all(not row["research_incomplete"] for row in self.companies(result)))
        self.assertTrue(all(row["memory_mutation_eligible"] for row in self.companies(result)))
        self.assertEqual(result["metrics"]["research_resolver_agent_call_count"], 0)
        apply_inputs = FakeInputs()
        apply_inputs["variables"].update(memory_mode="apply", publish_dossier=True)
        with patch.object(orchestration, "_agent_value", side_effect=sparse_company), \
             patch.object(adapter, "_agent_citations", side_effect=citations), \
             patch.object(adapter, "_apply_company_memory", return_value={"memory_update_status": "applied"}) as memory_apply, \
             patch.object(adapter, "_apply_company_methodology", return_value={"methodology_learning_update_status": "applied"}) as methodology_apply:
            applied = adapter.NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(apply_inputs, {})
        self.assertEqual(memory_apply.call_count, 2)
        self.assertEqual(methodology_apply.call_count, 2)
        self.assertEqual(applied["outputs"]["intelligence_dossier"]["business_result_state"], "reviewed")
        def undisposed(role, company_id, payload):
            value = sparse_company(role, company_id, payload)
            if role == "evidence_critic":
                value["unmet_plan_requirements"] = []
            return value
        with patch.object(orchestration, "_agent_value", side_effect=undisposed), patch.object(adapter, "_agent_citations", side_effect=citations):
            result = adapter.NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(FakeInputs(), {})
        self.assertTrue(all(not row["quality_gate_passed"] for row in self.companies(result)))
        self.assertTrue(all(row["issues_annex"]["items"][-1]["rule"] == "no_evidence_not_disposed"
                            for row in self.companies(result)))

    def test_all_role_citations_survive_reflection_without_truncation(self):
        from devtools.skill_citation import CitationRef
        def citations(result):
            company_id = result["content"][0]["value"]["company_id"]
            role = result["content"][0]["value"]["role"]
            return tuple(CitationRef(locator=f"https://example.test/{company_id}/{role}/{i}", title="Evidence",
                                     source_kind="agent_citation", provider_family="vertex_ai") for i in range(30))
        inputs = FakeInputs(); inputs["variables"].update(portfolio_review_passes=3, retain_review_packet=True)
        with patch.object(adapter, "_agent_citations", side_effect=citations):
            result = adapter.NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(inputs, {})
        packet = result["outputs"]["intelligence_dossier"]["review_packet"]
        for row in packet["companies"]:
            self.assertTrue(all(len(item["citations"]) == 30 for item in row["research_role_evidence"]))
            self.assertEqual(len(row["memory_apply_citations"]), 24)

    def test_repair_provider_failure_is_counted_and_not_hidden(self):
        class FailingResolver(RepairInputs):
            def invoke_agent(self, role, *, input, on_error="raise"):
                if role == adapter.RESEARCH_RESOLVER_ROLE:
                    self.agent_calls.append((role, input["company_id"]))
                    raise RuntimeError("synthetic resolver transport failure")
                return super().invoke_agent(role, input=input, on_error=on_error)
        inputs = FailingResolver()
        with self.assertRaisesRegex(RuntimeError, "synthetic resolver transport failure"):
            self.run_preview(inputs)
        self.assertEqual(Counter(inputs.agent_calls)[(adapter.RESEARCH_RESOLVER_ROLE, 13)], 1)
        self.assertFalse(any(role.endswith("_update") for role, _ in inputs.dynamic_skill_calls))

    def test_failed_reflection_preserves_last_valid_review_and_withholds_updates(self):
        inputs = RepairInputs(resolver_invalid=True, failed_pass=2)
        inputs["variables"]["portfolio_review_passes"] = 3
        result = self.run_preview(inputs)
        for row in self.companies(result):
            self.assertTrue(row["research_incomplete"])
            self.assertFalse(row["memory_mutation_eligible"])
            self.assertEqual(row["portfolio_review_pass_count"], 2)
            self.assertNotIn("portfolio_researcher", row["no_evidence_research_roles"])
            self.assertEqual(row["portfolio_review_trace"][0]["status"], "validated")
            self.assertEqual(row["portfolio_review_trace"][1]["status"], "unresolved")

    def test_wrong_company_is_never_sent_to_repair_agent(self):
        inputs = FakeInputs(wrong_company_role="portfolio_researcher")
        with self.assertRaises(adapter.AgentContractValidationError) as caught:
            self.run_preview(inputs)
        self.assertEqual(caught.exception.code, "pharma_agent_company_id_invalid")
        self.assertFalse(any(role == adapter.RESEARCH_RESOLVER_ROLE for role, _ in inputs.agent_calls))

    def test_budgets_bound_every_requested_pass_and_repair_for_five_companies(self):
        for passes in (1, 2, 3):
            for mode in ("preview", "apply"):
                runtime = limits.RecordingRuntime()
                request = adapter.validate_batch_request({"variables": {"company_ids": [1,2,3,4,5], "memory_mode": mode}})
                bounded = adapter._BoundedAgentInputs(runtime, request, review_passes=passes)
                for company_id in request.company_ids:
                    roles = [adapter.BENCHMARK_ROLE, *([adapter.PLANNER_ROLE] * 4),
                             *(["portfolio_researcher"] * passes), "market_researcher", "regulatory_risk_researcher",
                             adapter.STRATEGIC_ROLE, adapter.CRITIC_ROLE, adapter.SYNTHESIS_ROLE, adapter.BENCHMARK_ROLE]
                    if mode == "apply":
                        roles.append(adapter.BENCHMARK_ROLE)
                    for role in roles:
                        bounded.invoke_agent(role, input={"company_id": company_id})
                        bounded.invoke_response_resolver(original_role=role, input={"company_id": company_id})
                    with self.assertRaises(adapter.AgentContractValidationError):
                        bounded.invoke_response_resolver(original_role=adapter.BENCHMARK_ROLE, input={"company_id": company_id})
                expected = 5 * 2 * ((12 if mode == "preview" else 13) + passes - 1)
                self.assertEqual(bounded.agent_call_count, expected)
                self.assertEqual(bounded.agent_call_limit, expected)

