from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
EVAL_ROOT = HERE / "evaluation"
REF_ROOT = EVAL_ROOT / "reference"
sys.path.insert(0, str(REF_ROOT))

from evidence_verification import EvidenceVerificationError, final_claim_gate, verify_finding
from finite_plan import PlanAdmissionError, PlanBudget, admit_plan, reserve_task
from reconciliation import gate_memory_candidates, reconcile_findings
from release_checklist import validate_release_checklist
from release_evaluation import evaluate_cases, release_gate
from review_contracts import (
    ReviewContractError,
    validate_coverage_entry,
    validate_finding,
    validate_methodology_requirement,
    validate_review_result,
    validate_review_task,
    validate_source_chunk,
    validate_source_snapshot,
)
from role_packets import RolePacketError, assert_formatter_packet_minimal, build_role_packet
from safe_projection import project_review_status
from source_chunks import ChunkingError, build_source_inventory, chunk_inventory


class SpecializedReviewReferenceTests(unittest.TestCase):
    def test_work_package_manifest_covers_wp1_through_wp10_without_live_activation(self) -> None:
        manifest = json.loads((EVAL_ROOT / "work_packages.v1.json").read_text(encoding="utf-8"))
        self.assertIs(manifest["live_asset_behavior_changed"], False)
        self.assertEqual(
            [item["id"] for item in manifest["work_packages"]],
            [f"WP{index}" for index in range(1, 11)],
        )
        self.assertEqual(
            manifest["work_packages"][0]["artifact_state"],
            "implemented_evaluation_infrastructure",
        )
        self.assertTrue(
            all(
                item["artifact_state"] == "gated_reference_implementation"
                for item in manifest["work_packages"][1:]
            )
        )

    def test_wp2_contracts_keep_reviewed_separate_from_supported(self) -> None:
        snapshot = validate_source_snapshot(
            {
                "schema_version": "review_source_snapshot.v1",
                "entity_id": "company:13",
                "source_id": "synthetic:doc",
                "source_version": "v1",
                "source_hash": "abc123",
                "extraction_version": "extract.v1",
                "scope_mode": "exhaustive_in_scope",
                "inventory_ids": ["p1"],
                "inaccessible_ids": [],
            }
        )
        chunk = validate_source_chunk(
            {
                "schema_version": "review_source_chunk.v1",
                "chunk_id": "chunk:1",
                "snapshot_id": "synthetic:doc@v1",
                "entity_id": "company:13",
                "source_hash": "abc123",
                "chunk_digest": "digest1",
                "locators": ["p1"],
                "text": "Evidence text.",
                "quality_flags": [],
                "context_only_locators": [],
            },
            snapshot=snapshot,
        )
        requirement = validate_methodology_requirement(
            {
                "schema_version": "review_requirement.v1",
                "methodology_ref": "nusaibah.pharma-intelligence-methodology",
                "methodology_version": "1.0.0",
                "methodology_digest": "sha256:test",
                "requirement_id": "regulatory.approval",
                "role": "regulatory_risk_researcher",
                "risk_class": "high",
                "mandatory": True,
                "applicability_rule": "always",
                "expected_evidence_class": "authoritative_regulatory_source",
                "acceptance_criterion": "Jurisdiction and date aligned.",
            }
        )
        validate_review_task(
            {
                "schema_version": "review_task.v1",
                "run_id": "run:1",
                "entity_id": "company:13",
                "task_id": "task:1",
                "role": "regulatory_risk_researcher",
                "requirement_ids": [requirement["requirement_id"]],
                "chunk_ids": [chunk["chunk_id"]],
                "memory_ref_ids": [],
                "output_schema": "review_finding.v1",
                "logical_call_budget": 1,
                "provider_step_budget": 2,
                "transport_attempt_budget": 6,
            },
            known_requirement_ids={requirement["requirement_id"]},
            known_chunk_ids={chunk["chunk_id"]},
        )
        finding = validate_finding(
            {
                "schema_version": "review_finding.v1",
                "finding_id": "finding:1",
                "entity_id": "company:13",
                "requirement_id": requirement["requirement_id"],
                "section_id": "regulatory_clinical_risk_signals",
                "statement": "Approval evidence is insufficient.",
                "evidence_refs": ["p1"],
                "contradicting_evidence_refs": [],
                "evidence_state": "insufficient",
                "evidence_strength": "inspected_span",
                "observed_or_inferred": "observed",
                "date": None,
                "jurisdiction": "EU",
                "high_impact": True,
                "verification_reason": "Source does not establish approval.",
            },
            known_requirement_ids={requirement["requirement_id"]},
            known_evidence_refs={"p1"},
        )
        self.assertEqual(finding["evidence_state"], "insufficient")

        coverage = validate_coverage_entry(
            {
                "schema_version": "review_coverage.v1",
                "obligation_type": "requirement",
                "obligation_id": requirement["requirement_id"],
                "status": "reviewed",
                "outcome": "insufficient",
                "reason": "Reviewed but not supported.",
                "task_ids": ["task:1"],
            }
        )
        self.assertEqual(coverage["status"], "reviewed")
        self.assertEqual(coverage["outcome"], "insufficient")

        with self.assertRaises(ReviewContractError):
            validate_review_result(
                {
                    "schema_version": "review_result.v1",
                    "scope_mode": "exhaustive_in_scope",
                    "execution_state": "completed",
                    "review_outcome": "review_complete",
                    "coverage": [
                        coverage,
                        {
                            "schema_version": "review_coverage.v1",
                            "obligation_type": "source_unit",
                            "obligation_id": "p1",
                            "status": "unreviewed",
                            "outcome": None,
                            "reason": "Budget ended.",
                            "task_ids": [],
                        },
                    ],
                    "finding_ids": [],
                    "limitations": ["Source unit p1 remains unreviewed."],
                    "persistence_state": "preview_only",
                },
                required_requirement_ids={requirement["requirement_id"]},
                in_scope_source_ids={"p1"},
            )

    def test_wp3_role_packet_rejects_cross_company_memory_and_raw_formatter_payload(self) -> None:
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
                memory_records=[{"memory_id": "m1", "entity_id": "company:99"}],
                evidence_refs=["e1"],
                selected_memory_ids=["m1"],
                omitted_context_reasons=[],
            )

        packet = build_role_packet(
            entity_id="company:13",
            role="portfolio_researcher",
            requirement_ids=["portfolio.products"],
            allowed_section_ids=["company_profile"],
            global_rules=rules,
            domain_rules=["Preserve product status qualifiers."],
            memory_records=[{"memory_id": "m1", "entity_id": "company:13", "text": "Known fact."}],
            evidence_refs=["e1"],
            selected_memory_ids=["m1"],
            omitted_context_reasons=["Commercial-only memory omitted."],
        )
        with self.assertRaises(RolePacketError):
            assert_formatter_packet_minimal(
                role_packet=packet,
                evidence_notes=["Bounded note."],
                raw_search_payload_present=True,
            )

    def test_wp4_inventory_and_chunks_account_for_accessible_and_inaccessible_units(self) -> None:
        inventory = build_source_inventory(
            entity_id="company:13",
            source_id="synthetic:doc",
            source_version="v1",
            extraction_version="extract.v1",
            units=[
                {"locator": "p1", "kind": "paragraph", "text": "Definition.", "quality_flags": []},
                {"locator": "p2", "kind": "table", "text": "Header | Value", "quality_flags": ["table_header"]},
                {"locator": "p3", "kind": "paragraph", "text": "", "quality_flags": ["ocr_failed"]},
            ],
        )
        chunks = chunk_inventory(inventory, max_chars=100, neighbor_units=1)
        represented = {locator for chunk in chunks for locator in chunk["locators"]}
        self.assertIn("p1", represented)
        self.assertIn("p2", represented)
        self.assertNotIn("p3", represented)
        with self.assertRaises(ChunkingError):
            chunk_inventory(inventory, max_chars=2, neighbor_units=0)

    def test_wp5_finite_plan_counts_tasks_steps_attempts_and_reservations(self) -> None:
        tasks = [
            {
                "task_id": "task:1",
                "role": "portfolio_researcher",
                "provider_step_budget": 2,
                "transport_attempt_budget": 6,
                "input_char_budget": 1000,
            },
            {
                "task_id": "task:2",
                "role": "regulatory_risk_researcher",
                "provider_step_budget": 2,
                "transport_attempt_budget": 6,
                "input_char_budget": 1200,
            },
        ]
        plan = admit_plan(
            tasks,
            budget=PlanBudget(
                max_tasks=2,
                max_provider_steps=4,
                max_transport_attempts=12,
                max_total_input_chars=2500,
            ),
            allowed_roles={"portfolio_researcher", "regulatory_risk_researcher"},
        )
        self.assertEqual(plan["task_count"], 2)
        reservations: set[str] = set()
        reserve_task(plan, task_id="task:1", reservations=reservations)
        with self.assertRaises(PlanAdmissionError):
            reserve_task(plan, task_id="task:1", reservations=reservations)

    def test_wp6_evidence_gate_blocks_reference_only_high_impact_support_and_new_final_claims(self) -> None:
        finding = {
            "finding_id": "f1",
            "entity_id": "company:13",
            "evidence_refs": ["ref:1"],
            "contradicting_evidence_refs": [],
            "evidence_state": "supported",
            "high_impact": True,
            "verification_reason": "Candidate support.",
        }
        result = verify_finding(
            finding,
            entity_id="company:13",
            evidence_index={
                "ref:1": {"entity_id": "company:13", "strength": "reference_only"}
            },
        )
        self.assertIs(result["accepted"], False)
        self.assertEqual(result["verification_state"], "insufficient")
        with self.assertRaises(EvidenceVerificationError):
            final_claim_gate(
                final_claim_refs=["f2"],
                accepted_finding_ids={"f1"},
            )

    def test_wp7_reconciliation_preserves_conflicts_and_never_authorizes_mutation(self) -> None:
        findings = [
            {
                "finding_id": "f1",
                "entity_id": "company:13",
                "requirement_id": "commercial.launch",
                "date": "2026-01",
                "jurisdiction": "JO",
                "evidence_state": "supported",
            },
            {
                "finding_id": "f2",
                "entity_id": "company:13",
                "requirement_id": "commercial.launch",
                "date": "2026-01",
                "jurisdiction": "JO",
                "evidence_state": "contradicted",
            },
        ]
        ledger = reconcile_findings(findings)
        self.assertEqual(ledger["blocking_conflict_count"], 1)
        gate = gate_memory_candidates(
            candidate_finding_ids=["f1"],
            accepted_finding_ids=set(ledger["accepted_finding_ids"]),
            blocking_conflict_count=ledger["blocking_conflict_count"],
            preview=True,
        )
        self.assertIs(gate["eligible"], False)
        self.assertIs(gate["mutation_authorized"], False)

    def test_wp8_release_metrics_do_not_hide_critical_failures(self) -> None:
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
                }
            ]
        )
        gate = release_gate(
            metrics,
            calibrated_faithfulness_min=0.98,
            calibrated_precision_min=0.95,
            calibrated_recall_min=0.95,
        )
        self.assertIs(gate["passed"], False)
        self.assertIs(gate["blockers"]["critical_recall"], True)

    def test_wp9_projection_is_value_safe_and_keeps_persistence_separate(self) -> None:
        projection = project_review_status(
            {
                "scope_mode": "exhaustive_in_scope",
                "execution_state": "incomplete",
                "review_outcome": "review_incomplete",
                "coverage": [
                    {"status": "reviewed"},
                    {"status": "inaccessible"},
                ],
                "finding_ids": ["f1"],
                "limitations": ["One inaccessible unit."],
                "persistence_state": "preview_only",
                "stop_reason": "source_gap",
                "next_action": "provide_better_source",
                "raw_prompt": "must not project",
                "raw_source_text": "must not project",
            }
        )
        self.assertEqual(projection["coverage_counts"]["inaccessible"], 1)
        self.assertIs(projection["raw_content_included"], False)
        self.assertNotIn("raw_prompt", projection)
        self.assertNotIn("raw_source_text", projection)
        self.assertEqual(projection["persistence_state"], "preview_only")

    def test_wp10_release_checklist_does_not_conflate_preview_apply_and_publication(self) -> None:
        status = validate_release_checklist(
            {
                "intake_commit": "abc",
                "asset_version": "0.2.0",
                "runtime_version": "0.2.0",
                "assets_promotion_commit": "def",
                "package_ci_passed": True,
                "binding_identity": "binding:1",
                "agent_admission_identity": "admission:1",
                "evaluation_report_id": "eval:1",
                "single_company_preview_run": "run:1",
                "multi_company_isolation_run": "run:2",
                "rollback_version": "0.1.12",
                "memory_apply_receipt": None,
                "memory_fresh_readback": None,
                "publication_receipt": None,
                "publication_readback": None,
            }
        )
        self.assertIs(status["merge_ready_evidence_complete"], True)
        self.assertIs(status["memory_apply_proven"], False)
        self.assertIs(status["publication_proven"], False)


if __name__ == "__main__":
    unittest.main()
