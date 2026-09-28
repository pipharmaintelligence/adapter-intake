from __future__ import annotations

import sys
import unittest
from pathlib import Path

ASSET_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSET_ROOT))

from input_contract import (  # noqa: E402
    MAX_COMPANY_IDS,
    order_records_for_request,
    project_company_baseline,
    resolve_company_records,
    validate_batch_request,
)


def _inputs(company_ids: list[int]) -> dict:
    return {
        "variables": {
            "execution_scope": "batch",
            "company_ids": company_ids,
            "objective": "company_intelligence_memory",
            "research_depth": "deep",
            "memory_mode": "preview",
            "publish_dossier": False,
        }
    }


class BatchRequestTests(unittest.TestCase):
    def test_accepts_bounded_unique_positive_integer_ids(self) -> None:
        request = validate_batch_request(_inputs([13, 59]))
        self.assertEqual(request.company_ids, (13, 59))
        self.assertEqual(request.memory_mode, "preview")
        self.assertFalse(request.publish_dossier)

    def test_rejects_empty_company_ids(self) -> None:
        with self.assertRaises(ValueError):
            validate_batch_request(_inputs([]))

    def test_rejects_duplicate_company_ids(self) -> None:
        with self.assertRaises(ValueError):
            validate_batch_request(_inputs([13, 13]))

    def test_rejects_boolean_and_non_integer_ids(self) -> None:
        for invalid in ([True], ["13"], [13.0], [None]):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_batch_request(_inputs(invalid))  # type: ignore[arg-type]

    def test_rejects_oversized_batch(self) -> None:
        ids = list(range(1, MAX_COMPANY_IDS + 2))
        with self.assertRaises(ValueError):
            validate_batch_request(_inputs(ids))


class GovernedRecordTests(unittest.TestCase):
    def test_accepts_list_and_records_envelope(self) -> None:
        records = [{"company_id": 13}, {"company_id": 59}]
        self.assertEqual(resolve_company_records({"companies": records}), records)
        self.assertEqual(resolve_company_records({"companies": {"records": records}}), records)

    def test_preserves_caller_order_after_governed_resolution(self) -> None:
        request = validate_batch_request(_inputs([13, 59]))
        resolved = [{"company_id": 59, "company_name": "Pfizer"}, {"company_id": 13, "company_name": "Tabuk"}]

        ordered = order_records_for_request(resolved, request)

        self.assertEqual([row["company_id"] for row in ordered], [13, 59])

    def test_rejects_missing_requested_company(self) -> None:
        request = validate_batch_request(_inputs([13, 59]))
        with self.assertRaises(ValueError):
            order_records_for_request([{"company_id": 13}], request)

    def test_rejects_unexpected_company(self) -> None:
        request = validate_batch_request(_inputs([13, 59]))
        with self.assertRaises(ValueError):
            order_records_for_request(
                [{"company_id": 13}, {"company_id": 59}, {"company_id": 77}],
                request,
            )

    def test_rejects_duplicate_resolved_company(self) -> None:
        request = validate_batch_request(_inputs([13, 59]))
        with self.assertRaises(ValueError):
            order_records_for_request(
                [{"company_id": 13}, {"company_id": 13}, {"company_id": 59}],
                request,
            )

    def test_baseline_projection_excludes_sensitive_named_fields(self) -> None:
        record = {
            "company_id": 13,
            "company_name": "Tabuk",
            "country": "SA",
            "api_secret": "do-not-forward",
            "storage_path": "do-not-forward",
            "object_key": "do-not-forward",
            "authorization_note": "do-not-forward",
        }

        projected = project_company_baseline(record)

        self.assertEqual(projected["company_id"], 13)
        self.assertEqual(projected["company_name"], "Tabuk")
        self.assertEqual(projected["country"], "SA")
        self.assertNotIn("api_secret", projected)
        self.assertNotIn("storage_path", projected)
        self.assertNotIn("object_key", projected)
        self.assertNotIn("authorization_note", projected)


if __name__ == "__main__":
    unittest.main()
