from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from company_context_contract_v0_1_15 import CompanyContextContractError, RUNTIME_SKILL_ROLES, resolve_company_context
import company_context_contract_v0_1_14 as retained_014
from test_orchestration_preview import FakeInputs, _fake_citations, adapter_module


class OpaqueSkillSlot:
    def __getitem__(self, key):
        raise AssertionError("The handoff validator must not read runtime Skill slots")

    def get(self, *args):
        raise AssertionError("The handoff validator must not read runtime Skill slots")


class RuntimeSkillHandoffTests(unittest.TestCase):
    def test_server_injected_skill_slots_are_opaque_and_optional(self):
        roles = sorted(RUNTIME_SKILL_ROLES)
        for mask in range(1 << len(roles)):
            with self.subTest(mask=mask):
                inputs = FakeInputs()
                for index, role in enumerate(roles):
                    if mask & (1 << index):
                        inputs[role] = OpaqueSkillSlot()
                rows = resolve_company_context(inputs, company_ids=(13, 59))
                self.assertEqual([r["company_id"] for r in rows], [59, 13])
                self.assertEqual(inputs.agent_calls, [])
                self.assertEqual(inputs.dynamic_skill_calls, [])

    def test_unknown_roles_are_rejected_before_any_helper(self):
        for role in ("companies", "company_memory_other", "runtime_skills", "company_context_override"):
            inputs = FakeInputs()
            for known in RUNTIME_SKILL_ROLES:
                inputs[known] = OpaqueSkillSlot()
            inputs[role] = {}
            with patch.object(inputs, "skill", wraps=inputs.skill) as fixed:
                with self.assertRaises(CompanyContextContractError) as error:
                    adapter_module.NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(inputs, {})
            self.assertEqual(error.exception.proof_failure_detail["rule"], "input_roles")
            fixed.assert_not_called()
            self.assertEqual(inputs.agent_calls, [])
            self.assertEqual(inputs.dynamic_skill_calls, [])

    def test_missing_caller_roles_are_rejected_despite_skill_slots(self):
        for missing in ("company_context", "variables"):
            inputs = FakeInputs()
            del inputs[missing]
            for role in RUNTIME_SKILL_ROLES:
                inputs[role] = OpaqueSkillSlot()
            with self.assertRaises(CompanyContextContractError) as error:
                resolve_company_context(inputs, company_ids=(13, 59))
            self.assertEqual(error.exception.proof_failure_detail["rule"], "input_roles")

    def test_full_preview_with_runtime_slots_preserves_calls_and_write_guard(self):
        inputs = FakeInputs()
        marker = "RUNTIME-SKILL-SLOT-MUST-NOT-ENTER-AGENT-CONTEXT"
        for role in RUNTIME_SKILL_ROLES:
            inputs[role] = {"mode": "native_file", "status": "pending_runtime_hydration", "marker": marker}
        with patch.object(adapter_module, "_agent_citations", side_effect=_fake_citations):
            result = adapter_module.NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(inputs, {})
        self.assertEqual(len(inputs.agent_calls), 24)
        self.assertEqual({role for role, _ in inputs.dynamic_skill_calls}, {"company_memory", "company_methodology"})
        self.assertEqual(result["metrics"]["memory_mutations_made"], 0)
        self.assertNotIn(marker, json.dumps(inputs.agent_inputs))
        self.assertNotIn("companies", inputs)

    def test_published_014_validator_is_preserved_and_reproduces_the_boundary(self):
        inputs = FakeInputs()
        for role in RUNTIME_SKILL_ROLES:
            inputs[role] = OpaqueSkillSlot()
        with self.assertRaises(retained_014.CompanyContextContractError) as error:
            retained_014.resolve_company_context(inputs, company_ids=(13, 59))
        self.assertEqual(error.exception.proof_failure_detail["rule"], "input_roles")


if __name__ == "__main__":
    unittest.main()
