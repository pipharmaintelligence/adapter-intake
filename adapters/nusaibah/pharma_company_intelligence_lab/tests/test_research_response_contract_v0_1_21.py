from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest


ASSET_ROOT = Path(__file__).resolve().parents[1]
if str(ASSET_ROOT) not in sys.path:
    sys.path.insert(0, str(ASSET_ROOT))

from agent_contract import RESEARCH_ROLE_SECTIONS  # noqa: E402
from claim_semantics_v0_1_21 import (  # noqa: E402
    SCHEMA_VERSION as SEMANTIC_SCHEMA_VERSION,
)
from dossier_contract import SECTION_BY_ID  # noqa: E402
from research_claim_evidence_v0_1_21 import qualified_claim_id  # noqa: E402
from research_claim_pipeline_v0_1_21 import (  # noqa: E402
    research_response_contract_for_role_v0_1_21,
    validate_and_project_role_claim_evidence_v0_1_21,
)
from research_response_contract_v0_1_21 import (  # noqa: E402
    MAX_CITATION_LOCATORS_PER_CLAIM,
    MAX_EVIDENCE_QUALIFIERS_PER_CLAIM,
    RESEARCH_SCHEMA_VERSION,
    ResearchResponseContractError,
    project_repair_input_v0_1_21,
    require_repair_preserves_claim_evidence_v0_1_21,
    validate_research_payload_v0_1_21,
)


@dataclass(frozen=True)
class Citation:
    locator: str
    title: str | None
    source_kind: str = "agent_citation"
    provider_family: str | None = "vertex_ai"


def _sections(role: str) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for section_id in RESEARCH_ROLE_SECTIONS[role]:
        spec = SECTION_BY_ID[section_id]
        result.append(
            {
                "section_id": section_id,
                "content": "",
                "subsections": [
                    {
                        "subsection_id": subsection.subsection_id,
                        "content": f"Verified evidence for {subsection.subsection_id}.",
                    }
                    for subsection in spec.subsections
                ],
            }
        )
    return result


def _semantic_context(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": SEMANTIC_SCHEMA_VERSION,
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


def _claim(
    *,
    claim_id: str = "claim-1",
    section_id: str = "markets_commercial_signals",
    locator: str | None = "https://evidence.example/item",
) -> dict[str, object]:
    return {
        "claim_id": claim_id,
        "section_id": section_id,
        "statement": "The company reported one bounded commercial fact.",
        "evidence_kind": "grounded_external",
        "as_of_date": "2026-10-11",
        "confidence": "high",
        "inference": False,
        "citation_locators": [] if locator is None else [locator],
        "evidence_qualifiers": ["Company-reported; territory remains explicit."],
        "semantic_context": _semantic_context(),
    }


def _payload(
    *,
    role: str = "market_researcher",
    company_id: int = 14,
    claims: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": RESEARCH_SCHEMA_VERSION,
        "company_id": company_id,
        "role": role,
        "status": "completed",
        "sections": _sections(role),
        "claims": [_claim()] if claims is None else claims,
        "uncertainties": ["No uncertainty beyond the stated qualifier."],
    }


class ResearchResponseContractV021Tests(unittest.TestCase):
    def test_valid_payload_normalizes_evidence_without_mutating_input(self) -> None:
        value = _payload()
        claim = value["claims"][0]
        claim["citation_locators"] = ["  https://evidence.example/item  "]
        claim["evidence_qualifiers"] = [
            "  Event date   remains separate from publication date.  "
        ]
        original = deepcopy(value)

        validated = validate_research_payload_v0_1_21(
            value,
            role="market_researcher",
            company_id=14,
        )

        self.assertEqual(original, value)
        self.assertEqual(RESEARCH_SCHEMA_VERSION, validated["schema_version"])
        self.assertEqual(
            ["https://evidence.example/item"],
            validated["claims"][0]["citation_locators"],
        )
        self.assertEqual(
            ["Event date remains separate from publication date."],
            validated["claims"][0]["evidence_qualifiers"],
        )
        self.assertEqual(
            _semantic_context(),
            validated["claims"][0]["semantic_context"],
        )

    def test_missing_locator_withholds_only_affected_claim(self) -> None:
        admitted = Citation("https://evidence.example/item", "Commercial evidence")
        value = _payload(
            claims=[
                _claim(claim_id="accepted", locator=admitted.locator),
                _claim(claim_id="missing", locator=None),
            ]
        )

        validated = validate_research_payload_v0_1_21(
            value,
            role="market_researcher",
            company_id=14,
        )
        self.assertEqual([], validated["claims"][1]["citation_locators"])

        projection = validate_and_project_role_claim_evidence_v0_1_21(
            role="market_researcher",
            company_id=14,
            pass_number=1,
            payload=value,
            admitted_citations=[admitted],
        )
        self.assertEqual(
            (qualified_claim_id("market_researcher", "accepted"),),
            tuple(item["claim_id"] for item in projection.accepted_claims),
        )
        self.assertEqual(
            (qualified_claim_id("market_researcher", "missing"),),
            tuple(item["claim_id"] for item in projection.withheld_claims),
        )
        self.assertEqual("claim_citation_required", projection.issues[0]["rule"])

    def test_locator_list_remains_bounded_and_unique(self) -> None:
        duplicate = _payload()
        duplicate["claims"][0]["citation_locators"] = [
            "https://evidence.example/item",
            "https://evidence.example/item",
        ]
        with self.assertRaises(ResearchResponseContractError) as raised_duplicate:
            validate_research_payload_v0_1_21(
                duplicate,
                role="market_researcher",
                company_id=14,
            )
        self.assertEqual("duplicate", raised_duplicate.exception.proof_failure_detail["rule"])

        oversized = _payload()
        oversized["claims"][0]["citation_locators"] = [
            f"https://evidence.example/{index}"
            for index in range(MAX_CITATION_LOCATORS_PER_CLAIM + 1)
        ]
        with self.assertRaises(ResearchResponseContractError) as raised_oversized:
            validate_research_payload_v0_1_21(
                oversized,
                role="market_researcher",
                company_id=14,
            )
        self.assertEqual(
            "bounded_list_required",
            raised_oversized.exception.proof_failure_detail["rule"],
        )

    def test_payload_and_claim_shapes_are_exact(self) -> None:
        extra_payload = _payload()
        extra_payload["provider_payload"] = {"not": "allowed"}
        with self.assertRaises(ResearchResponseContractError) as payload_error:
            validate_research_payload_v0_1_21(
                extra_payload,
                role="market_researcher",
                company_id=14,
            )
        self.assertEqual("research_payload", payload_error.exception.proof_failure_detail["field"])

        extra_claim = _payload()
        extra_claim["claims"][0]["citation_id"] = "model-authored-id"
        with self.assertRaises(ResearchResponseContractError) as claim_error:
            validate_research_payload_v0_1_21(
                extra_claim,
                role="market_researcher",
                company_id=14,
            )
        self.assertEqual("claims", claim_error.exception.proof_failure_detail["field"])

    def test_provider_visible_contract_declares_evidence_and_semantic_authority(self) -> None:
        contract = research_response_contract_for_role_v0_1_21(
            role="regulatory_risk_researcher",
            company_id=14,
        )
        fields = contract["claims"]["fields"]

        self.assertEqual(0, fields["citation_locators"]["min_items"])
        self.assertEqual(
            MAX_CITATION_LOCATORS_PER_CLAIM,
            fields["citation_locators"]["max_items"],
        )
        self.assertEqual(
            MAX_EVIDENCE_QUALIFIERS_PER_CLAIM,
            fields["evidence_qualifiers"]["max_items"],
        )
        self.assertEqual(
            "must_exactly_match_runtime_admitted_citation_locator",
            fields["citation_locators"]["authority"],
        )
        self.assertEqual(
            SEMANTIC_SCHEMA_VERSION,
            fields["semantic_context"]["schema_version"],
        )
        self.assertFalse(
            contract["claim_evidence"]["model_authored_citation_ids_allowed"]
        )
        self.assertEqual(
            "claim_withheld",
            contract["claim_evidence"]["missing_locator_action"],
        )
        self.assertEqual(
            "preserve",
            contract["claim_evidence"]["valid_sibling_action"],
        )

    def test_repair_projection_keeps_declared_fields_and_omits_runtime_material(self) -> None:
        value = _payload()
        value["provider_payload"] = {"forbidden": "runtime material"}

        projected = project_repair_input_v0_1_21(value)

        self.assertNotIn("provider_payload", projected)
        self.assertEqual(
            ["https://evidence.example/item"],
            projected["claims"][0]["citation_locators"],
        )
        self.assertEqual(
            ["Company-reported; territory remains explicit."],
            projected["claims"][0]["evidence_qualifiers"],
        )
        self.assertEqual(
            _semantic_context(),
            projected["claims"][0]["semantic_context"],
        )

    def test_repair_cannot_change_locator_qualifier_or_semantic_context(self) -> None:
        original = _payload()
        repaired = validate_research_payload_v0_1_21(
            original,
            role="market_researcher",
            company_id=14,
        )
        require_repair_preserves_claim_evidence_v0_1_21(
            original,
            repaired,
            role="market_researcher",
        )

        changed_locator = deepcopy(repaired)
        changed_locator["claims"][0]["citation_locators"] = [
            "https://evidence.example/other"
        ]
        with self.assertRaises(ResearchResponseContractError) as locator_error:
            require_repair_preserves_claim_evidence_v0_1_21(
                original,
                changed_locator,
                role="market_researcher",
            )
        self.assertEqual(
            "claims.citation_locators",
            locator_error.exception.proof_failure_detail["field"],
        )

        changed_qualifier = deepcopy(repaired)
        changed_qualifier["claims"][0]["evidence_qualifiers"] = ["Stronger claim."]
        with self.assertRaises(ResearchResponseContractError) as qualifier_error:
            require_repair_preserves_claim_evidence_v0_1_21(
                original,
                changed_qualifier,
                role="market_researcher",
            )
        self.assertEqual(
            "claims.evidence_qualifiers",
            qualifier_error.exception.proof_failure_detail["field"],
        )

        changed_semantics = deepcopy(repaired)
        changed_semantics["claims"][0]["semantic_context"]["event_state"] = "completed"
        with self.assertRaises(ResearchResponseContractError) as semantic_error:
            require_repair_preserves_claim_evidence_v0_1_21(
                original,
                changed_semantics,
                role="market_researcher",
            )
        self.assertEqual(
            "claims.semantic_context",
            semantic_error.exception.proof_failure_detail["field"],
        )

    def test_thin_pipeline_returns_only_validated_role_projection(self) -> None:
        admitted = Citation("https://evidence.example/item", "Commercial evidence")
        value = _payload(
            claims=[
                _claim(claim_id="accepted", locator=admitted.locator),
                _claim(
                    claim_id="withheld",
                    locator="https://evidence.example/not-admitted",
                ),
            ]
        )

        projection = validate_and_project_role_claim_evidence_v0_1_21(
            role="market_researcher",
            company_id=14,
            pass_number=1,
            payload=value,
            admitted_citations=[admitted],
        )

        self.assertEqual(
            (qualified_claim_id("market_researcher", "accepted"),),
            tuple(item["claim_id"] for item in projection.accepted_claims),
        )
        self.assertEqual(
            (qualified_claim_id("market_researcher", "withheld"),),
            tuple(item["claim_id"] for item in projection.withheld_claims),
        )
        self.assertEqual("claim_withheld", projection.issues[0]["action"])

    def test_contract_and_pipeline_import_in_flat_and_packaged_contexts(self) -> None:
        helpers = (
            "agent_contract.py",
            "agent_response_recovery_v0_1_17.py",
            "claim_evidence_contract_v0_1_21.py",
            "claim_semantics_v0_1_21.py",
            "dossier_contract.py",
            "memory_contract.py",
            "research_claim_evidence_v0_1_21.py",
            "research_claim_pipeline_v0_1_21.py",
            "research_diagnostics_v0_1_17.py",
            "research_response_contract_v0_1_21.py",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package = root / "candidate_package"
            package.mkdir()
            (package / "__init__.py").write_text("", encoding="utf-8")
            for helper in helpers:
                shutil.copy2(ASSET_ROOT / helper, package / helper)

            code = textwrap.dedent(
                f"""
                import importlib
                import sys
                sys.path.insert(0, {str(root)!r})
                sys.path.insert(0, {str(package)!r})
                for name in (
                    "research_response_contract_v0_1_21",
                    "research_claim_pipeline_v0_1_21",
                    "candidate_package.research_response_contract_v0_1_21",
                    "candidate_package.research_claim_pipeline_v0_1_21",
                ):
                    module = importlib.import_module(name)
                    assert module.__doc__
                """
            )
            subprocess.run([sys.executable, "-c", code], check=True)


if __name__ == "__main__":
    unittest.main()
