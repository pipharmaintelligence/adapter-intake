from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CitationRef:
    locator: str
    title: str | None = None
    source_kind: str | None = None
    provider_family: str | None = None
    provider_turn_index: int | None = None


def dedupe_citations(citations: Iterable[CitationRef]) -> tuple[CitationRef, ...]:
    """Preserve first-seen citation identity for deterministic intake tests."""

    result: list[CitationRef] = []
    seen: set[tuple[object, ...]] = set()
    for citation in citations:
        key = (
            citation.locator,
            citation.title,
            citation.source_kind,
            citation.provider_family,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(citation)
    return tuple(result)
