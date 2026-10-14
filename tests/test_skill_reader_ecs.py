from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "adapters/nusaibah/skill_reader"


class SkillReaderEcsVersionTest(unittest.TestCase):
    def test_ecs_successor_preserves_exact_read_only_contract(self) -> None:
        manifest = json.loads((ROOT / "skill_reader.asset.json").read_text(encoding="utf-8"))
        self.assertEqual("0.1.1", manifest["default"])
        self.assertEqual(["local_worker"], manifest["execution"]["allowed_substrates"])
        version = manifest["versions"]["0.1.1"]
        self.assertEqual(["local_worker", "ecs"], version["execution"]["allowed_substrates"])
        self.assertEqual("ecs", version["execution"]["default_substrate"])
        self.assertEqual("read_only", version["runtime_skills"]["guidance"]["mutation"])
        self.assertEqual("skill_result", version["callable"]["result_key"])
        self.assertEqual(["nusaibah.reader-guidance"], [item["skill_ref"] for item in version["skills"]])

    def test_public_template_is_fixed_only_pending_dynamic_replay_authorization(self) -> None:
        publication = json.loads((ROOT / "capabilities.v0.1.1.json").read_text(encoding="utf-8"))
        self.assertEqual("templates_only", publication["publication_status"])
        self.assertEqual("0.1.1", publication["asset_version"])
        schema = publication["capabilities"]["skill.read"]["remote_mcp"]["input_schema"]
        self.assertEqual(["fixed"], schema["properties"]["variables"]["properties"]["source_kind"]["enum"])
        module = (ROOT / "skill_reader_v0_1_1_adapter.py").read_text(encoding="utf-8")
        self.assertIn('version: ClassVar[str] = "0.1.1"', module)


if __name__ == "__main__":
    unittest.main()
