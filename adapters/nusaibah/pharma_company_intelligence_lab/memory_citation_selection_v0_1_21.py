"""Fact-driven bounded citation selection for pharma memory candidates.

Selection covers candidate facts before adding secondary citations. The helper
has no provider, storage, mutation or approval authority and never increases the
reviewed citation bound.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable

try:
    from .claim_evidence_contract_v0_1_21 import (
        ClaimEvidenceIndex,
        CitationCatalogEntry,
    )
except ImportError:  # pragma: no cover - flat intake execution
    from claim_evidence_contract_v0_1_21 import (
        ClaimEvidenceIndex,
        CitationCatalogEntry,
    )


SCHEMA_VERSION = "pharma_memory_evidence_selection.v1"
DEFAULT_MAX_CITATIONS = 24


class MemoryCitationSelectionError(ValueError):
    """Value-safe deterministic memory-evidence selection rejection."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class FactCoverage:
    """Selected evidence coverage for one proposed memory fact."""

    fact_id: str
    status: str
    selected_citation_refs: tuple[str, ...]
    available_citation_refs: tuple[str, ...]
    reason_code: str | None


@dataclass(frozen=True)
class EvidenceSelection:
    """Immutable citation selection shared by review and apply consumers."""

    schema_version: str
    selected_citations: tuple[CitationCatalogEntry, ...]
    fact_coverage: tuple[FactCoverage, ...]
    uncovered_fact_ids: tuple[str, ...]
    omitted_counts_by_role: tuple[tuple[str, int], ...]
    maximum_citations: int
    selection_digest: str
    complete: bool

    def public_citations(self) -> list[dict[str, Any]]:
        """Return exact selected citation objects for review/apply projection."""

        return [item.public_value() for item in self.selected_citations]


def select_memory_citations(
    *,
    fact_ids: Iterable[str],
    evidence_index: ClaimEvidenceIndex,
    maximum_citations: int = DEFAULT_MAX_CITATIONS,
) -> EvidenceSelection:
    """Select bounded citations by memory fact coverage, never global prefix."""

    if not isinstance(evidence_index, ClaimEvidenceIndex):
        raise MemoryCitationSelectionError("memory_evidence_index_invalid")
    if type(maximum_citations) is not int or maximum_citations < 1:
        raise MemoryCitationSelectionError("memory_citation_limit_invalid")

    facts = _fact_ids(fact_ids)
    selected_refs: list[str] = []
    coverage: list[FactCoverage] = []
    secondary: list[tuple[str, ...]] = []

    for fact_id in facts:
        record = evidence_index.record(fact_id)
        if record is None:
            coverage.append(
                FactCoverage(
                    fact_id,
                    "uncovered",
                    (),
                    (),
                    "memory_fact_claim_unknown",
                )
            )
            continue
        if not record.accepted:
            coverage.append(
                FactCoverage(
                    fact_id,
                    "uncovered",
                    (),
                    record.citation_refs,
                    record.issue_code or "memory_fact_claim_withheld",
                )
            )
            continue

        available = tuple(
            reference
            for reference in record.citation_refs
            if evidence_index.citation(reference) is not None
        )
        if not available:
            coverage.append(
                FactCoverage(
                    fact_id,
                    "uncovered",
                    (),
                    (),
                    "memory_fact_citation_missing",
                )
            )
            continue

        shared = next(
            (reference for reference in available if reference in selected_refs),
            None,
        )
        if shared is not None:
            selected_for_fact = (shared,)
        elif len(selected_refs) < maximum_citations:
            selected_refs.append(available[0])
            selected_for_fact = (available[0],)
        else:
            selected_for_fact = ()

        if not selected_for_fact:
            coverage.append(
                FactCoverage(
                    fact_id,
                    "uncovered",
                    (),
                    available,
                    "memory_citation_bound_exceeded",
                )
            )
            continue

        coverage.append(
            FactCoverage(
                fact_id,
                "covered",
                selected_for_fact,
                available,
                None,
            )
        )
        secondary.append(available)

    # Add secondary evidence only after every coverable fact has primary support.
    for available in secondary:
        for reference in available:
            if reference in selected_refs:
                continue
            if len(selected_refs) >= maximum_citations:
                break
            selected_refs.append(reference)
        if len(selected_refs) >= maximum_citations:
            break

    selected_citations = tuple(
        citation
        for reference in selected_refs
        if (citation := evidence_index.citation(reference)) is not None
    )
    uncovered = tuple(item.fact_id for item in coverage if item.status != "covered")
    omitted = _omitted_counts(evidence_index, selected_refs)
    value = {
        "schema_version": SCHEMA_VERSION,
        "selected_citation_refs": selected_refs,
        "fact_coverage": [
            {
                "fact_id": item.fact_id,
                "status": item.status,
                "selected_citation_refs": list(item.selected_citation_refs),
                "available_citation_refs": list(item.available_citation_refs),
                "reason_code": item.reason_code,
            }
            for item in coverage
        ],
        "uncovered_fact_ids": list(uncovered),
        "omitted_counts_by_role": list(omitted),
        "maximum_citations": maximum_citations,
    }
    return EvidenceSelection(
        schema_version=SCHEMA_VERSION,
        selected_citations=selected_citations,
        fact_coverage=tuple(coverage),
        uncovered_fact_ids=uncovered,
        omitted_counts_by_role=omitted,
        maximum_citations=maximum_citations,
        selection_digest="sha256:" + sha256(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest(),
        complete=not uncovered,
    )


def require_complete_selection(selection: EvidenceSelection) -> None:
    """Fail closed before mutation when candidate facts lack evidence."""

    if not isinstance(selection, EvidenceSelection) or not selection.complete:
        raise MemoryCitationSelectionError("memory_evidence_selection_incomplete")


def _fact_ids(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise MemoryCitationSelectionError("memory_fact_id_invalid")
        item = value.strip()
        if item in result:
            raise MemoryCitationSelectionError("memory_fact_id_duplicate")
        result.append(item)
    return tuple(result)


def _omitted_counts(
    evidence_index: ClaimEvidenceIndex,
    selected_refs: list[str],
) -> tuple[tuple[str, int], ...]:
    # One source may support claims in more than one role. Count role evidence
    # from claim references rather than the globally deduplicated catalog.
    by_role: dict[str, set[str]] = {}
    for record in evidence_index.records:
        by_role.setdefault(record.role, set()).update(record.citation_refs)
    selected = set(selected_refs)
    return tuple(
        (role, len(references - selected))
        for role, references in sorted(by_role.items())
    )
