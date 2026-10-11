from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
import sys
import unittest


ASSET_ROOT = Path(__file__).resolve().parents[1]
if str(ASSET_ROOT) not in sys.path:
    sys.path.insert(0, str(ASSET_ROOT))

from research_claim_evidence_v0_1_21 import (  # noqa: E402
    RESEARCH_ROLES,
    accepted_claims_for_downstream,
    merge_role_claim_evidence,
    project_role_claim_evidence,
    qualified_claim_id,
)


ROLE_CATALOG = ASSET_ROOT / "pharma_roles_v0_1_21.json"
ACCEPTANCE = ASSET_ROOT / "materialization_promotion_acceptance_v0_1_21.json"
ADAPTER_YAML = ASSET_ROOT / "adapter.yaml"
MANIFEST = ASSET_ROOT / "nusaibah_pharma_company_intelligence_lab.asset.json"


@dataclass(frozen=True)
class Citation:
    locator: str
    title: str | None
    source_kind: str = "agent_citation"
    provider_family: str | None = "vertex_ai"


def _yaml_lists(path: Path) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    current: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not raw.startswith(" ") and stripped.endswith(":"):
            current = stripped[:-1]
            result.setdefault(current, [])
            continue
        if current is not None and stripped.startswith("- "):
            result[current].append(stripped[2:].strip())
        elif not raw.startswith(" "):
            current = None
    return result


def _claim(local_id: str, section_id: str, locator: str) -> dict[str, object]:
    return {
        "claim_id": local_id,
        "section_id": section_id,
        "statement": f"Statement for {local_id}",
        "evidence_kind": "grounded_external",
        "inference": False,
        "citation_locators": [locator],
        "evidence_qualifiers": [],
    }


def _payload(role: str, claims: list[dict[str, object]]) -> dict[str, object]:
    return {
        "role": role,
        "claims": claims,
    }


class PharmaRolePromotionContractTest(unittest.TestCase):
    def test_adapter_declares_modular_helpers_and_reviewed_support(self) -> None:
        declared = _yaml_lists(ADAPTER_YAML)
        self.assertTrue(
            {
                "claim_evidence_contract_v0_1_21.py",
                "research_claim_evidence_v0_1_21.py",
                "memory_citation_selection_v0_1_21.py",
            }.issubset(set(declared["reviewed_helpers"]))
        )
        self.assertEqual(
            {
                "pharma_roles_v0_1_21.json",
                "materialization_promotion_acceptance_v0_1_21.json",
            },
            set(declared["reviewed_support_files"]),
        )

    def test_role_catalog_matches_manifest_and_docstring(self) -> None:
        catalog = json.loads(ROLE_CATALOG.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        active = manifest["versions"][manifest["default"]]
        catalog_roles = [item["role"] for item in catalog["roles"]]
        manifest_roles = list(active["agents"])

        self.assertEqual(manifest_roles, catalog_roles)
        self.assertEqual("0.1.21", catalog["target_asset_version"])
        self.assertEqual(set(RESEARCH_ROLES), {
            item["role"]
            for item in catalog["roles"]
            if item["claim_evidence_owner"]
        })
        self.assertEqual(set(RESEARCH_ROLES), {
            item["role"]
            for item in catalog["roles"]
            if item["search_authority"]
        })
        self.assertFalse(any(item["mutation_authority"] for item in catalog["roles"]))

        module = importlib.import_module("research_claim_evidence_v0_1_21")
        docstring = module.__doc__ or ""
        for role in catalog_roles:
            self.assertIn(role, docstring)

    def test_materialization_and_promotion_acceptance_are_explicit(self) -> None:
        contract = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
        self.assertEqual(
            "pharma_materialization_promotion_acceptance.v1",
            contract["schema_version"],
        )
        self.assertEqual("0.1.21", contract["target_asset_version"])
        self.assertEqual(
            {f"M{index:02d}" for index in range(1, 11)},
            {item["id"] for item in contract["materialization"]["required_checks"]},
        )
        self.assertEqual(
            {f"P{index:02d}" for index in range(1, 11)},
            {item["id"] for item in contract["promotion"]["required_checks"]},
        )
        later = set(contract["promotion"]["separate_later_proofs"])
        self.assertIn("official_runtime_delivery", later)
        self.assertIn("capability_admission", later)
        self.assertIn("fresh_dynamic_skill_readback_and_history", later)

    def test_role_projection_qualifies_ids_and_withholds_only_bad_claim(self) -> None:
        citation = Citation("https://evidence.example/portfolio", "Portfolio")
        projection = project_role_claim_evidence(
            role="portfolio_researcher",
            pass_number=1,
            payload=_payload(
                "portfolio_researcher",
                [
                    _claim("accepted", "company_profile", citation.locator),
                    _claim(
                        "withheld",
                        "product_portfolio_intelligence",
                        "https://evidence.example/missing",
                    ),
                ],
            ),
            citations=[citation],
        )

        accepted_id = qualified_claim_id("portfolio_researcher", "accepted")
        withheld_id = qualified_claim_id("portfolio_researcher", "withheld")
        self.assertEqual((accepted_id,), tuple(
            item["claim_id"] for item in projection.accepted_claims
        ))
        self.assertEqual((withheld_id,), tuple(
            item["claim_id"] for item in projection.withheld_claims
        ))
        self.assertEqual(1, len(projection.issues))
        self.assertEqual("claim_withheld", projection.issues[0]["action"])

    def test_role_merge_preserves_canonical_role_order(self) -> None:
        sections = {
            "portfolio_researcher": "company_profile",
            "market_researcher": "markets_commercial_signals",
            "regulatory_risk_researcher": "regulatory_clinical_risk_signals",
        }
        projections = []
        for role in reversed(RESEARCH_ROLES):
            citation = Citation(f"https://evidence.example/{role}", role)
            projections.append(
                project_role_claim_evidence(
                    role=role,
                    pass_number=1,
                    payload=_payload(
                        role,
                        [_claim(f"{role}-claim", sections[role], citation.locator)],
                    ),
                    citations=[citation],
                )
            )

        merged = merge_role_claim_evidence(projections)
        accepted = accepted_claims_for_downstream(merged)
        self.assertEqual(
            list(RESEARCH_ROLES),
            [item["claim_id"].split(":", 1)[0] for item in accepted],
        )
        self.assertEqual((), merged.withheld_claims)
        self.assertEqual((), merged.issues)


if __name__ == "__main__":
    unittest.main()
