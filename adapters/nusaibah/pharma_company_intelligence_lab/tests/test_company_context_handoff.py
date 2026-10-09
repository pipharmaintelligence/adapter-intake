from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from company_context_contract_v0_1_15 import CompanyContextContractError, resolve_company_context
from company_context_fixture import handoff, sign
from test_orchestration_preview import FakeInputs, _fake_citations, adapter_module


class CompanyContextHandoffTests(unittest.TestCase):
    def reject(self, inputs, rule):
        with patch.object(inputs, "skill", wraps=inputs.skill) as fixed:
            with self.assertRaises(CompanyContextContractError) as caught:
                adapter_module.NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(inputs, {})
            self.assertEqual(caught.exception.proof_failure_detail["rule"], rule)
            fixed.assert_not_called()
        self.assertEqual(inputs.agent_calls, [])
        self.assertEqual(inputs.dynamic_skill_calls, [])
        return caught.exception

    def test_raw_context_and_caller_run_reference_are_not_hydrated_context(self):
        for value in ({"records": []}, {"run_uuid": "11111111-1111-4111-8111-111111111111"}):
            inputs = FakeInputs()
            inputs["company_context"] = value
            self.reject(inputs, "retained_handoff_required")

    def test_legacy_companies_role_is_rejected_in_new_identity(self):
        inputs = FakeInputs()
        inputs["companies"] = {"records": [{"id": 13}]}
        self.reject(inputs, "input_roles")

    def test_missing_context_has_no_legacy_fallback(self):
        self.reject(FakeInputs(legacy=True), "input_roles")

    def test_producer_and_output_role_are_exactly_pinned(self):
        for field, value in (("asset_identity", "nusaibah.company_scope:0.1.1"),
                             ("output_role", "company_scope_page"), ("authority", "caller"),
                             ("run_uuid", "invalid"), ("checksum_sha256", "invalid")):
            inputs = FakeInputs()
            inputs["company_context"]["provenance"][field] = value
            self.reject(inputs, "provenance")

    def test_partial_scope_is_rejected_even_with_matching_digest(self):
        inputs = FakeInputs()
        scope = inputs["company_context"]["value"]
        scope["complete"] = False
        sign(scope)
        self.reject(inputs, "complete_scope_required")

    def test_scope_count_and_record_identity_must_match(self):
        for change, rule in ((lambda s: s.update(company_count=True), "scope_count"),
                             (lambda s: s.update(requested_company_ids=[13, 13]), "scope_ids"),
                             (lambda s: s["records"].reverse(), "scope_record_ids")):
            inputs = FakeInputs()
            scope = inputs["company_context"]["value"]
            change(scope)
            sign(scope)
            self.reject(inputs, rule)

    def test_request_must_match_complete_scope_instead_of_silently_subsetting(self):
        inputs = FakeInputs()
        inputs["variables"]["company_ids"] = [13]
        self.reject(inputs, "requested_company_ids")

    def test_more_than_five_contexts_are_rejected_before_helpers(self):
        inputs = FakeInputs()
        inputs["company_context"] = handoff([{"id": n, "company": "Synthetic"} for n in range(1, 7)])
        self.reject(inputs, "scope_ids")

    def test_both_record_and_scope_digests_are_checked(self):
        inputs = FakeInputs()
        inputs["company_context"]["value"]["records"][0]["company_name"] = "Changed"
        self.reject(inputs, "context_digest")
        inputs = FakeInputs()
        inputs["company_context"]["value"]["digest"] = "sha256:" + "0" * 64
        self.reject(inputs, "scope_digest")

    def test_corporate_scope_cannot_be_changed_even_if_resigned(self):
        for location, rule in (("scope", "complete_scope_required"), ("record", "context_identity")):
            inputs = FakeInputs()
            scope = inputs["company_context"]["value"]
            target = scope if location == "scope" else scope["records"][0]
            target["corporate_id"] = 2
            sign(target)
            sign(scope)
            self.reject(inputs, rule)

    def test_identifier_types_and_limits_match_producer(self):
        for value in (True, 0, -1, "13", 2**63):
            inputs = FakeInputs()
            record = inputs["company_context"]["value"]["records"][0]
            record["company_id"] = value
            sign(record)
            self.reject(inputs, "context_identity")

    def test_unknown_fields_and_invalid_source_are_rejected(self):
        for mutate, rule in ((lambda r: r.update(extra="unexpected"), "context_shape"),
                             (lambda r: r["source"].update(node_key="other"), "source"),
                             (lambda r: r["source"].update(retrieved_at="invented"), "source"),
                             (lambda r: r.update(headquarters_country_id=True), "country_id")):
            inputs = FakeInputs()
            record = inputs["company_context"]["value"]["records"][0]
            mutate(record)
            sign(record)
            self.reject(inputs, rule)

    def test_optional_field_bounds_and_normalization_match_producer(self):
        for field, maximum in (("address_line1", 4096), ("address_line2", 4096), ("website", 2048), ("source_updated_at", 64)):
            for value in ("x" * (maximum + 1), " ", " x", "x\x00"):
                inputs = FakeInputs()
                record = inputs["company_context"]["value"]["records"][0]
                record[field] = value
                sign(record)
                self.reject(inputs, "context_field")

    def test_admitted_business_projection_has_no_storage_refs_or_inferred_country(self):
        inputs = FakeInputs()
        record = inputs["company_context"]["value"]["records"][0]
        record["headquarters_country_id"] = 99
        record["company_name"] = "x" * 512
        sign(record)
        sign(inputs["company_context"]["value"])
        before = deepcopy(inputs["company_context"])
        records = resolve_company_context(inputs, company_ids=(13, 59))
        self.assertEqual(records[0]["headquarters_country_id"], 99)
        self.assertEqual(len(records[0]["company_name"]), 512)
        self.assertNotIn("country", records[0])
        self.assertNotIn("source", records[0])
        self.assertNotIn("digest", records[0])
        records[0]["company_name"] = "Mutated copy"
        self.assertEqual(inputs["company_context"], before)

    def test_single_list_and_range_selector_semantics(self):
        for selector, ids in (("single", [13]), ("list", [59, 13]), ("range", [13, 14])):
            inputs = FakeInputs()
            inputs["company_context"] = handoff([{"id": n, "company": "Synthetic"} for n in ids])
            scope = inputs["company_context"]["value"]
            scope["selector_kind"] = selector
            sign(scope)
            self.assertEqual([r["company_id"] for r in resolve_company_context(inputs, company_ids=tuple(ids))], ids)
        for changes in ({"selector_kind": "range"}, {"selector_kind": "all"}, {"duplicate_id_count": True}, {"duplicate_id_count": 24}):
            inputs = FakeInputs()
            scope = inputs["company_context"]["value"]
            scope.update(changes)
            sign(scope)
            self.reject(inputs, "selector")

    def test_safe_diagnostics_never_include_context_values(self):
        inputs = FakeInputs()
        marker = "PRIVATE-CONTEXT-CONTENT"
        inputs["company_context"]["value"]["records"][0]["company_name"] = marker
        error = self.reject(inputs, "context_digest")
        self.assertEqual(error.code, "pharma_agent_business_schema_invalid")
        self.assertEqual(error.proof_failure_detail["stage"], "input_contract")
        self.assertNotIn(marker, str(error) + json.dumps(error.proof_failure_detail))

    def test_full_pipeline_uses_context_in_requested_order_without_companies_read(self):
        inputs = FakeInputs()
        with patch.object(adapter_module, "_agent_citations", side_effect=_fake_citations):
            response = adapter_module.NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(inputs, {})
        self.assertEqual([r["company_id"] for r in response["outputs"]["intelligence_dossier"]["company_results"]], [13, 59])
        self.assertNotIn("companies", inputs)
        self.assertEqual(len(inputs.agent_calls), 24)
        self.assertEqual({role for role, _ in inputs.dynamic_skill_calls}, {"company_memory", "company_methodology"})
        self.assertEqual(response["metrics"]["memory_mutations_made"], 0)
        payloads = json.dumps(inputs.agent_inputs)
        for forbidden in ("synthetic-lake", "core_artifact", "checksum_sha256", "retained_asset_output"):
            self.assertNotIn(forbidden, payloads)


if __name__ == "__main__":
    unittest.main()
