from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ASSET_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSET_ROOT))

import agent_contract as legacy
import critic_diagnostics_v0_1_13 as diagnostic
import nusaibah_pharma_company_intelligence_lab_adapter as adapter
import test_orchestration_preview as orchestration
from test_critic_plan_contract import _critic_payload

CONTEXT = {
    "company_id": 13,
    "known_claim_ids": {"claim-1"},
    "known_section_ids": {"company_profile"},
    "known_plan_requirement_ids": {"cross_cutting_question.1"},
}
REQUIREMENT = {
    "requirement_id": "cross_cutting_question.1",
    "disposition": "unresolved_evidence",
    "notes": "Evidence remains unavailable.",
}
SECRET = "PRIVATE_SENTINEL_DO_NOT_PROJECT"


def invalid_cases():
    # Each case names a static failed field/rule; no output value is diagnostic.
    for field in ("unsupported_claim_ids", "stale_claim_ids", "missing_section_ids",
                  "contradiction_items", "residual_uncertainties"):
        for value in (None, {}, "raw-value", [None], [""], ["x" * 2001], list(range(65))):
            payload = _critic_payload()
            payload[field] = value
            yield payload, "field_invalid", field
    for field in ("unsupported_claim_ids", "stale_claim_ids", "missing_section_ids"):
        payload = _critic_payload()
        payload[field] = ["claim-1", "claim-1"]
        yield payload, "field_invalid", field
    for field in ("unsupported_claim_ids", "stale_claim_ids"):
        payload = _critic_payload()
        payload[field] = [SECRET]
        yield payload, "unknown_claim_id", "claim_ids"
    payload = _critic_payload()
    payload["missing_section_ids"] = [SECRET]
    yield payload, "unknown_section_id", "missing_section_ids"
    for value in (None, {}, [dict(REQUIREMENT)] * 65):
        payload = _critic_payload()
        payload["unmet_plan_requirements"] = value
        yield payload, "bounded_list_required", "unmet_plan_requirements"
    payload = _critic_payload()
    del payload["unmet_plan_requirements"]
    yield payload, "bounded_list_required", "unmet_plan_requirements"
    for value, rule in (([None], "object_required"), ([{}], "entry_shape_invalid"),
                        ([{**REQUIREMENT, "extra": SECRET}], "entry_shape_invalid")):
        payload = _critic_payload()
        payload["unmet_plan_requirements"] = value
        yield payload, rule, "unmet_plan_requirements"
    for field in ("requirement_id", "disposition", "notes"):
        for value in (None, [], "", "x" * 2001):
            payload = _critic_payload()
            payload["unmet_plan_requirements"] = [{**REQUIREMENT, field: value}]
            yield payload, "field_invalid", "unmet_plan_requirements_" + field
    payload = _critic_payload()
    payload["unmet_plan_requirements"] = [{**REQUIREMENT, "requirement_id": SECRET}]
    yield payload, "unknown_requirement_id", "unmet_plan_requirements_requirement_id"
    payload = _critic_payload()
    payload["unmet_plan_requirements"] = [dict(REQUIREMENT), dict(REQUIREMENT)]
    yield payload, "duplicate_requirement_id", "unmet_plan_requirements_requirement_id"
    payload = _critic_payload()
    payload["unmet_plan_requirements"] = [{**REQUIREMENT, "disposition": "ignored"}]
    yield payload, "disposition_invalid", "unmet_plan_requirements_disposition"
    for value, rule in ((None, "field_invalid"), ([], "field_invalid"),
                        ("", "field_invalid"), ("x" * 17, "field_invalid"),
                        ("wrong", "recommendation_invalid")):
        payload = _critic_payload()
        payload["recommendation"] = value
        yield payload, rule, "recommendation"
    payload = _critic_payload()
    payload["citation_coverage"] = []
    yield payload, "object_required", "citation_coverage"
    for value, rule in ((None, "field_invalid"), ("", "field_invalid"),
                        ("x" * 33, "field_invalid"), ("wrong", "coverage_status_invalid")):
        payload = _critic_payload()
        payload["citation_coverage"]["status"] = value
        yield payload, rule, "citation_coverage_status"
    for value in (None, [], "x" * 2001):
        payload = _critic_payload()
        payload["citation_coverage"]["notes"] = value
        yield payload, "field_invalid", "citation_coverage_notes"


class CriticDiagnosticContractTests(unittest.TestCase):
    def test_invalid_payload_parity_and_static_diagnostics(self):
        count = 0
        for payload, rule, field in invalid_cases():
            with self.subTest(rule=rule, field=field, case=count):
                with self.assertRaises(ValueError):
                    legacy.validate_critic_payload(payload, **CONTEXT)
                with self.assertRaises(diagnostic.CriticContractValidationError) as caught:
                    diagnostic.validate_critic_payload(payload, **CONTEXT)
                error = caught.exception
                self.assertEqual(error.code, "pharma_agent_business_schema_invalid")
                self.assertEqual(error.proof_failure_detail, {
                    "schema_version": "proof_failure_detail.v1",
                    "proof_kind": "agent_contract", "role": "evidence_critic",
                    "stage": "critic_payload", "rule": rule, "field": field,
                })
                self.assertNotIn(SECRET, str(error) + json.dumps(error.proof_failure_detail))
                for key in ("role", "stage", "rule", "field"):
                    self.assertRegex(error.proof_failure_detail[key], r"^[a-z][a-z0-9_]{0,63}$")
            count += 1
        self.assertGreater(count, 65)

    def test_valid_payload_normalization_and_defaults_match_retained_validator(self):
        payloads = [_critic_payload()]
        minimal = _critic_payload()
        for field in ("unsupported_claim_ids", "stale_claim_ids", "missing_section_ids",
                      "contradiction_items", "residual_uncertainties"):
            del minimal[field]
        minimal["citation_coverage"] = {"status": " sufficient "}
        minimal["recommendation"] = " pass "
        payloads.append(minimal)
        complete = _critic_payload()
        complete.update({
            "unsupported_claim_ids": [" claim-1 "], "stale_claim_ids": ["claim-1"],
            "missing_section_ids": ["company_profile"], "recommendation": "fail",
            "contradiction_items": [" observed conflict "],
            "residual_uncertainties": [" unresolved "],
            "unmet_plan_requirements": [dict(REQUIREMENT)],
            "ignored_extra": SECRET,
        })
        payloads.append(complete)
        for payload in payloads:
            with self.subTest(payload=payload):
                self.assertEqual(
                    diagnostic.validate_critic_payload(payload, **CONTEXT),
                    legacy.validate_critic_payload(payload, **CONTEXT),
                )

    def test_validation_order_is_preserved_when_multiple_fields_fail(self):
        payload = _critic_payload()
        payload.update({"unsupported_claim_ids": None, "unmet_plan_requirements": None,
                        "recommendation": "wrong", "citation_coverage": None})
        with self.assertRaises(diagnostic.CriticContractValidationError) as caught:
            diagnostic.validate_critic_payload(payload, **CONTEXT)
        self.assertEqual(caught.exception.proof_failure_detail["field"], "unsupported_claim_ids")

    def test_all_quality_gates_keep_rejecting_with_distinct_safe_details(self):
        research = {role: {"_citations": [object()]} for role in adapter.RESEARCH_ROLES}
        cases = (
            ("research_citations_missing", "citations", lambda r, c: r[adapter.RESEARCH_ROLES[0]].update(_citations=[])),
            ("critic_rejected", "recommendation", lambda r, c: c.update(recommendation="fail")),
            ("citation_coverage_insufficient", "citation_coverage_status", lambda r, c: c["citation_coverage"].update(status="insufficient")),
            ("unsupported_claims_remaining", "unsupported_claim_ids", lambda r, c: c.update(unsupported_claim_ids=[SECRET])),
            ("required_sections_missing", "missing_section_ids", lambda r, c: c.update(missing_section_ids=[SECRET])),
            ("planner_requirements_unsatisfied", "unmet_plan_requirements", lambda r, c: c.update(unmet_plan_requirements=[{**REQUIREMENT, "disposition": "unsatisfied"}])),
        )
        for rule, field, mutate in cases:
            r, c = deepcopy(research), _critic_payload()
            mutate(r, c)
            with self.subTest(rule=rule):
                with self.assertRaises(adapter.AgentContractValidationError) as caught:
                    adapter._require_pre_synthesis_quality(r, c)
                detail = caught.exception.proof_failure_detail
                self.assertEqual(detail["stage"], "pre_synthesis_quality")
                self.assertEqual((detail["rule"], detail["field"]), (rule, field))
                self.assertEqual(detail["role"], adapter.RESEARCH_ROLES[0] if field == "citations" else "evidence_critic")
                self.assertNotIn(SECRET, str(caught.exception) + json.dumps(detail))
        adapter._require_pre_synthesis_quality(research, _critic_payload())

    def test_successful_first_run_preview_matches_retained_baseline(self):
        import importlib.util
        name = "_retained_pharma_production_012"
        spec = importlib.util.spec_from_file_location(name, ASSET_ROOT / "tests/fixtures/baseline-production-0.1.12.py")
        baseline = importlib.util.module_from_spec(spec)
        sys.modules[name] = baseline
        spec.loader.exec_module(baseline)
        outputs = []
        for module in (baseline, adapter):
            inputs = orchestration.FirstRunMethodologyInputs(legacy=module is baseline)
            with patch.object(module, "_agent_citations", side_effect=orchestration._fake_citations):
                outputs.append(module.NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(inputs, {}))
            self.assertFalse(any(role.endswith("_update") for role, _ in inputs.dynamic_skill_calls))
        # New 0.1.17 diagnostics/reflection fields are additive; all retained
        # default-pass business fields and call counts must remain identical.
        additive = {
            "research_incomplete_company_count", "business_result_state",
            "portfolio_review_passes_requested", "portfolio_review_pass_count",
            "portfolio_reflection_pass_count", "portfolio_review_trace",
            "research_resolver_agent_call_count", "research_incomplete",
            "unresolved_research_responses", "research_response_repair_count",
            "research_response_repairs", "no_evidence_research_roles",
            "incomplete_research_company_count",
            "agent_schema_incomplete_company_count", "agent_schema_incomplete",
            "unresolved_agent_responses", "agent_response_resolver_call_count", "agent_response_recovery_trace",
        }
        def retained_projection(old, new):
            if isinstance(old, dict):
                self.assertTrue(set(old).issubset(new))
                self.assertTrue((set(new) - set(old)).issubset(additive))
                return {key: retained_projection(value, new[key]) for key, value in old.items()}
            if isinstance(old, list):
                self.assertEqual(len(old), len(new))
                return [retained_projection(a, b) for a, b in zip(old, new)]
            return new
        self.assertEqual(outputs[0], retained_projection(outputs[0], outputs[1]))

    def test_critic_failures_stop_real_orchestration_before_synthesis_and_mutation(self):
        original = orchestration._agent_value
        for failure in ("missing_required_list", "critic_rejected", "citation_coverage_insufficient",
                        "unsupported_claims_remaining", "required_sections_missing", "planner_requirements_unsatisfied"):
            with self.subTest(failure=failure):
                inputs = orchestration.FakeInputs()
                inputs["variables"]["company_ids"] = [13]
                inputs["variables"]["memory_mode"] = "apply"
                inputs.set_company_records([{"id": 13, "company": "Tabuk Pharmaceuticals"}])

                def failing_value(role, company_id, input_value):
                    if role == adapter.RESEARCH_RESOLVER_ROLE:
                        return dict(input_value["invalid_response"])
                    value = original(role, company_id, input_value)
                    if role != "evidence_critic":
                        return value
                    if failure == "missing_required_list":
                        del value["unmet_plan_requirements"]
                    elif failure == "critic_rejected":
                        value["recommendation"] = "fail"
                    elif failure == "citation_coverage_insufficient":
                        value["citation_coverage"]["status"] = "insufficient"
                    elif failure == "unsupported_claims_remaining":
                        value["unsupported_claim_ids"] = [input_value["research_evidence"]["claims"][0]["claim_id"]]
                    elif failure == "required_sections_missing":
                        value["missing_section_ids"] = ["company_profile"]
                    else:
                        value["unmet_plan_requirements"] = [{
                            "requirement_id": input_value["planner_requirements"][0]["requirement_id"],
                            "disposition": "unsatisfied", "notes": SECRET,
                        }]
                    return value

                with patch.object(adapter, "_agent_citations", side_effect=orchestration._fake_citations), patch.object(orchestration, "_agent_value", side_effect=failing_value):
                    if failure == "missing_required_list":
                        result = adapter.NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(inputs, {})
                        row = result["outputs"]["intelligence_dossier"]["company_results"][0]
                        self.assertTrue(row["agent_schema_incomplete"])
                        self.assertFalse(row["quality_gate_passed"])
                        self.assertEqual(row["unresolved_agent_responses"][0]["rule"], "bounded_list_required")
                        self.assertEqual(row["agent_response_resolver_call_count"], 1)
                        self.assertFalse(any(role == "intelligence_synthesizer" for role, _ in inputs.agent_calls))
                        self.assertFalse(any(role.endswith("_update") for role, _ in inputs.dynamic_skill_calls))
                        continue
                    with self.assertRaises((diagnostic.CriticContractValidationError, adapter.AgentContractValidationError)) as caught:
                        adapter.NusaibahPharmaCompanyIntelligenceLabAdapter().invoke(inputs, {})
                self.assertEqual(caught.exception.code, "pharma_agent_business_schema_invalid")
                detail = caught.exception.proof_failure_detail
                self.assertEqual(detail["rule"], "bounded_list_required" if failure == "missing_required_list" else failure)
                self.assertIn(("evidence_critic", 13), inputs.agent_calls)
                self.assertFalse(any(role == "intelligence_synthesizer" for role, _ in inputs.agent_calls))
                self.assertFalse(any(role.endswith("_update") for role, _ in inputs.dynamic_skill_calls))
                self.assertNotIn(SECRET, json.dumps(detail))


if __name__ == "__main__":
    unittest.main()
