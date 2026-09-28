from __future__ import annotations

import sys
import unittest
from pathlib import Path

ASSET_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSET_ROOT))

from memory_contract import (  # noqa: E402
    MAX_MEMORY_CANDIDATE_CHARS,
    MEMORY_TARGET_SECTION,
    validate_memory_candidate,
)


def _candidate(company_id: int = 13) -> dict:
    return {
        "company_id": company_id,
        "target_section": MEMORY_TARGET_SECTION,
        "markdown": "Grounded company memory update.",
        "fact_ids": ["fact-1", "fact-2"],
    }


class MemoryCandidateTests(unittest.TestCase):
    def test_accepts_bounded_same_company_candidate(self) -> None:
        result = validate_memory_candidate(_candidate(), company_id=13)
        self.assertEqual(result.company_id, 13)
        self.assertEqual(result.fact_ids, ("fact-1", "fact-2"))

    def test_rejects_cross_company_candidate(self) -> None:
        with self.assertRaises(ValueError):
            validate_memory_candidate(_candidate(company_id=59), company_id=13)

    def test_rejects_unapproved_target_section(self) -> None:
        value = _candidate()
        value["target_section"] = "Other Section"
        with self.assertRaises(ValueError):
            validate_memory_candidate(value, company_id=13)

    def test_rejects_blank_markdown(self) -> None:
        value = _candidate()
        value["markdown"] = " "
        with self.assertRaises(ValueError):
            validate_memory_candidate(value, company_id=13)

    def test_rejects_oversized_markdown(self) -> None:
        value = _candidate()
        value["markdown"] = "x" * (MAX_MEMORY_CANDIDATE_CHARS + 1)
        with self.assertRaises(ValueError):
            validate_memory_candidate(value, company_id=13)

    def test_rejects_duplicate_fact_ids(self) -> None:
        value = _candidate()
        value["fact_ids"] = ["fact-1", "fact-1"]
        with self.assertRaises(ValueError):
            validate_memory_candidate(value, company_id=13)


if __name__ == "__main__":
    unittest.main()
