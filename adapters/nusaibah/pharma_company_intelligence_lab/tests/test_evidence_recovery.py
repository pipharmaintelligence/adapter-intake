from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

import test_orchestration_preview as orchestration

adapter = orchestration.adapter_module
SECRET = "UNSUPPORTED-CONTENT-MUST-NOT-ESCAPE"


class EvidenceInputs(orchestration.FakeInputs):
    def __init__(self, missing_roles=(), *, missing_pass=None, mutate=None):
        super().__init__()
        self.missing_roles = set(missing_roles)
        self.missing_pass = missing_pass
        self.mutate = mutate
        self["variables"].update(portfolio_review_passes=2, retain_review_packet=True)

    def invoke_agent(self, role, *, input, on_error="raise"):
        envelope = super().invoke_agent(role, input=input, on_error=on_error)
        if input["company_id"] == 13:
            if (role in self.missing_roles
                    and (self.missing_pass is None or input["portfolio_review"]["pass_number"] == self.missing_pass)):
                envelope["result"]["offline_missing_citations"] = True
                value = envelope["result"]["content"][0]["value"]
                for claim in value["claims"]:
                    claim["statement"] = SECRET
                for section in value["sections"]:
                    section["content"] = "" if section["subsections"] else SECRET
                    for subsection in section["subsections"]:
                        subsection["content"] = SECRET
            if self.mutate:
                self.mutate(role, input, envelope)
        return envelope


def citations(result):
    return () if result.get("offline_missing_citations") else orchestration._fake_citations(result)


class EvidenceRecoveryTests(unittest.TestCase):
    def run_preview(self, inputs):
        with patch.object(adapter, "_agent_citations", side_effect=citations):
            return adapter.NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(inputs, {})

    def assert_incomplete(self, result):
        self.assertEqual(result["status"], "success")
        dossier = result["outputs"]["intelligence_dossier"]
        first, second = dossier["company_results"]
        self.assertTrue(first["research_incomplete"])
        self.assertFalse(first["memory_mutation_eligible"])
        self.assertFalse(second["research_incomplete"])
        self.assertEqual(dossier["business_result_state"], "incomplete")
        self.assertGreater(first["issues_annex"]["issue_count"], 0)
        self.assertFalse(first["issues_annex"]["truncated"])
        self.assertNotIn(SECRET, json.dumps(dossier))
        packet = dossier["review_packet"]
        self.assertFalse(packet["companies"][0]["memory_proposal"]["mutation_eligible"])
        body = {key: value for key, value in packet.items() if key != "packet_sha256"}
        self.assertEqual(packet["packet_sha256"], "sha256:" + sha256(adapter.canonical_bytes(body)).hexdigest())
        return first, packet["companies"][0]

    def test_all_uncited_roles_retain_incomplete_without_resolver_or_dependent_calls(self):
        inputs = EvidenceInputs(adapter.RESEARCH_ROLES)
        result = self.run_preview(inputs)
        first, packet = self.assert_incomplete(result)
        counts = Counter(inputs.agent_calls)
        for role in (adapter.STRATEGIC_ROLE, adapter.CRITIC_ROLE, adapter.SYNTHESIS_ROLE, adapter.RESEARCH_RESOLVER_ROLE):
            self.assertEqual(counts[(role, 13)], 0)
        self.assertEqual(counts[("portfolio_researcher", 13)], 1)
        self.assertEqual(counts[(adapter.BENCHMARK_ROLE, 13)], 1)  # existing-memory before only
        self.assertFalse(first["agent_schema_incomplete"])
        self.assertEqual(first["citation_sources"], [])
        self.assertEqual(packet["claims"], [])
        self.assertIsNone(packet["memory_proposal"]["replacement_text"])
        self.assertIsNone(packet["methodology_proposal"]["replacement_text"])
        self.assertEqual({item["rule"] for item in first["issues_annex"]["items"]},
                         {"research_citations_missing", "no_usable_research_evidence"})

    def test_one_uncited_role_keeps_other_evidence_and_other_company_can_apply(self):
        inputs = EvidenceInputs(["market_researcher"])
        inputs["variables"].update(memory_mode="apply", publish_dossier=True)
        with patch.object(adapter, "_apply_company_memory", return_value={"memory_update_status": "applied"}) as memory, \
             patch.object(adapter, "_apply_company_methodology", return_value={"methodology_learning_update_status": "applied"}) as methodology:
            result = self.run_preview(inputs)
        first, packet = self.assert_incomplete(result)
        self.assertEqual([call.args[1]["company_id"] for call in memory.call_args_list], [59])
        self.assertEqual([call.kwargs["company_id"] for call in methodology.call_args_list], [59])
        self.assertEqual({item["role"] for item in packet["research_role_evidence"]},
                         {"portfolio_researcher", "regulatory_risk_researcher"})
        self.assertEqual(first["research_claim_count"], 3)  # two reflected portfolio + one regulatory
        self.assertFalse(first["quality_gate_passed"])
        self.assertEqual(result["outputs"]["intelligence_dossier"]["publication_state"],
                         "runtime_output_ready_for_output_policy")

    def test_uncited_reflection_cannot_borrow_prior_citations_or_erase_prior_work(self):
        inputs = EvidenceInputs(["portfolio_researcher"], missing_pass=2)
        first, packet = self.assert_incomplete(self.run_preview(inputs))
        entry = next(item for item in first["issues_annex"]["items"] if item["role"] == "portfolio_researcher")
        self.assertEqual(entry["action"], "previous_validated_pass_retained")
        self.assertEqual(entry["pass_number"], 2)
        self.assertEqual(entry["withheld_claim_count"], 2)
        self.assertEqual(first["portfolio_review_trace"][0]["result_sha256"],
                         first["portfolio_review_trace"][1]["result_sha256"])
        self.assertEqual(Counter(inputs.agent_calls)[(adapter.RESEARCH_RESOLVER_ROLE, 13)], 0)
        self.assertTrue(any(claim["claim_id"].startswith("portfolio_researcher:") for claim in packet["claims"]))

    def test_other_roles_can_finish_when_critic_disposes_a_withheld_role(self):
        def mutate(role, input, envelope):
            if role == adapter.CRITIC_ROLE:
                envelope["result"]["content"][0]["value"]["unmet_plan_requirements"] = [
                    {"requirement_id": item["requirement_id"], "disposition": "unresolved_evidence",
                     "notes": "Research evidence was withheld; this gap remains explicit."}
                    for item in input["planner_requirements"] if item["role"] == "market_researcher"
                ]
        inputs = EvidenceInputs(["market_researcher"], mutate=mutate)
        first, packet = self.assert_incomplete(self.run_preview(inputs))
        self.assertTrue(first["quality_gate_passed"])
        self.assertEqual(Counter(inputs.agent_calls)[(adapter.SYNTHESIS_ROLE, 13)], 1)
        self.assertEqual(first["memory_update_status"], "withheld_incomplete")
        self.assertEqual(first["methodology_learning_update_status"], "withheld_incomplete")
        self.assertTrue(packet["claims"])
        self.assertIsNone(packet["methodology_proposal"]["replacement_text"])

    def test_critic_rejections_retain_issues_instead_of_aborting_batch(self):
        for rule, change in (
            ("critic_rejected", lambda v: v.update(recommendation="fail")),
            ("citation_coverage_insufficient", lambda v: v["citation_coverage"].update(status="insufficient")),
            ("unsupported_claims_remaining", lambda v: v.update(unsupported_claim_ids=["unknown-claim"])),
            ("required_sections_missing", lambda v: v.update(missing_section_ids=["company_profile"])),
        ):
            def mutate(role, input, envelope):
                if role == adapter.CRITIC_ROLE:
                    value = envelope["result"]["content"][0]["value"]
                    change(value)
                    if rule == "unsupported_claims_remaining":
                        value["unsupported_claim_ids"] = [input["research_evidence"]["claims"][0]["claim_id"]]
            with self.subTest(rule=rule):
                inputs = EvidenceInputs(mutate=mutate)
                first, packet = self.assert_incomplete(self.run_preview(inputs))
                self.assertFalse(first["quality_gate_passed"])
                self.assertIn(rule, {item["rule"] for item in first["issues_annex"]["items"]})
                self.assertEqual(Counter(inputs.agent_calls)[(adapter.SYNTHESIS_ROLE, 13)], 0)
                self.assertEqual(Counter(inputs.agent_calls)[(adapter.RESEARCH_RESOLVER_ROLE, 13)], 0)
                self.assertIsNone(packet["memory_proposal"]["replacement_text"])

    def test_original_malformed_json_is_withheld_without_raw_prose_or_blind_repair(self):
        for role in (adapter.PLANNER_ROLE, *adapter.RESEARCH_ROLES, adapter.STRATEGIC_ROLE,
                     adapter.CRITIC_ROLE, adapter.SYNTHESIS_ROLE, adapter.BENCHMARK_ROLE):
            def mutate(actual, input, envelope):
                if actual == role:
                    envelope["result"]["content"][0]["value"] = "```json\n{" + SECRET
            with self.subTest(role=role):
                inputs = EvidenceInputs(mutate=mutate)
                first, _ = self.assert_incomplete(self.run_preview(inputs))
                self.assertIn("json_object_invalid", {item["rule"] for item in first["issues_annex"]["items"]})
                self.assertEqual(Counter(inputs.agent_calls)[(adapter.RESEARCH_RESOLVER_ROLE, 13)], 0)

    def test_wrong_company_cannot_hide_behind_wrong_business_schema(self):
        def mutate(role, input, envelope):
            if role == "market_researcher":
                envelope["result"]["content"][0]["value"].update(company_id=999, schema_version="wrong")
        with self.assertRaises(adapter.AgentContractValidationError) as caught:
            self.run_preview(EvidenceInputs(mutate=mutate))
        self.assertEqual(caught.exception.code, "pharma_agent_company_id_invalid")

    def test_corrupt_citation_authority_stays_fatal(self):
        with patch.object(adapter, "_agent_citations", side_effect=ValueError("invalid authority")):
            with self.assertRaises(adapter.AgentContractValidationError) as caught:
                adapter.NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(EvidenceInputs(), {})
        self.assertEqual(caught.exception.proof_failure_detail["stage"], "research_citations")

    def test_negative_critic_claim_withholds_its_role_prose_from_partial_packet(self):
        def mutate(role, input, envelope):
            if role == adapter.CRITIC_ROLE:
                claim = next(c for c in input["research_evidence"]["claims"] if c["claim_id"].startswith("market_researcher:"))
                envelope["result"]["content"][0]["value"]["unsupported_claim_ids"] = [claim["claim_id"]]
        first, packet = self.assert_incomplete(self.run_preview(EvidenceInputs(mutate=mutate)))
        self.assertNotIn("market_researcher", {row["role"] for row in packet["research_role_evidence"]})
        self.assertTrue(packet["claims"])

    def test_empty_claims_and_uncertainties_are_an_issue_not_a_join_failure(self):
        def mutate(role, input, envelope):
            if role in adapter.RESEARCH_ROLES:
                envelope["result"]["content"][0]["value"].update(claims=[], uncertainties=[])
        inputs = EvidenceInputs(mutate=mutate)
        first, packet = self.assert_incomplete(self.run_preview(inputs))
        self.assertIn("explicit_evidence_gap_required", {item["rule"] for item in first["issues_annex"]["items"]})
        self.assertEqual(packet["claims"], [])
        self.assertEqual(Counter(inputs.agent_calls)[(adapter.RESEARCH_RESOLVER_ROLE, 13)], 0)

    def test_claimless_uncited_prose_cannot_leak_as_accepted_evidence(self):
        def mutate(role, input, envelope):
            if role == "market_researcher":
                envelope["result"]["content"][0]["value"].update(claims=[], uncertainties=["Evidence is unavailable."])
        inputs = EvidenceInputs(["market_researcher"], mutate=mutate)
        self.assert_incomplete(self.run_preview(inputs))

    def test_successful_companies_have_empty_annex_and_unchanged_eligibility(self):
        result = self.run_preview(EvidenceInputs())
        for row in result["outputs"]["intelligence_dossier"]["company_results"]:
            self.assertEqual(row["issues_annex"]["items"], [])
            self.assertFalse(row["issues_annex"]["canonical_candidates_withheld"])
            self.assertTrue(row["memory_mutation_eligible"])


if __name__ == "__main__":
    unittest.main()
