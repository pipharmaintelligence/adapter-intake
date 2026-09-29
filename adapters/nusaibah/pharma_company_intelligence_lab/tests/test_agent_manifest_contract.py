from __future__ import annotations

import json
import unittest
from pathlib import Path

ASSET_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ASSET_ROOT / "nusaibah_pharma_company_intelligence_lab.asset.json"
ADAPTER_YAML = ASSET_ROOT / "adapter.yaml"
ADAPTER_MODULE = ASSET_ROOT / "nusaibah_pharma_company_intelligence_lab_adapter.py"

ASSET_VERSION = "0.1.3"
CANONICAL_PROVIDER_REGISTRY_ENTRY = {
    "handle": "provider:text_generation",
    "type": "provider_execution",
    "version": "1.0.0",
    "visibility": "internal",
    "status": "active",
    "capabilities": ["text_generation"],
    "input_schema_version": None,
    "output_schema_version": None,
    "runtime": None,
    "safety_policy": {
        "store_prompt": False,
        "store_output": False,
    },
    "provenance_policy": {
        "record_step": True,
    },
    "access_policy": None,
    "metadata": {
        "provisioning_source": "pi_1895_capability_lab",
    },
}

EXPECTED = {
    "methodology_planner": ("gemini-3.8-flash", "medium", 2048, False),
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
        cls.agents = cls.manifest["versions"][ASSET_VERSION]["agents"]

    def test_asset_version_is_synchronized_across_intake_contract_and_manifest(self) -> None:
        adapter_yaml = ADAPTER_YAML.read_text(encoding="utf-8")
        adapter_module = ADAPTER_MODULE.read_text(encoding="utf-8")
        self.assertIn(f"asset_version: {ASSET_VERSION}", adapter_yaml)
        self.assertIn(f'version: ClassVar[str] = "{ASSET_VERSION}"', adapter_module)
        self.assertEqual(self.manifest["default"], ASSET_VERSION)
        self.assertEqual(set(self.manifest["versions"]), {ASSET_VERSION})

    def test_input_roles_freeze_governed_binding_and_direct_variables(self) -> None:
        inputs = self.manifest["versions"][ASSET_VERSION]["inputs"]
        self.assertEqual(
            inputs["companies"],
            {
                "required": True,
                "source": "binding",
                "shape": "object",
            },
        )
        self.assertEqual(
            inputs["variables"],
            {
                "required": True,
                "source": "direct",
                "shape": "object",
            },
        )

    def test_packaged_adapter_declares_python_agent_orchestration_owner_exactly_once(self) -> None:
        adapter_module = ADAPTER_MODULE.read_text(encoding="utf-8")
        marker = 'AGENT_ORCHESTRATION_OWNER = "python_adapter"'
        self.assertEqual(adapter_module.count(marker), 1)

    def test_exact_role_set_is_frozen(self) -> None:
        self.assertEqual(set(self.agents), set(EXPECTED))

    def test_all_roles_reuse_one_canonical_shared_provider_registry_entry(self) -> None:
        registry_entries = []
        for role, agent in self.agents.items():
            with self.subTest(role=role):
                entries = agent["definition"]["registry_entries"]
                self.assertEqual(len(entries), 1)
                self.assertEqual(entries[0], CANONICAL_PROVIDER_REGISTRY_ENTRY)
                registry_entries.append(entries[0])

        first = registry_entries[0]
        self.assertTrue(all(entry == first for entry in registry_entries[1:]))

    def test_chain_metadata_remains_agent_specific_not_shared_registry_metadata(self) -> None:
        planner_chain = self.agents["methodology_planner"]["definition"]["chain"]
        self.assertEqual(
            planner_chain["metadata"]["provisioning_source"],
            "pi_1954_adaptive_methodology_planner",
        )

        for role, agent in self.agents.items():
            if role == "methodology_planner":
                continue
            with self.subTest(role=role):
                self.assertEqual(
                    agent["definition"]["chain"]["metadata"]["provisioning_source"],
                    "pi_1951_pharma_company_intelligence_lab",
                )

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
                self.assertEqual(
                    chain["budget_policy"],
                    {
                        "max_tool_calls": 0,
                        "max_provider_calls": 1,
                    },
                )
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

    def test_methodology_planner_instruction_preserves_authority_boundaries(self) -> None:
        prompt = (
            self.agents["methodology_planner"]["definition"]["chain"]["steps"][0]
            ["input"]["text"]
        )
        required_phrases = (
            "Do not search for or introduce public facts.",
            "preserve the supplied company_id exactly",
            "may not change company scope",
            "provider authority",
            "required canonical section IDs",
            "required Agent roles",
            "memory mutation authority",
            "publication authority",
            "Do not compare this company with another company.",
        )
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, prompt)

    def test_evidence_critic_instruction_requires_plan_requirement_dispositions(self) -> None:
        prompt = (
            self.agents["evidence_critic"]["definition"]["chain"]["steps"][0]
            ["input"]["text"]
        )
        required_phrases = (
            "Evaluate every supplied planner requirement",
            "exact supplied requirement_id",
            "unmet_plan_requirements",
            "unresolved_evidence",
            "unsatisfied",
            "Do not invent requirement IDs.",
            "do not authorize memory mutation.",
        )
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, prompt)

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