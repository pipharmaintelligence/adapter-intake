from __future__ import annotations

from unittest.mock import patch
import unittest

import nusaibah_pharma_company_intelligence_lab_adapter as legacy
from orchestration_v0_1_21 import (
    IndependentReviewRequiredError,
    invoke_v0_1_21,
)
from review_packet_v0_1_21 import SCHEMA_VERSION as REVIEW_SCHEMA_VERSION
from test_orchestration_preview import FakeInputs, _fake_citations


class V021Inputs(FakeInputs):
    """Return deterministic v2 research claims with admitted test locators."""

    def invoke_agent(self, role: str, *, input=None, on_error="raise"):
        envelope = super().invoke_agent(role, input=input, on_error=on_error)
        value = envelope["result"]["content"][0]["value"]

        if role in legacy.RESEARCH_ROLES:
            locator = f"urn:pi:test:{value['company_id']}:{role}"
            value["schema_version"] = "pharma_research_agent.v2"
            for claim in value["claims"]:
                claim["citation_locators"] = [locator]
                claim["evidence_qualifiers"] = []

        if role == legacy.SYNTHESIS_ROLE:
            allowed = list(input["allowed_memory_fact_ids"])
            value["memory_candidate"]["fact_ids"] = [allowed[0], allowed[-1]]

        return envelope


class OrchestrationV021Tests(unittest.TestCase):
    def test_preview_uses_claim_evidence_and_blocks_all_mutation(self) -> None:
        inputs = V021Inputs()
        inputs["variables"]["retain_review_packet"] = True

        with patch.object(legacy, "_agent_citations", side_effect=_fake_citations):
            response = invoke_v0_1_21(
                inputs,
                asset_identity="nusaibah.pharma_company_intelligence_lab:0.1.21",
            )

        self.assertEqual("success", response["status"])
        dossier = response["outputs"]["intelligence_dossier"]
        self.assertEqual("review_pending", dossier["business_result_state"])
        self.assertEqual("not_reviewed", dossier["independent_review_status"])
        self.assertEqual(REVIEW_SCHEMA_VERSION, dossier["review_packet"]["schema_version"])
        self.assertFalse(dossier["review_packet"]["apply_authority"])
        self.assertEqual(0, response["metrics"]["memory_mutations_made"])
        self.assertEqual(
            0,
            response["metrics"]["methodology_learning_mutations_made"],
        )
        self.assertFalse(
            any(role.endswith("_update") for role, _ in inputs.dynamic_skill_calls)
        )

        for result, review in zip(
            dossier["company_results"],
            dossier["review_packet"]["companies"],
            strict=True,
        ):
            self.assertTrue(result["automated_quality_gate_passed"])
            self.assertTrue(result["evidence_selection_complete"])
            self.assertEqual("not_reviewed", result["independent_review_status"])
            self.assertFalse(result["memory_mutation_eligible"])
            self.assertTrue(result["memory_pre_review_candidate_eligible"])
            self.assertEqual("review_required", result["memory_update_status"])
            self.assertEqual(
                result["evidence_selection_digest"],
                review["evidence_selection"]["selection_digest"],
            )
            self.assertEqual(
                result["evidence_selection_digest"],
                review["memory_proposal"]["evidence_selection_digest"],
            )
            selected_locators = {
                item["locator"] for item in review["memory_apply_citations"]
            }
            company_id = result["company_id"]
            self.assertIn(
                f"urn:pi:test:{company_id}:portfolio_researcher",
                selected_locators,
            )
            self.assertIn(
                f"urn:pi:test:{company_id}:regulatory_risk_researcher",
                selected_locators,
            )
            self.assertEqual("claim", review["evidence_granularity"])
            self.assertFalse(review["apply_authority"])

    def test_apply_is_rejected_before_helpers_or_provider_calls(self) -> None:
        inputs = V021Inputs()
        inputs["variables"]["memory_mode"] = "apply"

        with self.assertRaises(IndependentReviewRequiredError) as raised:
            invoke_v0_1_21(
                inputs,
                asset_identity="nusaibah.pharma_company_intelligence_lab:0.1.21",
            )

        self.assertEqual(
            "pharma_independent_review_required",
            raised.exception.code,
        )
        self.assertEqual([], inputs.agent_calls)
        self.assertEqual([], inputs.dynamic_skill_calls)

    def test_review_packet_is_optional_but_apply_authority_stays_false(self) -> None:
        inputs = V021Inputs()

        with patch.object(legacy, "_agent_citations", side_effect=_fake_citations):
            response = invoke_v0_1_21(
                inputs,
                asset_identity="nusaibah.pharma_company_intelligence_lab:0.1.21",
            )

        dossier = response["outputs"]["intelligence_dossier"]
        self.assertNotIn("review_packet", dossier)
        self.assertTrue(
            all(
                item["independent_review_status"] == "not_reviewed"
                for item in dossier["company_results"]
            )
        )
        self.assertTrue(
            all(
                item["memory_mutation_eligible"] is False
                for item in dossier["company_results"]
            )
        )


if __name__ == "__main__":
    unittest.main()
