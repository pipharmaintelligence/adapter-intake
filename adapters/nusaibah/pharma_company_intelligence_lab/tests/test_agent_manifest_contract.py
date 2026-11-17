from __future__ import annotations

import json
import unittest
from pathlib import Path


ASSET_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = (
    ASSET_ROOT / "tests/fixtures/release-0.1.21/nusaibah_pharma_company_intelligence_lab.asset.json"
)
ADAPTER_YAML = ASSET_ROOT / "tests/fixtures/release-0.1.21/adapter.yaml"
ADAPTER_MODULE = (
    ASSET_ROOT / "nusaibah_pharma_company_intelligence_lab_v0_1_21_adapter.py"
)
HISTORICAL_ADAPTER_MODULE = (
    ASSET_ROOT / "legacy_preparation_helpers_v0_1_21.py"
)
HISTORICAL_MANIFEST = (
    ASSET_ROOT / "tests/fixtures/release-0.1.21/nusaibah_pharma_company_intelligence_lab.asset.json"
)

ASSET_VERSION = "0.1.21"
HISTORICAL_VERSION = "0.1.20"
HISTORICAL_RESEARCH_CONTRACT_VERSION = "1.0.7"
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
EXPECTED_INPUTS = {
    "company_context": {
        "required": True,
        "source": "direct",
        "shape": "object",
        "retained_output": {
            "asset_identity": "nusaibah.company_scope:0.1.0",
            "output_role": "company_scope_result",
        },
    },
    "variables": {
        "required": True,
        "source": "direct",
        "shape": "object",
    },
}
EXPECTED_OUTPUTS = {
    "intelligence_dossier": {
        "required": True,
        "shape": "object",
    }
}
EXPECTED_PUBLISHED_SKILL = {
    "skill_ref": "nusaibah.pharma-intelligence-methodology",
    "version": "1.0.0",
    "digest": (
        "sha256:2fa082aca1c100abb60a4bf77aa4cf796da2707bb951a3b51f11948efd2dd564"
    ),
}
EXPECTED_RUNTIME_SKILLS = {
    "company_memory": ("company_memory", "read_only"),
    "company_memory_update": ("company_memory", "mutable"),
    "company_methodology": ("company_methodology", "read_only"),
    "company_methodology_update": ("company_methodology", "mutable"),
}


class PackagedAgentDefinitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.version = cls.manifest["versions"][ASSET_VERSION]
        cls.agents = cls.version["agents"]

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

    def test_historical_identity_remains_source_only_in_intake(self) -> None:
        historical_module = HISTORICAL_ADAPTER_MODULE.read_text(encoding="utf-8")
        adapter_yaml = ADAPTER_YAML.read_text(encoding="utf-8")

        self.assertIn(
            f'version: ClassVar[str] = "{HISTORICAL_VERSION}"',
            historical_module,
        )
        self.assertIn(HISTORICAL_ADAPTER_MODULE.name, adapter_yaml)
        # Canonical filename is required by the existing Assets history merge;
        # its intake contents still contain only the current version.
        self.assertEqual(MANIFEST, HISTORICAL_MANIFEST)
        self.assertIn(MANIFEST.name, adapter_yaml)
        self.assertEqual({ASSET_VERSION}, set(self.manifest["versions"]))
        self.assertNotIn("class NusaibahPharmaCompanyIntelligenceLabAdapter(Adapter)", historical_module)

    def test_non_agent_business_contract_is_explicitly_frozen(self) -> None:
        self.assertEqual("active", self.version["state"])
        self.assertEqual(EXPECTED_INPUTS, self.version["inputs"])
        self.assertEqual(EXPECTED_OUTPUTS, self.version["outputs"])
        self.assertEqual(
            [EXPECTED_PUBLISHED_SKILL],
            self.version["published_skills"],
        )

        runtime_skills = self.version["runtime_skills"]
        self.assertEqual(set(EXPECTED_RUNTIME_SKILLS), set(runtime_skills))
        for role, (node_key, mutation) in EXPECTED_RUNTIME_SKILLS.items():
            with self.subTest(role=role):
                self.assertEqual(
                    {"lake_ref": "googl123", "node_key": node_key},
                    runtime_skills[role]["source"],
                )
                self.assertEqual("current", runtime_skills[role]["resolution"])
                self.assertEqual(mutation, runtime_skills[role]["mutation"])
                self.assertEqual(
                    {"company_id": {"from_variable": "company_id"}},
                    runtime_skills[role]["partition"],
                )

        output_contract = self.version["output_contracts"][
            "intelligence_dossier"
        ]
        self.assertEqual("dlm_file_artifact_output", output_contract["target_kind"])
        self.assertEqual("dry_run", output_contract["write_mode"])
        self.assertEqual(
            "json",
            output_contract["format_policy"]["developer_selected_format"],
        )
        self.assertTrue(
            output_contract["validation"]["self_inspection"]["enforce"]
        )
        self.assertEqual(
            [
                "schema_version",
                "status",
                "requested_company_count",
                "completed_company_count",
                "failed_company_count",
                "company_results",
            ],
            [
                field["name"]
                for field in output_contract["schema"]["fields"]
            ],
        )

    def test_exact_role_set_and_order_are_frozen(self) -> None:
        self.assertEqual(EXPECTED_ROLE_ORDER, tuple(self.agents))

    def test_only_changed_roles_embed_new_agent_definitions(self) -> None:
        preparation_versions = {
            "methodology_planner": "1.0.7",
            "evidence_critic": "1.0.8",
            "intelligence_synthesizer": "1.0.6",
        }
        for role, agent in self.agents.items():
            with self.subTest(role=role):
                if role in CHANGED_RESEARCH_ROLES:
                    self.assertIn("definition", agent)
                    self.assertEqual("1.0.8", agent["contract_version"])
                    self.assertEqual(
                        "1.0.8",
                        agent["definition"]["chain"]["version"],
                    )
                    self.assertNotEqual(
                        HISTORICAL_RESEARCH_CONTRACT_VERSION,
                        agent["contract_version"],
                    )
                elif role in preparation_versions:
                    self.assertIn("definition", agent)
                    self.assertEqual(preparation_versions[role], agent["contract_version"])
                    chain = agent["definition"]["chain"]
                    self.assertEqual(preparation_versions[role], chain["version"])
                    self.assertEqual({"max_tool_calls": 0, "max_provider_calls": 1}, chain["budget_policy"])
                    for step in chain["steps"]:
                        self.assertEqual(600, step["provider_policy"]["timeout_seconds"])
                else:
                    self.assertNotIn("definition", agent)
                    self.assertEqual(
                        UNCHANGED_ROLE_VERSIONS[role],
                        agent["contract_version"],
                    )
                    self.assertEqual(
                        {
                            "contract_key": agent["contract_key"],
                            "contract_version": UNCHANGED_ROLE_VERSIONS[role],
                            "reference": agent["reference"],
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
                self.assertEqual(
                    self.agents[role]["contract_key"],
                    chain["chain_id"],
                )
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
            [EXPECTED_PUBLISHED_SKILL],
            self.version["published_skills"],
        )
        self.assertEqual(
            set(EXPECTED_RUNTIME_SKILLS),
            set(self.version["runtime_skills"]),
        )

    def test_input_and_output_contracts_remain_company_context_scoped(self) -> None:
        self.assertEqual(EXPECTED_INPUTS, self.version["inputs"])
        self.assertEqual(EXPECTED_OUTPUTS, self.version["outputs"])
        self.assertEqual(
            "nusaibah.company_scope:0.1.0",
            self.version["inputs"]["company_context"]["retained_output"][
                "asset_identity"
            ],
        )
        self.assertEqual(
            "dry_run",
            self.version["output_contracts"]["intelligence_dossier"][
                "write_mode"
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
                "minimum_version": "0.1.137",
            },
            dependency_manifest["runtime_package"],
        )


if __name__ == "__main__":
    unittest.main()
