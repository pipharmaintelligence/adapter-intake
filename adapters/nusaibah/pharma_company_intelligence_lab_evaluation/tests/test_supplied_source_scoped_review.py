from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
from pathlib import Path
import unittest

import test_commercial_role_scope as boundary
import test_supplied_source_quote_review as quote_tests

ROOT = Path(__file__).resolve().parents[1]
scoped = quote_tests.load(ROOT, "supplied_source_scoped_review.py", "_scoped_review_tests")
engine = quote_tests.load(ROOT, "quote_review_orchestration.py", "_scoped_engine_tests")
# Preserve the reviewed LF and CRLF checkout encodings; no mixed/new content.
HISTORICAL_HASHES = {'supplied_source_review.py': ['1f42be30db0306edfdaaf3c77574afbf4d7771815402f562264b91937afbe2bc',
                               '668b802e626a59e5f40a4b97897e70059d2eb47f20e3cbb4fbb67eced334ef60'],
 'supplied_source_quote_review.py': ['3b09cfd10d4de13a7e5c6f32c01c1f64649fc433dd04e850cbffcde0e0b2f3a4',
                                     'd1ee99ad3ede793599adc9fdbb3eb096564dffb3c4d1e44247710bae5fea6cff'],
 'nusaibah_pharma_company_intelligence_lab_evaluation_v0_2_2_adapter.py': ['565ae107a8a9c5ba8741f17a760590a84556d782bf0db6ce20808a991097e406',
                                                                           '682aa1ef851821c2756f0f5cf95cb518c59a3320d1551940bcd799dcc0149386']}


class RoleScopedReviewTests(unittest.TestCase):
    def run_case(self, case_id):
        inputs = boundary.ScriptedRoleInputs(boundary.CASES[case_id])
        result = scoped.run_review(inputs)
        scoped.validate_resolution_receipts(result, scoped.prepare_review(inputs))
        self.assertEqual((5, 1, 0), (result["agent_call_count"], result["child_call_count"], result["mutable_call_count"]))
        self.assertEqual(0, result["plan"]["repair_iterations"])
        self.assertEqual([], result["withheld_findings"])
        return inputs, result

    def test_historical_source_bytes_and_methodology_digest_are_preserved(self):
        for name, expected in HISTORICAL_HASHES.items():
            with self.subTest(name=name):
                self.assertIn(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected)
        self.assertEqual(boundary.FROZEN_METHOD_DIGEST, quote_tests.review.digest(quote_tests.review.METHOD))
        self.assertEqual("supplied_source_methodology.v3", scoped.METHOD["schema_version"])
        self.assertEqual(boundary.PROPOSAL["questions"], scoped.QUESTION_OVERRIDES)
        self.assertEqual(boundary.PROPOSAL["requirement_scopes"], scoped.REQUIREMENT_SCOPES)
        self.assertNotEqual(boundary.FROZEN_METHOD_DIGEST, scoped.digest(scoped.METHOD))

    def test_actual_candidate_headquarters_only_has_one_identity_finding_and_no_commercial_evidence(self):
        inputs, result = self.run_case("role-scope-headquarters-only")
        self.assertEqual(["company_identity"], [f["requirement_id"] for f in result["accepted_findings"]])
        commercial = boundary.CommercialRoleScopeTests.coverage_for(result, "commercial_signals")
        self.assertEqual("no_evidence", commercial["specialist_disposition"])
        self.assertEqual([], commercial["finding_ids"])
        self.assertTrue(commercial["reviewed"])
        self.assertFalse(commercial["unrepresented_evidence"])
        self.assertEqual(1, len(inputs.child_calls[0]["arguments"]["requests"]))

    def test_address_only_abstains_while_explicit_market_and_shared_span_commercial_facts_remain_eligible(self):
        expected = {
            "role-scope-registered-address-only": ["company_identity"],
            "role-scope-explicit-market-geography": ["commercial_signals"],
            "role-scope-distinct-claims-shared-span": ["company_identity", "commercial_signals"],
        }
        for case_id, requirements in expected.items():
            with self.subTest(case_id=case_id):
                _, result = self.run_case(case_id)
                self.assertEqual(requirements, [f["requirement_id"] for f in result["accepted_findings"]])
                if len(requirements) == 2:
                    a, b = result["accepted_findings"]
                    self.assertEqual(a["evidence"], b["evidence"])
                    self.assertNotEqual(a["statement"], b["statement"])

    def test_specialists_and_both_verifier_stages_receive_the_bound_role_scopes(self):
        inputs, result = self.run_case("role-scope-headquarters-only")
        for role, packet in inputs.calls:
            contract = packet["response_contract"]
            if role == scoped.VERIFIER_ROLE:
                self.assertEqual(scoped.REQUIREMENT_SCOPES, contract["requirement_scopes"])
                self.assertIn("A supported finding must also belong", " ".join(contract["coverage_rules"]))
            else:
                self.assertEqual(result["plan"]["methodology_digest"], packet["methodology_digest"])
                if role in {"source_portfolio_reviewer", "source_commercial_reviewer"}:
                    for requirement, scope in contract["requirement_scopes"].items():
                        self.assertEqual(scoped.REQUIREMENT_SCOPES[requirement], scope)
                        self.assertEqual(scoped.QUESTIONS[requirement], packet["requirements"][requirement])
            self.assertNotIn("scripted_findings", str(packet))
        self.assertEqual({"chunk_evidence_verification", "global_consistency"}, {
            p["task_stage"] for r, p in inputs.calls if r == scoped.VERIFIER_ROLE})

    def test_bound_semantic_verifier_can_withhold_a_supported_but_misrouted_commercial_claim(self):
        case = copy.deepcopy(boundary.CASES["role-scope-headquarters-only"])
        case["scripted_findings"]["commercial_signals"] = copy.deepcopy(case["scripted_findings"]["company_identity"])
        class ScopeVerdictInputs(boundary.ScriptedRoleInputs):
            def scripted_response(self, role, packet, value):
                value = super().scripted_response(role, packet, value)
                if packet["task_stage"] == "chunk_evidence_verification":
                    rejected = {c["finding"]["finding_id"] for c in packet["candidates"]
                                if c["finding"]["requirement_id"] == "commercial_signals"}
                    for verdict in value["verdicts"]:
                        if verdict["finding_id"] in rejected:
                            verdict["state"] = "insufficient"
                return value
        inputs = ScopeVerdictInputs(case)
        result = scoped.run_review(inputs)
        self.assertEqual(["company_identity"], [f["requirement_id"] for f in result["accepted_findings"]])
        self.assertEqual(["commercial_signals"], [f["requirement_id"] for f in result["withheld_findings"]])
        self.assertEqual("insufficient", result["withheld_findings"][0]["state"])
        self.assertEqual(2, len(result["span_resolution_receipts"][0]["result"]["output"]["spans"]))
        scoped.validate_resolution_receipts(result, scoped.prepare_review(inputs))

    def test_noncompliant_supported_verdict_is_not_misrepresented_as_deterministic_semantic_proof(self):
        case = copy.deepcopy(boundary.CASES["role-scope-headquarters-only"])
        case["scripted_findings"]["commercial_signals"] = copy.deepcopy(case["scripted_findings"]["company_identity"])
        result = scoped.run_review(boundary.ScriptedRoleInputs(case))
        self.assertEqual(2, len(result["accepted_findings"]))
        self.assertFalse(result["external_truth_verified"])

    def test_shared_orchestration_matches_historical_result_packets_and_call_order_with_legacy_contract(self):
        old = quote_tests.review
        contract = engine.ReviewContract(old.METHOD, old.QUESTIONS, old.prepare_review,
                                        old._specialist_contract, old._verifier_contract, old._verification_material)
        for findings in (False, True):
            with self.subTest(findings=findings):
                before = quote_tests.FakeInputs(findings=findings)
                after = quote_tests.FakeInputs(findings=findings)
                expected = old.run_review(before)
                actual = engine.run_review(after, profile=contract)
                self.assertEqual(expected, actual)
                self.assertEqual(before.events, after.events)
                self.assertEqual(before.child_calls, after.child_calls)
                normalize = lambda rows: sorted(old._encode(row) for row in rows)
                self.assertEqual(normalize(before.calls), normalize(after.calls))

    def test_concurrent_old_and_new_contracts_do_not_mutate_shared_module_globals(self):
        old_inputs = quote_tests.FakeInputs()
        new_inputs = boundary.ScriptedRoleInputs(boundary.CASES["role-scope-headquarters-only"])
        with ThreadPoolExecutor(max_workers=2) as pool:
            old_future = pool.submit(quote_tests.review.run_review, old_inputs)
            new_future = pool.submit(scoped.run_review, new_inputs)
            old_result, new_result = old_future.result(), new_future.result()
        self.assertEqual(boundary.FROZEN_METHOD_DIGEST, old_result["plan"]["methodology_digest"])
        self.assertEqual(scoped.digest(scoped.METHOD), new_result["plan"]["methodology_digest"])
        self.assertEqual(boundary.FROZEN_METHOD_DIGEST, quote_tests.review.digest(quote_tests.review.METHOD))
        for inputs, expected in ((old_inputs, quote_tests.review.QUESTIONS["commercial_signals"]),
                                 (new_inputs, scoped.QUESTIONS["commercial_signals"])):
            packet = next(p for r, p in inputs.calls if r == "source_commercial_reviewer")
            self.assertEqual(expected, packet["requirements"]["commercial_signals"])

    def test_no_findings_and_four_chunks_retain_finite_agent_child_and_repair_controls(self):
        inputs = quote_tests.FakeInputs(findings=False)
        result = scoped.run_review(inputs)
        self.assertEqual((4, 1), (result["agent_call_count"], result["child_call_count"]))
        inputs = quote_tests.FakeInputs()
        inputs["evaluation_case"]["records"][0]["source_units"] = [
            {"locator": f"source:{i}", "entity_id": "ficta", "text": f"Source evidence {i}."} for i in range(4)]
        result = scoped.run_review(inputs)
        self.assertEqual((17, 4), (result["agent_call_count"], result["child_call_count"]))
        self.assertEqual(3, result["plan"]["max_concurrency"])
        self.assertEqual(1800, result["plan"]["deadline_seconds"])
        self.assertEqual(0, result["plan"]["repair_iterations"])
        self.assertFalse(result["publication_allowed"])
        scoped.validate_resolution_receipts(result, scoped.prepare_review(inputs))

    def test_missing_child_helper_and_excess_chunks_fail_before_any_agent(self):
        inputs = quote_tests.FakeInputs()
        inputs.invoke_asset = None
        with self.assertRaises(scoped.SourceReviewError):
            scoped.run_review(inputs)
        self.assertEqual([], inputs.calls)
        inputs = quote_tests.FakeInputs()
        inputs["evaluation_case"]["records"][0]["source_units"] = [
            {"locator": f"source:{i}", "entity_id": "ficta", "text": "Evidence."} for i in range(5)]
        with self.assertRaises(scoped.SourceReviewError):
            scoped.run_review(inputs)
        self.assertEqual([], inputs.calls)

    def test_ambiguous_literal_quote_still_blocks_without_a_repair_or_extra_verifier(self):
        inputs = quote_tests.FakeInputs(transform=lambda role, packet, value:
            quote_tests.QuoteReviewTests.select_quote(role, value, "aa"))
        inputs["evaluation_case"]["records"][0]["source_units"][0]["text"] = "aaa"
        with self.assertRaises(scoped.SourceReviewError) as caught:
            scoped.run_review(inputs)
        self.assertEqual("evidence_quote_ambiguous", caught.exception.proof_failure_detail["rule"])
        self.assertEqual((3, 1), (len(inputs.calls), len(inputs.child_calls)))

    def test_deadline_after_child_prevents_semantic_verification_without_retry(self):
        expired = False
        def expire(request, result):
            nonlocal expired
            expired = True
            return result
        inputs = quote_tests.FakeInputs(tool_transform=expire)
        with self.assertRaises(scoped.SourceReviewError) as caught:
            scoped.run_review(inputs, clock=lambda: 1800 if expired else 0)
        self.assertEqual("deadline_exceeded", caught.exception.proof_failure_detail["rule"])
        self.assertEqual((3, 1), (len(inputs.calls), len(inputs.child_calls)))


if __name__ == "__main__":
    unittest.main()
