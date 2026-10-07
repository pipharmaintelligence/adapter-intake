from __future__ import annotations

import copy
from contextlib import contextmanager
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_supplied_source_quote_review as quote_tests

review = quote_tests.review
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "commercial_role_scope.v1.json").read_text(encoding="utf-8"))
PROPOSAL = FIXTURE["contract_proposal"]
CASES = {case["case_id"]: case for case in FIXTURE["cases"]}
FROZEN_METHOD_DIGEST = "sha256:500331a69b4bcdd4c81b64e2bedf222afe371277e390092ffe8d2e53b6dfd631"


class ScriptedRoleInputs(quote_tests.FakeInputs):
    """Canned specialist/verifier responses; never a semantic classifier or model eval."""

    def __init__(self, case):
        self.case = copy.deepcopy(case)
        initial = quote_tests.old.fixture()
        record = initial["evaluation_case"]["records"][0]
        record["case_id"] = case["case_id"]
        record["entity_name"] = "Ficta Therapeutics Ltd."
        record["source_units"][0]["text"] = case["source_text"]
        super().__init__(initial, findings=False, transform=self.scripted_response)

    def scripted_response(self, role, packet, value):
        if role != review.VERIFIER_ROLE:
            for requirement in value["requirements"]:
                scripted = self.case["scripted_findings"].get(requirement["requirement_id"], [])
                requirement["disposition"] = "findings" if scripted else "no_evidence"
                requirement["findings"] = [{
                    "statement": item["statement"],
                    "evidence": [{"locator": "source:identity", "quote": item["quote"]}],
                } for item in scripted]
        return value


@contextmanager
def proposed_role_contract():
    """Exercise a separately signed proposal in tests without editing runtime 0.2.2."""
    questions = {**review.QUESTIONS, **PROPOSAL["questions"]}
    method = {**copy.deepcopy(review.METHOD),
              "schema_version": "supplied_source_methodology.role_scope_proposal.v1",
              "questions": questions,
              "requirement_scopes": copy.deepcopy(PROPOSAL["requirement_scopes"])}
    original_contract = review._specialist_contract

    def scoped_contract(prepared, chunk, role):
        contract = original_contract(prepared, chunk, role)
        scopes = {rid: copy.deepcopy(PROPOSAL["requirement_scopes"][rid])
                  for rid in review.ROLES[role] if rid in PROPOSAL["requirement_scopes"]}
        if scopes:
            contract["requirement_scopes"] = scopes
        return contract

    with patch.multiple(review, QUESTIONS=questions, METHOD=method,
                        _specialist_contract=scoped_contract):
        yield


class CommercialRoleScopeTests(unittest.TestCase):
    def run_proposal(self, case_id):
        inputs = ScriptedRoleInputs(CASES[case_id])
        with proposed_role_contract():
            prepared = review.prepare_review(inputs)
            result = review.run_review(inputs)
            review.validate_resolution_receipts(result, prepared)
            self.assertNotEqual(FROZEN_METHOD_DIGEST, prepared["plan"]["methodology_digest"])
        self.assertEqual(FROZEN_METHOD_DIGEST, review.digest(review.METHOD))
        self.assertEqual((5, 1, 0), (result["agent_call_count"], result["child_call_count"], result["mutable_call_count"]))
        self.assertEqual(0, result["plan"]["repair_iterations"])
        self.assertEqual([], result["withheld_findings"])
        self.assertFalse(result["publication_allowed"])
        self.assertFalse(result["external_truth_verified"])
        self.assertNotIn("Other Company", json.dumps(inputs.calls + inputs.child_calls))
        # Expected/scripted decisions are test-side only, never source or Agent context.
        packets = json.dumps(inputs.calls + inputs.child_calls)
        self.assertNotIn("scripted_findings", packets)
        self.assertNotIn("contract_proposal", packets)
        self.assertNotIn("included_fact_types", json.dumps(inputs["evaluation_case"]))
        return inputs, result

    @staticmethod
    def coverage_for(result, requirement_id):
        return next(row for row in result["coverage"] if row["requirement_id"] == requirement_id)

    def test_proposal_declares_identity_ownership_and_preserves_explicit_commercial_geography(self):
        self.assertEqual("offline_proposal", PROPOSAL["status"])
        identity = PROPOSAL["requirement_scopes"]["company_identity"]
        commercial = PROPOSAL["requirement_scopes"]["commercial_signals"]
        self.assertIn("headquarters", identity["included_fact_types"])
        self.assertIn("headquarters", commercial["excluded_fact_types"])
        self.assertIn("registered_address", commercial["excluded_fact_types"])
        self.assertIn("identity_only_geography", commercial["excluded_fact_types"])
        self.assertIn("distribution_territory", commercial["included_fact_types"])
        self.assertIn("licensing", commercial["included_fact_types"])
        question = PROPOSAL["questions"]["commercial_signals"]
        self.assertIn("Geography is commercial only when explicitly tied", question)
        self.assertIn("return no_evidence with an empty findings list", question)

    def test_headquarters_only_belongs_to_identity_and_commercial_returns_no_evidence(self):
        inputs, result = self.run_proposal("role-scope-headquarters-only")
        self.assertEqual(["company_identity"], [item["requirement_id"] for item in result["accepted_findings"]])
        commercial = self.coverage_for(result, "commercial_signals")
        self.assertEqual("no_evidence", commercial["specialist_disposition"])
        self.assertEqual([], commercial["finding_ids"])
        self.assertTrue(commercial["reviewed"])
        self.assertFalse(commercial["unrepresented_evidence"])
        self.assertEqual(1, len(inputs.child_calls[0]["arguments"]["requests"]))
        self.assertEqual("review_complete_with_evidence_gaps", result["review_outcome"])
        packets = {role: packet for role, packet in inputs.calls if packet["task_stage"] == "specialist_review"}
        packet = packets["source_commercial_reviewer"]
        self.assertEqual(PROPOSAL["questions"]["commercial_signals"], packet["requirements"]["commercial_signals"])
        self.assertEqual(PROPOSAL["requirement_scopes"]["commercial_signals"], packet["response_contract"]["requirement_scopes"]["commercial_signals"])
        self.assertEqual(["locator", "quote"], packet["response_contract"]["evidence_fields"])
        finding = result["accepted_findings"][0]
        ref = finding["evidence"][0]
        self.assertEqual((0, len(CASES["role-scope-headquarters-only"]["source_text"])), (ref["start"], ref["end"]))

    def test_registered_address_only_does_not_become_a_sales_market(self):
        _, result = self.run_proposal("role-scope-registered-address-only")
        self.assertEqual(["company_identity"], [item["requirement_id"] for item in result["accepted_findings"]])
        self.assertEqual("no_evidence", self.coverage_for(result, "commercial_signals")["specialist_disposition"])

    def test_explicit_sales_geography_remains_commercial_evidence(self):
        _, result = self.run_proposal("role-scope-explicit-market-geography")
        self.assertEqual(["commercial_signals"], [item["requirement_id"] for item in result["accepted_findings"]])
        self.assertEqual("findings", self.coverage_for(result, "commercial_signals")["specialist_disposition"])

    def test_distinct_identity_and_distribution_claims_can_share_one_exact_span(self):
        _, result = self.run_proposal("role-scope-distinct-claims-shared-span")
        accepted = result["accepted_findings"]
        self.assertEqual(["company_identity", "commercial_signals"], [item["requirement_id"] for item in accepted])
        self.assertNotEqual(accepted[0]["statement"], accepted[1]["statement"])
        self.assertEqual(accepted[0]["evidence"], accepted[1]["evidence"])
        self.assertEqual(2, len(result["span_resolution_receipts"][0]["result"]["output"]["spans"]))

    def test_current_022_can_accept_the_same_headquarters_claim_in_both_roles(self):
        case = copy.deepcopy(CASES["role-scope-headquarters-only"])
        case["scripted_findings"]["commercial_signals"] = copy.deepcopy(case["scripted_findings"]["company_identity"])
        inputs = ScriptedRoleInputs(case)
        result = review.run_review(inputs)
        self.assertEqual(2, len(result["accepted_findings"]))
        self.assertEqual(result["accepted_findings"][0]["statement"], result["accepted_findings"][1]["statement"])
        self.assertEqual(FROZEN_METHOD_DIGEST, result["plan"]["methodology_digest"])
        review.validate_resolution_receipts(result, review.prepare_review(inputs))

    def test_prompt_narrowing_alone_is_not_a_deterministic_semantic_rejection(self):
        case = copy.deepcopy(CASES["role-scope-headquarters-only"])
        case["scripted_findings"]["commercial_signals"] = copy.deepcopy(case["scripted_findings"]["company_identity"])
        # Deliberately noncompliant canned Agent output exposes the proof boundary.
        inputs = ScriptedRoleInputs(case)
        with proposed_role_contract():
            result = review.run_review(inputs)
            self.assertEqual(2, len(result["accepted_findings"]))
            review.validate_resolution_receipts(result, review.prepare_review(inputs))
        self.assertEqual(FROZEN_METHOD_DIGEST, review.digest(review.METHOD))


if __name__ == "__main__":
    unittest.main()
