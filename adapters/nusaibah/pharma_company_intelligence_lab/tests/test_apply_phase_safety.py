from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ASSET_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ASSET_ROOT))
sys.path.insert(0, str(TEST_ROOT))

import nusaibah_pharma_company_intelligence_lab_adapter as adapter_module  # noqa: E402
from nusaibah_pharma_company_intelligence_lab_adapter import (  # noqa: E402
    NusaibahPharmaCompanyIntelligenceLabAdapter,
)
from test_orchestration_preview import (  # noqa: E402
    FakeInputs,
    FirstRunMethodologyInputs,
    _fake_citations,
)


class ApplyPhaseSafetyTests(unittest.TestCase):
    def test_uninitialized_methodology_apply_fails_before_any_mutation(self) -> None:
        inputs = FirstRunMethodologyInputs()
        inputs["variables"]["memory_mode"] = "apply"
        adapter = NusaibahPharmaCompanyIntelligenceLabAdapter()

        with patch.object(adapter_module, "_agent_citations", side_effect=_fake_citations):
            with self.assertRaisesRegex(
                RuntimeError,
                "governed create-if-absent is required before apply",
            ):
                adapter.invoke(inputs, {})

        mutable_calls = [
            item for item in inputs.dynamic_skill_calls if item[0].endswith("_update")
        ]
        self.assertEqual(mutable_calls, [])

    def test_phase_one_failure_on_second_company_starts_zero_mutations(self) -> None:
        inputs = FakeInputs(wrong_company_role="market_researcher")
        inputs["variables"]["memory_mode"] = "apply"
        adapter = NusaibahPharmaCompanyIntelligenceLabAdapter()

        with patch.object(adapter_module, "_agent_citations", side_effect=_fake_citations):
            if hasattr(adapter_module, "issues_annex"):
                with self.assertRaises(adapter_module.AgentContractValidationError) as caught:
                    adapter.invoke(inputs, {})
                self.assertEqual(caught.exception.code, "pharma_agent_company_id_invalid")
            elif hasattr(adapter_module, "RESEARCH_RESOLVER_ROLE"):
                from research_diagnostics_v0_1_17 import ResearchContractValidationError
                with self.assertRaises(ResearchContractValidationError) as caught:
                    adapter.invoke(inputs, {})
                self.assertEqual(caught.exception.proof_failure_detail["field"], "company_id")
            else:
                with self.assertRaisesRegex(RuntimeError, "wrong company_id"):
                    adapter.invoke(inputs, {})

        mutable_calls = [
            item for item in inputs.dynamic_skill_calls if item[0] == "company_memory_update"
        ]
        self.assertEqual(mutable_calls, [])


if __name__ == "__main__":
    unittest.main()
