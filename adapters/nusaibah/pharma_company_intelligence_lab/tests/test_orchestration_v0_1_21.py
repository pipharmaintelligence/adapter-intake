from __future__ import annotations

import json
from unittest.mock import patch
import unittest

import nusaibah_pharma_company_intelligence_lab_adapter as legacy
from claim_semantics_v0_1_21 import SCHEMA_VERSION as SEMANTIC_SCHEMA_VERSION
from methodology_learning_v0_1_21 import LESSONS
from orchestration_v0_1_21 import (
    IndependentReviewRequiredError,
    invoke_v0_1_21,
)
from research_section_projection_v0_1_21 import WITHHELD_SECTION_TEXT
from review_packet_v0_1_21 import SCHEMA_VERSION as REVIEW_SCHEMA_VERSION
from test_orchestration_preview import FakeInputs, _fake_citations


ASSET_IDENTITY = "nusaibah.pharma_company_intelligence_lab:0.1.21"


def _semantic_context() -> dict[str, object]:
    return {
        "schema_version": SEMANTIC_SCHEMA_VERSION,
        "event_date": None,
        "publication_date": None,
        "status_as_of_date": None,
        "event_state": "not_applicable",
        "observation_kind": "company_reported",
        "actor": None,
        "counterparty": None,
        "territory": None,
        "manufacturing_responsibility": None,
        "reported_total": None,
        "component_total": None,
        "remainder_label": None,
        "governed_snapshot_relation": "not_applicable",
        "entity_label_kind": "not_applicable",
    }


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
                claim["semantic_context"] = _semantic_context()

        if role == legacy.SYNTHESIS_ROLE:
            allowed = list(input["allowed_memory_fact_ids"])
            value["memory_candidate"]["fact_ids"] = [allowed[0], allowed[-1]]

        return envelope


class WithheldClaimInputs(V021Inputs):
    """Inject one unsupported claim and matching unsafe section prose."""

    sentinel = "UNSUPPORTED-SECTION-PROSE-MUST-NOT-REACH-DOWNSTREAM"

    def invoke_agent(self, role: str, *, input=None, on_error="raise"):
        envelope = super().invoke_agent(role, input=input, on_error=on_error)
        if role != "portfolio_researcher":
            return envelope

        value = envelope["result"]["content"][0]["value"]
        if len(value["claims"]) < 2:
            raise AssertionError("portfolio fixture must expose sibling claims")
        value["claims"][1]["statement"] = self.sentinel
        value["claims"][1]["citation_locators"] = []
        affected_section = value["claims"][1]["section_id"]
        section = next(
            item for item in value["sections"]
            if item["section_id"] == affected_section
        )
        section["content"] = self.sentinel
        for subsection in section["subsections"]:
            subsection["content"] = self.sentinel
        return envelope


class UnknownCandidateInputs(V021Inputs):
    """Return one synthesis candidate that references no accepted claim."""

    def invoke_agent(self, role: str, *, input=None, on_error="raise"):
        envelope = super().invoke_agent(role, input=input, on_error=on_error)
        if role == legacy.SYNTHESIS_ROLE:
            value = envelope["result"]["content"][0]["value"]
            value["memory_candidate"]["fact_ids"] = ["unknown-fact-id"]
        return envelope


class OrchestrationV021Tests(unittest.TestCase):
    def test_preview_uses_claim_evidence_and_blocks_all_mutation(self) -> None:
        inputs = V021Inputs()
        inputs["variables"]["retain_review_packet"] = True

        with patch.object(legacy, "_agent_citations", side_effect=_fake_citations):
            response = invoke_v0_1_21(
                inputs,
                asset_identity=ASSET_IDENTITY,
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

        expected_rule_ids = {rule_id for rule_id, _instruction in LESSONS}
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
            self.assertEqual(
                expected_rule_ids,
                set(result["methodology_learning_rule_ids"]),
            )
            self.assertTrue(result["methodology_learning_previous_preserved"])
            self.assertFalse(result["methodology_learning_apply_authority"])
            self.assertEqual(
                result["methodology_learning_proposal_digest"],
                review["methodology_proposal"]["proposal_digest"],
            )
            baseline = review["methodology_proposal"]["baseline_section_text"]
            replacement = review["methodology_proposal"]["replacement_text"]
            self.assertTrue(replacement.startswith(baseline))

    def test_withheld_claim_cannot_leak_through_section_prose(self) -> None:
        inputs = WithheldClaimInputs()
        inputs["variables"]["retain_review_packet"] = True

        with patch.object(legacy, "_agent_citations", side_effect=_fake_citations):
            response = invoke_v0_1_21(inputs, asset_identity=ASSET_IDENTITY)

        dossier = response["outputs"]["intelligence_dossier"]
        self.assertEqual("incomplete", dossier["business_result_state"])
        result = dossier["company_results"][0]
        review = dossier["review_packet"]["companies"][0]
        self.assertGreater(result["accepted_claim_count"], 0)
        self.assertGreater(result["withheld_claim_count"], 0)
        self.assertFalse(result["automated_quality_gate_passed"])
        self.assertEqual("withheld_incomplete", result["memory_update_status"])

        strategic_input = next(
            value
            for role, company_id, value in inputs.agent_inputs
            if role == legacy.STRATEGIC_ROLE and company_id == result["company_id"]
        )
        serialized = json.dumps(strategic_input["research_evidence"])
        self.assertNotIn(WithheldClaimInputs.sentinel, serialized)
        self.assertIn(WITHHELD_SECTION_TEXT, serialized)

        portfolio = next(
            item for item in review["research_role_evidence"]
            if item["role"] == "portfolio_researcher"
        )
        self.assertIn(
            WithheldClaimInputs.sentinel,
            json.dumps(portfolio["sections"]),
        )
        self.assertNotIn(
            WithheldClaimInputs.sentinel,
            json.dumps(portfolio["downstream_sections"]),
        )
        self.assertTrue(portfolio["withheld_section_ids"])

    def test_unknown_candidate_fact_is_recoverable_and_research_is_retained(self) -> None:
        inputs = UnknownCandidateInputs()
        inputs["variables"]["retain_review_packet"] = True

        with patch.object(legacy, "_agent_citations", side_effect=_fake_citations):
            response = invoke_v0_1_21(inputs, asset_identity=ASSET_IDENTITY)

        dossier = response["outputs"]["intelligence_dossier"]
        self.assertEqual("incomplete", dossier["business_result_state"])
        result = dossier["company_results"][0]
        review = dossier["review_packet"]["companies"][0]
        self.assertTrue(result["research_incomplete"])
        self.assertGreater(result["accepted_claim_count"], 0)
        self.assertEqual("withheld_incomplete", result["memory_update_status"])
        self.assertFalse(result["memory_mutation_eligible"])
        self.assertFalse(result["automated_quality_gate_passed"])
        self.assertEqual([], review["memory_proposal"]["fact_ids"])
        self.assertGreater(len(review["accepted_claims"]), 0)
        self.assertIn(
            "candidate_fact_id_unknown",
            json.dumps(result["issues_annex"]),
        )
        self.assertFalse(
            any(role.endswith("_update") for role, _ in inputs.dynamic_skill_calls)
        )

    def test_apply_is_rejected_before_helpers_or_provider_calls(self) -> None:
        inputs = V021Inputs()
        inputs["variables"]["memory_mode"] = "apply"

        with self.assertRaises(IndependentReviewRequiredError) as raised:
            invoke_v0_1_21(
                inputs,
                asset_identity=ASSET_IDENTITY,
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
                asset_identity=ASSET_IDENTITY,
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
