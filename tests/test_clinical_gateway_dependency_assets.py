"""Local official validation. Set explicit Assets source and PHP binary; no service access."""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_clinical_gateway_dependency as contract


class GatewayAssetsDependencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(os.environ["CLINICAL_USAGE_RUNTIME_SOURCE"])
        cls.php = Path(os.environ["CLINICAL_GATEWAY_PHP_BINARY"])
        cls.validator = contract.package.load_validator(cls.source)

    def setUp(self):
        self.descriptor = json.loads(contract.DESCRIPTOR.read_text(encoding="utf-8"))
        self.version = self.descriptor["versions"][contract.ASSET_VERSION]

    def test_actual_descriptor_normalizes_and_rejects_launch_and_resume(self):
        result = contract.verify_official_contract(self.source, self.php)
        self.assertTrue(result["portable_validator_executed"])
        self.assertTrue(result["assets_descriptor_normalizer_executed"])
        self.assertEqual([contract.IDENTITY], result["descriptor_normalization"]["skills"])

    def test_digest_and_tampered_bytes_are_blocked_by_official_validator(self):
        for mutation in ("digest", "bytes"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                version = copy.deepcopy(self.version)
                contract.stage_package(root, self.descriptor)
                if mutation == "digest":
                    version["skills"][0]["digest"] = "sha256:" + "0" * 64
                else:
                    with (root / "skills" / contract.package.NAME / "SKILL.md").open("ab") as stream:
                        stream.write(b"\n")
                report = self.validator.validate_manifest_skill_dependencies(asset_root=root, version_manifest=version)
                self.assertEqual("blocked", report["status"])
                self.assertEqual("skill_digest_mismatch", report["items"][0]["reason"])

    def test_missing_package_cannot_be_fetched_or_silently_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            report = self.validator.validate_manifest_skill_dependencies(asset_root=Path(directory), version_manifest=self.version)
            self.assertEqual("blocked", report["status"])
            self.assertEqual(0, report["validated_count"])

    def test_scoped_guard_supplies_approval_pinning_generic_validator_does_not(self):
        self.version["skills"][0]["version"] = "1.0.1"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract.stage_package(root, self.descriptor)
            report = self.validator.validate_manifest_skill_dependencies(asset_root=root, version_manifest=self.version)
            self.assertEqual("ready", report["status"])
        with self.assertRaisesRegex(contract.DependencyContractError, "approved_skill_dependency_required"):
            contract.validate_descriptor(self.descriptor)


if __name__ == "__main__":
    unittest.main()
