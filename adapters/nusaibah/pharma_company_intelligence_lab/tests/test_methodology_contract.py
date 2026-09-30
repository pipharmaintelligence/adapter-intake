from __future__ import annotations

import sys
import unittest
from pathlib import Path

ASSET_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSET_ROOT))

from agent_contract import RESEARCH_ROLE_SECTIONS  # noqa: E402
from methodology_contract import (  # noqa: E402
    MAX_PLANNER_TEXT_CHARS,
    MANDATORY_RESEARCH_ROLES,
    PLANNER_ROLE,
    PLANNER_SCHEMA_VERSION,
    _build_methodology_packet,
    validate_methodology_plan,
)


def _valid_plan(company_id: int = 13) -> dict:
    return {
        "schema_version": PLANNER_SCHEMA_VERSION,
        "company_id": company_id,
        "role": PLANNER_ROLE,
        "status": "completed",
        "research_focus": [
            {
                "role": role,
                "priority": "high" if role == "regulatory_risk_researcher" else "medium",
                "section_ids": list(RESEARCH_ROLE_SECTIONS[role]),
                "questions": [f"What matters most for {role}?"],
                "freshness_focus": ["recent material changes"],
                "evidence_focus": ["authoritative public evidence"],
            }
            for role in MANDATORY_RESEARCH_ROLES
        ],
        "cross_cutting_questions": ["What changed compared with stored memory?"],
        "known_memory_gaps": ["Recent developments may be incomplete."],
        "expected_uncertainties": ["Some evidence may remain unresolved."],
    }


class MethodologyPacketTests(unittest.TestCase):
    def test_builds_bounded_packet_from_fixed_methodology_text(self) -> None:
        root = ASSET_ROOT / "tests" / "fixtures" / "skills" / "pharma-intelligence-methodology"
        packet = _build_methodology_packet(
            skill_text=(root / "SKILL.md").read_text(encoding="utf-8"),
            evidence_policy=(root / "references" / "evidence-policy.md").read_text(encoding="utf-8"),
            benchmark_questions=(
                {"question_id": "company_identity", "question": "What is the company identity?"},
            ),
            memory_policy={
                "schema_version": "pharma_company_memory_policy.v1",
                "target_section": "Current Public Research",
                "max_candidate_chars": 24000,
                "max_fact_ids": 256,
                "require_company_id_match": True,
                "require_novelty": True,
                "require_deduplication": True,
                "require_quality_gate": True,
                "require_expected_digest_on_apply": True,
                "require_fresh_readback": True,
                "require_history_verification": True,
            },
            package_digest="sha256:" + "1" * 64,
        )

        value = packet.to_agent_input()
        self.assertEqual(value["skill_ref"], "nusaibah.pharma-intelligence-methodology")
        self.assertEqual(
            value["canonical_section_ids"][2:6],
            [
                "company_profile",
                "product_portfolio_intelligence",
                "markets_commercial_signals",
                "regulatory_clinical_risk_signals",
            ],
        )
        self.assertTrue(value["mission"])
        self.assertTrue(value["structural_rules"])
        self.assertGreater(len(value["evidence_rules"]), 6)
        self.assertIs(value["memory_policy"]["require_expected_digest_on_apply"], True)


class MethodologyPlanTests(unittest.TestCase):
    def test_accepts_exact_role_section_map_and_exposes_role_fragments(self) -> None:
        plan = validate_methodology_plan(_valid_plan(), company_id=13)

        self.assertEqual(plan.company_id, 13)
        self.assertEqual(
            [item.role for item in plan.research_focus],
            list(MANDATORY_RESEARCH_ROLES),
        )
        self.assertEqual(
            plan.role_focus("portfolio_researcher")["section_ids"],
            list(RESEARCH_ROLE_SECTIONS["portfolio_researcher"]),
        )

    def test_requirement_catalog_has_stable_unique_ids(self) -> None:
        plan = validate_methodology_plan(_valid_plan(), company_id=13)

        catalog = plan.requirement_catalog()
        requirement_ids = [item["requirement_id"] for item in catalog]

        self.assertEqual(len(requirement_ids), len(set(requirement_ids)))
        self.assertEqual(tuple(requirement_ids), plan.requirement_ids())
        self.assertIn(
            "research.portfolio_researcher.question.1",
            requirement_ids,
        )
        self.assertIn("cross_cutting_question.1", requirement_ids)
        self.assertIn("known_memory_gap.1", requirement_ids)
        self.assertIn("expected_uncertainty.1", requirement_ids)
        self.assertTrue(all(item["mandatory"] is True for item in catalog))

    def test_rejects_wrong_company(self) -> None:
        with self.assertRaisesRegex(ValueError, "company_id"):
            validate_methodology_plan(_valid_plan(company_id=59), company_id=13)

    def test_rejects_unknown_role(self) -> None:
        value = _valid_plan()
        value["research_focus"][0]["role"] = "unknown_researcher"

        with self.assertRaisesRegex(ValueError, "unknown research role"):
            validate_methodology_plan(value, company_id=13)

    def test_rejects_wrong_section_ownership(self) -> None:
        value = _valid_plan()
        value["research_focus"][0]["section_ids"] = ["markets_commercial_signals"]

        with self.assertRaisesRegex(ValueError, "section ownership"):
            validate_methodology_plan(value, company_id=13)

    def test_rejects_missing_mandatory_role(self) -> None:
        value = _valid_plan()
        value["research_focus"].pop()

        with self.assertRaisesRegex(ValueError, "mandatory research role"):
            validate_methodology_plan(value, company_id=13)

    def test_rejects_duplicate_section(self) -> None:
        value = _valid_plan()
        value["research_focus"][0]["section_ids"] = [
            "company_profile",
            "company_profile",
        ]

        with self.assertRaisesRegex(ValueError, "duplicates"):
            validate_methodology_plan(value, company_id=13)

    def test_rejects_oversized_question(self) -> None:
        value = _valid_plan()
        value["research_focus"][0]["questions"] = ["x" * (MAX_PLANNER_TEXT_CHARS + 1)]

        with self.assertRaisesRegex(ValueError, "character bound"):
            validate_methodology_plan(value, company_id=13)

    def test_rejects_control_authority_field(self) -> None:
        value = _valid_plan()
        value["model"] = "planner-selected-model"

        with self.assertRaisesRegex(ValueError, "control-authority"):
            validate_methodology_plan(value, company_id=13)

    def test_rejects_unknown_non_control_field(self) -> None:
        value = _valid_plan()
        value["notes"] = "free-form bypass"

        with self.assertRaisesRegex(ValueError, "unknown keys: notes"):
            validate_methodology_plan(value, company_id=13)


if __name__ == "__main__":
    unittest.main()
