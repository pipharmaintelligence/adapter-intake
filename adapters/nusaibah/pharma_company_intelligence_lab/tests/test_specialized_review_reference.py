from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
EVAL_ROOT = HERE / "evaluation"
REF_ROOT = EVAL_ROOT / "reference"
sys.path.insert(0, str(REF_ROOT))

from evidence_verification import (
    EvidenceVerificationError,
    final_claim_gate,
    final_claim_semantic_input_digest,
    finding_semantic_input_digest,
    verify_finding,
)
from finite_plan import (
    PlanAdmissionError,
    PlanBudget,
    ReservationLedger,
    admit_plan,
    reserve_task,
)
from reconciliation import gate_memory_candidates, reconcile_findings
from release_checklist import validate_release_checklist
from release_evaluation import evaluate_cases, release_gate
from review_contracts import (
    ReviewContractError,
    validate_review_result,
    validate_review_task,
)
from role_packets import RolePacketError, build_role_packet
from safe_projection import project_review_status
from source_chunks import ChunkingError, build_source_inventory, chunk_inventory


class SpecializedReviewReferenceTests(unittest.TestCase):
    def _task(self) -> dict:
        return {
            "schema_version": "review_task.v1",
            "run_id": "run:1",
            "entity_id": "company:13",
            "task_id": "task:1",
            "role": "portfolio_researcher",
            "requirement_ids": ["portfolio.products"],
            "chunk_ids": ["chunk:1"],
            "memory_ref_ids": [],
            "output_schema": "review_finding.v1",
            "logical_call_budget": 1,
            "provider_step_budget": 2,
            "transport_attempt_budget": 3,
            "input_char_budget": 4000,
            "output_token_budget": 2048,
            "timeout_seconds": 120,
        }

    def _coverage(self, obligation_type: str, obligation_id: str, *, status: str, outcome=None):
        return {
            "schema_version": "review_coverage.v1",
            "obligation_type": obligation_type,
            "obligation_id": obligation_id,
            "status": status,
            "outcome": outcome,
            "reason": "Synthetic regression disposition.",
            "task_ids": ["task:1"] if status in {"assigned", "reviewed"} else [],
        }

    def test_wp_manifest_keeps_wp2_through_wp10_gated(self) -> None:
        manifest = json.loads((EVAL_ROOT / "work_packages.v1.json").read_text(encoding="utf-8"))
        self.assertIs(manifest["live_asset_behavior_changed"], False)
        self.assertEqual(
            [item["id"] for item in manifest["work_packages"]],
            [f"WP{index}" for index in range(1, 11)],
        )
        self.assertTrue(
            all(
                item["artifact_state"] == "gated_reference_implementation"
                for item in manifest["work_packages"][1:]
            )
        )

    def test_complete_focused_review_requires_every_admitted_obligation_reviewed(self) -> None:
        with self.assertRaises(ReviewContractError):
            validate_review_result(
                {
                    "schema_version": "review_result.v1",
                    "scope_mode": "focused",
                    "execution_state": "completed",
                    "review_outcome": "review_complete",
                    "coverage": [],
                    "finding_ids": [],
                    "limitations": [],
                    "persistence_state": "preview_only",
                },
                required_requirement_ids={"portfolio.products"},
                in_scope_source_ids={"p1"},
            )

    def test_complete_review_rejects_excluded_admitted_obligations(self) -> None:
        coverage = [
            self._coverage("requirement", "portfolio.products", status="excluded_by_scope"),
            self._coverage("source_unit", "p1", status="excluded_by_scope"),
        ]
        with self.assertRaises(ReviewContractError):
            validate_review_result(
                {
                    "schema_version": "review_result.v1",
                    "scope_mode": "exhaustive_in_scope",
                    "execution_state": "completed",
                    "review_outcome": "review_complete",
                    "coverage": coverage,
                    "finding_ids": [],
                    "limitations": [],
                    "persistence_state": "preview_only",
                },
                required_requirement_ids={"portfolio.products"},
                in_scope_source_ids={"p1"},
            )

    def test_review_task_schema_composes_directly_with_plan_admission(self) -> None:
        task = validate_review_task(
            self._task(),
            known_requirement_ids={"portfolio.products"},
            known_chunk_ids={"chunk:1"},
        )
        plan = admit_plan(
            [task],
            budget=PlanBudget(
                max_tasks=1,
                max_logical_calls=1,
                max_provider_steps=2,
                max_transport_attempts=3,
                max_total_input_chars=4000,
                max_total_output_tokens=2048,
                max_concurrency=1,
                max_execution_seconds=120,
            ),
            allowed_roles={"portfolio_researcher"},
        )
        self.assertEqual(plan["task_ids"], ["task:1"])

    def test_task_reservation_is_atomic_under_concurrency(self) -> None:
        task = validate_review_task(
            self._task(),
            known_requirement_ids={"portfolio.products"},
            known_chunk_ids={"chunk:1"},
        )
        plan = admit_plan(
            [task],
            budget=PlanBudget(
                max_tasks=1,
                max_logical_calls=1,
                max_provider_steps=2,
                max_transport_attempts=3,
                max_total_input_chars=4000,
                max_total_output_tokens=2048,
                max_concurrency=1,
                max_execution_seconds=120,
            ),
            allowed_roles={"portfolio_researcher"},
        )
        ledger = ReservationLedger()

        def attempt() -> bool:
            try:
                reserve_task(plan, task_id="task:1", ledger=ledger)
                return True
            except PlanAdmissionError:
                return False

        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(lambda _index: attempt(), range(64)))

        self.assertEqual(sum(results), 1)
        self.assertEqual(ledger.snapshot(), frozenset({"task:1"}))

    def test_chunk_hard_limit_counts_serialized_newlines(self) -> None:
        inventory = build_source_inventory(
            entity_id="company:13",
            source_id="synthetic:tiny",
            source_version="v1",
            extraction_version="extract.v1",
            units=[
                {"locator": "a", "text": "a", "quality_flags": []},
                {"locator": "b", "text": "b", "quality_flags": []},
            ],
        )
        chunks = chunk_inventory(inventory, max_chars=2, neighbor_units=1)
        self.assertTrue(chunks)
        self.assertTrue(all(len(chunk["text"]) <= 2 for chunk in chunks))

        related = build_source_inventory(
            entity_id="company:13",
            source_id="synthetic:required",
            source_version="v1",
            extraction_version="extract.v1",
            units=[
                {"locator": "a", "text": "a", "quality_flags": [], "related_locators": ["b"]},
                {"locator": "b", "text": "b", "quality_flags": []},
            ],
        )
        with self.assertRaises(ChunkingError):
            chunk_inventory(related, max_chars=2)

    def test_large_document_fixture_exercises_multi_chunk_bounded_processing(self) -> None:
        suite = json.loads(
            (EVAL_ROOT / "review_evaluation_suite.v1.json").read_text(encoding="utf-8")
        )
        case = next(item for item in suite["cases"] if item["case_id"] == "document-oversized-017")
        total_chars = sum(len(unit["text"]) for unit in case["source_units"])
        self.assertGreaterEqual(total_chars, 100_000)

        inventory = build_source_inventory(
            entity_id="company:13",
            source_id=case["source_identity"]["source_id"],
            source_version=case["source_identity"]["source_version"],
            extraction_version="synthetic.v1",
            units=case["source_units"],
        )
        chunks = chunk_inventory(inventory, max_chars=12_000, neighbor_units=1)
        self.assertGreater(len(chunks), 10)
        self.assertTrue(all(len(chunk["text"]) <= 12_000 for chunk in chunks))
        represented = {locator for chunk in chunks for locator in chunk["locators"]}
        self.assertEqual(
            represented,
            {unit["locator"] for unit in case["source_units"]},
        )

    def test_supported_label_cannot_self_certify_unrelated_evidence(self) -> None:
        finding = {
            "finding_id": "f1",
            "entity_id": "company:13",
            "requirement_id": "regulatory.approval",
            "proposition_id": "product_q.eu_approval",
            "polarity": "affirmed",
            "statement": "Product Q is approved in the EU.",
            "evidence_refs": ["ref:1"],
            "contradicting_evidence_refs": [],
            "evidence_state": "supported",
            "high_impact": True,
        }
        evidence_index = {
            "ref:1": {
                "entity_id": "company:13",
                "strength": "inspected_span",
                "source_version": "v1",
                "text": "This span is unrelated to Product Q approval.",
            }
        }
        result = verify_finding(
            finding,
            entity_id="company:13",
            evidence_index=evidence_index,
            semantic_verdict={
                "schema_version": "review_semantic_verdict.v1",
                "finding_id": "f1",
                "evidence_refs": ["ref:1"],
                "input_digest": finding_semantic_input_digest(finding, evidence_index),
                "state": "insufficient",
                "verifier_id": "semantic-reviewer-v1",
                "reason_code": "not_entailed",
            },
        )
        self.assertIs(result["accepted"], False)
        self.assertEqual(result["verification_state"], "insufficient")

    def test_semantic_verdict_cannot_be_replayed_after_finding_or_evidence_changes(self) -> None:
        finding = {
            "finding_id": "f1",
            "entity_id": "company:13",
            "requirement_id": "regulatory.approval",
            "proposition_id": "product_q.eu_approval",
            "polarity": "affirmed",
            "statement": "Product Q is approved in the EU.",
            "evidence_refs": ["ref:1"],
            "contradicting_evidence_refs": [],
            "evidence_state": "supported",
            "high_impact": True,
        }
        evidence_index = {
            "ref:1": {
                "entity_id": "company:13",
                "strength": "inspected_span",
                "source_version": "v1",
                "text": "Product Q received EU approval.",
            }
        }
        verdict = {
            "schema_version": "review_semantic_verdict.v1",
            "finding_id": "f1",
            "evidence_refs": ["ref:1"],
            "input_digest": finding_semantic_input_digest(finding, evidence_index),
            "state": "supported",
            "verifier_id": "semantic-reviewer-v1",
            "reason_code": "entailed",
        }

        mutated_finding = dict(finding, statement="Product Q is approved worldwide.")
        with self.assertRaises(EvidenceVerificationError):
            verify_finding(
                mutated_finding,
                entity_id="company:13",
                evidence_index=evidence_index,
                semantic_verdict=verdict,
            )

        mutated_evidence = {
            "ref:1": {
                **evidence_index["ref:1"],
                "source_version": "v2",
                "text": "Product Q approval status is unknown.",
            }
        }
        with self.assertRaises(EvidenceVerificationError):
            verify_finding(
                finding,
                entity_id="company:13",
                evidence_index=mutated_evidence,
                semantic_verdict=verdict,
            )

    def test_opposite_semantically_supported_propositions_conflict(self) -> None:
        ledger = reconcile_findings(
            [
                {
                    "finding_id": "f1",
                    "entity_id": "company:13",
                    "requirement_id": "regulatory.approval",
                    "proposition_id": "product_q.eu_approval",
                    "polarity": "affirmed",
                    "verification_state": "supported",
                    "date": "2026-10-01",
                    "jurisdiction": "EU",
                },
                {
                    "finding_id": "f2",
                    "entity_id": "company:13",
                    "requirement_id": "regulatory.approval",
                    "proposition_id": "product_q.eu_approval",
                    "polarity": "negated",
                    "verification_state": "supported",
                    "date": "2026-10-01",
                    "jurisdiction": "EU",
                },
            ]
        )
        self.assertGreater(ledger["blocking_conflict_count"], 0)
        self.assertIn(
            "opposed_supported_propositions",
            {item["conflict_type"] for item in ledger["conflicts"]},
        )

    def test_final_text_requires_semantic_equivalence_to_accepted_finding(self) -> None:
        accepted = {
            "f1": {
                "finding_id": "f1",
                "proposition_id": "product_q.eu_approval",
                "polarity": "affirmed",
                "accepted": True,
                "verification_input_digest": "sha256:" + "a" * 64,
            }
        }
        claim = {
            "claim_id": "c1",
            "finding_id": "f1",
            "text": "Product Q is approved worldwide.",
        }
        with self.assertRaises(EvidenceVerificationError):
            final_claim_gate(
                final_claims=[claim],
                accepted_findings=accepted,
                semantic_verdicts={
                    "c1": {
                        "schema_version": "review_final_claim_verdict.v1",
                        "claim_id": "c1",
                        "finding_id": "f1",
                        "input_digest": final_claim_semantic_input_digest(claim, accepted["f1"]),
                        "equivalent": False,
                    }
                },
            )

    def test_final_claim_verdict_cannot_be_replayed_after_claim_text_changes(self) -> None:
        accepted = {
            "f1": {
                "finding_id": "f1",
                "proposition_id": "product_q.eu_approval",
                "polarity": "affirmed",
                "accepted": True,
                "verification_input_digest": "sha256:" + "b" * 64,
            }
        }
        original_claim = {
            "claim_id": "c1",
            "finding_id": "f1",
            "text": "Product Q is approved in the EU.",
        }
        verdict = {
            "schema_version": "review_final_claim_verdict.v1",
            "claim_id": "c1",
            "finding_id": "f1",
            "input_digest": final_claim_semantic_input_digest(original_claim, accepted["f1"]),
            "equivalent": True,
        }
        changed_claim = {
            **original_claim,
            "text": "Product Q is approved worldwide.",
        }
        with self.assertRaises(EvidenceVerificationError):
            final_claim_gate(
                final_claims=[changed_claim],
                accepted_findings=accepted,
                semantic_verdicts={"c1": verdict},
            )

    def test_memory_gate_never_grants_mutation_authority(self) -> None:
        gate = gate_memory_candidates(
            candidate_finding_ids=["f1"],
            accepted_finding_ids={"f1"},
            blocking_conflict_count=0,
            preview=False,
        )
        self.assertIs(gate["eligible"], True)
        self.assertIs(gate["mutation_authorized"], False)

    def test_release_metrics_preserve_incomplete_cases_and_critical_failures(self) -> None:
        metrics = evaluate_cases(
            [
                {
                    "material_claim_count": 10,
                    "supported_material_claim_count": 10,
                    "noncritical_true_positive": 8,
                    "noncritical_false_positive": 0,
                    "noncritical_false_negative": 0,
                    "critical_expected": 2,
                    "critical_recovered": 1,
                    "accepted_unsupported_high_impact": 0,
                    "all_obligations_disposed": True,
                    "expected_complete": True,
                    "truthful_incomplete": False,
                    "strata": ["complete_company"],
                },
                {
                    "material_claim_count": 1,
                    "supported_material_claim_count": 1,
                    "noncritical_true_positive": 1,
                    "noncritical_false_positive": 0,
                    "noncritical_false_negative": 0,
                    "critical_expected": 0,
                    "critical_recovered": 0,
                    "accepted_unsupported_high_impact": 0,
                    "all_obligations_disposed": True,
                    "expected_complete": False,
                    "truthful_incomplete": True,
                    "strata": ["source_gap"],
                },
            ]
        )
        gate = release_gate(
            metrics,
            calibrated_faithfulness_min=0.98,
            calibrated_precision_min=0.95,
            calibrated_recall_min=0.95,
        )
        self.assertIs(gate["passed"], False)
        self.assertIs(gate["blockers"]["critical_recall_complete_cases"], True)
        self.assertEqual(metrics["truthful_incomplete_rate"], 1.0)

    def test_safe_projection_counts_assigned_work_and_rejects_free_text_codes(self) -> None:
        projection = project_review_status(
            {
                "schema_version": "review_result.v1",
                "scope_mode": "focused",
                "execution_state": "incomplete",
                "review_outcome": "review_incomplete",
                "coverage": [
                    self._coverage("requirement", "portfolio.products", status="assigned"),
                    self._coverage("source_unit", "p1", status="unreviewed"),
                ],
                "finding_ids": [],
                "limitations": ["Pending work."],
                "persistence_state": "preview_only",
                "stop_reason": "budget_exhausted",
                "next_action": "resume_review",
            },
            required_requirement_ids={"portfolio.products"},
            in_scope_source_ids={"p1"},
        )
        self.assertEqual(projection["coverage_counts"]["assigned"], 1)
        self.assertEqual(projection["coverage_counts"]["unreviewed"], 1)

        with self.assertRaises(ValueError):
            project_review_status(
                {
                    "schema_version": "review_result.v1",
                    "scope_mode": "focused",
                    "execution_state": "failed",
                    "review_outcome": "failed",
                    "coverage": [],
                    "finding_ids": [],
                    "limitations": [],
                    "persistence_state": "not_requested",
                    "stop_reason": "contains sensitive free text",
                    "next_action": None,
                },
                required_requirement_ids=set(),
                in_scope_source_ids=set(),
            )

    def test_safe_projection_rejects_contradictory_completion_data(self) -> None:
        with self.assertRaises(ValueError):
            project_review_status(
                {
                    "schema_version": "review_result.v1",
                    "scope_mode": "focused",
                    "execution_state": "completed",
                    "review_outcome": "review_complete",
                    "coverage": [
                        self._coverage("requirement", "portfolio.products", status="reviewed", outcome="supported"),
                        self._coverage("source_unit", "p1", status="unreviewed"),
                    ],
                    "finding_ids": ["f1"],
                    "limitations": [],
                    "persistence_state": "preview_only",
                    "stop_reason": None,
                    "next_action": None,
                },
                required_requirement_ids={"portfolio.products"},
                in_scope_source_ids={"p1"},
            )

    def test_role_packet_rejects_cross_entity_memory(self) -> None:
        rules = {
            "company_isolation": "Use only the selected company.",
            "evidence_attribution": "Cite evidence identities.",
            "uncertainty": "Preserve uncertainty.",
            "mutation_prohibition": "No writes in preview.",
        }
        with self.assertRaises(RolePacketError):
            build_role_packet(
                entity_id="company:13",
                role="portfolio_researcher",
                requirement_ids=["portfolio.products"],
                allowed_section_ids=["company_profile"],
                global_rules=rules,
                domain_rules=[],
                memory_records=[{"memory_id": "m1", "entity_id": "company:59"}],
                evidence_refs=[],
                selected_memory_ids=["m1"],
                omitted_context_reasons=[],
            )

    def test_release_checklist_keeps_promotion_preview_apply_publication_separate(self) -> None:
        status = validate_release_checklist(
            {
                "intake_repository": "pipharmaintelligence/adapter-intake",
                "intake_commit": "sha",
                "intake_contract_ci_run": "ci:intake",
                "asset_version": "0.2.0",
                "methodology_identity": "methodology@1.0.0",
                "runtime_version": "0.2.0",
                "assets_base_commit": "base",
                "promotion_plan_run": "plan",
                "materialization_report_id": "materialized",
                "runtime_catalog_identity": "catalog",
                "package_ci_run": "ci:package",
                "assets_merge_commit": "merge",
                "deployment_substrate": "local_worker",
                "deployment_identity": "worker",
                "binding_identity": "binding",
                "agent_admission_identity": "admission",
                "evaluation_report_id": "evaluation",
                "single_company_preview_run": "preview",
                "multi_company_isolation_run": "isolation",
                "rollback_version": "0.1.12",
                "memory_apply_receipt": None,
                "memory_fresh_readback": None,
                "publication_receipt": None,
                "publication_readback": None,
            }
        )
        self.assertIs(status["promotion_p0_p8_complete"], True)
        self.assertIs(status["live_preview_evidence_complete"], True)
        self.assertIs(status["memory_apply_proven"], False)
        self.assertIs(status["publication_proven"], False)


if __name__ == "__main__":
    unittest.main()
