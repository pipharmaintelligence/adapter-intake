from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import unittest


ASSET_ROOT = Path(__file__).resolve().parents[1]
if str(ASSET_ROOT) not in sys.path:
    sys.path.insert(0, str(ASSET_ROOT))

from claim_evidence_contract_v0_1_21 import (  # noqa: E402
    build_claim_evidence_index,
    merge_claim_evidence_indexes,
)
from memory_citation_selection_v0_1_21 import (  # noqa: E402
    MemoryCitationSelectionError,
    require_complete_selection,
    select_memory_citations,
)


@dataclass(frozen=True)
class Citation:
    locator: str
    title: str | None
    source_kind: str = "agent_citation"
    provider_family: str | None = "vertex_ai"


def citations(role: str, count: int) -> list[Citation]:
    return [
        Citation(
            locator=f"https://evidence.example/{role}/{index}",
            title=f"{role} evidence {index}",
        )
        for index in range(1, count + 1)
    ]


def claim(
    claim_id: str,
    section_id: str,
    locators: list[str],
) -> dict[str, object]:
    return {
        "claim_id": claim_id,
        "section_id": section_id,
        "evidence_kind": "grounded_external",
        "inference": False,
        "citation_locators": locators,
        "evidence_qualifiers": [],
    }


class ClaimEvidenceSelectionTest(unittest.TestCase):
    def test_candidate_facts_get_support_before_prefix_secondary_citations(self) -> None:
        portfolio = citations("portfolio_researcher", 22)
        market = citations("market_researcher", 14)
        regulatory = citations("regulatory_risk_researcher", 12)
        evidence = merge_claim_evidence_indexes(
            [
                build_claim_evidence_index(
                    role="portfolio_researcher",
                    pass_number=1,
                    claims=[
                        claim(
                            "portfolio-fact",
                            "product_portfolio_intelligence",
                            [item.locator for item in portfolio],
                        )
                    ],
                    citations=portfolio,
                ),
                build_claim_evidence_index(
                    role="market_researcher",
                    pass_number=1,
                    claims=[
                        claim(
                            "market-fact",
                            "markets_commercial_signals",
                            [market[0].locator],
                        )
                    ],
                    citations=market,
                ),
                build_claim_evidence_index(
                    role="regulatory_risk_researcher",
                    pass_number=1,
                    claims=[
                        claim(
                            "regulatory-fact",
                            "regulatory_clinical_risk_signals",
                            [regulatory[0].locator],
                        )
                    ],
                    citations=regulatory,
                ),
            ]
        )

        selection = select_memory_citations(
            fact_ids=["portfolio-fact", "regulatory-fact"],
            evidence_index=evidence,
            maximum_citations=24,
        )

        self.assertTrue(selection.complete)
        self.assertEqual((), selection.uncovered_fact_ids)
        selected_roles = {item.role for item in selection.selected_citations}
        self.assertIn("portfolio_researcher", selected_roles)
        self.assertIn("regulatory_risk_researcher", selected_roles)
        self.assertNotIn("market_researcher", selected_roles)
        self.assertLessEqual(len(selection.selected_citations), 24)
        require_complete_selection(selection)

    def test_unknown_locator_withholds_only_affected_claim(self) -> None:
        role_citations = citations("portfolio_researcher", 2)
        index = build_claim_evidence_index(
            role="portfolio_researcher",
            pass_number=1,
            claims=[
                claim("supported", "company_profile", [role_citations[0].locator]),
                claim("withheld", "company_profile", ["https://unknown.example"]),
            ],
            citations=role_citations,
        )

        self.assertEqual(("supported",), index.accepted_claim_ids)
        self.assertEqual(("withheld",), index.withheld_claim_ids)
        self.assertEqual(
            "claim_citation_locator_not_admitted",
            index.record("withheld").issue_code,
        )

    def test_duplicate_runtime_citations_create_one_reference(self) -> None:
        citation = Citation("https://evidence.example/shared", "Shared")
        index = build_claim_evidence_index(
            role="market_researcher",
            pass_number=1,
            claims=[claim("fact", "markets_commercial_signals", [citation.locator])],
            citations=[citation, citation],
        )

        self.assertEqual(1, len(index.citations))
        self.assertEqual(1, len(index.record("fact").citation_refs))

    def test_ambiguous_locator_with_different_titles_is_withheld(self) -> None:
        first = Citation("https://evidence.example/shared", "Title A")
        second = Citation("https://evidence.example/shared", "Title B")
        index = build_claim_evidence_index(
            role="market_researcher",
            pass_number=1,
            claims=[claim("fact", "markets_commercial_signals", [first.locator])],
            citations=[first, second],
        )

        self.assertEqual(("fact",), index.withheld_claim_ids)
        self.assertEqual(
            "claim_citation_locator_ambiguous",
            index.record("fact").issue_code,
        )

    def test_same_semantic_citation_can_cover_facts_in_multiple_roles(self) -> None:
        first = Citation(
            "https://evidence.example/shared-role",
            "Shared role evidence",
            provider_family="vertex_ai",
        )
        second = Citation(
            "https://evidence.example/shared-role",
            "Shared role evidence",
            provider_family="other_provider",
        )
        evidence = merge_claim_evidence_indexes(
            [
                build_claim_evidence_index(
                    role="portfolio_researcher",
                    pass_number=1,
                    claims=[
                        claim("portfolio-fact", "company_profile", [first.locator])
                    ],
                    citations=[first],
                ),
                build_claim_evidence_index(
                    role="regulatory_risk_researcher",
                    pass_number=1,
                    claims=[
                        claim(
                            "regulatory-fact",
                            "regulatory_clinical_risk_signals",
                            [second.locator],
                        )
                    ],
                    citations=[second],
                ),
            ]
        )

        self.assertEqual(1, len(evidence.citations))
        self.assertEqual(
            evidence.record("portfolio-fact").citation_refs,
            evidence.record("regulatory-fact").citation_refs,
        )
        selection = select_memory_citations(
            fact_ids=["portfolio-fact", "regulatory-fact"],
            evidence_index=evidence,
        )
        self.assertTrue(selection.complete)
        self.assertEqual(1, len(selection.selected_citations))
        self.assertEqual(
            (("portfolio_researcher", 0), ("regulatory_risk_researcher", 0)),
            selection.omitted_counts_by_role,
        )

    def test_bound_failure_is_explicit_and_deterministic(self) -> None:
        indexes = []
        fact_ids = []
        for ordinal in range(25):
            role = f"role-{ordinal:02d}"
            citation = Citation(
                locator=f"https://evidence.example/fact/{ordinal}",
                title=f"Fact {ordinal}",
            )
            fact_id = f"fact-{ordinal:02d}"
            fact_ids.append(fact_id)
            indexes.append(
                build_claim_evidence_index(
                    role=role,
                    pass_number=1,
                    claims=[claim(fact_id, "company_profile", [citation.locator])],
                    citations=[citation],
                )
            )
        evidence = merge_claim_evidence_indexes(indexes)

        first = select_memory_citations(
            fact_ids=fact_ids,
            evidence_index=evidence,
            maximum_citations=24,
        )
        second = select_memory_citations(
            fact_ids=fact_ids,
            evidence_index=evidence,
            maximum_citations=24,
        )

        self.assertFalse(first.complete)
        self.assertEqual(("fact-24",), first.uncovered_fact_ids)
        self.assertEqual(24, len(first.selected_citations))
        self.assertEqual(first.selection_digest, second.selection_digest)
        with self.assertRaisesRegex(
            MemoryCitationSelectionError,
            "memory_evidence_selection_incomplete",
        ):
            require_complete_selection(first)

    def test_review_and_apply_consumers_receive_same_selection_digest(self) -> None:
        role_citations = citations("regulatory_risk_researcher", 3)
        index = build_claim_evidence_index(
            role="regulatory_risk_researcher",
            pass_number=1,
            claims=[
                claim(
                    "regulatory-fact",
                    "regulatory_clinical_risk_signals",
                    [item.locator for item in role_citations],
                )
            ],
            citations=role_citations,
        )

        review_selection = select_memory_citations(
            fact_ids=["regulatory-fact"],
            evidence_index=index,
        )
        apply_selection = select_memory_citations(
            fact_ids=["regulatory-fact"],
            evidence_index=index,
        )

        self.assertEqual(
            review_selection.selection_digest,
            apply_selection.selection_digest,
        )
        self.assertEqual(
            review_selection.public_citations(),
            apply_selection.public_citations(),
        )


if __name__ == "__main__":
    unittest.main()
