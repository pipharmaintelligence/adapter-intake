from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from test_orchestration_preview import (
    FakeInputs, _agent_value, _fake_citations, adapter_module,
    NusaibahPharmaCompanyIntelligenceLabAdapter,
)
from devtools.proof_failure_detail import safe_proof_failure_detail


def research_payloads(local_id="claim_1"):
    return {
        role: {
            "claims": [{"claim_id": local_id, "statement": "Evidence preserved", "inference": False}],
            "sections": [{"section_id": role, "content": "Unchanged content"}],
            "uncertainties": [], "_citations": [],
        }
        for role in adapter_module.RESEARCH_ROLES
    }


class ResearchIdentityTests(unittest.TestCase):
    def test_valid_role_local_collision_is_disambiguated_without_changing_evidence(self):
        payloads = research_payloads()
        before = deepcopy(payloads)
        joined = adapter_module._join_research(payloads)
        self.assertEqual(len({c["claim_id"] for c in joined["claims"]}), 3)
        self.assertEqual(payloads, before)
        for role, claim in zip(adapter_module.RESEARCH_ROLES, joined["claims"]):
            self.assertTrue(claim["claim_id"].startswith(role + ":"))
            self.assertEqual({k: v for k, v in claim.items() if k != "claim_id"},
                             {k: v for k, v in before[role]["claims"][0].items() if k != "claim_id"})

    def test_long_ids_stay_bounded_and_stable_when_role_order_changes(self):
        payloads = research_payloads("x" * 128)
        first = adapter_module._join_research(payloads)
        second = adapter_module._join_research(dict(reversed(list(payloads.items()))))
        self.assertEqual(first, second)
        self.assertTrue(all(len(c["claim_id"]) <= 128 for c in first["claims"]))

    def test_empty_or_duplicate_claims_still_fail_with_safe_role_proof(self):
        role = adapter_module.RESEARCH_ROLES[0]
        for rule in ("missing_claims", "duplicate_claim_id"):
            with self.subTest(rule=rule):
                payloads = research_payloads()
                claims = payloads[role]["claims"]
                payloads[role]["claims"] = [] if rule == "missing_claims" else claims * 2
                with self.assertRaises(adapter_module.AgentContractValidationError) as caught:
                    adapter_module._join_research(payloads)
                error = caught.exception
                self.assertEqual(error.code, "pharma_agent_business_schema_invalid")
                self.assertEqual(error.proof_failure_detail["role"], role)
                self.assertEqual(error.proof_failure_detail["rule"], rule)
                self.assertEqual(safe_proof_failure_detail(error.proof_failure_detail), error.proof_failure_detail)

    def test_full_preview_accepts_reused_local_ids_and_preserves_downstream_references(self):
        def local_ids(role, company_id, input_value):
            value = _agent_value(role, company_id, input_value)
            if role in adapter_module.RESEARCH_ROLES:
                for ordinal, claim in enumerate(value["claims"]):
                    claim["claim_id"] = f"claim_{ordinal}"
            return value
        inputs = FakeInputs()
        with patch("test_orchestration_preview._agent_value", side_effect=local_ids), patch.object(
            adapter_module, "_agent_citations", side_effect=_fake_citations,
        ):
            result = NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(inputs, {})
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["metrics"]["completed_company_count"], 2)
        self.assertEqual(result["metrics"]["memory_mutations_made"], 0)
        for role, _, payload in inputs.agent_inputs:
            if role == "intelligence_synthesizer":
                ids = payload["allowed_memory_fact_ids"]
                self.assertEqual(len(ids), len(set(ids)))
                self.assertTrue(all(":" in claim_id for claim_id in ids))

    def test_invalid_research_payload_has_safe_stage_and_role(self):
        def malformed(role, company_id, input_value):
            value = _agent_value(role, company_id, input_value)
            if role == "market_researcher":
                value["claims"][0]["confidence"] = "sensitive-unreviewed-value"
            return value
        with patch("test_orchestration_preview._agent_value", side_effect=malformed), patch.object(
            adapter_module, "_agent_citations", side_effect=_fake_citations,
        ):
            with self.assertRaises(adapter_module.AgentContractValidationError) as caught:
                NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(FakeInputs(), {})
        proof = caught.exception.proof_failure_detail
        self.assertEqual(proof["role"], "market_researcher")
        self.assertEqual(proof["stage"], "research_payload")
        self.assertEqual(safe_proof_failure_detail(proof), proof)
        self.assertNotIn("sensitive-unreviewed-value", json.dumps(proof) + str(caught.exception))

    def test_invalid_citation_has_safe_stage_and_role(self):
        def invalid_citations(agent_result):
            role = agent_result["content"][0]["value"]["role"]
            if role == "market_researcher":
                raise ValueError("sensitive-citation-value")
            return _fake_citations(agent_result)
        with patch.object(adapter_module, "_agent_citations", side_effect=invalid_citations):
            with self.assertRaises(adapter_module.AgentContractValidationError) as caught:
                NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(FakeInputs(), {})
        proof = caught.exception.proof_failure_detail
        self.assertEqual(proof["role"], "market_researcher")
        self.assertEqual(proof["stage"], "research_citations")
        self.assertEqual(safe_proof_failure_detail(proof), proof)
        self.assertNotIn("sensitive-citation-value", json.dumps(proof) + str(caught.exception))
