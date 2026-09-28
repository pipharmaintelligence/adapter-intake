from __future__ import annotations

import json
import sys
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ASSET_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSET_ROOT))

import nusaibah_pharma_company_intelligence_lab_adapter as adapter_module  # noqa: E402
from dossier_contract import CANONICAL_SECTIONS  # noqa: E402
from nusaibah_pharma_company_intelligence_lab_adapter import (  # noqa: E402
    NusaibahPharmaCompanyIntelligenceLabAdapter,
)
from devtools.skill_citation import CitationRef  # noqa: E402


class FakeSkill:
    def __init__(self) -> None:
        self.root = ASSET_ROOT / "skills" / "pharma-intelligence-methodology"

    def validate(self):
        return SimpleNamespace(
            status="ready",
            skill_ref="nusaibah.pharma-intelligence-methodology",
            version="1.0.0",
            package_digest="sha256:" + "1" * 64,
        )

    def read_resource(self, path: str) -> str:
        return (self.root / path).read_text(encoding="utf-8")


class FakeMemory:
    def __init__(self, company_id: int) -> None:
        self.company_id = company_id
        self.text = (
            "---\n"
            "name: company-memory\n"
            "description: Test memory.\n"
            "---\n"
            "# Company Memory\n\n"
            "## Current Public Research\n\n"
            f"Existing memory for company {company_id}.\n"
        )

    def provenance(self):
        return SimpleNamespace(mutable=False, role="company_memory")

    def read(self) -> str:
        return self.text

    def has_section(self, section: str) -> bool:
        return section == "Current Public Research"

    def section_text(self, section: str) -> str:
        if not self.has_section(section):
            raise KeyError(section)
        return f"Existing memory for company {self.company_id}."

    def content_digest(self) -> str:
        return "sha256:" + format(self.company_id, "064x")[-64:]


class FakeInputs(dict):
    def __init__(self, *, wrong_company_role: str | None = None) -> None:
        super().__init__(
            {
                "variables": {
                    "execution_scope": "batch",
                    "company_ids": [13, 59],
                    "objective": "company_intelligence_memory",
                    "research_depth": "deep",
                    "memory_mode": "preview",
                    "publish_dossier": False,
                },
                "companies": [
                    {"company_id": 59, "company_name": "Pfizer", "country": "US"},
                    {"company_id": 13, "company_name": "Tabuk Pharmaceuticals", "country": "SA"},
                ],
            }
        )
        self.wrong_company_role = wrong_company_role
        self.agent_calls: list[tuple[str, int]] = []
        self.dynamic_skill_calls: list[tuple[str, int]] = []

    def skill(self, selector: str):
        self.assert_equal(selector, "nusaibah.pharma-intelligence-methodology")
        return FakeSkill()

    def dynamic_skill(self, role: str, *, variables=None):
        company_id = int((variables or {})["company_id"])
        self.dynamic_skill_calls.append((role, company_id))
        if role != "company_memory":
            raise AssertionError("preview fixture must not request mutable memory")
        return FakeMemory(company_id)

    def invoke_agent(self, role: str, *, input=None, on_error="raise"):
        del on_error
        company_id = int(input["company_id"])
        self.agent_calls.append((role, company_id))
        output_company_id = (
            999 if role == self.wrong_company_role and company_id == 13 else company_id
        )
        value = _agent_value(role, output_company_id, input)
        return {
            "status": "completed",
            "result": {
                "schema_version": "agent_result.v1",
                "kind": "json",
                "content": [{"type": "json", "value": value}],
                "text": json.dumps(value, separators=(",", ":")),
                "model": "fake",
                "usage": {},
                "metadata": {},
                "provider_metadata": {
                    "schema_version": "agent_provider_metadata.v1",
                    "turns": [],
                },
            },
        }

    @staticmethod
    def assert_equal(actual, expected) -> None:
        if actual != expected:
            raise AssertionError(f"{actual!r} != {expected!r}")


def _agent_value(role: str, company_id: int, input_value: dict) -> dict:
    if role in {
        "portfolio_researcher",
        "market_researcher",
        "regulatory_risk_researcher",
    }:
        sections = []
        claims = []
        for section in input_value["required_sections"]:
            subsections = [
                {
                    "subsection_id": subsection_id,
                    "content": f"{role} evidence for {subsection_id} company {company_id}.",
                }
                for subsection_id in section["subsection_ids"]
            ]
            sections.append(
                {
                    "section_id": section["section_id"],
                    "content": (
                        "" if subsections else
                        f"{role} evidence for {section['section_id']} company {company_id}."
                    ),
                    "subsections": subsections,
                }
            )
            claims.append(
                {
                    "claim_id": f"{company_id}-{role}-{section['section_id']}",
                    "section_id": section["section_id"],
                    "statement": f"Grounded claim for company {company_id}.",
                    "evidence_kind": "grounded_external",
                    "as_of_date": "2026-09-28",
                    "confidence": "high",
                    "inference": False,
                }
            )
        return {
            "schema_version": "pharma_research_agent.v1",
            "company_id": company_id,
            "role": role,
            "status": "completed",
            "sections": sections,
            "claims": claims,
            "uncertainties": [],
        }

    if role == "strategic_analyst":
        return {
            "schema_version": "pharma_strategic_agent.v1",
            "company_id": company_id,
            "role": role,
            "status": "completed",
            "implications": ["Evidence-backed implication."],
            "opportunities": ["Evidence-backed opportunity."],
            "risks": ["Evidence-backed risk."],
            "internal_public_deltas": ["New evidence is available."],
            "uncertainties": [],
        }

    if role == "evidence_critic":
        return {
            "schema_version": "pharma_evidence_critic.v1",
            "company_id": company_id,
            "role": role,
            "status": "completed",
            "unsupported_claim_ids": [],
            "contradiction_items": [],
            "stale_claim_ids": [],
            "missing_section_ids": [],
            "citation_coverage": {"status": "sufficient", "notes": "Grounded."},
            "residual_uncertainties": [],
            "recommendation": "pass",
        }

    if role == "intelligence_synthesizer":
        sections = []
        for section in CANONICAL_SECTIONS:
            subsections = [
                {
                    "subsection_id": subsection.subsection_id,
                    "content": f"Final content for {subsection.subsection_id} company {company_id}.",
                }
                for subsection in section.subsections
            ]
            sections.append(
                {
                    "section_id": section.section_id,
                    "content": (
                        "" if subsections else
                        f"Final content for {section.section_id} company {company_id}."
                    ),
                    "subsections": subsections,
                }
            )
        allowed = input_value["allowed_memory_fact_ids"]
        return {
            "schema_version": "pharma_synthesis_agent.v1",
            "company_id": company_id,
            "role": role,
            "status": "completed",
            "sections": sections,
            "memory_candidate": {
                "company_id": company_id,
                "target_section": "Current Public Research",
                "markdown": f"Updated grounded memory for company {company_id}.",
                "fact_ids": allowed[:2],
            },
            "residual_uncertainties": [],
        }

    if role == "memory_benchmark_reviewer":
        return {
            "schema_version": "pharma_memory_benchmark.v1",
            "company_id": company_id,
            "role": role,
            "status": "completed",
            "results": [
                {
                    "question_id": item["question_id"],
                    "coverage": (
                        "partially_covered"
                        if input_value["memory_stage"] == "before"
                        else "covered"
                    ),
                    "evidence_basis": f"Memory evidence for {item['question_id']}.",
                }
                for item in input_value["benchmark_questions"]
            ],
        }

    raise AssertionError(f"unexpected role: {role}")


def _fake_citations(agent_result):
    role = agent_result["content"][0]["value"]["role"]
    company_id = agent_result["content"][0]["value"]["company_id"]
    return (
        CitationRef(
            locator=f"urn:pi:test:{company_id}:{role}",
            title=f"{role} evidence",
            source_kind="agent_citation",
            provider_family="vertex_ai",
            provider_turn_index=0,
        ),
    )


class FullPreviewOrchestrationTests(unittest.TestCase):
    def test_two_company_preview_runs_full_isolated_agent_graph_without_mutation(self) -> None:
        inputs = FakeInputs()
        adapter = NusaibahPharmaCompanyIntelligenceLabAdapter()

        with patch.object(adapter_module, "_agent_citations", side_effect=_fake_citations):
            response = adapter.invoke(inputs, {})

        self.assertEqual(response["status"], "success")
        dossier = response["outputs"]["intelligence_dossier"]
        self.assertEqual(dossier["status"], "completed")
        self.assertEqual(
            [item["company_id"] for item in dossier["company_results"]],
            [13, 59],
        )
        self.assertEqual(response["metrics"]["logical_agent_invocations"], 16)
        self.assertEqual(response["metrics"]["search_enabled_agent_invocations"], 6)
        self.assertEqual(response["metrics"]["memory_mutations_made"], 0)

        counts = Counter(role for role, _company_id in inputs.agent_calls)
        self.assertEqual(counts["portfolio_researcher"], 2)
        self.assertEqual(counts["market_researcher"], 2)
        self.assertEqual(counts["regulatory_risk_researcher"], 2)
        self.assertEqual(counts["strategic_analyst"], 2)
        self.assertEqual(counts["evidence_critic"], 2)
        self.assertEqual(counts["intelligence_synthesizer"], 2)
        self.assertEqual(counts["memory_benchmark_reviewer"], 4)

        self.assertEqual(
            inputs.dynamic_skill_calls,
            [("company_memory", 13), ("company_memory", 59)],
        )
        for result in dossier["company_results"]:
            self.assertTrue(result["quality_gate_passed"])
            self.assertTrue(result["memory_mutation_eligible"])
            self.assertEqual(result["memory_update_status"], "preview_ready")
            self.assertEqual(result["benchmark_result_basis"], "projected_memory_candidate")
            self.assertFalse(result["memory_readback_verified"])
            self.assertEqual(
                [section["title"] for section in result["sections"]],
                [section.title for section in CANONICAL_SECTIONS],
            )

    def test_cross_company_agent_result_fails_before_any_mutation(self) -> None:
        inputs = FakeInputs(wrong_company_role="market_researcher")
        adapter = NusaibahPharmaCompanyIntelligenceLabAdapter()

        with patch.object(adapter_module, "_agent_citations", side_effect=_fake_citations):
            with self.assertRaisesRegex(RuntimeError, "wrong company_id"):
                adapter.invoke(inputs, {})

        self.assertNotIn(("company_memory_update", 13), inputs.dynamic_skill_calls)
        self.assertNotIn(("company_memory_update", 59), inputs.dynamic_skill_calls)


if __name__ == "__main__":
    unittest.main()
