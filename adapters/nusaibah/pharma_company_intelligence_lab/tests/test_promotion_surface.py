from __future__ import annotations

import unittest
from pathlib import Path


ASSET_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_YAML = ASSET_ROOT / "adapter.yaml"

EXPECTED_REVIEWED_HELPERS = {
    'agent_chunks_v0_1_47.py', 'orchestration_v0_1_47.py', 'nusaibah_pharma_company_intelligence_lab_v0_1_46_adapter.py',
    'company_preparation_v0_1_46.py', 'downstream_chunks_v0_1_46.py',
    'orchestration_v0_1_46.py', 'profile_narrative_v0_1_46.py', 'reflection_v0_1_46.py',
    'nusaibah_pharma_company_intelligence_lab_v0_1_45_adapter.py',
    'source_verification_v0_1_45.py', 'company_preparation_v0_1_45.py',
    'downstream_chunks_v0_1_45.py', 'orchestration_v0_1_45.py',
    'profile_narrative_v0_1_45.py', 'profile_rendering_v0_1_45.py',
    'profile_research_v0_1_45.py', 'reflection_v0_1_45.py',
    'automatic_publication_v0_1_45.py', 'skill_publication_v0_1_45.py',
    'profile_memory_v0_1_45.py', 'reference_budget_v0_1_45.py',
    'nusaibah_pharma_company_intelligence_lab_v0_1_44_adapter.py',
    "source_verification_v0_1_44.py",
    'company_preparation_v0_1_44.py', 'downstream_chunks_v0_1_44.py',
    'orchestration_v0_1_44.py', 'profile_narrative_v0_1_44.py',
    'profile_rendering_v0_1_44.py', 'profile_research_v0_1_44.py', 'reflection_v0_1_44.py',
    'nusaibah_pharma_company_intelligence_lab_v0_1_43_adapter.py',
    'automatic_publication_v0_1_43.py',
    'company_preparation_v0_1_43.py',
    'continuation_v0_1_43.py',
    'downstream_chunks_v0_1_43.py',
    'input_projection_v0_1_43.py',
    'orchestration_v0_1_43.py',
    'preparation_context_v0_1_43.py',
    'profile_narrative_v0_1_43.py',
    'profile_rendering_v0_1_43.py',
    'profile_research_v0_1_43.py',
    'reflection_v0_1_43.py',
    'section_critic_v0_1_43.py',
    'targeted_inputs_v0_1_43.py',
    'nusaibah_pharma_company_intelligence_lab_v0_1_42_adapter.py',

    'company_title_v0_1_42.py',
    'skill_publication_v0_1_42.py',
    'skill_initialization_v0_1_42.py',
    'automatic_publication_v0_1_42.py',

    'agent_chunks_v0_1_42.py',
    'nusaibah_pharma_company_intelligence_lab_v0_1_41_adapter.py',
    'orchestration_v0_1_42.py', 'company_preparation_v0_1_42.py', 'reflection_v0_1_42.py',
    'downstream_chunks_v0_1_42.py', 'section_critic_v0_1_42.py', 'targeted_inputs_v0_1_42.py',
    'preparation_context_v0_1_42.py', 'methodology_learning_v0_1_42.py', 'continuation_v0_1_42.py',
    'profile_narrative_v0_1_42.py', 'profile_rendering_v0_1_42.py', 'input_projection_v0_1_42.py',
    'retention_preflight_v0_1_42.py',
    'nusaibah_pharma_company_intelligence_lab_v0_1_40_adapter.py',
    'agent_chunks_v0_1_41.py', 'company_preparation_v0_1_41.py',
    'invocation_recovery_v0_1_41.py', 'orchestration_v0_1_41.py',
    'reflection_v0_1_41.py', 'research_execution_v0_1_41.py', 'section_critic_v0_1_41.py',
    'agent_response_recovery_v0_1_40.py',
    'critic_response_v0_1_40.py',
    'invocation_recovery_v0_1_40.py',

    "skill_reads_v0_1_40.py",
    'automatic_publication_v0_1_40.py',
    'company_preparation_v0_1_40.py',
    'continuation_v0_1_40.py',
    'critic_contract_v0_1_40.py',
    'downstream_chunks_v0_1_40.py',
    'methodology_learning_v0_1_40.py',
    'orchestration_v0_1_40.py',
    'planner_execution_v0_1_40.py',
    'preparation_context_v0_1_40.py',
    'reflection_v0_1_40.py',
    'research_execution_v0_1_40.py',
    'section_critic_v0_1_40.py',
    'section_enrichment_v0_1_40.py',
    'source_evidence_v0_1_40.py',
    'targeted_inputs_v0_1_40.py',
    'nusaibah_pharma_company_intelligence_lab_v0_1_39_adapter.py',

    'agent_chunks_v0_1_39.py', 'planner_execution_v0_1_39.py', 'research_execution_v0_1_39.py', 'source_evidence_v0_1_39.py', 'targeted_inputs_v0_1_39.py', 'section_critic_v0_1_39.py', 'company_preparation_v0_1_39.py', 'continuation_v0_1_39.py',
    "nusaibah_pharma_company_intelligence_lab_v0_1_38_adapter.py",
    "orchestration_v0_1_39.py", "automatic_publication_v0_1_39.py", "no_enrichment_v0_1_39.py",
    "nusaibah_pharma_company_intelligence_lab_v0_1_37_adapter.py",
    "orchestration_v0_1_38.py", "automatic_publication_v0_1_38.py", "skill_initialization_v0_1_38.py",
    "nusaibah_pharma_company_intelligence_lab_v0_1_36_adapter.py", "orchestration_v0_1_37.py",
    "automatic_publication_v0_1_37.py", "skill_publication_v0_1_37.py",
    "nusaibah_pharma_company_intelligence_lab_v0_1_35_adapter.py",
    "company_preparation_v0_1_36.py", "orchestration_v0_1_36.py", "section_critic_v0_1_36.py",
    "company_preparation_v0_1_35.py", "orchestration_v0_1_35.py", "targeted_inputs_v0_1_35.py",
    "source_evidence_v0_1_35.py", "invocation_recovery_v0_1_35.py",
    "nusaibah_pharma_company_intelligence_lab_v0_1_34_adapter.py",
    "company_preparation_v0_1_34.py", "orchestration_v0_1_34.py", "targeted_inputs_v0_1_34.py",
    "nusaibah_pharma_company_intelligence_lab_v0_1_33_adapter.py",
    "agent_chunks_v0_1_33.py",
    "invocation_recovery_v0_1_33.py",
    "source_evidence_v0_1_33.py",
    "targeted_inputs_v0_1_33.py",
    "research_execution_v0_1_33.py",
    "planner_execution_v0_1_33.py",
    "downstream_chunks_v0_1_33.py",
    "section_critic_v0_1_33.py",
    "company_preparation_v0_1_33.py",
    "orchestration_v0_1_33.py",
    "nusaibah_pharma_company_intelligence_lab_v0_1_32_adapter.py",

    "nusaibah_pharma_company_intelligence_lab_v0_1_31_adapter.py",
    "orchestration_v0_1_32.py",
    "company_preparation_v0_1_32.py",
    "research_execution_v0_1_32.py",
    "nusaibah_pharma_company_intelligence_lab_v0_1_30_adapter.py",
    "invocation_recovery_v0_1_31.py",
    "orchestration_v0_1_31.py",
    "nusaibah_pharma_company_intelligence_lab_v0_1_29_adapter.py",
    "invocation_recovery_v0_1_30.py",
    "orchestration_v0_1_30.py",
    "nusaibah_pharma_company_intelligence_lab_v0_1_28_adapter.py",
    "company_preparation_v0_1_29.py",
    "orchestration_v0_1_29.py",
    "automatic_publication_v0_1_29.py",
    "benchmark_observation_v0_1_29.py",

    "nusaibah_pharma_company_intelligence_lab_v0_1_27_adapter.py",
    "company_preparation_v0_1_28.py",
    "orchestration_v0_1_28.py",
    "section_critic_v0_1_28.py",
    "section_enrichment_v0_1_28.py",
    "benchmark_projection_v0_1_28.py",

    "skill_publication_v0_1_27.py",
    "nusaibah_pharma_company_intelligence_lab_v0_1_26_adapter.py",
    "automatic_publication_v0_1_27.py",
    "company_preparation_v0_1_27.py",
    "orchestration_v0_1_27.py",
    "section_enrichment_v0_1_27.py",
    "targeted_inputs_v0_1_27.py",

    "section_critic_v0_1_27.py",
    "nusaibah_pharma_company_intelligence_lab_v0_1_25_adapter.py",
    "claim_semantics_v0_1_26.py",
    "research_claim_evidence_v0_1_26.py",
    "research_claim_pipeline_v0_1_26.py",
    "research_response_contract_v0_1_26.py",
    "research_envelope_v0_1_26.py",
    "invocation_recovery_v0_1_26.py",
    "research_execution_v0_1_26.py",
    "company_preparation_v0_1_26.py",
    "orchestration_v0_1_26.py",
    "source_evidence_v0_1_26.py",
    "reviewed_apply_v0_1_26.py",
    "review_packet_v0_1_26.py",
    "nusaibah_pharma_company_intelligence_lab_v0_1_24_adapter.py",
    "invocation_recovery_v0_1_25.py",
    "research_execution_v0_1_25.py",
    "company_preparation_v0_1_25.py",
    "orchestration_v0_1_25.py",
    "nusaibah_pharma_company_intelligence_lab_v0_1_23_adapter.py",
    "orchestration_v0_1_24.py",
    "nusaibah_pharma_company_intelligence_lab_v0_1_22_adapter.py",
    "legacy_preparation_helpers_v0_1_23.py",
    "research_execution_v0_1_23.py",
    "company_preparation_v0_1_23.py",
    "orchestration_v0_1_23.py",
    "nusaibah_pharma_company_intelligence_lab_v0_1_21_adapter.py",
    "legacy_preparation_helpers_v0_1_21.py",
    "input_contract.py",
    "dossier_contract.py",
    "memory_contract.py",
    "agent_contract.py",
    "critic_diagnostics_v0_1_13.py",
    "company_context_contract_v0_1_14.py",
    "company_context_contract_v0_1_15.py",
    "methodology_contract.py",
    "review_packet_v0_1_16.py",
    "research_diagnostics_v0_1_17.py",
    "portfolio_review_v0_1_17.py",
    "agent_response_recovery_v0_1_17.py",
    "evidence_recovery_v0_1_20.py",
    "claim_semantics_v0_1_21.py",
    "claim_evidence_contract_v0_1_21.py",
    "research_response_contract_v0_1_21.py",
    "research_claim_evidence_v0_1_21.py",
    "research_claim_pipeline_v0_1_21.py",
    "research_section_projection_v0_1_21.py",
    "research_execution_v0_1_21.py",
    "candidate_validation_v0_1_21.py",
    "memory_citation_selection_v0_1_21.py",
    "methodology_learning_v0_1_21.py",
    "preparation_context_v0_1_21.py",
    "company_result_v0_1_21.py",
    "company_preparation_v0_1_21.py",
    "review_packet_v0_1_21.py",
    "orchestration_v0_1_21.py",
}

EXPECTED_REVIEWED_SUPPORT_FILES = {'pharma_roles_v0_1_47.json', 'materialization_promotion_acceptance_v0_1_47.json','pharma_roles_v0_1_46.json', 'materialization_promotion_acceptance_v0_1_46.json',
    'pharma_roles_v0_1_45.json', 'materialization_promotion_acceptance_v0_1_45.json',
    'pharma_roles_v0_1_44.json', 'materialization_promotion_acceptance_v0_1_44.json',
    'pharma_roles_v0_1_43.json',
    'materialization_promotion_acceptance_v0_1_43.json',

    'pharma_roles_v0_1_42.json', 'materialization_promotion_acceptance_v0_1_42.json',
    'pharma_roles_v0_1_41.json', 'materialization_promotion_acceptance_v0_1_41.json',
    "pharma_roles_v0_1_37.json", "materialization_promotion_acceptance_v0_1_37.json",
    "pharma_roles_v0_1_36.json", "materialization_promotion_acceptance_v0_1_36.json",
    "pharma_roles_v0_1_35.json", "materialization_promotion_acceptance_v0_1_35.json",
    "pharma_roles_v0_1_34.json", "materialization_promotion_acceptance_v0_1_34.json",
    "pharma_roles_v0_1_33.json",
    "materialization_promotion_acceptance_v0_1_33.json",
    "pharma_roles_v0_1_32.json",
    "materialization_promotion_acceptance_v0_1_32.json",
    "pharma_roles_v0_1_31.json",
    "materialization_promotion_acceptance_v0_1_31.json",
    "pharma_roles_v0_1_30.json",
    "materialization_promotion_acceptance_v0_1_30.json",
    "pharma_roles_v0_1_29.json",
    "materialization_promotion_acceptance_v0_1_29.json",
    "pharma_roles_v0_1_28.json",
    "materialization_promotion_acceptance_v0_1_28.json",
    "pharma_roles_v0_1_27.json",
    "materialization_promotion_acceptance_v0_1_27.json",
    "pharma_roles_v0_1_26.json",
    "materialization_promotion_acceptance_v0_1_26.json",
    "pharma_roles_v0_1_25.json",
    "materialization_promotion_acceptance_v0_1_25.json",
    "pharma_roles_v0_1_24.json",
    "materialization_promotion_acceptance_v0_1_24.json",
    "pharma_roles_v0_1_23.json",
    "materialization_promotion_acceptance_v0_1_23.json",
    "pharma_roles_v0_1_21.json",
    "materialization_promotion_acceptance_v0_1_21.json",
    "pharma_roles_v0_1_22.json",
    "materialization_promotion_acceptance_v0_1_22.json",
    "pharma_response_budgets_v0_1_22.json",
}

EXPECTED_RUNTIME_FILES = {"agent_chunks_v0_1_47.py", "orchestration_v0_1_47.py", "nusaibah_pharma_company_intelligence_lab_v0_1_47_adapter.py","nusaibah_pharma_company_intelligence_lab_v0_1_46_adapter.py",
    "ENRICHMENT_V047_GUIDE.md", "ENRICHMENT_V046_GUIDE.md",
    "ENRICHMENT_V045_GUIDE.md", "nusaibah_pharma_company_intelligence_lab_v0_1_45_adapter.py",
    'nusaibah_pharma_company_intelligence_lab_v0_1_44_adapter.py', 'ENRICHMENT_V044_GUIDE.md',
    'nusaibah_pharma_company_intelligence_lab_v0_1_43_adapter.py', 'ENRICHMENT_V043_GUIDE.md',
    'nusaibah_pharma_company_intelligence_lab_v0_1_42_adapter.py', 'ENRICHMENT_V042_GUIDE.md',
    'nusaibah_pharma_company_intelligence_lab_v0_1_41_adapter.py', 'ENRICHMENT_V041_GUIDE.md',
    'ACCEPTANCE_V040.md', 'REQUIREMENTS_V040.md', 'ENRICHMENT_V040_GUIDE.md', 'VERIFICATION_V040.md',
    'pharma_roles_v0_1_40.json', 'materialization_promotion_acceptance_v0_1_40.json',
    'nusaibah_pharma_company_intelligence_lab_v0_1_40_adapter.py',
    "ENRICHMENT_V039_GUIDE.md", "EXECUTION_EXCEPTION_AUDIT.md",
    "nusaibah_pharma_company_intelligence_lab_v0_1_39_adapter.py",
    "nusaibah_pharma_company_intelligence_lab_v0_1_38_adapter.py", "ENRICHMENT_V038_GUIDE.md",
    "nusaibah_pharma_company_intelligence_lab_v0_1_37_adapter.py", "ENRICHMENT_V037_GUIDE.md",
    "nusaibah_pharma_company_intelligence_lab_v0_1_36_adapter.py", "ENRICHMENT_V036_GUIDE.md",
    "nusaibah_pharma_company_intelligence_lab_v0_1_35_adapter.py",
    "ENRICHMENT_V035_GUIDE.md",
    "ENRICHMENT_V034_GUIDE.md",
    "ENRICHMENT_V033_GUIDE.md",
    "ENRICHMENT_V032_GUIDE.md",
    "ENRICHMENT_V031_GUIDE.md",
    "ENRICHMENT_V030_GUIDE.md",
    "ENRICHMENT_V029_GUIDE.md",
    "ENRICHMENT_V028_GUIDE.md",
    "ENRICHMENT_GUIDE.md",
    "nusaibah_pharma_company_intelligence_lab.asset.json",
    "adapter.dependencies.json",
    *EXPECTED_REVIEWED_HELPERS,
    *EXPECTED_REVIEWED_SUPPORT_FILES,
    "README.md",
    "DEVELOPER_GUIDE.md",
}


def _list_under(lines: list[str], key: str) -> list[str]:
    start = lines.index(f"{key}:") + 1
    values: list[str] = []
    for line in lines[start:]:
        if line and not line.startswith(" "):
            break
        stripped = line.strip()
        if stripped.startswith("- "):
            values.append(stripped[2:].strip())
    return values


def _scalar(lines: list[str], key: str) -> str:
    prefix = f"{key}:"
    for line in lines:
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"Missing {key} in adapter.yaml")


class PromotionSurfaceTests(unittest.TestCase):
    def test_declared_entrypoint_exists_with_current_identity(self):
        import ast
        lines = ADAPTER_YAML.read_text(encoding='utf-8').splitlines()
        entrypoint = ASSET_ROOT / _scalar(lines, 'adapter_module')
        tree = ast.parse(entrypoint.read_text(encoding='utf-8'))
        versions = [node.value.value for node in ast.walk(tree)
                    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                    and node.target.id == 'version' and isinstance(node.value, ast.Constant)]
        self.assertEqual([_scalar(lines, 'asset_version')], versions)

    def test_declared_file_lists_are_unique_before_set_comparison(self):
        lines=ADAPTER_YAML.read_text(encoding='utf-8').splitlines()
        for key in ('reviewed_helpers','reviewed_support_files','optional_files'):
            with self.subTest(key=key):
                items=_list_under(lines,key)
                self.assertEqual(len(items),len(set(items)))

    def test_runtime_materialization_surface_excludes_evaluation_and_test_scaffolding(self) -> None:
        text = ADAPTER_YAML.read_text(encoding="utf-8")
        lines = text.splitlines()

        reviewed_helpers = set(_list_under(lines, "reviewed_helpers"))
        reviewed_support = set(_list_under(lines, "reviewed_support_files"))
        optional_files = set(_list_under(lines, "optional_files"))
        adapter_module = _scalar(lines, "adapter_module")
        manifest = _scalar(lines, "manifest")

        self.assertEqual(reviewed_helpers, EXPECTED_REVIEWED_HELPERS)
        self.assertEqual(reviewed_support, EXPECTED_REVIEWED_SUPPORT_FILES | {'pharma_roles_v0_1_40.json','materialization_promotion_acceptance_v0_1_40.json'})
        self.assertEqual(optional_files, {"README.md", "DEVELOPER_GUIDE.md", "ENRICHMENT_GUIDE.md", "ENRICHMENT_V028_GUIDE.md", "ENRICHMENT_V029_GUIDE.md", "ENRICHMENT_V030_GUIDE.md", "ENRICHMENT_V031_GUIDE.md", "ENRICHMENT_V032_GUIDE.md", "ENRICHMENT_V033_GUIDE.md", "ENRICHMENT_V034_GUIDE.md", "ENRICHMENT_V035_GUIDE.md", "ENRICHMENT_V036_GUIDE.md", "ENRICHMENT_V037_GUIDE.md", "ENRICHMENT_V038_GUIDE.md", "ENRICHMENT_V039_GUIDE.md", "EXECUTION_EXCEPTION_AUDIT.md", "ENRICHMENT_V040_GUIDE.md", "REQUIREMENTS_V040.md", "ACCEPTANCE_V040.md", "VERIFICATION_V040.md", "ENRICHMENT_V041_GUIDE.md", "ENRICHMENT_V042_GUIDE.md", "ENRICHMENT_V043_GUIDE.md", "ENRICHMENT_V044_GUIDE.md", "ENRICHMENT_V045_GUIDE.md", "ENRICHMENT_V046_GUIDE.md", "ENRICHMENT_V047_GUIDE.md"})
        self.assertNotIn("tests", text)
        self.assertNotIn("evaluation", text)
        self.assertNotIn("stubs", text)

        declared_runtime_files = {
            adapter_module,
            manifest,
            "adapter.dependencies.json",
            *reviewed_helpers,
            *reviewed_support,
            *optional_files,
        }
        self.assertEqual(declared_runtime_files, EXPECTED_RUNTIME_FILES)
        current_manifest = (
            ASSET_ROOT / "nusaibah_pharma_company_intelligence_lab.asset.json"
        )
        self.assertTrue(current_manifest.exists())
        self.assertIn(current_manifest.name, declared_runtime_files)
        import json
        self.assertEqual({"0.1.43", "0.1.44", "0.1.45", "0.1.46", "0.1.47"}, set(json.loads(current_manifest.read_text(encoding="utf-8"))["versions"]))

    def test_wp_reference_modules_remain_under_tests_only(self) -> None:
        evaluation_root = ASSET_ROOT / "tests" / "evaluation"
        reference_root = evaluation_root / "reference"
        stub_root = ASSET_ROOT / "tests" / "stubs"

        self.assertTrue(reference_root.is_dir())
        self.assertTrue(stub_root.is_dir())

        for path in reference_root.rglob("*.py"):
            self.assertTrue(path.is_relative_to(ASSET_ROOT / "tests"))
        for path in stub_root.rglob("*.py"):
            self.assertTrue(path.is_relative_to(ASSET_ROOT / "tests"))

    def test_all_machine_readable_wp_artifacts_are_present(self) -> None:
        import json

        manifest = json.loads(
            (ASSET_ROOT / "tests" / "evaluation" / "work_packages.v1.json").read_text(
                encoding="utf-8"
            )
        )
        evaluation_root = ASSET_ROOT / "tests" / "evaluation"

        for work_package in manifest["work_packages"]:
            with self.subTest(work_package=work_package["id"]):
                self.assertTrue(work_package["artifacts"])
                for relative_path in work_package["artifacts"]:
                    self.assertTrue(
                        (evaluation_root / relative_path).is_file(),
                        f"{work_package['id']} missing artifact {relative_path}",
                    )


if __name__ == "__main__":
    unittest.main()
