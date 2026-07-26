from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "adapters" / "nusaibah" / "sfda_getdrugs_daily_changes"
ROLES = ("latest_snapshot", "previous_snapshot")
CANONICAL_ADAPTER_SHA256 = "79fa9ad34c399bad85d7f7a93db31d1d5178cb330f0dcb4e666e6aacf0e04747"


class SfdaFilePreparationContractTest(unittest.TestCase):
    def test_python_callable_is_unchanged(self) -> None:
        payload = (ASSET / "sfda_getdrugs_daily_changes_adapter.py").read_bytes()
        self.assertEqual(CANONICAL_ADAPTER_SHA256, hashlib.sha256(payload).hexdigest())

    def test_authoring_declares_two_independent_partition_file_roles(self) -> None:
        authoring = self._json("sfda_getdrugs_daily_changes.authoring.json")
        for role in ROLES:
            config = authoring["inputs"][role]
            self.assertEqual("partition_file", config["mode"])
            self.assertEqual(["extraction_date"], config["partitioning"]["dimensions"])
            self.assertEqual("governed", config["partitioning"]["source"])
            self.assertEqual(
                {"extraction_date": f"{role.removesuffix('_snapshot')}_extraction_date"},
                config["partitioning"]["partition_filters_from_variables"],
            )
            self._assert_materializer(config["materializer"])

    def test_preparation_profile_uses_only_logical_governed_references(self) -> None:
        profile = self._json("run_profiles/sfda_getdrugs_daily_changes.dlm.json")
        encoded = json.dumps(profile, sort_keys=True).lower()
        for forbidden in (
            "retrieval_handle",
            "http://",
            "https://",
            "gs://",
            "gcs://",
            "bucket",
            "object_key",
            "storage_path",
            "credential",
            "provider_payload",
        ):
            self.assertNotIn(forbidden, encoded)

        for role in ROLES:
            config = profile["inputs"][role]
            self.assertEqual("partition_file", config["mode"])
            self.assertEqual(f"@input.{role}.source", config["source_ref"])
            self.assertEqual(f"@input.{role}.node", config["node_ref"])
            self._assert_materializer(config["materializer"])

    def test_intake_packet_promotes_documentation_not_local_profiles_or_fixtures(self) -> None:
        contract = (ASSET / "adapter.yaml").read_text(encoding="utf-8")
        self.assertIn("optional_files:\n  - README.md", contract)
        self.assertNotIn("run_profiles/", contract)
        self.assertNotIn("fixtures/", contract)
        self.assertIn("allow_raw_fixtures: false", contract)

    def _json(self, relative: str) -> dict[str, object]:
        value = json.loads((ASSET / relative).read_text(encoding="utf-8"))
        self.assertIsInstance(value, dict)
        return value

    def _assert_materializer(self, value: object) -> None:
        self.assertEqual(
            {
                "key": "json_object",
                "format": "json",
                "content_type": "application/json",
                "record_path": "/records",
                "complete_required": True,
            },
            value,
        )


if __name__ == "__main__":
    unittest.main()
