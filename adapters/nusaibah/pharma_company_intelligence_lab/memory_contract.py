from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MEMORY_TARGET_SECTION = "Current Public Research"
MAX_MEMORY_CANDIDATE_CHARS = 24000
MAX_MEMORY_FACT_IDS = 256


@dataclass(frozen=True)
class MemoryCandidate:
    """Validated company-scoped memory candidate prepared before mutation."""

    company_id: int
    target_section: str
    markdown: str
    fact_ids: tuple[str, ...]


def validate_memory_candidate(value: dict[str, Any], *, company_id: int) -> MemoryCandidate:
    """Validate a bounded same-company Dynamic Skill memory candidate."""
    candidate_company_id = value.get("company_id")
    if candidate_company_id != company_id:
        raise ValueError("Memory candidate company_id does not match the current company.")

    target_section = value.get("target_section", MEMORY_TARGET_SECTION)
    if target_section != MEMORY_TARGET_SECTION:
        raise ValueError("Memory candidate target section is not approved by v0.1.0.")

    markdown = value.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        raise ValueError("Memory candidate markdown must be a non-empty string.")
    markdown = markdown.strip()
    if len(markdown) > MAX_MEMORY_CANDIDATE_CHARS:
        raise ValueError("Memory candidate exceeds the v0.1.0 size bound.")

    raw_fact_ids = value.get("fact_ids", [])
    if not isinstance(raw_fact_ids, list) or len(raw_fact_ids) > MAX_MEMORY_FACT_IDS:
        raise ValueError("Memory candidate fact_ids must be a bounded list.")

    fact_ids: list[str] = []
    for raw_fact_id in raw_fact_ids:
        if not isinstance(raw_fact_id, str) or not raw_fact_id.strip():
            raise ValueError("Memory candidate fact_ids must contain non-empty strings.")
        fact_ids.append(raw_fact_id.strip())
    if len(set(fact_ids)) != len(fact_ids):
        raise ValueError("Memory candidate fact_ids must be unique.")

    return MemoryCandidate(
        company_id=company_id,
        target_section=target_section,
        markdown=markdown,
        fact_ids=tuple(fact_ids),
    )
