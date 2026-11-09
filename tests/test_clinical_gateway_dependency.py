"""Public F3 approval guard; does not pretend to execute private Assets validators."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_clinical_gateway_dependency as contract


class GatewayDependencyTests(unittest.TestCase):
    def setUp(self):
        self.descriptor = json.loads(contract.DESCRIPTOR.read_text(encoding="utf-8"))
        self.version = self.descriptor["versions"][contract.ASSET_VERSION]

    def reject(self, value, code):
        with self.assertRaises(contract.DependencyContractError) as caught:
            contract.validate_descriptor(value)
        self.assertEqual(code, str(caught.exception))

    def test_exact_descriptor_and_sealed_package_agree(self):
        result = contract.verify_public_contract()
        self.assertEqual("f3_contract_verified", result["status"])
        self.assertFalse(result["portable_validator_executed"])
        self.assertFalse(result["assets_descriptor_normalizer_executed"])
        self.assertFalse(result["runtime_admitted"])

    def test_fragment_is_not_a_descriptor(self):
        self.reject({"skills": [contract.IDENTITY]}, "draft_descriptor_fields_changed")

    def test_wrong_skill_versions_fail_even_with_same_package_bytes(self):
        for version in ("0.9.0", "1.0.1", "2.0.0", "latest", None):
            with self.subTest(version=version):
                self.version["skills"][0]["version"] = version
                self.reject(self.descriptor, "approved_skill_dependency_required")

    def test_changed_digest_fails(self):
        self.version["skills"][0]["digest"] = "sha256:" + "0" * 64
        self.reject(self.descriptor, "approved_skill_dependency_required")

    def test_wrong_namespace_and_methodology_substitution_fail(self):
        for reference in ("other.clinical-intelligence-gateway-usage", "nusaibah.clinical-failure-methodology"):
            self.version["skills"][0]["skill_ref"] = reference
            self.reject(self.descriptor, "approved_skill_dependency_required")

    def test_missing_duplicate_and_additional_skills_fail(self):
        for skills in ([], None, [contract.IDENTITY, contract.IDENTITY],
                       [contract.IDENTITY, {"skill_ref": "nusaibah.undeclared", "version": "1.0.0", "digest": contract.IDENTITY["digest"]}]):
            with self.subTest(skills=skills):
                self.version["skills"] = skills
                self.reject(self.descriptor, "approved_skill_dependency_required")

    def test_dependency_fields_cannot_grant_fallbacks_or_readers(self):
        self.version["skills"][0]["fallback"] = "latest"
        self.reject(self.descriptor, "approved_skill_dependency_required")

    def test_other_skill_resolution_lanes_are_not_substitutes(self):
        for lane in ("published_skills", "runtime_skills"):
            descriptor = copy.deepcopy(self.descriptor)
            version = descriptor["versions"][contract.ASSET_VERSION]
            version[lane] = version.pop("skills")
            self.reject(descriptor, "draft_version_fields_changed")

    def test_launch_default_active_state_and_resume_are_rejected(self):
        descriptor = copy.deepcopy(self.descriptor)
        descriptor["default"] = contract.ASSET_VERSION
        self.reject(descriptor, "draft_descriptor_fields_changed")
        self.version["state"] = "active"
        self.reject(self.descriptor, "gateway_must_remain_draft")
        self.version["state"] = "draft"
        self.version["allow_resume"] = True
        self.reject(self.descriptor, "gateway_must_remain_draft")

    def test_gateway_identity_and_version_are_explicit(self):
        descriptor = copy.deepcopy(self.descriptor)
        descriptor["key"] = "nusaibah.other_gateway"
        self.reject(descriptor, "gateway_identity_changed")
        self.descriptor["versions"] = {"0.1.1": self.version}
        self.reject(self.descriptor, "gateway_version_changed")


if __name__ == "__main__":
    unittest.main()
