from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "adapters" / "nusaibah" / "sfda_getdrugs_daily_changes"
ROLES = ("latest_snapshot", "previous_snapshot")
CANONICAL_ADAPTER_LF_SHA256 = "79fa9ad34c399bad85d7f7a93db31d1d5178cb330f0dcb4e666e6aacf0e04747"
INSPECTOR_PATH = ASSET / "daily_changes_self_inspection.py"


def _load_inspector():
    spec = importlib.util.spec_from_file_location("daily_changes_self_inspection", INSPECTOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("daily_changes_self_inspection_import_failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


INSPECTOR = _load_inspector()
SCHEMA_SHA256 = "a" * 64
SCHEMA_CONTRACT = {
    "pointer": {
        "node_key": "sfda_getdrugs_daily_changes",
        "schema_version": "sfda_getdrugs_daily_changes.v1",
        "schema_sha256": SCHEMA_SHA256,
    },
    "schema": {
        "payload_schema_version": "sfda_getdrugs_daily_changes.changes.v1",
        "results": {
            "contract": {
                "type": "object",
                "required": ["change_type", "record_key"],
                "properties": {
                    "change_type": {
                        "type": "string",
                        "enum": ["added", "changed", "removed"],
                    },
                    "record_key": {"type": "string", "minLength": 1},
                },
                "additionalProperties": True,
            }
        },
        "payload_contract": {
            "type": "object",
            "required": ["trace", "summary", "changes"],
            "properties": {
                "trace": {"type": "object"},
                "summary": {"type": "object"},
                "changes": {"type": "array"},
            },
            "additionalProperties": False,
        },
    },
}


class SfdaFilePreparationContractTest(unittest.TestCase):
    def test_python_callable_source_is_unchanged(self) -> None:
        payload = (ASSET / "sfda_getdrugs_daily_changes_adapter.py").read_bytes()
        normalized = payload.replace(b"\r\n", b"\n")
        self.assertEqual(
            CANONICAL_ADAPTER_LF_SHA256,
            hashlib.sha256(normalized).hexdigest(),
        )

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
            self.assertEqual("batch", config["execution"]["strategy"])

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

    def test_intake_packet_promotes_inspector_not_local_profiles_or_fixtures(self) -> None:
        contract = (ASSET / "adapter.yaml").read_text(encoding="utf-8")
        self.assertIn("reviewed_helpers:\n  - daily_changes_self_inspection.py", contract)
        self.assertIn("optional_files:\n  - README.md", contract)
        self.assertNotIn("run_profiles/", contract)
        self.assertNotIn("fixtures/", contract)
        self.assertIn("allow_raw_fixtures: false", contract)

    def test_exact_output_inspection_passes_and_binds_hashes(self) -> None:
        payload = {
            "trace": {"latest_extraction_date": "2026-07-27"},
            "summary": {"added_count": 1},
            "changes": [{"change_type": "added", "record_key": "reg:1"}],
        }
        report, encoded = self._inspect(payload)

        self.assertEqual("passed", report.status)
        self.assertEqual("sfda_getdrugs_daily_changes.changes.v1", report.payload_schema_version)
        self.assertEqual("sfda_getdrugs_daily_changes.v1", report.node_schema_version)
        self.assertEqual(SCHEMA_SHA256, report.node_schema_sha256)
        self.assertEqual(hashlib.sha256(encoded).hexdigest(), report.payload_sha256)
        self.assertEqual(1, report.records_inspected)
        self.assertEqual(0, report.records_failed)
        self.assertEqual(0, report.error_count)

    def test_invalid_change_fails_without_exposing_value(self) -> None:
        report, _ = self._inspect(
            {
                "trace": {},
                "summary": {},
                "changes": [{"change_type": "updated", "record_key": "reg:1"}],
            }
        )

        self.assertEqual("failed", report.status)
        self.assertEqual(1, report.records_inspected)
        self.assertEqual(1, report.records_failed)
        self.assertGreater(report.error_count, 0)
        encoded_report = json.dumps(report.to_dict(), sort_keys=True).lower()
        self.assertNotIn("updated", encoded_report)
        self.assertIn("allowed value", encoded_report)

    def test_external_schema_reference_is_rejected(self) -> None:
        contract = json.loads(json.dumps(SCHEMA_CONTRACT))
        contract["schema"]["results"]["contract"] = {
            "$ref": "https://example.invalid/change-schema.json"
        }

        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory) / "payload.json"
            staged.write_text(
                json.dumps({"trace": {}, "summary": {}, "changes": []}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                INSPECTOR.SchemaContractError,
                "external_schema_ref_rejected",
            ):
                INSPECTOR.inspect_staged_payload(staged, contract)

    def test_cutover_disables_materialized_binding_before_file_activation(self) -> None:
        readme = (ASSET / "README.md").read_text(encoding="utf-8")
        disable = readme.index("Disable the old materialized binding")
        activate = readme.index("Activate the reviewed file binding")

        self.assertLess(disable, activate)
        self.assertIn(
            "must never be runtime-eligible for the same SFDA role at the same time",
            readme,
        )

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

    def _inspect(self, payload: dict[str, object]):
        encoded = (
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory) / "payload.json"
            staged.write_bytes(encoded)
            report = INSPECTOR.inspect_staged_payload(staged, SCHEMA_CONTRACT)
        return report, encoded


if __name__ == "__main__":
    unittest.main()
