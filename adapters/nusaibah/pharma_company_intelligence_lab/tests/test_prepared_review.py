from __future__ import annotations
import copy
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import nusaibah_pharma_company_intelligence_lab_adapter as adapter
import review_packet_v0_1_16 as packet
from devtools.dynamic_skill_runtime import DynamicSkillRuntimeError
import test_orchestration_preview as orchestration
from test_orchestration_preview import FakeInputs, FirstRunMethodologyInputs, _fake_citations


class PreparedReviewTests(unittest.TestCase):
    def run_preview(self, inputs):
        with patch.object(adapter, "_agent_citations", side_effect=_fake_citations):
            return adapter.NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(inputs, {})

    def test_default_preserves_output_and_call_budget(self):
        inputs = FakeInputs()
        result = self.run_preview(inputs)
        self.assertNotIn("review_packet", result["outputs"]["intelligence_dossier"])
        self.assertEqual(len(inputs.agent_calls), 24)
        self.assertFalse(any(role.endswith("_update") for role, _ in inputs.dynamic_skill_calls))

    def test_exact_proposals_and_full_quality_evidence_survive_json_roundtrip(self):
        inputs = FakeInputs()
        inputs["variables"]["retain_review_packet"] = True
        states = []
        original = adapter._prepare_company
        def capture(*args, **kwargs):
            state = original(*args, **kwargs)
            states.append(state)
            return state
        with patch.object(adapter, "_prepare_company", side_effect=capture):
            result = self.run_preview(inputs)
        value = json.loads(json.dumps(result))["outputs"]["intelligence_dossier"]["review_packet"]
        self.assertEqual(value["review_state"], "not_reviewed")
        self.assertIs(value["apply_authority"], False)
        self.assertEqual(value["asset_identity"], "nusaibah.pharma_company_intelligence_lab:0.1.19")
        for company, state in zip(value["companies"], states):
            memory = company["memory_proposal"]
            expected = state["memory_candidate"].markdown.rstrip() + "\n"
            self.assertEqual(memory["replacement_text"], expected)
            self.assertEqual(memory["replacement_sha256"], "sha256:" + sha256(expected.encode()).hexdigest())
            self.assertEqual(memory["fact_ids"], list(state["memory_candidate"].fact_ids))
            self.assertEqual(company["methodology_proposal"]["replacement_text"], state["methodology_learning_candidate"])
            self.assertEqual(company["claims"], state["joined_research"]["claims"])
            self.assertTrue(set(memory["fact_ids"]) <= {claim["claim_id"] for claim in company["claims"]})
            self.assertEqual(company["critic"], state["critic"])
            self.assertEqual(company["planner_chunks"], list(state["planner_chunks"]))
            self.assertEqual(company["benchmark"]["before"], state["before_benchmark"])
            self.assertEqual(company["benchmark"]["projected"], state["projected_after_benchmark"])
            self.assertIsNone(company["benchmark"]["committed"])
            self.assertEqual(company["residual_uncertainties"], state["residual_uncertainties"])
            self.assertEqual(len(company["research_role_evidence"]), 3)
        self.assertEqual(len(inputs.agent_calls), 24)
        self.assertFalse(any(role.endswith("_update") for role, _ in inputs.dynamic_skill_calls))

    def test_regressing_memory_retains_rejected_proposal_and_skips_methodology(self):
        inputs=FakeInputs()
        inputs["variables"]["retain_review_packet"]=True
        original=orchestration._agent_value
        def regress(role,company_id,input_value):
            value=original(role,company_id,input_value)
            if role=="memory_benchmark_reviewer" and input_value["memory_stage"]=="proposed":
                for answer in value["results"]:
                    answer["coverage"]="not_covered"
            return value
        with patch.object(orchestration,"_agent_value",side_effect=regress):
            dossier=self.run_preview(inputs)["outputs"]["intelligence_dossier"]
        for result,company in zip(dossier["company_results"],dossier["review_packet"]["companies"]):
            self.assertFalse(result["benchmark_non_regression"])
            self.assertFalse(company["memory_proposal"]["mutation_eligible"])
            self.assertTrue(company["memory_proposal"]["replacement_text"])
            self.assertIsNone(company["methodology_proposal"]["replacement_text"])
            self.assertIsNone(company["methodology_proposal"]["replacement_sha256"])
            self.assertEqual(result["methodology_learning_update_status"],"no_change_recommended")
        self.assertEqual(len(inputs.agent_calls),24)
        self.assertFalse(any(role.endswith("_update") for role,_ in inputs.dynamic_skill_calls))

    def test_digest_binds_the_entire_packet(self):
        inputs=FakeInputs()
        inputs["variables"]["retain_review_packet"]=True
        value=self.run_preview(inputs)["outputs"]["intelligence_dossier"]["review_packet"]
        expected=value.pop("packet_sha256")
        self.assertEqual(expected, "sha256:" + sha256(packet.canonical_bytes(value)).hexdigest())
        value["companies"][0]["critic"]["recommendation"]="fail"
        self.assertNotEqual(expected, "sha256:" + sha256(packet.canonical_bytes(value)).hexdigest())

    def test_invalid_opt_in_rejected_before_skill_or_agent_calls(self):
        for value in (1, "true", None, [], {}):
            with self.subTest(value=value):
                inputs=FakeInputs()
                inputs["variables"]["retain_review_packet"]=value
                with self.assertRaisesRegex(ValueError, "must be boolean"):
                    self.run_preview(inputs)
                self.assertEqual(inputs.agent_calls, [])
                self.assertEqual(inputs.dynamic_skill_calls, [])

    def test_missing_methodology_still_allows_preview_and_reports_uninitialized(self):
        inputs=FirstRunMethodologyInputs()
        inputs["variables"]["retain_review_packet"]=True
        value=self.run_preview(inputs)["outputs"]["intelligence_dossier"]["review_packet"]
        for company in value["companies"]:
            learning=company["methodology_proposal"]
            self.assertFalse(learning["initialized"])
            self.assertIsNone(learning["baseline_content_digest"])
            self.assertTrue(learning["replacement_text"])
        self.assertEqual(len(inputs.agent_calls),24)

    def test_apply_uninitialized_first_or_second_company_costs_zero_agent_calls(self):
        for missing_id in (13,59):
            class Missing(FakeInputs):
                def dynamic_skill(self, role, *, variables=None):
                    if role=="company_methodology" and int(variables["company_id"])==missing_id:
                        raise DynamicSkillRuntimeError("dynamic_skill_not_initialized")
                    return super().dynamic_skill(role,variables=variables)
            inputs=Missing()
            inputs["variables"]["memory_mode"]="apply"
            with self.assertRaisesRegex(RuntimeError,"governed create-if-absent"):
                self.run_preview(inputs)
            self.assertEqual(inputs.agent_calls,[])
            self.assertFalse(any(role.endswith("_update") for role,_ in inputs.dynamic_skill_calls))

    def test_apply_invalid_second_memory_costs_zero_agent_calls(self):
        class Empty(FakeInputs):
            def dynamic_skill(self, role, *, variables=None):
                handle=super().dynamic_skill(role,variables=variables)
                if role=="company_memory" and int(variables["company_id"])==59:
                    handle.text=""
                return handle
        inputs=Empty()
        inputs["variables"]["memory_mode"]="apply"
        with self.assertRaisesRegex(RuntimeError,"memory is empty"):
            self.run_preview(inputs)
        self.assertEqual(inputs.agent_calls,[])
        self.assertFalse(any(role.endswith("_update") for role,_ in inputs.dynamic_skill_calls))

    def test_oversized_packet_fails_before_mutation_without_truncation(self):
        inputs=FakeInputs()
        inputs["variables"].update(memory_mode="apply",retain_review_packet=True)
        with patch.object(packet,"MAX_REVIEW_OUTPUT_BYTES",1):
            with self.assertRaisesRegex(RuntimeError,"no candidate was truncated"):
                self.run_preview(inputs)
        self.assertFalse(any(role.endswith("_update") for role,_ in inputs.dynamic_skill_calls))

    def test_no_handles_raw_agent_envelopes_or_caller_authority_in_output(self):
        inputs=FakeInputs()
        inputs["variables"].update(retain_review_packet=True, arbitrary_handle="do-not-export")
        value=self.run_preview(inputs)["outputs"]["intelligence_dossier"]["review_packet"]
        encoded=json.dumps(value)
        for forbidden in ("do-not-export", "provider_metadata", "agent_result.v1", "methodology_learning_handle"):
            self.assertNotIn(forbidden,encoded)
        self.assertIn("individual claim-to-citation mapping unavailable",encoded)

    def test_role_citations_are_complete_while_apply_citations_match_existing_limit(self):
        states=[]
        original=adapter._prepare_company
        def capture(*args,**kwargs):
            state=original(*args,**kwargs)
            citations=list(state["citations"])*12
            for research in state["research"].values():
                research["_citations"]=citations
            state["citations"]=citations
            states.append(state)
            return state
        inputs=FakeInputs()
        inputs["variables"]["retain_review_packet"]=True
        with patch.object(adapter,"_prepare_company",side_effect=capture):
            value=self.run_preview(inputs)["outputs"]["intelligence_dossier"]["review_packet"]
        for company,state in zip(value["companies"],states):
            self.assertEqual(len(company["memory_apply_citations"]),24)
            self.assertGreater(len(company["research_role_evidence"][0]["citations"]),24)
            self.assertEqual(len(company["research_role_evidence"][0]["citations"]),len(state["citations"]))


if __name__=="__main__":
    unittest.main()
