from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ASSET_ROOT = Path(__file__).resolve().parents[1]
if str(ASSET_ROOT) not in sys.path:
    sys.path.insert(0, str(ASSET_ROOT))

import legacy_preparation_helpers_v0_1_21 as legacy
from nusaibah_pharma_company_intelligence_lab_v0_1_22_adapter import (
    NusaibahPharmaCompanyIntelligenceLabV022Adapter,
)
from orchestration_v0_1_21 import IndependentReviewRequiredError
from test_orchestration_preview import _fake_citations
from test_orchestration_v0_1_21 import V021Inputs


def _json(name: str) -> dict:
    return json.loads((ASSET_ROOT / name).read_text(encoding="utf-8"))


class ResponseBudgetV022Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = _json("tests/fixtures/release-0.1.22/nusaibah_pharma_company_intelligence_lab.asset.json")
        self.active = self.manifest["versions"]["0.1.22"]
        self.previous = _json(
            "tests/fixtures/release-0.1.21/nusaibah_pharma_company_intelligence_lab.asset.json"
        )["versions"]["0.1.21"]
        self.definitions = _json("tests/fixtures/release-0.1.21/exact-agent-definitions.json")
        self.budgets = _json("pharma_response_budgets_v0_1_22.json")

    def test_every_provider_step_has_a_budget_and_fresh_contract(self) -> None:
        self.assertEqual("0.1.22", self.manifest["default"])
        self.assertEqual({"0.1.22"}, set(self.manifest["versions"]))
        self.assertEqual("0.1.22", self.budgets["asset_version"])
        self.assertEqual(32000, self.budgets["provider_token_ceiling"])
        self.assertTrue(self.budgets["visible_targets_are_prompt_guidance"])
        self.assertEqual(set(self.active["agents"]), set(self.budgets["role_budgets"]))
        step_count = 0
        for role, agent in self.active["agents"].items():
            with self.subTest(role=role):
                budget = self.budgets["role_budgets"][role]
                self.assertEqual(budget["contract_version"], agent["contract_version"])
                self.assertNotEqual(self.previous["agents"][role]["contract_version"], agent["contract_version"])
                steps = agent["definition"]["chain"]["steps"]
                self.assertEqual(len(steps), len(budget["visible_character_targets"]))
                for step, target in zip(steps, budget["visible_character_targets"]):
                    policy = step["provider_policy"]
                    self.assertEqual(32000, policy["generation_policy"]["max_tokens"])
                    self.assertEqual(600, policy["timeout_seconds"])
                    guidance = step["input"]["text"].split("ROLE RESPONSE BUDGET (v1):", 1)[1]
                    self.assertIn(f"at most {target} characters", guidance)
                    self.assertIn("including thinking headroom", guidance)
                    self.assertIn("every tighter response_contract.compact_limits", guidance)
                    self.assertIn("one complete object with every required field", guidance)
                    self.assertIn("Never truncate JSON, drop required IDs", guidance)
                    self.assertIn("preserving existing facts, IDs and cardinality takes precedence", guidance)
                    step_count += 1
        self.assertEqual(12, step_count)

    def test_generation_repair_preserves_models_tools_authority_and_original_prompts(self) -> None:
        # Compare with exact previously admitted definitions, including the three
        # roles that 0.1.21 referenced without embedding their definitions.
        for role, agent in self.active["agents"].items():
            with self.subTest(role=role):
                previous_agent = self.previous["agents"][role]
                current_agent = {key: value for key, value in agent.items() if key not in {"definition", "contract_version"}}
                previous_refs = {key: value for key, value in previous_agent.items() if key not in {"definition", "contract_version"}}
                self.assertEqual(previous_refs, current_agent)
                normalized = copy.deepcopy(agent["definition"])
                old = self.definitions[role]
                normalized["chain"]["version"] = old["chain"]["version"]
                for step, original in zip(normalized["chain"]["steps"], old["chain"]["steps"]):
                    original_text, marker, guidance = step["input"]["text"].partition("\n\nROLE RESPONSE BUDGET (v1):")
                    self.assertTrue(marker)
                    self.assertTrue(guidance)
                    step["input"]["text"] = original_text
                    step["provider_policy"]["generation_policy"]["max_tokens"] = original["provider_policy"]["generation_policy"]["max_tokens"]
                self.assertEqual(old, normalized)

    def test_business_inputs_outputs_skills_and_promotion_metadata_remain_compatible(self) -> None:
        self.assertEqual(
            {key: value for key, value in self.previous.items() if key != "agents"},
            {key: value for key, value in self.active.items() if key != "agents"},
        )
        self.assertEqual("0.1.22", _json("pharma_roles_v0_1_22.json")["target_asset_version"])
        self.assertEqual("0.1.22", _json("materialization_promotion_acceptance_v0_1_22.json")["target_asset_version"])
        yaml = (ASSET_ROOT / "tests/fixtures/release-0.1.22/adapter.yaml").read_text(encoding="utf-8")
        self.assertIn("asset_version: 0.1.22\n", yaml)
        self.assertIn("adapter_module: nusaibah_pharma_company_intelligence_lab_v0_1_22_adapter.py", yaml)
        self.assertIn("  - nusaibah_pharma_company_intelligence_lab_v0_1_21_adapter.py", yaml)
        self.assertIn("  - pharma_response_budgets_v0_1_22.json", yaml)

    def test_new_entry_keeps_claim_review_and_zero_mutation_behavior(self) -> None:
        inputs = V021Inputs()
        inputs["variables"]["retain_review_packet"] = True
        with patch.object(legacy, "_agent_citations", side_effect=_fake_citations):
            result = NusaibahPharmaCompanyIntelligenceLabV022Adapter().invoke(inputs, {})
        self.assertEqual("success", result["status"])
        dossier = result["outputs"]["intelligence_dossier"]
        self.assertEqual("nusaibah.pharma_company_intelligence_lab:0.1.22", dossier["review_packet"]["asset_identity"])
        self.assertFalse(dossier["review_packet"]["apply_authority"])
        self.assertEqual(0, result["metrics"]["memory_mutations_made"])
        self.assertEqual(0, result["metrics"]["methodology_learning_mutations_made"])
        self.assertTrue(all(company["accepted_claim_count"] > 0 for company in dossier["company_results"]))

    def test_larger_generation_budget_does_not_grant_skill_publication_authority(self) -> None:
        inputs = V021Inputs()
        inputs["variables"]["memory_mode"] = "apply"
        with self.assertRaises(IndependentReviewRequiredError) as raised:
            NusaibahPharmaCompanyIntelligenceLabV022Adapter().invoke(inputs, {})
        self.assertEqual("pharma_independent_review_required", raised.exception.code)
        self.assertEqual([], inputs.agent_calls)
        self.assertEqual([], inputs.dynamic_skill_calls)


if __name__ == "__main__":
    unittest.main()
