from __future__ import annotations

import sys
import unittest
from pathlib import Path

ASSET_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSET_ROOT))

import nusaibah_pharma_company_intelligence_lab_adapter as adapter_module  # noqa: E402


def _research() -> dict:
    return {
        role: {"_citations": [object()]}
        for role in adapter_module.RESEARCH_ROLES
    }


def _critic() -> dict:
    return {
        "recommendation": "pass",
        "citation_coverage": {"status": "sufficient", "notes": ""},
        "unsupported_claim_ids": [],
        "contradiction_items": [],
        "stale_claim_ids": [],
        "missing_section_ids": [],
        "unmet_plan_requirements": [],
    }


class PreSynthesisQualityGateTests(unittest.TestCase):
    def test_passes_clean_evidence_package(self) -> None:
        adapter_module._require_pre_synthesis_quality(_research(), _critic())

    def test_rejects_missing_research_citations(self) -> None:
        research = _research()
        research["market_researcher"]["_citations"] = []

        with self.assertRaisesRegex(RuntimeError, "must return admitted citations"):
            adapter_module._require_pre_synthesis_quality(research, _critic())

    def test_rejects_critic_fail_recommendation(self) -> None:
        critic = _critic()
        critic["recommendation"] = "fail"

        with self.assertRaisesRegex(RuntimeError, "critic rejected"):
            adapter_module._require_pre_synthesis_quality(_research(), critic)

    def test_rejects_insufficient_citation_coverage(self) -> None:
        critic = _critic()
        critic["citation_coverage"]["status"] = "insufficient"

        with self.assertRaisesRegex(RuntimeError, "insufficient citation coverage"):
            adapter_module._require_pre_synthesis_quality(_research(), critic)

    def test_rejects_unsupported_claims(self) -> None:
        critic = _critic()
        critic["unsupported_claim_ids"] = ["claim-1"]

        with self.assertRaisesRegex(RuntimeError, "Unsupported research claims"):
            adapter_module._require_pre_synthesis_quality(_research(), critic)

    def test_rejects_missing_sections(self) -> None:
        critic = _critic()
        critic["missing_section_ids"] = ["company_profile"]

        with self.assertRaisesRegex(RuntimeError, "Mandatory research sections"):
            adapter_module._require_pre_synthesis_quality(_research(), critic)

    def test_rejects_unsatisfied_planner_requirement(self) -> None:
        critic = _critic()
        critic["unmet_plan_requirements"] = [
            {
                "requirement_id": "cross_cutting_question.1",
                "disposition": "unsatisfied",
                "notes": "Required item was not fulfilled.",
            }
        ]

        with self.assertRaisesRegex(RuntimeError, "plan requirements remain unsatisfied"):
            adapter_module._require_pre_synthesis_quality(_research(), critic)

    def test_allows_explicit_unresolved_evidence(self) -> None:
        critic = _critic()
        critic["unmet_plan_requirements"] = [
            {
                "requirement_id": "cross_cutting_question.1",
                "disposition": "unresolved_evidence",
                "notes": "Evidence remains unavailable.",
            }
        ]

        adapter_module._require_pre_synthesis_quality(_research(), critic)


if __name__ == "__main__":
    unittest.main()
