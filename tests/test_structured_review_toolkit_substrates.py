from pathlib import Path
import json
import unittest

MANIFEST = Path(__file__).resolve().parents[1] / "adapters/nusaibah/structured_review_toolkit/structured_review_toolkit.asset.json"

class ToolkitSubstrateContractTest(unittest.TestCase):
    def test_only_qualified_exact_versions_allow_ecs(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(["local_worker"], manifest["execution"]["allowed_substrates"])
        self.assertNotIn("execution", manifest["versions"]["0.1.0"])
        for version in ("0.1.1", "0.1.2"):
            with self.subTest(version=version):
                execution = manifest["versions"][version]["execution"]
                self.assertEqual(["local_worker", "ecs"], execution["allowed_substrates"])
                self.assertEqual("local_worker", execution["default_substrate"])
                self.assertEqual(60, execution["timeout_seconds"])

    def test_version_identity_and_default_are_preserved(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual({"0.1.0", "0.1.1", "0.1.2"}, set(manifest["versions"]))
        self.assertEqual("0.1.2", manifest["default"])
        for version in manifest["versions"].values():
            self.assertEqual("active", version["state"])
            self.assertTrue(version["callable"]["enabled"])
