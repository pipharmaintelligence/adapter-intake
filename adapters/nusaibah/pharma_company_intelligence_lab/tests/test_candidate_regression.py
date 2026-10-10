from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import textwrap
import unittest

ASSET_ROOT = Path(__file__).resolve().parents[1]


class RetainedBaselineRegressionTests(unittest.TestCase):
    def test_retained_baseline_passes_existing_orchestration_apply_and_budget_suites(self):
        self.run_retained_baseline("0.1.12")
        self.run_retained_baseline("0.1.13")
        self.run_retained_baseline("0.1.14")
        self.run_retained_baseline("0.1.15")

    def run_retained_baseline(self, version):
        # Run the pinned historical source in a separate process; the ordinary
        # suite runs against the current 0.1.16 production candidate.
        code = textwrap.dedent(f"""
            import importlib.util, sys, unittest
            from pathlib import Path
            root = Path({str(ASSET_ROOT)!r})
            sys.path.insert(0, str(root / "tests/stubs"))
            sys.path.insert(0, str(root / "tests"))
            sys.path.insert(0, str(root))
            name = "nusaibah_pharma_company_intelligence_lab_adapter"
            spec = importlib.util.spec_from_file_location(name, root / "tests/fixtures/baseline-production-{version}.py")
            baseline = importlib.util.module_from_spec(spec)
            sys.modules[name] = baseline
            spec.loader.exec_module(baseline)
            assert baseline.NusaibahPharmaCompanyIntelligenceLabAdapter.version == "{version}"
            suite = unittest.defaultTestLoader.loadTestsFromNames([
                "test_orchestration_preview", "test_apply_phase_safety",
                "test_iteration_limits", "test_memory_apply_contract",
            ])
            result = unittest.TextTestRunner().run(suite)
            assert result.testsRun >= 50
            raise SystemExit(not result.wasSuccessful())
        """)
        subprocess.run([sys.executable, "-c", code], check=True)


if __name__ == "__main__":
    unittest.main()
