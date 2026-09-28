from __future__ import annotations

import sys
import unittest
from pathlib import Path

ASSET_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSET_ROOT))

from agent_contract import validate_critic_payload  # noqa: E402


KNOWN_REQUIREMENTS = {
    "research.portfolio_researcher.question.1",
    "cross_cutting_question.1",
}


def _critic_payload() -> dict:
    return {
        "schema_version": "pharma_evidence_critic.v1",
        "company_id": 13,
        "role": "evidence_critic",
        "status": "completed",
        "unsupported_claim_ids": [],
        "contradiction_items": [],
        "stale_claim_ids": [],
        "missing_section_ids": [],
        "unmet_plan_requirements": [],
        "citation_coverage": {
            "status": "sufficient",
            "notes": "Grounded.",
        },
        "residual_uncertainties": [],
        "recommendation": "pass",
    }


def _validate(value: dict) -> dict:
    return validate_critic_payload(
        value,
        company_id=13,
        known_claim_ids={"claim-1"},
        known_section_ids={"company_profile"},
        known_plan_requirement_ids=KNOWN_REQUIREMENTS,
    )


class CriticPlanRequirementContractTests(unittest.TestCase):
    def test_accepts_explicit_unresolved_evidence(self) -> None:
        value = _critic_payload()
        value["unmet_plan_requirements"] = [
            {
                "requirement_id": "cross_cutting_question.1",
                "disposition": "unresolved_evidence",
                "notes": "The supplied evidence cannot resolve this item.",
            }
        ]

        result = _validate(value)

        self.assertEqual(
            result["unmet_plan_requirements"][0]["disposition"],
            "unresolved_evidence",
        )

    def test_accepts_explicit_unsatisfied_requirement_for_adapter_gate(self) -> None:
        value = _critic_payload()
        value["unmet_plan_requirements"] = [
            {
                "requirement_id": "research.portfolio_researcher.question.1",
                "disposition": "unsatisfied",
                "notes": "The supplied research did not answer this required question.",
            }
        ]

        result = _validate(value)

        self.assertEqual(
            result["unmet_plan_requirements"][0]["requirement_id"],
            "research.portfolio_researcher.question.1",
        )

    def test_rejects_unknown_requirement_id(self) -> None:
        value = _critic_payload()
        value["unmet_plan_requirements"] = [
            {
                "requirement_id": "invented.requirement.1",
                "disposition": "unresolved_evidence",
                "notes": "Not admitted by the adapter.",
            }
        ]

        with self.assertRaisesRegex(ValueError, "unknown planner requirement_id"):
            _validate(value)

    def test_rejects_duplicate_requirement_id(self) -> None:
        value = _critic_payload()
        item = {
            "requirement_id": "cross_cutting_question.1",
            "disposition": "unresolved_evidence",
            "notes": "Still unresolved.",
        }
        value["unmet_plan_requirements"] = [dict(item), dict(item)]

        with self.assertRaisesRegex(ValueError, "must be unique"):
            _validate(value)

    def test_rejects_unknown_disposition(self) -> None:
        value = _critic_payload()
        value["unmet_plan_requirements"] = [
            {
                "requirement_id": "cross_cutting_question.1",
                "disposition": "ignored",
                "notes": "Invalid disposition.",
            }
        ]

        with self.assertRaisesRegex(ValueError, "disposition is unsupported"):
            _validate(value)

    def test_requires_unmet_plan_requirements_field(self) -> None:
        value = _critic_payload()
        del value["unmet_plan_requirements"]

        with self.assertRaisesRegex(ValueError, "must be a bounded list"):
            _validate(value)


if __name__ == "__main__":
    unittest.main()
