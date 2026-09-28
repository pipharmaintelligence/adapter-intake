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

    def read(self) -> str:
        return (self.root / "SKILL.md").read_text(encoding="utf-8")

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
        self.agent_inputs: list[tuple[str, int, dict]] = []
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
        self.agent_inputs.append((role, company_id, dict(input)))
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
    if role == "methodology_planner":
        return {
            "schema_version": "pharma_methodology_plan.v1",
            "company_id": company_id,
            "role": role,
            "status": "completed",
            "research_focus": [
                {
                    "role": research_role,
                    "priority": "high" if research_role == "regulatory_risk_researcher" else "medium",
                    "section_ids": list(adapter_module.RESEARCH_ROLE_SECTIONS[research_role]),
                    "questions": [f"Question for {research_role} company {company_id}."],
                    "freshness_focus": ["recent material changes"],
                    "evidence_focus": ["authoritative public evidence"],
                }
                for research_role in adapter_module.RESEARCH_ROLES
            ],
            "cross_cutting_questions": [f"Cross-cutting question for company {company_id}."],
            "known_memory_gaps": [f"Known gap for company {company_id}."],
            "expected_uncertainties": [f"Expected uncertainty for company {company_id}."],
        }

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
            "unmet_plan_requirements": [],
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
        self.assertEqual(response["metrics"]["logical_agent_invocations"], 18)
        self.assertEqual(response["metrics"]["search_enabled_agent_invocations"], 6)
        self.assertEqual(response["metrics"]["memory_mutations_made"], 0)

        counts = Counter(role for role, _company_id in inputs.agent_calls)
        self.assertEqual(counts["methodology_planner"], 2)
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

    def test_planner_runs_after_before_benchmark_and_before_research(self) -> None:
        inputs = FakeInputs()
        adapter = NusaibahPharmaCompanyIntelligenceLabAdapter()

        with patch.object(adapter_module, "_agent_citations", side_effect=_fake_citations):
            adapter.invoke(inputs, {})

        company_13_roles = [
            role for role, company_id in inputs.agent_calls if company_id == 13
        ]
        self.assertEqual(company_13_roles[0], "memory_benchmark_reviewer")
        self.assertEqual(company_13_roles[1], "methodology_planner")
        first_research_index = min(
            company_13_roles.index(role)
            for role in adapter_module.RESEARCH_ROLES
        )
        self.assertGreater(first_research_index, company_13_roles.index("methodology_planner"))

    def test_planner_input_is_company_scoped_and_researchers_receive_only_role_focus(self) -> None:
        inputs = FakeInputs()
        adapter = NusaibahPharmaCompanyIntelligenceLabAdapter()

        with patch.object(adapter_module, "_agent_citations", side_effect=_fake_citations):
            adapter.invoke(inputs, {})

        planner_inputs = {
            company_id: payload
            for role, company_id, payload in inputs.agent_inputs
            if role == "methodology_planner"
        }
        self.assertEqual(set(planner_inputs), {13, 59})
        self.assertEqual(planner_inputs[13]["company_id"], 13)
        self.assertEqual(planner_inputs[59]["company_id"], 59)
        self.assertNotEqual(
            planner_inputs[13]["governed_company_baseline"]["company_name"],
            planner_inputs[59]["governed_company_baseline"]["company_name"],
        )

        researcher_inputs = [
            (role, company_id, payload)
            for role, company_id, payload in inputs.agent_inputs
            if role in adapter_module.RESEARCH_ROLES
        ]
        self.assertEqual(len(researcher_inputs), 6)

        for role, company_id, payload in researcher_inputs:
            focus = payload["methodology_plan"]
            self.assertEqual(focus["role"], role)
            self.assertEqual(
                focus["section_ids"],
                list(adapter_module.RESEARCH_ROLE_SECTIONS[role]),
            )
            self.assertEqual(
                focus["questions"],
                [f"Question for {role} company {company_id}."],
            )
            self.assertNotIn("research_focus", payload)
            self.assertNotIn("cross_cutting_questions", focus)
            self.assertNotIn("known_memory_gaps", focus)
            self.assertNotIn("expected_uncertainties", focus)

    def test_downstream_roles_receive_bounded_validated_methodology_context(self) -> None:
        inputs = FakeInputs()
        adapter = NusaibahPharmaCompanyIntelligenceLabAdapter()

        with patch.object(adapter_module, "_agent_citations", side_effect=_fake_citations):
            adapter.invoke(inputs, {})

        by_role_company = {
            (role, company_id): payload
            for role, company_id, payload in inputs.agent_inputs
        }

        for company_id in (13, 59):
            strategic = by_role_company[("strategic_analyst", company_id)]
            self.assertEqual(
                strategic["methodology_plan"],
                {
                    "cross_cutting_questions": [
                        f"Cross-cutting question for company {company_id}."
                    ]
                },
            )

            critic = by_role_company[("evidence_critic", company_id)]
            critic_plan = critic["methodology_plan"]
            self.assertEqual(critic_plan["company_id"], company_id)
            self.assertEqual(critic_plan["role"], "methodology_planner")
            self.assertEqual(
                critic_plan["cross_cutting_questions"],
                [f"Cross-cutting question for company {company_id}."],
            )
            self.assertEqual(
                critic_plan["known_memory_gaps"],
                [f"Known gap for company {company_id}."],
            )
            self.assertEqual(
                critic_plan["expected_uncertainties"],
                [f"Expected uncertainty for company {company_id}."],
            )
            self.assertTrue(critic["methodology_packet"]["evidence_rules"])
            self.assertNotIn("memory_rules", critic["methodology_packet"])

            synthesis = by_role_company[("intelligence_synthesizer", company_id)]
            synthesis_plan = synthesis["methodology_plan"]
            self.assertEqual(synthesis_plan["company_id"], company_id)
            self.assertEqual(
                synthesis_plan["cross_cutting_questions"],
                [f"Cross-cutting question for company {company_id}."],
            )
            self.assertTrue(synthesis["methodology_packet"]["memory_rules"])
            self.assertNotIn("evidence_rules", synthesis["methodology_packet"])

    def test_critic_receives_stable_planner_requirement_catalog(self) -> None:
        inputs = FakeInputs()
        adapter = NusaibahPharmaCompanyIntelligenceLabAdapter()

        with patch.object(adapter_module, "_agent_citations", side_effect=_fake_citations):
            adapter.invoke(inputs, {})

        critic_inputs = [
            payload
            for role, _company_id, payload in inputs.agent_inputs
            if role == "evidence_critic"
        ]
        self.assertEqual(len(critic_inputs), 2)

        for payload in critic_inputs:
            requirement_ids = [
                item["requirement_id"] for item in payload["planner_requirements"]
            ]
            self.assertEqual(
                requirement_ids,
                payload["response_contract"]["unmet_plan_requirement_ids"],
            )
            self.assertEqual(len(requirement_ids), len(set(requirement_ids)))
            self.assertIn(
                "unresolved_evidence",
                payload["response_contract"]["unmet_plan_requirement_dispositions"],
            )
            self.assertIn(
                "unsatisfied",
                payload["response_contract"]["unmet_plan_requirement_dispositions"],
            )

    def test_unresolved_plan_requirement_can_reach_synthesis(self) -> None:
        inputs = FakeInputs()
        adapter = NusaibahPharmaCompanyIntelligenceLabAdapter()
        original_agent_value = _agent_value

        def agent_value_with_unresolved(role: str, company_id: int, input_value: dict) -> dict:
            value = original_agent_value(role, company_id, input_value)
            if role == "evidence_critic" and company_id == 13:
                value["unmet_plan_requirements"] = [
                    {
                        "requirement_id": input_value["planner_requirements"][0]["requirement_id"],
                        "disposition": "unresolved_evidence",
                        "notes": "Required evidence remains unavailable and is explicitly retained as unresolved.",
                    }
                ]
            return value

        with (
            patch.object(adapter_module, "_agent_citations", side_effect=_fake_citations),
            patch(__name__ + "._agent_value", side_effect=agent_value_with_unresolved),
        ):
            response = adapter.invoke(inputs, {})

        self.assertEqual(response["status"], "success")
        self.assertTrue(
            any(role == "intelligence_synthesizer" and company_id == 13 for role, company_id in inputs.agent_calls)
        )

    def test_unsatisfied_plan_requirement_fails_before_synthesis_and_mutation(self) -> None:
        inputs = FakeInputs()
        adapter = NusaibahPharmaCompanyIntelligenceLabAdapter()
        original_agent_value = _agent_value

        def agent_value_with_unsatisfied(role: str, company_id: int, input_value: dict) -> dict:
            value = original_agent_value(role, company_id, input_value)
            if role == "evidence_critic" and company_id == 13:
                value["unmet_plan_requirements"] = [
                    {
                        "requirement_id": input_value["planner_requirements"][0]["requirement_id"],
                        "disposition": "unsatisfied",
                        "notes": "The required plan item was not satisfied by the supplied evidence.",
                    }
                ]
            return value

        with (
            patch.object(adapter_module, "_agent_citations", side_effect=_fake_citations),
            patch(__name__ + "._agent_value", side_effect=agent_value_with_unsatisfied),
        ):
            with self.assertRaisesRegex(RuntimeError, "plan requirements remain unsatisfied"):
                adapter.invoke(inputs, {})

        self.assertFalse(
            any(role == "intelligence_synthesizer" and company_id == 13 for role, company_id in inputs.agent_calls)
        )
        self.assertNotIn(("company_memory_update", 13), inputs.dynamic_skill_calls)
        self.assertNotIn(("company_memory_update", 59), inputs.dynamic_skill_calls)

    def test_memory_benchmark_reviewer_remains_planner_independent(self) -> None:
        inputs = FakeInputs()
        adapter = NusaibahPharmaCompanyIntelligenceLabAdapter()

        with patch.object(adapter_module, "_agent_citations", side_effect=_fake_citations):
            adapter.invoke(inputs, {})

        benchmark_inputs = [
            payload
            for role, _company_id, payload in inputs.agent_inputs
            if role == "memory_benchmark_reviewer"
        ]
        self.assertEqual(len(benchmark_inputs), 4)
        for payload in benchmark_inputs:
            self.assertNotIn("methodology_plan", payload)
            self.assertNotIn("methodology_packet", payload)
            self.assertNotIn("research_focus", payload)
            self.assertNotIn("cross_cutting_questions", payload)

    def test_invalid_planner_company_fails_before_research_for_that_company(self) -> None:
        inputs = FakeInputs(wrong_company_role="methodology_planner")
        adapter = NusaibahPharmaCompanyIntelligenceLabAdapter()

        with patch.object(adapter_module, "_agent_citations", side_effect=_fake_citations):
            with self.assertRaisesRegex(RuntimeError, "wrong company_id"):
                adapter.invoke(inputs, {})

        company_13_roles = [
            role for role, company_id in inputs.agent_calls if company_id == 13
        ]
        self.assertEqual(
            company_13_roles,
            ["memory_benchmark_reviewer", "methodology_planner"],
        )
        self.assertFalse(
            any(role in adapter_module.RESEARCH_ROLES for role in company_13_roles)
        )
        self.assertNotIn(("company_memory_update", 13), inputs.dynamic_skill_calls)
        self.assertNotIn(("company_memory_update", 59), inputs.dynamic_skill_calls)

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
