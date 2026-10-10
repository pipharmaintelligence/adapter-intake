from __future__ import annotations

from copy import deepcopy
import json
import unittest

import test_orchestration_preview as orchestration
import agent_contract as legacy
import research_diagnostics_v0_1_17 as diagnostic
from devtools.proof_failure_detail import safe_proof_failure_detail

ROLE = "portfolio_researcher"
SECRET = "PRIVATE_SENTINEL_NEVER_PROJECT"


def valid_payload(role=ROLE):
    return orchestration._agent_value(role, 13, {
        "required_sections": orchestration.adapter_module._section_requests(legacy.RESEARCH_ROLE_SECTIONS[role]),
    })


class ResearchDiagnosticParityTests(unittest.TestCase):
    def test_valid_payloads_match_retained_validator_without_mutation(self):
        for role in legacy.RESEARCH_ROLE_SECTIONS:
            for empty_claims in (False, True):
                value = valid_payload(role)
                if empty_claims:
                    value["claims"] = []
                value["uncertainties"] = ["  Explicit uncertainty.  "]
                value["ignored_extra"] = SECRET
                before = deepcopy(value)
                self.assertEqual(diagnostic.validate_research_payload(value, role=role, company_id=13),
                                 legacy.validate_research_payload(value, role=role, company_id=13))
                self.assertEqual(value, before)

    def test_invalid_payload_parity_and_static_diagnostics(self):
        cases = []
        for field, values in {
            "sections": [None, {}, [None]],
            "claims": [None, {}, [None], [{}] * 17],
            "uncertainties": [None, {}, [None], [""], ["x" * 2001], ["x"] * 33],
            "company_id": [999], "role": [SECRET],
        }.items():
            for item in values:
                payload = valid_payload(); payload[field] = item; cases.append(payload)
        for field, maximum in (("claim_id", 128), ("section_id", 128),
                               ("evidence_kind", 64), ("confidence", 32),
                               ("as_of_date", 64), ("statement", 2000)):
            for item in (None, [], "", "x" * (maximum + 1), SECRET):
                if field == "as_of_date" and item is None:
                    continue
                if field in {"claim_id", "as_of_date", "statement"} and item == SECRET:
                    continue
                payload = valid_payload(); payload["claims"][0][field] = item; cases.append(payload)
        for item in (None, "false", 0):
            payload = valid_payload(); payload["claims"][0]["inference"] = item; cases.append(payload)
        payload = valid_payload(); payload["claims"][0]["evidence_kind"] = "inference"; cases.append(payload)
        payload = valid_payload(); payload["claims"] *= 2; cases.append(payload)
        payload = valid_payload(); payload["sections"].reverse(); cases.append(payload)
        payload = valid_payload(); payload["sections"][0]["subsections"].reverse(); cases.append(payload)
        for text in ("", "x" * 2001):
            payload = valid_payload(); payload["sections"][0]["subsections"][0]["content"] = text; cases.append(payload)
        for ordinal, payload in enumerate(cases):
            with self.subTest(case=ordinal):
                with self.assertRaises((ValueError, TypeError)):
                    legacy.validate_research_payload(payload, role=ROLE, company_id=13)
                with self.assertRaises(diagnostic.ResearchContractValidationError) as caught:
                    diagnostic.validate_research_payload(payload, role=ROLE, company_id=13)
                proof = caught.exception.proof_failure_detail
                self.assertEqual(safe_proof_failure_detail(proof), proof)
                self.assertEqual(proof["stage"], "research_payload")
                self.assertIn("field", proof)
                self.assertNotIn(SECRET, json.dumps(proof) + str(caught.exception))
        self.assertGreaterEqual(len(cases), 50)

    def test_first_failed_field_follows_retained_validation_order(self):
        value = valid_payload()
        value["claims"][0].update(confidence="unknown", inference="false", statement=None)
        with self.assertRaises(diagnostic.ResearchContractValidationError) as caught:
            diagnostic.validate_research_payload(value, role=ROLE, company_id=13)
        self.assertEqual(caught.exception.proof_failure_detail["field"], "claims_confidence")
        self.assertEqual(caught.exception.proof_failure_detail["rule"], "enum_invalid")

    def test_envelope_parity_and_identity_diagnostics(self):
        envelope = {"status": "completed", "result": {"schema_version": "agent_result.v1", "kind": "json",
                    "content": [{"type": "json", "value": valid_payload()}]}}
        self.assertEqual(diagnostic.extract_research_json(envelope, role=ROLE, company_id=13),
                         legacy.extract_agent_json(envelope, expected_role=ROLE, company_id=13,
                                                   expected_schema_version=legacy.RESEARCH_SCHEMA_VERSION))
        for field, item in (("company_id", 59), ("role", SECRET), ("schema_version", SECRET), ("status", "failed")):
            malformed = deepcopy(envelope); malformed["result"]["content"][0]["value"][field] = item
            with self.assertRaises(RuntimeError):
                legacy.extract_agent_json(malformed, expected_role=ROLE, company_id=13,
                                          expected_schema_version=legacy.RESEARCH_SCHEMA_VERSION)
            with self.assertRaises(diagnostic.ResearchContractValidationError) as caught:
                diagnostic.extract_research_json(malformed, role=ROLE, company_id=13)
            proof = caught.exception.proof_failure_detail
            self.assertEqual(proof["field"], field)
            self.assertEqual(safe_proof_failure_detail(proof), proof)
            self.assertNotIn(SECRET, str(caught.exception) + json.dumps(proof))

    def test_cleanup_restores_only_equivalent_representation(self):
        value = valid_payload(); before = deepcopy(value)
        value["sections"].reverse()
        for section in value["sections"]:
            section["subsections"].reverse()
        value["claims"][0]["confidence"] = " HIGH "
        value["claims"][0]["evidence_kind"] = " GROUNDED_EXTERNAL "
        malformed = deepcopy(value)
        payload, repairs = diagnostic.resolve_research_payload(value, role=ROLE, company_id=13)
        self.assertEqual(value, malformed)
        self.assertEqual(payload, legacy.validate_research_payload(before, role=ROLE, company_id=13))
        self.assertEqual(sum(item["count"] for item in repairs), 5)
        self.assertEqual(diagnostic.resolve_research_payload(payload, role=ROLE, company_id=13), (payload, []))

    def test_cleanup_cannot_fill_identity_boolean_or_missing_evidence(self):
        for mutation in (lambda p: p.update(company_id=59),
                         lambda p: p["claims"][0].update(inference="false"),
                         lambda p: p["claims"][0].update(confidence="certain"),
                         lambda p: p["sections"].pop()):
            value = valid_payload(); mutation(value)
            with self.assertRaises(diagnostic.ResearchContractValidationError):
                diagnostic.resolve_research_payload(value, role=ROLE, company_id=13)

    def test_agent_repair_cannot_change_facts_scope_or_strengthen_confidence(self):
        original = valid_payload(); original["claims"][0]["confidence"] = "unknown"
        repaired = valid_payload(); repaired["claims"][0]["confidence"] = "low"
        repaired = diagnostic.validate_research_payload(repaired, role=ROLE, company_id=13)
        diagnostic.require_repair_preserves_evidence(original, repaired, role=ROLE)
        for mutation in (lambda p: p["claims"][0].update(statement="Invented claim."),
                         lambda p: p["claims"][0].update(confidence="high"),
                         lambda p: p["claims"].pop(),
                         lambda p: p["sections"][0]["subsections"][0].update(content="Invented fact.")):
            modified = deepcopy(repaired); mutation(modified)
            with self.assertRaises(diagnostic.ResearchContractValidationError):
                diagnostic.require_repair_preserves_evidence(original, modified, role=ROLE)

