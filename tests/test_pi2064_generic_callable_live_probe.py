"""Provider-free intake contract checks for the two generic PI-2064 proof assets."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "adapters/nusaibah"


def _load(slug: str) -> dict:
    return json.loads((ROOT / slug / f"{slug}.asset.json").read_text(encoding="utf-8"))


def _adapter(slug: str):
    """Load only the candidate's code with a harmless Adapter base class."""
    source = (ROOT / slug / f"{slug}_adapter.py").read_text(encoding="utf-8")
    source = source.replace("from adapters.base import Adapter", "class Adapter:\n    pass")
    scope: dict = {"__name__": f"pi2064_{slug}"}
    exec(compile(source, slug, "exec"), scope)
    return next(v() for v in scope.values() if isinstance(v, type) and v.__name__.endswith("Adapter") and v.__name__ != "Adapter")


class ChildInputs(dict):
    def __init__(self, rows=None, outcome="completed"):
        super().__init__(records={"records": [] if rows is None else rows}, variables={})
        self.calls = []
        self.outcome = outcome

    def invoke_agent(self, role, *, input, on_error):
        self.calls.append((role, input, on_error))
        return {"status": self.outcome}


class ParentInputs(dict):
    def __init__(self, result=None, provenance=None):
        super().__init__(variables={})
        self.calls = []
        self.result = result or {
            "schema_version": "callable_probe_result.v1",
            "record_count": 2, "agent_completed": True, "preview_only": True,
        }
        self.provenance = provenance or {
            "callable_asset": True,
            "asset_key": "nusaibah.callable_probe_child",
            "asset_version": "0.1.0",
        }

    def invoke_asset(self, role, *, variables, on_error):
        self.calls.append((role, variables, on_error))
        return {"status": "success", "provenance": self.provenance, "result": self.result}


class ProbeIntakeTests(unittest.TestCase):
    def test_manifest_contract_and_exact_parent_dependency(self):
        child, parent = _load("callable_probe_child"), _load("callable_probe_parent")
        c = child["versions"]["0.1.0"]
        p = parent["versions"]["0.1.0"]
        self.assertTrue(c["callable"]["enabled"])
        self.assertEqual(c["inputs"]["records"]["source"], "binding")
        self.assertTrue(c["inputs"]["records"]["required"])
        self.assertEqual(set(c["agents"]), {"summarizer"})
        self.assertEqual(set(p["callable_assets"]), {"probe"})
        self.assertEqual(p["callable_assets"]["probe"]["asset_key"], child["key"])
        self.assertEqual(p["callable_assets"]["probe"]["asset_version"], "0.1.0")
        self.assertEqual(child["execution"]["allowed_substrates"], ["local_worker", "ecs"])

    def test_child_calls_one_agent_and_never_outputs_source_rows(self):
        inputs = ChildInputs([{"id": "one"}, {"id": "two"}])
        outputs = _adapter("callable_probe_child").invoke(inputs, {})["outputs"]
        self.assertEqual(outputs["probe_result"]["record_count"], 2)
        self.assertEqual(len(inputs.calls), 1)
        self.assertEqual(inputs.calls[0][0], "summarizer")
        self.assertEqual(inputs.calls[0][1]["record_count"], 2)
        self.assertNotIn("one", json.dumps(outputs))

    def test_child_missing_governed_input_fails_closed(self):
        inputs = ChildInputs()
        del inputs["records"]
        with self.assertRaisesRegex(ValueError, "governed_records_missing"):
            _adapter("callable_probe_child").invoke(inputs, {})
        self.assertEqual(inputs.calls, [])

    def test_child_incomplete_agent_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "agent_incomplete"):
            _adapter("callable_probe_child").invoke(ChildInputs(outcome="failed"), {})

    def test_parent_calls_exact_child_once(self):
        inputs = ParentInputs()
        result = _adapter("callable_probe_parent").invoke(inputs, {})
        self.assertEqual(len(inputs.calls), 1)
        self.assertEqual(inputs.calls[0][0], "probe")
        self.assertEqual(result["outputs"]["probe_summary"]["record_count"], 2)

    def test_parent_rejects_wrong_child_identity(self):
        inputs = ParentInputs(provenance={"callable_asset": True, "asset_key": "other", "asset_version": "0.1.0"})
        with self.assertRaisesRegex(RuntimeError, "identity_invalid"):
            _adapter("callable_probe_parent").invoke(inputs, {})


if __name__ == "__main__":
    unittest.main()
