from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import unittest


ASSET_ROOT = Path(__file__).resolve().parents[1]
if str(ASSET_ROOT) not in sys.path:
    sys.path.insert(0, str(ASSET_ROOT))

from claim_semantics_v0_1_21 import (  # noqa: E402
    SCHEMA_VERSION,
    ClaimSemanticContractError,
    validate_claim_semantic_context,
)
from methodology_learning_v0_1_21 import (  # noqa: E402
    LESSONS,
    MARKER,
    MAX_TOTAL_CHARS,
    build_methodology_learning_proposal,
    reviewed_methodology_addendum,
)
from research_claim_evidence_v0_1_21 import (  # noqa: E402
    project_role_claim_evidence,
    qualified_claim_id,
)


@dataclass(frozen=True)
class Citation:
    locator: str
    title: str | None
    source_kind: str = "agent_citation"
    provider_family: str | None = "vertex_ai"


def context(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "event_date": None,
        "publication_date": None,
        "status_as_of_date": None,
        "event_state": "not_applicable",
        "observation_kind": "company_reported",
        "actor": None,
        "counterparty": None,
        "territory": None,
        "manufacturing_responsibility": None,
        "reported_total": None,
        "component_total": None,
        "remainder_label": None,
        "governed_snapshot_relation": "not_applicable",
        "entity_label_kind": "not_applicable",
    }
    value.update(overrides)
    return value


def claim(claim_id: str, semantic_context: dict[str, object]) -> dict[str, object]:
    return {
        "claim_id": claim_id,
        "section_id": "markets_commercial_signals",
        "statement": f"Bounded statement {claim_id}.",
        "evidence_kind": "grounded_external",
        "inference": False,
        "citation_locators": ["https://evidence.example/source"],
        "evidence_qualifiers": [],
        "semantic_context": semantic_context,
    }


class SemanticQualityV021Tests(unittest.TestCase):
    def test_repeated_planner_headings_do_not_make_skill_sections_ambiguous(self) -> None:
        existing = "### company_profile\nPrior verified procedure.\n"
        snapshot = "### company_profile\nNew planning procedure.\n"
        proposal = build_methodology_learning_proposal(existing, planner_snapshot=snapshot)
        self.assertTrue(proposal.candidate.startswith(existing))
        self.assertEqual(1, proposal.candidate.count("### company_profile"))
        self.assertFalse(proposal.planner_snapshot_included)
        self.assertIn(MARKER, proposal.candidate)

    def test_full_learning_budget_withholds_only_optional_proposal(self) -> None:
        existing = "x" * MAX_TOTAL_CHARS
        proposal = build_methodology_learning_proposal(existing)
        self.assertEqual(existing, proposal.candidate)
        self.assertFalse(proposal.changed)
        self.assertFalse(proposal.apply_authority)
        self.assertTrue(proposal.previous_learning_preserved)
        self.assertEqual((), proposal.rule_ids)
        self.assertEqual("methodology_learning_budget_exhausted", proposal.withheld_reason)

    def test_reviewed_learning_projection_requires_stored_known_rules(self) -> None:
        self.assertEqual("", reviewed_methodology_addendum("No learning exists."))
        proposal = build_methodology_learning_proposal("")
        projected = reviewed_methodology_addendum(proposal.candidate + "\nCompany fact must not leak.\n")
        self.assertEqual(len(LESSONS), len(projected.splitlines()))
        self.assertNotIn("Company fact", projected)
        self.assertLess(len(projected), 2400)

    def test_event_date_and_publication_date_remain_distinct(self) -> None:
        validated = validate_claim_semantic_context(
            context(
                event_date="2026-01-10",
                publication_date="2026-01-12",
                status_as_of_date="2026-01-12",
                event_state="approved",
            )
        )
        self.assertEqual("2026-01-10", validated.event_date)
        self.assertEqual("2026-01-12", validated.publication_date)
        self.assertIn("event_date_vs_publication_date", validated.rule_ids)
        self.assertIn("current_vs_historical_status", validated.rule_ids)

    def test_agreement_and_completion_have_different_required_dates(self) -> None:
        agreed = validate_claim_semantic_context(
            context(
                publication_date="2026-02-01",
                event_state="agreed",
            )
        )
        self.assertIsNone(agreed.event_date)
        self.assertIn("agreement_vs_completion", agreed.rule_ids)

        with self.assertRaises(ClaimSemanticContractError) as raised:
            validate_claim_semantic_context(
                context(
                    publication_date="2026-02-01",
                    event_state="completed",
                )
            )
        self.assertEqual("event_date_required", raised.exception.rule)

    def test_rights_direction_requires_actor_counterparty_and_territory(self) -> None:
        with self.assertRaises(ClaimSemanticContractError) as raised:
            validate_claim_semantic_context(
                context(
                    actor="Grantor",
                    counterparty="Recipient",
                )
            )
        self.assertEqual("relationship_territory_required", raised.exception.rule)

        validated = validate_claim_semantic_context(
            context(
                actor="Grantor",
                counterparty="Recipient",
                territory="Jordan",
                manufacturing_responsibility="Recipient manufactures locally.",
            )
        )
        self.assertEqual("Grantor", validated.actor)
        self.assertEqual("Recipient", validated.counterparty)
        self.assertEqual("Jordan", validated.territory)
        self.assertIn("commercial_rights_direction", validated.rule_ids)

    def test_current_status_and_later_external_update_are_as_of_bound(self) -> None:
        launched = validate_claim_semantic_context(
            context(
                event_date="2026-03-01",
                status_as_of_date="2026-03-02",
                event_state="launched",
            )
        )
        self.assertEqual("launched", launched.event_state)
        self.assertEqual("2026-03-02", launched.status_as_of_date)

        with self.assertRaises(ClaimSemanticContractError) as raised:
            validate_claim_semantic_context(
                context(governed_snapshot_relation="later_external_update")
            )
        self.assertEqual("external_update_date_required", raised.exception.rule)

        updated = validate_claim_semantic_context(
            context(
                status_as_of_date="2026-03-02",
                governed_snapshot_relation="later_external_update",
            )
        )
        self.assertIn(
            "governed_snapshot_vs_later_external_update",
            updated.rule_ids,
        )

    def test_governed_display_name_and_external_legal_name_are_distinct(self) -> None:
        governed = validate_claim_semantic_context(
            context(entity_label_kind="governed_display_name")
        )
        legal = validate_claim_semantic_context(
            context(entity_label_kind="external_legal_name")
        )
        self.assertNotEqual(governed.entity_label_kind, legal.entity_label_kind)
        self.assertIn(
            "governed_display_name_vs_external_legal_identity",
            governed.rule_ids,
        )

    def test_financial_components_require_named_remainder(self) -> None:
        with self.assertRaises(ClaimSemanticContractError) as raised:
            validate_claim_semantic_context(
                context(reported_total=3349, component_total=3309)
            )
        self.assertEqual("remainder_label_required", raised.exception.rule)

        reconciled = validate_claim_semantic_context(
            context(
                reported_total=3349,
                component_total=3309,
                remainder_label="Others",
            )
        )
        self.assertEqual(3349.0, reconciled.reported_total)
        self.assertEqual(3309.0, reconciled.component_total)
        self.assertEqual("Others", reconciled.remainder_label)
        self.assertIn("reported_total_reconciliation", reconciled.rule_ids)

    def test_potential_effect_is_not_an_observed_event(self) -> None:
        potential = validate_claim_semantic_context(
            context(observation_kind="potential_effect")
        )
        observed = validate_claim_semantic_context(
            context(observation_kind="observed_event")
        )
        self.assertNotEqual(potential.observation_kind, observed.observation_kind)
        self.assertIn("potential_harm_vs_observed_event", potential.rule_ids)

    def test_invalid_semantics_withhold_one_claim_and_preserve_sibling(self) -> None:
        citation = Citation(
            "https://evidence.example/source",
            "Evidence source",
        )
        projection = project_role_claim_evidence(
            role="market_researcher",
            pass_number=1,
            payload={
                "role": "market_researcher",
                "claims": [
                    claim("valid", context()),
                    claim(
                        "invalid",
                        context(event_state="completed"),
                    ),
                ],
            },
            citations=[citation],
        )
        self.assertEqual(
            (qualified_claim_id("market_researcher", "valid"),),
            tuple(item["claim_id"] for item in projection.accepted_claims),
        )
        self.assertEqual(
            (qualified_claim_id("market_researcher", "invalid"),),
            tuple(item["claim_id"] for item in projection.withheld_claims),
        )
        self.assertEqual("semantic_quality", projection.issues[0]["category"])
        self.assertEqual("withhold", projection.issues[0]["disposition"])

    def test_methodology_proposal_preserves_existing_lessons_and_adds_reviewed_rules(self) -> None:
        existing = "### Existing Lesson\n- preserve this exact line\n"
        planner = "### Planner Snapshot\n- bounded planner lesson\n"
        proposal = build_methodology_learning_proposal(
            existing,
            planner_snapshot=planner,
        )
        self.assertTrue(proposal.candidate.startswith(existing))
        self.assertIn(planner.strip(), proposal.candidate)
        self.assertIn(MARKER, proposal.candidate)
        self.assertTrue(proposal.previous_learning_preserved)
        self.assertTrue(proposal.planner_snapshot_included)
        self.assertFalse(proposal.apply_authority)
        self.assertEqual(
            {rule_id for rule_id, _instruction in LESSONS},
            set(proposal.rule_ids),
        )
        for rule_id in proposal.rule_ids:
            self.assertIn(f"[{rule_id}]", proposal.candidate)


if __name__ == "__main__":
    unittest.main()
