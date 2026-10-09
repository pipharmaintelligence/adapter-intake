from __future__ import annotations

import unittest
from pathlib import Path


ASSET_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_YAML = ASSET_ROOT / "adapter.yaml"

EXPECTED_REVIEWED_HELPERS = {
    "input_contract.py",
    "dossier_contract.py",
    "memory_contract.py",
    "agent_contract.py",
    "critic_diagnostics_v0_1_13.py",
    "methodology_contract.py",
}

EXPECTED_RUNTIME_FILES = {
    "nusaibah_pharma_company_intelligence_lab_v0_1_13_adapter.py",
    "nusaibah_pharma_company_intelligence_lab.asset.json",
    "adapter.dependencies.json",
    "input_contract.py",
    "dossier_contract.py",
    "memory_contract.py",
    "agent_contract.py",
    "critic_diagnostics_v0_1_13.py",
    "methodology_contract.py",
    "README.md",
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


class PromotionSurfaceTests(unittest.TestCase):
    def test_runtime_materialization_surface_excludes_evaluation_and_test_scaffolding(self) -> None:
        text = ADAPTER_YAML.read_text(encoding="utf-8")
        lines = text.splitlines()

        reviewed_helpers = set(_list_under(lines, "reviewed_helpers"))
        optional_files = set(_list_under(lines, "optional_files"))

        self.assertEqual(reviewed_helpers, EXPECTED_REVIEWED_HELPERS)
        self.assertEqual(optional_files, {"README.md"})
        self.assertNotIn("tests", text)
        self.assertNotIn("evaluation", text)
        self.assertNotIn("stubs", text)

        declared_runtime_files = {
            "nusaibah_pharma_company_intelligence_lab_v0_1_13_adapter.py",
            "nusaibah_pharma_company_intelligence_lab.asset.json",
            "adapter.dependencies.json",
            *reviewed_helpers,
            *optional_files,
        }
        self.assertEqual(declared_runtime_files, EXPECTED_RUNTIME_FILES)

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
