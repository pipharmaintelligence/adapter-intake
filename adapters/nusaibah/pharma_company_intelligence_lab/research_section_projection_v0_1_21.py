"""Deterministic section projection for accepted pharma claims in 0.1.21.

Research Agents may emit section prose that summarizes several claims. When one
claim in a section is withheld, the adapter cannot safely attribute fragments of
that prose to individual claims. The original section remains available in the
review packet, while downstream strategy/critic/synthesis receive a neutral
section placeholder and the surviving accepted claim records.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "pharma_research_section_projection.v1"
WITHHELD_SECTION_TEXT = (
    "Section prose is withheld because one or more claims lacked admitted "
    "support or valid semantic context. Use the accepted claim records only."
)


class ResearchSectionProjectionError(ValueError):
    """Value-safe deterministic section-projection rejection."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ResearchSectionProjection:
    """Review-preserved and downstream-safe views for one research pass."""

    schema_version: str
    review_sections: tuple[dict[str, Any], ...]
    downstream_sections: tuple[dict[str, Any], ...]
    withheld_section_ids: tuple[str, ...]


def project_research_sections(
    *,
    sections: Iterable[Mapping[str, Any]],
    withheld_claims: Iterable[Mapping[str, Any]],
) -> ResearchSectionProjection:
    """Withhold affected section prose while preserving accepted claim objects."""

    review_sections: list[dict[str, Any]] = []
    section_ids: list[str] = []
    for raw in sections:
        if not isinstance(raw, Mapping):
            raise ResearchSectionProjectionError("research_section_invalid")
        section = deepcopy(dict(raw))
        section_id = section.get("section_id")
        if not isinstance(section_id, str) or not section_id.strip():
            raise ResearchSectionProjectionError("research_section_id_invalid")
        section_id = section_id.strip()
        if section_id in section_ids:
            raise ResearchSectionProjectionError("research_section_duplicate")
        section["section_id"] = section_id
        section_ids.append(section_id)
        review_sections.append(section)

    withheld_ids: list[str] = []
    for claim in withheld_claims:
        if not isinstance(claim, Mapping):
            raise ResearchSectionProjectionError("research_withheld_claim_invalid")
        section_id = claim.get("section_id")
        if not isinstance(section_id, str) or section_id not in section_ids:
            raise ResearchSectionProjectionError(
                "research_withheld_claim_section_invalid"
            )
        if section_id not in withheld_ids:
            withheld_ids.append(section_id)

    downstream = deepcopy(review_sections)
    for section in downstream:
        if section["section_id"] not in withheld_ids:
            continue
        subsections = section.get("subsections")
        if not isinstance(subsections, list):
            raise ResearchSectionProjectionError(
                "research_section_subsections_invalid"
            )
        section["content"] = "" if subsections else WITHHELD_SECTION_TEXT
        for subsection in subsections:
            if not isinstance(subsection, dict):
                raise ResearchSectionProjectionError(
                    "research_subsection_invalid"
                )
            subsection["content"] = WITHHELD_SECTION_TEXT

    return ResearchSectionProjection(
        schema_version=SCHEMA_VERSION,
        review_sections=tuple(review_sections),
        downstream_sections=tuple(downstream),
        withheld_section_ids=tuple(withheld_ids),
    )
