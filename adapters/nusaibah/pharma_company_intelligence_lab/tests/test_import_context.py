from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ASSET_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_YAML = ASSET_ROOT / "adapter.yaml"
NEW_ADAPTER_MODULE = "nusaibah_pharma_company_intelligence_lab_v0_1_21_adapter.py"
HISTORICAL_ADAPTER_MODULE = "legacy_preparation_helpers_v0_1_21.py"
NEW_CLASS = "NusaibahPharmaCompanyIntelligenceLabV021Adapter"
HISTORICAL_CLASS = "NusaibahPharmaCompanyIntelligenceLabAdapter"


def _yaml_list(key: str) -> tuple[str, ...]:
    lines = ADAPTER_YAML.read_text(encoding="utf-8").splitlines()
    start = lines.index(f"{key}:") + 1
    values: list[str] = []
    for line in lines[start:]:
        if line and not line.startswith(" "):
            break
        stripped = line.strip()
        if stripped.startswith("- "):
            values.append(stripped[2:].strip())
    return tuple(values)


def _python_materialization_files() -> tuple[str, ...]:
    return tuple(
        dict.fromkeys((NEW_ADAPTER_MODULE, *_yaml_list("reviewed_helpers")))
    )


def _adapter_stub() -> str:
    return "class Adapter:\n    pass\n"


class ImportContextTests(unittest.TestCase):
    def test_local_root_imports_new_entrypoint_and_non_adapter_helpers(self) -> None:
        code = textwrap.dedent(
            f"""
            import sys
            import types
            from pathlib import Path

            adapters = types.ModuleType("adapters")
            base = types.ModuleType("adapters.base")
            base.Adapter = type("Adapter", (), {{}})
            adapters.base = base
            sys.modules["adapters"] = adapters
            sys.modules["adapters.base"] = base

            asset_root = Path({str(ASSET_ROOT)!r})
            sys.path.insert(0, str(asset_root))

            from {NEW_ADAPTER_MODULE[:-3]} import {NEW_CLASS}
            from {HISTORICAL_ADAPTER_MODULE[:-3]} import {HISTORICAL_CLASS}

            assert {NEW_CLASS}.key == "nusaibah.pharma_company_intelligence_lab"
            assert {NEW_CLASS}.version == "0.1.21"
            assert {HISTORICAL_CLASS}.key == "nusaibah.pharma_company_intelligence_lab"
            assert {HISTORICAL_CLASS}.version == "0.1.20"
            assert not issubclass({HISTORICAL_CLASS}, base.Adapter)
            """
        )
        subprocess.run([sys.executable, "-c", code], check=True)

    def test_packaged_dotted_imports_new_entrypoint_and_non_adapter_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package = (
                root
                / "python_runtime"
                / "adapters"
                / "intake"
                / "nusaibah"
                / "pharma_company_intelligence_lab"
            )
            package.mkdir(parents=True)

            for path in (
                root / "python_runtime",
                root / "python_runtime" / "adapters",
                root / "python_runtime" / "adapters" / "intake",
                root / "python_runtime" / "adapters" / "intake" / "nusaibah",
                package,
            ):
                (path / "__init__.py").write_text("", encoding="utf-8")

            adapters = root / "adapters"
            adapters.mkdir()
            (adapters / "__init__.py").write_text("", encoding="utf-8")
            (adapters / "base.py").write_text(
                _adapter_stub(),
                encoding="utf-8",
            )

            for filename in _python_materialization_files():
                shutil.copy2(ASSET_ROOT / filename, package / filename)

            package_name = (
                "python_runtime.adapters.intake.nusaibah."
                "pharma_company_intelligence_lab"
            )
            code = textwrap.dedent(
                f"""
                import sys
                sys.path.insert(0, {str(root)!r})

                from {package_name}.{NEW_ADAPTER_MODULE[:-3]} import {NEW_CLASS}
                from {package_name}.{HISTORICAL_ADAPTER_MODULE[:-3]} import {HISTORICAL_CLASS}

                assert {NEW_CLASS}.key == "nusaibah.pharma_company_intelligence_lab"
                assert {NEW_CLASS}.version == "0.1.21"
                assert {HISTORICAL_CLASS}.version == "0.1.20"
                from adapters.base import Adapter
                assert not issubclass({HISTORICAL_CLASS}, Adapter)
                """
            )
            subprocess.run([sys.executable, "-c", code], check=True)

    def test_every_declared_python_file_is_present_for_materialization(self) -> None:
        files = _python_materialization_files()
        self.assertEqual(len(files), len(set(files)))
        self.assertIn(NEW_ADAPTER_MODULE, files)
        self.assertIn(HISTORICAL_ADAPTER_MODULE, files)
        for filename in files:
            with self.subTest(filename=filename):
                self.assertTrue((ASSET_ROOT / filename).is_file())


if __name__ == "__main__":
    unittest.main()
