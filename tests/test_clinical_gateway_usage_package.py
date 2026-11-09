"""F1/F2 offline packaging proof against the pinned current Assets validator."""
import importlib.util
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("usage_package", ROOT / "tools/package_clinical_gateway_usage_skill.py")
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)


class ClinicalGatewayUsagePackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = os.environ.get("CLINICAL_USAGE_RUNTIME_SOURCE")
        if not source:
            raise RuntimeError("Set CLINICAL_USAGE_RUNTIME_SOURCE to the pinned Assets source checkout")
        cls.validator = PACKAGE.load_validator(Path(source))

    def copy_package(self, base):
        root = Path(base) / PACKAGE.NAME
        root.mkdir()
        (root / "SKILL.md").write_bytes((PACKAGE.PACKAGE_ROOT / "SKILL.md").read_bytes())
        return root

    def assert_package_error(self, root, code, name=None):
        with self.assertRaises(self.validator.SkillPackageError) as caught:
            self.validator.validate_skill_package(root, expected_name=name or PACKAGE.NAME)
        self.assertEqual(code, caught.exception.code)

    def test_current_validator_and_exact_recorded_package_are_reproducible(self):
        proof, archive = PACKAGE.inspect_package(self.validator)
        self.assertEqual(proof, json.loads(PACKAGE.PROOF.read_text(encoding="utf-8")))
        self.assertEqual(archive, PACKAGE.ARCHIVE.read_bytes())
        self.assertEqual(proof["identity"]["digest"], proof["archive"]["roundtrip_canonical_digest"])
        self.assertEqual(PACKAGE.VERSION, proof["identity"]["version"])

    def test_all_seven_approved_sections_are_preserved_as_exact_utf8(self):
        self.assertEqual(PACKAGE.approved_markdown(), (PACKAGE.PACKAGE_ROOT / "SKILL.md").read_bytes())
        proof = json.loads(PACKAGE.PROOF.read_text(encoding="utf-8"))
        self.assertEqual(list(PACKAGE.SECTIONS), [row["section_id"] for row in proof["approval"]["sections"]])

    def test_changed_document_bytes_change_canonical_identity(self):
        original = self.validator.compute_skill_package_digest(PACKAGE.PACKAGE_ROOT)
        with tempfile.TemporaryDirectory() as temp:
            root = self.copy_package(temp)
            with (root / "SKILL.md").open("ab") as handle:
                handle.write(b"\n")
            self.assertNotEqual(original, self.validator.compute_skill_package_digest(root))

    def test_integrity_only_check_rejects_identity_and_release_claim_drift(self):
        result = PACKAGE.verify_recorded_integrity()
        self.assertFalse(result["portable_validator_executed"])
        for mutation, code in (("digest", "recorded_canonical_identity_changed"), ("published", "unauthorized_release_claim")):
            proof = json.loads(PACKAGE.PROOF.read_text(encoding="utf-8"))
            if mutation == "digest":
                proof["identity"]["digest"] = "sha256:" + "0" * 64
            else:
                proof["published"] = True
            with tempfile.TemporaryDirectory() as temp:
                changed = Path(temp) / "proof.json"
                changed.write_text(json.dumps(proof), encoding="utf-8")
                with patch.object(PACKAGE, "PROOF", changed), self.assertRaises(PACKAGE.PackageProofError) as caught:
                    PACKAGE.verify_recorded_integrity()
                self.assertEqual(code, str(caught.exception))

    def test_wrong_directory_and_frontmatter_identity_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.copy_package(temp)
            self.assert_package_error(root, "skill_name_directory_mismatch", name="other-skill")
            text = (root / "SKILL.md").read_text(encoding="utf-8").replace("name: " + PACKAGE.NAME, "name: other-skill")
            (root / "SKILL.md").write_text(text, encoding="utf-8")
            self.assert_package_error(root, "skill_name_directory_mismatch")

    def test_portable_frontmatter_rejects_unsupported_runtime_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.copy_package(temp)
            raw = (root / "SKILL.md").read_bytes().replace(b"---\nname:", b"---\nversion: 1.0.0\nname:", 1)
            (root / "SKILL.md").write_bytes(raw)
            self.assert_package_error(root, "skill_frontmatter_unknown_field")

    def test_non_utf8_and_nonportable_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.copy_package(temp)
            (root / "SKILL.md").write_bytes(b"\xff")
            self.assert_package_error(root, "skill_package_text_invalid")
        with tempfile.TemporaryDirectory() as temp:
            root = self.copy_package(temp)
            (root / ".env").write_text("SYNTHETIC", encoding="utf-8")
            self.assert_package_error(root, "skill_package_layout_invalid")
        with tempfile.TemporaryDirectory() as temp:
            root = self.copy_package(temp)
            (root / "scripts").mkdir()
            (root / "scripts/run.py").write_text("pass", encoding="utf-8")
            self.assert_package_error(root, "skill_scripts_unsupported")

    def test_per_file_limit_boundary_and_excess(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.copy_package(temp)
            (root / "references").mkdir()
            resource = root / "references/bounded.txt"
            resource.write_bytes(b"x" * self.validator.MAX_SKILL_FILE_BYTES)
            self.validator.validate_skill_package(root, expected_name=PACKAGE.NAME)
            with resource.open("ab") as handle:
                handle.write(b"x")
            self.assert_package_error(root, "skill_package_too_large")

    def test_package_byte_limit_boundary_and_excess(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.copy_package(temp)
            (root / "references").mkdir()
            for index in range(3):
                (root / f"references/{index}.txt").write_bytes(b"x" * self.validator.MAX_SKILL_FILE_BYTES)
            remaining = self.validator.MAX_SKILL_PACKAGE_BYTES - 3 * self.validator.MAX_SKILL_FILE_BYTES - (root / "SKILL.md").stat().st_size
            final = root / "references/3.txt"
            final.write_bytes(b"x" * remaining)
            checked = self.validator.validate_skill_package(root, expected_name=PACKAGE.NAME)
            self.assertEqual(self.validator.MAX_SKILL_PACKAGE_BYTES, checked.total_bytes)
            with final.open("ab") as handle:
                handle.write(b"x")
            self.assert_package_error(root, "skill_package_too_large")

    def test_file_count_limit_boundary_and_excess(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.copy_package(temp)
            (root / "references").mkdir()
            for index in range(self.validator.MAX_SKILL_FILES - 1):
                (root / f"references/{index:03}.txt").write_bytes(b"x")
            checked = self.validator.validate_skill_package(root, expected_name=PACKAGE.NAME)
            self.assertEqual(self.validator.MAX_SKILL_FILES, checked.file_count)
            (root / "references/extra.txt").write_bytes(b"x")
            self.assert_package_error(root, "skill_package_too_large")


if __name__ == "__main__":
    unittest.main()
