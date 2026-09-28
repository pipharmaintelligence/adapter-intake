from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ASSET_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_MODULE = "nusaibah_pharma_company_intelligence_lab_adapter.py"
HELPERS = ("input_contract.py", "dossier_contract.py", "memory_contract.py")


class ImportContextTests(unittest.TestCase):
    def test_local_root_import(self) -> None:
        code = textwrap.dedent(
            f"""
            import sys
            import types
            from pathlib import Path

            class Adapter:
                pass

            adapters = types.ModuleType("adapters")
            base = types.ModuleType("adapters.base")
            base.Adapter = Adapter
            adapters.base = base
            sys.modules["adapters"] = adapters
            sys.modules["adapters.base"] = base

            asset_root = Path({str(ASSET_ROOT)!r})
            sys.path.insert(0, str(asset_root))

            import nusaibah_pharma_company_intelligence_lab_adapter as module
            assert module.NusaibahPharmaCompanyIntelligenceLabAdapter.key == "nusaibah.pharma_company_intelligence_lab"
            assert module.NusaibahPharmaCompanyIntelligenceLabAdapter.version == "0.1.0"
            """
        )
        subprocess.run([sys.executable, "-c", code], check=True)

    def test_packaged_dotted_import(self) -> None:
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
                "class Adapter:\n    pass\n",
                encoding="utf-8",
            )

            shutil.copy2(ASSET_ROOT / ADAPTER_MODULE, package / ADAPTER_MODULE)
            for helper in HELPERS:
                shutil.copy2(ASSET_ROOT / helper, package / helper)

            code = textwrap.dedent(
                f"""
                import sys
                sys.path.insert(0, {str(root)!r})
                from python_runtime.adapters.intake.nusaibah.pharma_company_intelligence_lab.nusaibah_pharma_company_intelligence_lab_adapter import NusaibahPharmaCompanyIntelligenceLabAdapter
                assert NusaibahPharmaCompanyIntelligenceLabAdapter.key == "nusaibah.pharma_company_intelligence_lab"
                assert NusaibahPharmaCompanyIntelligenceLabAdapter.version == "0.1.0"
                """
            )
            subprocess.run([sys.executable, "-c", code], check=True)


if __name__ == "__main__":
    unittest.main()
