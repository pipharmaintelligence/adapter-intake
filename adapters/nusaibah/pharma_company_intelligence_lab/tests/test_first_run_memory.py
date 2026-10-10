"""First-use preview must not manufacture memory or broaden write authority."""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import nusaibah_pharma_company_intelligence_lab_adapter as adapter
from devtools.dynamic_skill_runtime import DynamicSkillRuntimeError
from test_orchestration_preview import FakeInputs, FirstRunMethodologyInputs, _fake_citations


class FirstMemoryInputs(FirstRunMethodologyInputs):
    def __init__(self, *, missing_ids=(14,), error="dynamic_skill_not_initialized"):
        super().__init__()
        self.missing_ids = missing_ids
        self.error = error
        self["variables"].update(company_ids=[14], retain_review_packet=True)
        self.set_company_records([{"id": 14, "company": "Example Company"}])

    def dynamic_skill(self, role, *, variables=None):
        company_id = int(variables["company_id"])
        if role == "company_memory" and company_id in self.missing_ids:
            self.dynamic_skill_calls.append((role, company_id))
            raise DynamicSkillRuntimeError(self.error)
        return super().dynamic_skill(role, variables=variables)


class FirstRunMemoryTests(unittest.TestCase):
    def run_preview(self, inputs):
        with patch.object(adapter, "_agent_citations", side_effect=_fake_citations):
            return adapter.NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(inputs, {})["outputs"]["intelligence_dossier"]

    def test_first_run_two_passes_retains_candidate_without_inventing_existing_memory(self):
        inputs = FirstMemoryInputs()
        inputs["variables"]["portfolio_review_passes"] = 2
        dossier = self.run_preview(inputs)
        row = dossier["company_results"][0]
        packet = dossier["review_packet"]
        company = packet["companies"][0]
        proposal = company["memory_proposal"]
        self.assertFalse(row["memory_initialized"])
        self.assertTrue(row["memory_initialization_required"])
        self.assertFalse(row["memory_mutation_eligible"])
        self.assertEqual(row["portfolio_review_pass_count"], 2)
        self.assertEqual(row["portfolio_reflection_pass_count"], 1)
        self.assertIsNone(row["memory_before_digest"])
        self.assertIsNone(row["memory_after_digest"])
        self.assertFalse(row["memory_readback_verified"])
        self.assertEqual(row["benchmark_before_basis"], "deterministic_absent_memory")
        self.assertEqual(row["benchmark_before_covered_count"], 0)
        self.assertEqual(row["benchmark_before_partially_covered_count"], 0)
        self.assertIsNone(proposal["baseline_content_digest"])
        self.assertIsNone(proposal["baseline_section_text"])
        self.assertTrue(proposal["replacement_text"])
        self.assertFalse(proposal["mutation_eligible"])
        self.assertFalse(proposal["initialized"])
        self.assertTrue(proposal["initialization_required"])
        self.assertEqual(company["benchmark"]["before_basis"], "deterministic_absent_memory")
        self.assertTrue(all(item["coverage"] == "not_covered" for item in company["benchmark"]["before"]["results"]))
        self.assertFalse(packet["apply_authority"])
        self.assertEqual(len(inputs.agent_calls), 12)  # 13 minus the absent-memory baseline call.
        self.assertEqual([data["memory_stage"] for role, _, data in inputs.agent_inputs if role == "memory_benchmark_reviewer"], ["proposed"])
        for _, _, data in inputs.agent_inputs:
            if "existing_company_memory" in data:
                self.assertEqual(data["existing_company_memory"], "")
        self.assertFalse(any(role.endswith("_update") for role, _ in inputs.dynamic_skill_calls))
        encoded = json.loads(json.dumps(packet))
        digest = encoded.pop("packet_sha256")
        self.assertEqual(digest, "sha256:" + sha256(adapter.canonical_bytes(encoded)).hexdigest())

    def test_only_explicit_missing_package_is_optional(self):
        for code in ("dynamic_skill_delivery_failed", "dynamic_skill_forbidden", "dynamic_skill_integrity_invalid"):
            with self.subTest(code=code):
                inputs = FirstMemoryInputs(error=code)
                with self.assertRaises(DynamicSkillRuntimeError) as caught:
                    self.run_preview(inputs)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(inputs.agent_calls, [])
                self.assertFalse(any(role.endswith("_update") for role, _ in inputs.dynamic_skill_calls))

    def test_apply_still_requires_memory_before_any_provider_or_mutable_call(self):
        inputs = FirstMemoryInputs()
        inputs["variables"]["memory_mode"] = "apply"
        with self.assertRaises(DynamicSkillRuntimeError) as caught:
            self.run_preview(inputs)
        self.assertEqual(caught.exception.code, "dynamic_skill_not_initialized")
        self.assertEqual(inputs.agent_calls, [])
        self.assertFalse(any(role.endswith("_update") for role, _ in inputs.dynamic_skill_calls))

    def test_empty_existing_package_is_not_treated_as_absent(self):
        class Empty(FakeInputs):
            def dynamic_skill(self, role, *, variables=None):
                handle = super().dynamic_skill(role, variables=variables)
                if role == "company_memory":
                    handle.text = ""
                return handle
        inputs = Empty()
        with self.assertRaisesRegex(RuntimeError, "Existing company memory is empty"):
            self.run_preview(inputs)
        self.assertEqual(inputs.agent_calls, [])

    def test_existing_package_safety_checks_still_fail_before_agent_calls(self):
        for failure, message in (("mutable", "must resolve read-only"),
                                 ("section", "missing the approved update section"),
                                 ("oversized", "exceeds the adapter context bound")):
            with self.subTest(failure=failure):
                class Invalid(FakeInputs):
                    def dynamic_skill(self, role, *, variables=None):
                        handle = super().dynamic_skill(role, variables=variables)
                        if role == "company_memory":
                            if failure == "mutable":
                                from types import SimpleNamespace
                                handle.provenance = lambda: SimpleNamespace(mutable=True)
                            elif failure == "section":
                                handle.has_section = lambda _: False
                            else:
                                handle.text = "x" * (adapter.MAX_MEMORY_CONTEXT_CHARS + 1)
                        return handle
                inputs = Invalid()
                with self.assertRaisesRegex(RuntimeError, message):
                    self.run_preview(inputs)
                self.assertEqual(inputs.agent_calls, [])

    def test_absent_second_company_apply_blocks_entire_preparation_before_paid_work(self):
        class MissingSecond(FakeInputs):
            def dynamic_skill(self, role, *, variables=None):
                if role == "company_memory" and int(variables["company_id"]) == 59:
                    raise DynamicSkillRuntimeError("dynamic_skill_not_initialized")
                return super().dynamic_skill(role, variables=variables)
        inputs = MissingSecond()
        inputs["variables"]["memory_mode"] = "apply"
        with self.assertRaises(DynamicSkillRuntimeError):
            self.run_preview(inputs)
        self.assertEqual(inputs.agent_calls, [])
        self.assertFalse(any(role.endswith("_update") for role, _ in inputs.dynamic_skill_calls))

    def test_mixed_preview_keeps_existing_memory_behavior_and_company_isolation(self):
        inputs = FirstMemoryInputs()
        inputs["variables"]["company_ids"] = [13, 14]
        inputs.set_company_records([{"id": 14, "company": "Example Company"}, {"id": 13, "company": "Tabuk Pharmaceuticals"}])
        dossier = self.run_preview(inputs)
        existing, first = dossier["company_results"]
        self.assertEqual([existing["company_id"], first["company_id"]], [13, 14])
        self.assertTrue(existing["memory_initialized"])
        self.assertTrue(existing["memory_mutation_eligible"])
        self.assertFalse(existing["memory_initialization_required"])
        self.assertEqual(existing["benchmark_before_basis"], "existing_memory_agent_review")
        self.assertFalse(first["memory_mutation_eligible"])
        self.assertEqual([len([c for c in inputs.agent_calls if c[1] == company]) for company in (13, 14)], [12, 11])
        self.assertFalse(any(role.endswith("_update") for role, _ in inputs.dynamic_skill_calls))


if __name__ == "__main__":
    unittest.main()
