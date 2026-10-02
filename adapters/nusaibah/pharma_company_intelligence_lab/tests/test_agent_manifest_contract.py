from __future__ import annotations

import json
import unittest
from pathlib import Path

ASSET_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ASSET_ROOT / "nusaibah_pharma_company_intelligence_lab.asset.json"
ADAPTER_YAML = ASSET_ROOT / "adapter.yaml"
ADAPTER_MODULE = ASSET_ROOT / "nusaibah_pharma_company_intelligence_lab_adapter.py"

ASSET_VERSION = "0.1.8"
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
    "methodology_planner": ("gemini-3.8-flash", "medium", 8192, False, 60),
    "portfolio_researcher": ("gemini-3.8-flash", "medium", 4096, True, 120),
    "market_researcher": ("gemini-3.8-flash", "medium", 4096, True, 120),
    "regulatory_risk_researcher": ("gemini-3.8-flash", "high", 6144, True, 120),
    "strategic_analyst": ("gemini-3.1-pro-preview", "high", 6144, False, 180),
    "evidence_critic": ("gemini-3.1-pro-preview", "high", 6144, False, 180),
    "intelligence_synthesizer": ("gemini-3.8-flash", "high", 8192, False, 180),
    "memory_benchmark_reviewer": ("gemini-3.8-flash", "medium", 4096, False, 60),
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

    def test_runtime_floor_requires_governed_long_request_support(self) -> None:
        dependency_manifest = json.loads(
            (ASSET_ROOT / "adapter.dependencies.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            dependency_manifest["runtime_package"],
            {
                "name": "pi-obs-python-runtime",
                "minimum_version": "0.1.91",
            },
        )

    def test_fixed_skill_uses_published_delivery_not_bundled_bytes(self) -> None:
        version = self.manifest["versions"][ASSET_VERSION]
        self.assertNotIn("skills", version)
        self.assertFalse((ASSET_ROOT / "skills").exists())
        self.assertEqual(
            version["published_skills"],
            [
                {
                    "skill_ref": "nusaibah.pharma-intelligence-methodology",
                    "version": "1.0.0",
                    "digest": "sha256:2fa082aca1c100abb60a4bf77aa4cf796da2707bb951a3b51f11948efd2dd564",
                }
            ],
        )

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
            "pi_1965_section_chunk_planner",
        )

        for role, agent in self.agents.items():
            if role == "methodology_planner":
                continue
            with self.subTest(role=role):
                self.assertEqual(
                    agent["definition"]["chain"]["metadata"]["provisioning_source"],
                    "pi_1951_pharma_company_intelligence_lab",
                )

    def test_model_thinking_search_json_and_timeout_policy_are_exact(self) -> None:
        self.assertEqual(self.manifest["execution"]["timeout_seconds"], 1800)
        for role, (model, thinking, max_tokens, search_enabled, timeout) in EXPECTED.items():
            with self.subTest(role=role):
                agent = self.agents[role]
                expected_contract_version = (
                    "1.0.3" if role == "methodology_planner" else "1.0.2"
                )
                self.assertEqual(agent["contract_version"], expected_contract_version)
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

                self.assertEqual(policy["timeout_seconds"], timeout)
                self.assertIs(type(policy["timeout_seconds"]), int)
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

    def test_methodology_learning_dynamic_skill_roles_are_company_scoped(self) -> None:
        runtime_skills = self.manifest["versions"][ASSET_VERSION]["runtime_skills"]

        self.assertEqual(
            runtime_skills["company_methodology"]["source"],
            {"lake_ref": "googl123", "node_key": "company_methodology"},
        )
        self.assertEqual(runtime_skills["company_methodology"]["resolution"], "current")
        self.assertEqual(runtime_skills["company_methodology"]["mutation"], "read_only")
        self.assertEqual(
            runtime_skills["company_methodology"]["partition"],
            {"company_id": {"from_variable": "company_id"}},
        )

        self.assertEqual(
            runtime_skills["company_methodology_update"]["source"],
            {"lake_ref": "googl123", "node_key": "company_methodology"},
        )
        self.assertEqual(runtime_skills["company_methodology_update"]["resolution"], "current")
        self.assertEqual(runtime_skills["company_methodology_update"]["mutation"], "mutable")
        self.assertEqual(
            runtime_skills["company_methodology_update"]["partition"],
            {"company_id": {"from_variable": "company_id"}},
        )

    def test_timeout_policy_changes_use_new_agent_contract_versions(self) -> None:
        self.assertEqual(
            self.agents["methodology_planner"]["contract_version"],
            "1.0.3",
        )
        self.assertEqual(
            self.agents["methodology_planner"]["definition"]["chain"]["version"],
            "1.0.3",
        )
        for role, agent in self.agents.items():
            if role == "methodology_planner":
                continue
            with self.subTest(role=role):
                self.assertEqual(agent["contract_version"], "1.0.2")
                self.assertEqual(agent["definition"]["chain"]["version"], "1.0.2")

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
            "section ownership",
            "required Agent roles",
            "memory mutation authority",
            "publication authority",
            "Do not compare this company with another company.",
            "Plan only the supplied section",
            "priority_hint",
            "response_contract.compact_limits",
            "Do not fill optional lists merely to reach their maxima.",
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
        for role, (model, _thinking, _max_tokens, _search, _timeout) in EXPECTED.items():
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

    def test_every_role_instruction_requires_exact_supplied_response_contract(self) -> None:
        for role, agent in self.agents.items():
            with self.subTest(role=role):
                prompt = agent["definition"]["chain"]["steps"][0]["input"]["text"]
                self.assertIn(
                    "response_contract is authoritative for the complete JSON shape",
                    prompt,
                )
                self.assertIn("Return every required field", prompt)
                self.assertIn("required ID ordering", prompt)

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
