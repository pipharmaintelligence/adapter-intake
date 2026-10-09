from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import textwrap
import unittest

ASSET_ROOT = Path(__file__).resolve().parents[1]


class DiagnosticCandidateRegressionTests(unittest.TestCase):
    def test_candidate_passes_existing_orchestration_apply_and_budget_suites(self):
        # Import the candidate under the historical test seam in a separate
        # process; the ordinary suite still runs against retained 0.1.12.
        code = textwrap.dedent(f"""
            import sys, unittest
            from pathlib import Path
            root = Path({str(ASSET_ROOT)!r})
            sys.path.insert(0, str(root / "tests/stubs"))
            sys.path.insert(0, str(root / "tests"))
            sys.path.insert(0, str(root))
            import nusaibah_pharma_company_intelligence_lab_v0_1_13_adapter as candidate
            sys.modules["nusaibah_pharma_company_intelligence_lab_adapter"] = candidate
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
