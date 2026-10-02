from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

ASSET_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSET_ROOT))

try:
    from adapters.base import Adapter
except ModuleNotFoundError as error:
    if error.name not in {"adapters", "adapters.base"}:
        raise
    package = ModuleType("adapters")
    base = ModuleType("adapters.base")
    base.Adapter = object
    package.base = base
    with patch.dict(sys.modules, {"adapters": package, "adapters.base": base}):
        import nusaibah_pharma_company_intelligence_lab_adapter as adapter
else:
    import nusaibah_pharma_company_intelligence_lab_adapter as adapter


def planner_chunk() -> dict:
    return {
        "chunk_id": "portfolio_researcher:company_profile",
        "research_role": "portfolio_researcher",
        "section_id": "company_profile",
        "priority_hint": "medium",
    }


class PlannerContractParityTests(unittest.TestCase):
    def test_provider_visible_contract_matches_validator_invariants(self) -> None:
        chunk = planner_chunk()
        contract = adapter.planner_section_response_contract(
            company_id=13,
            planner_chunk=chunk,
            priority_hint="medium",
        )
        validation = contract["validation_contract"]
        fields = validation["fields"]

        self.assertIs(validation["exact_fields"], True)
        self.assertEqual(validation["text_normalization"], "collapse_whitespace_and_trim")
        self.assertEqual(set(fields), set(contract["required_fields"]))
        self.assertEqual(fields["schema_version"]["required_value"], adapter.PLANNER_CHUNK_SCHEMA_VERSION)
        self.assertEqual(fields["company_id"], {"type": "integer", "required_value": 13})
        self.assertEqual(fields["role"]["required_value"], adapter.PLANNER_ROLE)
        self.assertEqual(fields["status"]["required_value"], "completed")
        self.assertEqual(fields["chunk_id"]["required_value"], chunk["chunk_id"])
        self.assertEqual(fields["research_role"]["required_value"], chunk["research_role"])
        self.assertEqual(fields["section_id"]["required_value"], chunk["section_id"])
        self.assertEqual(fields["priority"]["required_value"], "medium")
        self.assertEqual(fields["priority"]["allowed_values"], sorted(adapter.PLANNER_PRIORITIES))

        expected_lists = (
            ("questions", 1, adapter.PLANNER_MAX_QUESTIONS_PER_SECTION),
            ("freshness_focus", 0, adapter.PLANNER_MAX_FRESHNESS_FOCUS_ITEMS_PER_SECTION),
            ("evidence_focus", 0, adapter.PLANNER_MAX_EVIDENCE_FOCUS_ITEMS_PER_SECTION),
            ("methodology_steps", 1, adapter.PLANNER_MAX_METHODOLOGY_STEPS_PER_SECTION),
        )
        for field, minimum, maximum in expected_lists:
            with self.subTest(field=field):
                descriptor = fields[field]
                self.assertEqual(descriptor["type"], "array")
                self.assertEqual(descriptor["min_items"], minimum)
                self.assertEqual(descriptor["max_items"], maximum)
                self.assertIs(descriptor["unique_after_normalization"], True)
                self.assertEqual(
                    descriptor["items"],
                    {
                        "type": "string",
                        "nonempty": True,
                        "max_chars": adapter.PLANNER_MAX_TEXT_CHARS,
                    },
                )

        self.assertEqual(
            fields["priority_rationale"],
            {
                "type": "string",
                "nonempty": True,
                "max_chars": adapter.PLANNER_MAX_TEXT_CHARS,
            },
        )

    def test_validation_failure_projects_only_reviewed_enum_metadata(self) -> None:
        chunk = planner_chunk()
        value = {
            "schema_version": adapter.PLANNER_CHUNK_SCHEMA_VERSION,
            "company_id": 13,
            "role": adapter.PLANNER_ROLE,
            "status": "completed",
            "chunk_id": chunk["chunk_id"],
            "research_role": chunk["research_role"],
            "section_id": chunk["section_id"],
            "priority": "medium",
            "questions": [],
            "freshness_focus": [],
            "evidence_focus": [],
            "methodology_steps": ["Verify authoritative evidence."],
            "priority_rationale": "Baseline coverage is incomplete.",
        }

        with self.assertRaises(adapter.AgentContractValidationError) as raised:
            adapter._validate_planner_section(value, company_id=13, planner_chunk=chunk)

        self.assertEqual(
            raised.exception.proof_failure_detail,
            {
                "schema_version": "proof_failure_detail.v1",
                "proof_kind": "agent_contract",
                "role": "methodology_planner",
                "stage": "planner_section",
                "rule": "item_count",
                "field": "questions",
            },
        )

    def test_iteration_limit_projects_distinct_enum_metadata(self) -> None:
        with self.assertRaises(adapter.AgentContractValidationError) as raised:
            adapter._iteration_limit_exceeded()

        self.assertEqual(
            raised.exception.proof_failure_detail,
            {
                "schema_version": "proof_failure_detail.v1",
                "proof_kind": "agent_contract",
                "role": "orchestration",
                "stage": "logical_agent_budget",
                "rule": "iteration_limit",
            },
        )


if __name__ == "__main__":
    unittest.main()
