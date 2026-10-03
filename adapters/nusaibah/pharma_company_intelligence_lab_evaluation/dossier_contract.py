from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

DOSSIER_SCHEMA_VERSION = "pharma_company_intelligence_dossier.v1"


@dataclass(frozen=True)
class SubsectionSpec:
    """Canonical subsection identity owned by the adapter contract."""

    subsection_id: str
    title: str


@dataclass(frozen=True)
class SectionSpec:
    """Canonical section identity and ordered subsection registry."""

    section_id: str
    title: str
    subsections: tuple[SubsectionSpec, ...] = ()


CANONICAL_SECTIONS: tuple[SectionSpec, ...] = (
    SectionSpec("executive_intelligence_summary", "Executive Intelligence Summary"),
    SectionSpec("internal_baseline", "Internal Baseline"),
    SectionSpec(
        "company_profile",
        "Company Profile",
        (
            SubsectionSpec("identity", "Identity"),
            SubsectionSpec("ownership_structure", "Ownership & Structure"),
            SubsectionSpec("headquarters_footprint", "Headquarters & Footprint"),
            SubsectionSpec("manufacturing_footprint", "Manufacturing Footprint"),
        ),
    ),
    SectionSpec(
        "product_portfolio_intelligence",
        "Product & Portfolio Intelligence",
        (
            SubsectionSpec("therapeutic_areas", "Therapeutic Areas"),
            SubsectionSpec("key_products", "Key Products"),
            SubsectionSpec("pipeline_lifecycle_signals", "Pipeline & Lifecycle Signals"),
            SubsectionSpec("licensing_partnerships", "Licensing & Partnerships"),
        ),
    ),
    SectionSpec(
        "markets_commercial_signals",
        "Markets & Commercial Signals",
        (
            SubsectionSpec("geographies", "Geographies"),
            SubsectionSpec("market_presence", "Market Presence"),
            SubsectionSpec("launches_distribution", "Launches & Distribution"),
            SubsectionSpec("commercial_partnerships", "Commercial Partnerships"),
        ),
    ),
    SectionSpec(
        "regulatory_clinical_risk_signals",
        "Regulatory / Clinical / Risk Signals",
        (
            SubsectionSpec("approvals", "Approvals"),
            SubsectionSpec("clinical_evidence", "Clinical Evidence"),
            SubsectionSpec("safety", "Safety"),
            SubsectionSpec("manufacturing_quality", "Manufacturing & Quality"),
            SubsectionSpec("regulatory_uncertainty", "Regulatory Uncertainty"),
        ),
    ),
    SectionSpec(
        "strategic_developments",
        "Strategic Developments",
        (
            SubsectionSpec("recent_material_developments", "Recent Material Developments"),
            SubsectionSpec("implications", "Implications"),
            SubsectionSpec("opportunities", "Opportunities"),
            SubsectionSpec("risks", "Risks"),
        ),
    ),
    SectionSpec("contradictions_uncertainty_register", "Contradictions & Uncertainty Register"),
    SectionSpec("new_evidence_since_existing_memory", "New Evidence Since Existing Memory"),
    SectionSpec("recommended_memory_update", "Recommended Memory Update"),
    SectionSpec("evidence_citation_coverage", "Evidence / Citation Coverage"),
    SectionSpec("quality_performance_scorecard", "Quality / Performance Scorecard"),
)

SECTION_BY_ID = {section.section_id: section for section in CANONICAL_SECTIONS}


def canonical_section_ids() -> tuple[str, ...]:
    """Return the immutable ordered section-id registry."""
    return tuple(section.section_id for section in CANONICAL_SECTIONS)


def render_empty_sections() -> list[dict[str, Any]]:
    """Render the canonical hierarchy without provider-authored titles."""
    return [
        {
            "section_id": section.section_id,
            "title": section.title,
            "content": "",
            "subsections": [
                {
                    "subsection_id": subsection.subsection_id,
                    "title": subsection.title,
                    "content": "",
                }
                for subsection in section.subsections
            ],
        }
        for section in CANONICAL_SECTIONS
    ]


def normalize_sections(
    raw_sections: Any,
    *,
    require_all: bool = True,
    allowed_section_ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Validate model section IDs and inject canonical titles/order."""
    if not isinstance(raw_sections, list):
        raise ValueError("sections must be a list.")

    allowed = tuple(allowed_section_ids) if allowed_section_ids is not None else canonical_section_ids()
    if len(set(allowed)) != len(allowed) or any(section_id not in SECTION_BY_ID for section_id in allowed):
        raise ValueError("allowed section registry is invalid.")

    expected_ids = allowed if require_all else tuple(
        section_id
        for section_id in allowed
        if any(isinstance(item, dict) and item.get("section_id") == section_id for item in raw_sections)
    )
    actual_ids = tuple(item.get("section_id") for item in raw_sections if isinstance(item, dict))

    if len(actual_ids) != len(raw_sections):
        raise ValueError("Every section must be an object with section_id.")
    if len(set(actual_ids)) != len(actual_ids):
        raise ValueError("Duplicate section_id values are not allowed.")
    if any(section_id not in allowed for section_id in actual_ids):
        raise ValueError("Unknown section_id is not allowed.")
    if actual_ids != expected_ids:
        raise ValueError("Section IDs must exactly match canonical order.")

    normalized: list[dict[str, Any]] = []
    for raw_section in raw_sections:
        section_id = raw_section["section_id"]
        spec = SECTION_BY_ID[section_id]
        content = _bounded_text(raw_section.get("content", ""), field="section.content")
        raw_subsections = raw_section.get("subsections", [])
        if not isinstance(raw_subsections, list):
            raise ValueError("section.subsections must be a list.")

        expected_sub_ids = tuple(item.subsection_id for item in spec.subsections)
        actual_sub_ids = tuple(
            item.get("subsection_id") for item in raw_subsections if isinstance(item, dict)
        )
        if len(actual_sub_ids) != len(raw_subsections):
            raise ValueError("Every subsection must be an object with subsection_id.")
        if len(set(actual_sub_ids)) != len(actual_sub_ids):
            raise ValueError("Duplicate subsection_id values are not allowed.")
        if actual_sub_ids != expected_sub_ids:
            raise ValueError("Subsection IDs must exactly match canonical order.")

        normalized.append(
            {
                "section_id": section_id,
                "title": spec.title,
                "content": content,
                "subsections": [
                    {
                        "subsection_id": sub_spec.subsection_id,
                        "title": sub_spec.title,
                        "content": _bounded_text(raw_sub.get("content", ""), field="subsection.content"),
                    }
                    for raw_sub, sub_spec in zip(raw_subsections, spec.subsections, strict=True)
                ],
            }
        )

    return normalized


def _bounded_text(value: Any, *, field: str, max_chars: int = 20000) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string.")
    text = value.strip()
    if len(text) > max_chars:
        raise ValueError(f"{field} exceeds the allowed character bound.")
    return text
