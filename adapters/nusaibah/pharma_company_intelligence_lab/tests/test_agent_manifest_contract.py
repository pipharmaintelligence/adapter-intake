from __future__ import annotations

import json
import unittest
from pathlib import Path

ASSET_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ASSET_ROOT / "nusaibah_pharma_company_intelligence_lab.asset.json"

EXPECTED = {
    "portfolio_researcher": ("gemini-3.8-flash", "medium", 4096, True),
    "market_researcher": ("gemini-3.8-flash", "medium", 4096, True),
    "regulatory_risk_researcher": ("gemini-3.8-flash", "high", 6144, True),
    "strategic_analyst": ("gemini-3.1-pro-preview", "high", 6144, False),
    "evidence_critic": ("gemini-3.1-pro-preview", "high", 6144, False),
    "intelligence_synthesizer": ("gemini-3.8-flash", "high", 8192, False),
    "memory_benchmark_reviewer": ("gemini-3.8-flash", "medium", 4096, False),
}


class PackagedAgentDefinitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.agents = cls.manifest["versions"]["0.1.0"]["agents"]

    def test_exact_role_set_is_frozen(self) -> None:
        self.assertEqual(set(self.agents), set(EXPECTED))

    def test_model_thinking_search_and_json_policy_are_exact(self) -> None:
        for role, (model, thinking, max_tokens, search_enabled) in EXPECTED.items():
            with self.subTest(role=role):
                agent = self.agents[role]
                self.assertEqual(agent["contract_version"], "1.0.0")
                definition = agent["definition"]
                self.assertEqual(len(definition["registry_entries"]), 1)
                chain = definition["chain"]
                self.assertEqual(chain["chain_id"], agent["contract_key"])
                self.assertEqual(chain["version"], agent["contract_version"])
                self.assertEqual(chain["budget_policy"], {
                    "max_tool_calls": 0,
                    "max_provider_calls": 1,
                })
                self.assertEqual(len(chain["steps"]), 1)

                step = chain["steps"][0]
                self.assertEqual(step["provider"], "vertex_ai")
                policy = step["provider_policy"]
                generation = policy["generation_policy"]

                self.assertEqual(policy["model"], model)
                self.assertEqual(generation["thinking_level"], thinking)
                self.assertEqual(generation["max_tokens"], max_tokens)
                self.assertEqual(generation["response_format"], "json_object")

                if search_enabled:
                    self.assertIs(policy["search_enabled"], True)
                    self.assertEqual(policy["search_mode"], "provider_grounding")
                    self.assertEqual(policy["citation_policy"], "refs_only")
                else:
                    self.assertNotIn("search_enabled", policy)
                    self.assertNotIn("search_mode", policy)
                    self.assertNotIn("citation_policy", policy)

    def test_gemini_38_roles_omit_sampling_parameters(self) -> None:
        for role, (model, _thinking, _max_tokens, _search) in EXPECTED.items():
            if model != "gemini-3.8-flash":
                continue
            with self.subTest(role=role):
                generation = (
                    self.agents[role]["definition"]["chain"]["steps"][0]
                    ["provider_policy"]["generation_policy"]
                )
                self.assertNotIn("temperature", generation)
                self.assertNotIn("top_p", generation)
                self.assertNotIn("top_k", generation)

    def test_every_role_has_fixed_prompt_and_safe_storage_policy(self) -> None:
        for role, agent in self.agents.items():
            with self.subTest(role=role):
                definition = agent["definition"]
                prompt = definition["chain"]["steps"][0]["input"]["text"]
                self.assertIsInstance(prompt, str)
                self.assertTrue(prompt.strip())
                self.assertGreaterEqual(len(prompt.strip()), 80)
                self.assertEqual(
                    definition["chain"]["safety_policy"],
                    {"store_prompt": False, "store_output": False},
                )
                self.assertEqual(
                    definition["registry_entries"][0]["safety_policy"],
                    {"store_prompt": False, "store_output": False},
                )


if __name__ == "__main__":
    unittest.main()
