from __future__ import annotations

import json
import unittest
from pathlib import Path


ASSET_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ASSET_ROOT / "nusaibah_pharma_company_intelligence_lab_v0_1_21.asset.json"
HISTORICAL_MANIFEST = ASSET_ROOT / "nusaibah_pharma_company_intelligence_lab.asset.json"
ADAPTER_YAML = ASSET_ROOT / "adapter.yaml"
ADAPTER_MODULE = ASSET_ROOT / "nusaibah_pharma_company_intelligence_lab_v0_1_21_adapter.py"
HISTORICAL_ADAPTER_MODULE = (
    ASSET_ROOT / "nusaibah_pharma_company_intelligence_lab_adapter.py"
)

ASSET_VERSION = "0.1.21"
HISTORICAL_VERSION = "0.1.20"
CHANGED_RESEARCH_ROLES = (
    "portfolio_researcher",
    "market_researcher",
    "regulatory_risk_researcher",
)
EXPECTED_ROLE_ORDER = (
    "methodology_planner",
    "portfolio_researcher",
    "market_researcher",
    "regulatory_risk_researcher",
    "strategic_analyst",
    "evidence_critic",
    "intelligence_synthesizer",
    "memory_benchmark_reviewer",
    "research_response_resolver",
)
UNCHANGED_ROLE_VERSIONS = {
    "methodology_planner": "1.0.6",
    "strategic_analyst": "1.0.5",
    "evidence_critic": "1.0.7",
    "intelligence_synthesizer": "1.0.5",
    "memory_benchmark_reviewer": "1.0.4",
    "research_response_resolver": "1.0.3",
}
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


class PackagedAgentDefinitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.version = cls.manifest["versions"][ASSET_VERSION]
        cls.agents = cls.version["agents"]
        cls.historical_manifest = json.loads(
            HISTORICAL_MANIFEST.read_text(encoding="utf-8")
        )
        cls.historical_version = cls.historical_manifest["versions"][
            HISTORICAL_VERSION
        ]
        cls.historical_agents = cls.historical_version["agents"]

    def test_asset_version_is_synchronized_across_intake_contract_and_manifest(self) -> None:
        adapter_yaml = ADAPTER_YAML.read_text(encoding="utf-8")
        adapter_module = ADAPTER_MODULE.read_text(encoding="utf-8")

        self.assertIn(f"asset_version: {ASSET_VERSION}", adapter_yaml)
        self.assertIn(MANIFEST.name, adapter_yaml)
        self.assertIn(ADAPTER_MODULE.name, adapter_yaml)
        self.assertIn(
            f'version: ClassVar[str] = "{ASSET_VERSION}"',
            adapter_module,
        )
        self.assertEqual(ASSET_VERSION, self.manifest["default"])
        self.assertEqual({ASSET_VERSION}, set(self.manifest["versions"]))

    def test_historical_0_1_20_identity_remains_unchanged_and_separate(self) -> None:
        historical_module = HISTORICAL_ADAPTER_MODULE.read_text(encoding="utf-8")

        self.assertEqual(HISTORICAL_VERSION, self.historical_manifest["default"])
        self.assertEqual(
            {HISTORICAL_VERSION},
            set(self.historical_manifest["versions"]),
        )
        self.assertIn(
            f'version: ClassVar[str] = "{HISTORICAL_VERSION}"',
            historical_module,
        )
        self.assertNotEqual(MANIFEST.name, HISTORICAL_MANIFEST.name)
        self.assertNotEqual(ADAPTER_MODULE.name, HISTORICAL_ADAPTER_MODULE.name)

    def test_new_version_preserves_non_agent_business_contracts(self) -> None:
        excluded = {"agents"}
        current = {
            key: value
            for key, value in self.version.items()
            if key not in excluded
        }
        historical = {
            key: value
            for key, value in self.historical_version.items()
            if key not in excluded
        }
        self.assertEqual(historical, current)

    def test_exact_role_set_and_order_match_historical_contract(self) -> None:
        self.assertEqual(EXPECTED_ROLE_ORDER, tuple(self.agents))
        self.assertEqual(tuple(self.historical_agents), tuple(self.agents))

    def test_only_changed_research_roles_embed_new_agent_definitions(self) -> None:
        for role, agent in self.agents.items():
            with self.subTest(role=role):
                if role in CHANGED_RESEARCH_ROLES:
                    self.assertIn("definition", agent)
                    self.assertEqual("1.0.8", agent["contract_version"])
                    self.assertEqual(
                        "1.0.8",
                        agent["definition"]["chain"]["version"],
                    )
                    self.assertEqual(
                        "1.0.7",
                        self.historical_agents[role]["contract_version"],
                    )
                else:
                    self.assertNotIn("definition", agent)
                    self.assertEqual(
                        UNCHANGED_ROLE_VERSIONS[role],
                        agent["contract_version"],
                    )
                    self.assertEqual(
                        {
                            key: self.historical_agents[role][key]
                            for key in (
                                "contract_key",
                                "contract_version",
                                "reference",
                            )
                        },
                        agent,
                    )

    def test_changed_roles_reuse_canonical_provider_registry_entry(self) -> None:
        registry_entries = []
        for role in CHANGED_RESEARCH_ROLES:
            entries = self.agents[role]["definition"]["registry_entries"]
            with self.subTest(role=role):
                self.assertEqual(1, len(entries))
                self.assertEqual(CANONICAL_PROVIDER_REGISTRY_ENTRY, entries[0])
            registry_entries.append(entries[0])

        self.assertTrue(
            all(entry == registry_entries[0] for entry in registry_entries[1:])
        )

    def test_changed_research_provider_policies_are_exact_and_bounded(self) -> None:
        self.assertEqual(1800, self.manifest["execution"]["timeout_seconds"])

        for role in CHANGED_RESEARCH_ROLES:
            chain = self.agents[role]["definition"]["chain"]
            with self.subTest(role=role):
                self.assertEqual(self.agents[role]["contract_key"], chain["chain_id"])
                self.assertEqual("1.0.8", chain["version"])
                self.assertEqual(
                    {"max_tool_calls": 0, "max_provider_calls": 2},
                    chain["budget_policy"],
                )
                self.assertEqual(
                    {"store_prompt": False, "store_output": False},
                    chain["safety_policy"],
                )
                self.assertEqual(2, len(chain["steps"]))

                evidence, formatter = chain["steps"]
                evidence_policy = evidence["provider_policy"]
                self.assertEqual("vertex_ai", evidence["provider"])
                self.assertEqual("gemini-3.8-flash", evidence_policy["model"])
                self.assertEqual(600, evidence_policy["timeout_seconds"])
                self.assertIs(True, evidence_policy["search_enabled"])
                self.assertEqual(
                    "provider_grounding",
                    evidence_policy["search_mode"],
                )
                self.assertEqual("refs_only", evidence_policy["citation_policy"])
                self.assertEqual(
                    {
                        "max_tokens": 8192,
                        "thinking_level": "medium",
                        "response_format": "text",
                    },
                    evidence_policy["generation_policy"],
                )

                formatter_policy = formatter["provider_policy"]
                self.assertEqual("vertex_ai", formatter["provider"])
                self.assertEqual("gemini-3.8-flash", formatter_policy["model"])
                self.assertEqual(600, formatter_policy["timeout_seconds"])
                self.assertNotIn("search_enabled", formatter_policy)
                self.assertEqual(
                    {
                        "max_tokens": 8192,
                        "thinking_level": "medium",
                        "response_format": "json_object",
                    },
                    formatter_policy["generation_policy"],
                )
                for step in chain["steps"]:
                    generation = step["provider_policy"]["generation_policy"]
                    self.assertNotIn("temperature", generation)
                    self.assertNotIn("top_p", generation)
                    self.assertNotIn("top_k", generation)

    def test_research_prompts_require_exact_admitted_locator_semantics(self) -> None:
        common_evidence_phrases = (
            "exact source locators",
            "Separate event date from publication date",
            "agreement from completion",
            "current from historical status",
            "grantor from recipient and territory",
            "potential effects from observed events",
            "Do not invent facts, IDs, sources or locators.",
        )
        common_formatter_phrases = (
            "response_contract exactly",
            "copy one or more exact admitted source strings",
            "citation_locators",
            "never invent, normalize or repair a locator",
            "evidence_qualifiers",
            "Do not author citation IDs.",
            "Without a supporting locator, omit the positive claim",
        )

        for role in CHANGED_RESEARCH_ROLES:
            evidence, formatter = self.agents[role]["definition"]["chain"][
                "steps"
            ]
            evidence_prompt = evidence["input"]["text"]
            formatter_prompt = formatter["input"]["text"]
            for phrase in common_evidence_phrases:
                with self.subTest(role=role, phrase=phrase):
                    self.assertIn(phrase, evidence_prompt)
            for phrase in common_formatter_phrases:
                with self.subTest(role=role, phrase=phrase):
                    self.assertIn(phrase, formatter_prompt)

        market_prompt = self.agents["market_researcher"]["definition"][
            "chain"
        ]["steps"][0]["input"]["text"]
        regulatory_prompt = self.agents[
            "regulatory_risk_researcher"
        ]["definition"]["chain"]["steps"][0]["input"]["text"]
        self.assertIn("manufacturing responsibility", market_prompt)
        self.assertIn("approval/event dates", regulatory_prompt)
        self.assertIn("potential harm from observed events", regulatory_prompt)

    def test_fixed_skill_and_dynamic_skill_authority_are_unchanged(self) -> None:
        self.assertNotIn("skills", self.version)
        self.assertFalse((ASSET_ROOT / "skills").exists())
        self.assertEqual(
            [
                {
                    "skill_ref": "nusaibah.pharma-intelligence-methodology",
                    "version": "1.0.0",
                    "digest": (
                        "sha256:2fa082aca1c100abb60a4bf77aa4cf796da2707bb"
                        "951a3b51f11948efd2dd564"
                    ),
                }
            ],
            self.version["published_skills"],
        )
        self.assertEqual(
            self.historical_version["runtime_skills"],
            self.version["runtime_skills"],
        )

    def test_input_and_output_contracts_remain_company_context_scoped(self) -> None:
        self.assertEqual(
            self.historical_version["inputs"],
            self.version["inputs"],
        )
        self.assertEqual(
            self.historical_version["outputs"],
            self.version["outputs"],
        )
        self.assertEqual(
            self.historical_version["output_contracts"],
            self.version["output_contracts"],
        )
        output_contract = self.version["output_contracts"][
            "intelligence_dossier"
        ]
        self.assertEqual("dry_run", output_contract["write_mode"])
        self.assertEqual(
            "nusaibah.company_scope:0.1.0",
            self.version["inputs"]["company_context"]["retained_output"][
                "asset_identity"
            ],
        )

    def test_packaged_adapter_declares_orchestration_owner_exactly_once(self) -> None:
        adapter_module = ADAPTER_MODULE.read_text(encoding="utf-8")
        marker = 'AGENT_ORCHESTRATION_OWNER = "python_adapter"'
        self.assertEqual(1, adapter_module.count(marker))
        for role in EXPECTED_ROLE_ORDER:
            self.assertIn(role, adapter_module)

    def test_runtime_floor_requires_current_trusted_runtime_support(self) -> None:
        dependency_manifest = json.loads(
            (ASSET_ROOT / "adapter.dependencies.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            {
                "name": "pi-obs-python-runtime",
                "minimum_version": "0.1.98",
            },
            dependency_manifest["runtime_package"],
        )


if __name__ == "__main__":
    unittest.main()
