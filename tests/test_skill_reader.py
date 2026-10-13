from __future__ import annotations

import hashlib
import importlib.util
import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

try:
    from adapters.base import Adapter
except ImportError:
    base = types.ModuleType("adapters.base")
    base.Adapter = type("Adapter", (), {})
    package = types.ModuleType("adapters")
    package.__path__ = []
    sys.modules.setdefault("adapters", package)
    sys.modules["adapters.base"] = base

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("_skill_reader", ROOT / "adapters/nusaibah/skill_reader/skill_reader_adapter.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class View:
    def __init__(self, text="Use primary evidence.\n", *, dynamic=False, mutable=False, count=1):
        self.text = text
        self.sections = {f"Rule {index}": text for index in range(count)}
        self.dynamic = dynamic
        self.mutable = mutable
        self.digest = "sha256:" + hashlib.sha256(text.encode()).hexdigest()

    def validate(self):
        return SimpleNamespace(status="ready")

    def provenance(self):
        return SimpleNamespace(content_digest=self.digest, package_digest="sha256:" + "a" * 64,
                               skill_ref=None if self.dynamic else "demo.reader-guidance",
                               version=None if self.dynamic else "1.0.0", mutable=self.mutable,
                               snapshot_id="snapshot-1" if self.dynamic else None,
                               observed_at=datetime(2026, 10, 13, tzinfo=timezone.utc))

    def content_digest(self):
        return self.digest

    def snapshot(self):
        return SimpleNamespace(content_digest=self.digest, snapshot_id="snapshot-1")

    def list_sections(self):
        return tuple(self.section(name) for name in self.sections)

    def section(self, name):
        key = name[0] if isinstance(name, list) else name
        return SimpleNamespace(path=SimpleNamespace(parts=(key,)))

    def has_section(self, name):
        return (name[0] if isinstance(name, list) else name) in self.sections

    def section_text(self, name):
        return self.sections[name[0] if isinstance(name, list) else name]

    def resource_exists(self, name):
        return name == "references/policy.md"

    def read_resource(self, name):
        return self.text

    def read(self):
        return self.text


class Inputs(dict):
    def __init__(self, view, **values):
        super().__init__(values)
        self.view = view
        self.calls = []

    def skill(self, selector):
        self.calls.append(("fixed", selector))
        return self.view

    def dynamic_skill(self, role, *, variables):
        self.calls.append(("dynamic", role, variables))
        return self.view


class SkillReaderTest(unittest.TestCase):
    def query(self, **changes):
        return {"source_kind": "fixed", "selector": "demo.reader-guidance", "read": "section", "section": "Rule 0", **changes}

    def test_fixed_section_returns_exact_text_and_visible_integrity(self):
        inputs = Inputs(View())
        result = reader.read_skill(inputs, self.query())
        self.assertEqual("Use primary evidence.\n", result["text"])
        self.assertEqual(inputs.view.digest, result["identity"]["content_digest"])
        self.assertEqual("1.0.0", result["identity"]["version"])
        self.assertEqual("execution_snapshot", result["resolution"])
        self.assertEqual([( "fixed", "demo.reader-guidance")], inputs.calls)

    def test_project_and_document_selectors_use_the_same_dynamic_contract(self):
        for selector_name in ("project_id", "document_id"):
            inputs = Inputs(View(dynamic=True))
            result = reader.read_skill(inputs, self.query(source_kind="dynamic", selector="guidance", selectors={selector_name: "demo-7"}))
            self.assertEqual(("dynamic", "guidance", {selector_name: "demo-7"}), inputs.calls[0])
            self.assertEqual("snapshot-1", result["identity"]["snapshot_id"])
            self.assertIsNone(result["identity"]["version"])

    def test_adapter_uses_the_same_projection(self):
        inputs = Inputs(View(), variables=self.query())
        result = reader.SkillReaderAdapter().invoke(inputs, {"unused": "business context"})
        self.assertEqual("ready", result["outputs"]["skill_result"]["status"])
        self.assertEqual(0, result["metrics"]["mutation_calls"])

    def test_resource_components_preserve_existing_safe_variable_contract(self):
        query = self.query(read="resource", resource=["references", "policy.md"])
        query.pop("section")
        result = reader.read_skill(Inputs(View()), query)
        self.assertEqual("references/policy.md", result["resource"])
        for parts in (["..", "policy.md"], ["references/policy.md"], ["references", ".private"]):
            with self.assertRaises(reader.SkillReaderError):
                reader.read_skill(Inputs(View()), {**query, "resource": parts})

    def test_inventory_is_bounded_with_truthful_completeness(self):
        result = reader.read_skill(Inputs(View(count=21)), {"source_kind": "fixed", "selector": "demo.guidance"})
        self.assertEqual(20, len(result["sections"]))
        self.assertTrue(result["has_more"])
        self.assertIsNone(result["text"])

    def test_missing_sections_do_not_become_empty_success(self):
        with self.assertRaisesRegex(reader.SkillReaderError, "skill_reader_section_unavailable"):
            reader.read_skill(Inputs(View()), self.query(section="Missing"))

    def test_digest_change_and_mutable_sources_fail_closed(self):
        with self.assertRaisesRegex(reader.SkillReaderError, "skill_reader_snapshot_changed"):
            reader.read_skill(Inputs(View()), self.query(expected_digest="sha256:" + "b" * 64))
        with self.assertRaisesRegex(reader.SkillReaderError, "skill_reader_mutable_source_rejected"):
            reader.read_skill(Inputs(View(dynamic=True, mutable=True)), self.query(source_kind="dynamic"))

    def test_utf8_budget_is_bytes_and_never_silent_truncation(self):
        with self.assertRaisesRegex(reader.SkillReaderError, "skill_reader_text_limit_exceeded"):
            reader.read_skill(Inputs(View("é" * 4097)), self.query())
        result = reader.read_skill(Inputs(View("é" * 4096)), self.query())
        self.assertEqual(8192, result["byte_count"])

    def test_unsafe_resource_paths_fail_before_resolution(self):
        for path in ("../policy.md", "/policy.md", "references/../policy.md", "C:\\policy.md", ".env", "references//policy.md"):
            inputs = Inputs(View())
            with self.assertRaises(reader.SkillReaderError):
                reader.read_skill(inputs, {"source_kind": "fixed", "selector": "demo.guidance", "read": "resource", "resource": path})
            self.assertEqual([], inputs.calls)

    def test_admitted_resources_are_exact_reads(self):
        result = reader.read_skill(Inputs(View()), {"source_kind": "fixed", "selector": "demo.guidance", "read": "resource", "resource": "references/policy.md"})
        self.assertEqual("Use primary evidence.\n", result["text"])

    def test_unknown_controls_and_malformed_selectors_are_rejected(self):
        for change in ({"client_id": "other"}, {"selector": "https://private.example"}, {"selectors": {"project_id": {"nested": "value"}}}):
            with self.assertRaises(reader.SkillReaderError):
                reader.read_skill(Inputs(View()), self.query(**change))

    def test_runtime_failure_text_does_not_escape(self):
        inputs = Inputs(View())
        def fail(selector):
            raise RuntimeError("private path and unapproved source contents")
        inputs.skill = fail
        with self.assertRaisesRegex(reader.SkillReaderError, "^skill_reader_source_unavailable$"):
            reader.read_skill(inputs, self.query())


if __name__ == "__main__":
    unittest.main()
