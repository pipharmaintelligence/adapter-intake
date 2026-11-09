"""Offline guidance contract boundaries; no host Skill, MCP or runtime call."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("clinical_guidance_check", ROOT / "tools/check_clinical_preparation.py")
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


def example(name):
    return json.loads((CHECK.DESIGN / "examples" / (name + ".json")).read_text(encoding="utf-8"))


class ClinicalGatewayGuidanceTests(unittest.TestCase):
    def rejected(self, kind, data, code=None):
        with self.assertRaises(CHECK.DraftContractError) as caught:
            CHECK.validate(kind, data)
        if code:
            self.assertEqual(code, str(caught.exception))

    def ready_guidance(self):
        response = example("unavailable.guidance-response")
        response.update(status="ready", text="Synthetic approved usage section.", complete=True, reason_codes=[])
        response["utf8_bytes"] = len(response["text"].encode("utf-8"))
        # Synthetic identity for a structural positive test, not a release digest.
        response["usage_skill"]["digest"] = "sha256:" + "f" * 64
        return response

    def test_draft_usage_contract_validates_without_release_claim(self):
        contract = json.loads((CHECK.DESIGN / "gateway-usage.contract.json").read_text(encoding="utf-8"))
        CHECK.validate("gateway-guidance", contract)
        for field in ("content_digest_sealed", "runtime_admitted", "published", "installed"):
            changed = copy.deepcopy(contract)
            changed[field] = True
            self.rejected("gateway-guidance", changed)

    def test_exact_version_and_usage_identity_are_pinned(self):
        for field, value in (("version", "latest"), ("version", "1.0.1"),
                             ("skill_ref", "nusaibah.clinical-failure-methodology"), ("kind", "dynamic")):
            changed = example("unavailable.guidance-response")
            changed["usage_skill"][field] = value
            self.rejected("gateway-response", changed)

    def test_public_guidance_requests_cannot_select_authority_or_other_skills(self):
        for field in ("skill_ref", "version", "digest", "source_kind", "selector", "partition", "resource", "url",
                      "binding_id", "actor_id", "approved", "output_destination"):
            changed = example("read-guidance.request")
            changed[field] = "SYNTH_FORBIDDEN"
            self.rejected("gateway-request", changed)

    def test_only_approved_section_ids_can_be_requested(self):
        for value in ("internal_methodology", "product_memory", "../SKILL.md", "all", "credentials"):
            request = example("read-guidance.request")
            request["section_id"] = value
            self.rejected("gateway-request", request)

    def test_missing_section_and_extra_discovery_arguments_rejected(self):
        request = example("read-guidance.request")
        request.pop("section_id")
        self.rejected("gateway-request", request)
        request = example("describe-capabilities.request")
        request["run_ref"] = "SYNTH_RUN"
        self.rejected("gateway-request", request)

    def test_blocked_guidance_has_no_text_or_invented_digest(self):
        response = example("unavailable.guidance-response")
        CHECK.validate("gateway-response", response)
        self.assertIsNone(response["usage_skill"]["digest"])
        response["text"] = "Unverified fallback text."
        self.rejected("gateway-response", response)

    def test_ready_requires_digest_complete_text_and_matching_bytes(self):
        CHECK.validate("gateway-response", self.ready_guidance())
        for field, value in (("complete", False), ("text", None), ("reason_codes", ["usage_skill_unavailable"])):
            changed = self.ready_guidance()
            changed[field] = value
            self.rejected("gateway-response", changed)
        changed = self.ready_guidance()
        changed["usage_skill"]["digest"] = None
        self.rejected("gateway-response", changed)
        changed = self.ready_guidance()
        changed["utf8_bytes"] += 1
        self.rejected("gateway-response", changed, "guidance_byte_count_mismatch")

    def test_multibyte_text_uses_utf8_budget_without_truncation(self):
        response = self.ready_guidance()
        response["text"] = "界" * 2730
        response["utf8_bytes"] = 8190
        CHECK.validate("gateway-response", response)
        response["text"] += "界"
        # A false smaller byte count must not hide an oversized section.
        self.rejected("gateway-response", response, "guidance_section_byte_limit")

    def test_capability_routes_and_side_effect_hints_match_operations(self):
        response = example("capabilities.guidance-response")
        CHECK.validate("gateway-response", response)
        changed = copy.deepcopy(response)
        changed["capabilities"][2]["read_only"] = True
        self.rejected("gateway-response", changed, "guidance_side_effect_hint_mismatch")
        changed = copy.deepcopy(response)
        changed["capabilities"][2]["operation"] = "get_result"
        self.rejected("gateway-response", changed, "guidance_operation_route_mismatch")

    def test_unsealed_capability_cannot_be_available(self):
        response = example("capabilities.guidance-response")
        response["capabilities"][0].update(availability="available", reason_codes=[])
        self.rejected("gateway-response", response, "available_guidance_unsealed_or_blocked")

    def test_response_cannot_expose_internal_skill_payloads(self):
        for field in ("methodology_text", "dynamic_skill", "raw_assessment", "node_id", "credential", "run_ref"):
            response = example("unavailable.guidance-response")
            response[field] = "SYNTH_FORBIDDEN"
            self.rejected("gateway-response", response)

    def test_entire_guidance_response_budget_is_independent_of_text_budget(self):
        response = example("capabilities.guidance-response")
        bounded_codes = ["SYNTH_" + str(index) + "_" + "x" * 115 for index in range(16)]
        for row in response["capabilities"]:
            row["prerequisite_codes"] = bounded_codes
            row["reason_codes"] = bounded_codes
        self.rejected("gateway-response", response, "guidance_response_byte_limit")

    def test_duplicate_section_identity_rejected(self):
        contract = json.loads((CHECK.DESIGN / "gateway-usage.contract.json").read_text(encoding="utf-8"))
        contract["sections"][1]["section_id"] = "overview"
        self.rejected("gateway-guidance", contract, "duplicate_semantic_identity")


if __name__ == "__main__":
    unittest.main()
