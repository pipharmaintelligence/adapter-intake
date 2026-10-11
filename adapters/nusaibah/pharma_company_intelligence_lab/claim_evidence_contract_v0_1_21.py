"""Version-owned claim-to-citation evidence contracts for pharma 0.1.21.

The adapter derives stable references only from runtime-admitted citation values.
Models may propose exact locators, but they never author citation identifiers or
runtime authority. Missing or unmatched evidence withholds the affected claim.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Protocol


SCHEMA_VERSION = "pharma_claim_evidence_index.v1"
MAX_CITATION_REFS_PER_CLAIM = 24
MAX_QUALIFIERS_PER_CLAIM = 8
MAX_QUALIFIER_CHARS = 500


class CitationLike(Protocol):
    """Structural citation fields exposed by the trusted runtime citation view."""

    locator: str
    title: str | None
    source_kind: str
    provider_family: str | None


class ClaimEvidenceError(ValueError):
    """Value-safe deterministic claim-evidence contract rejection."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class CitationCatalogEntry:
    """One runtime-admitted citation with an adapter-derived stable reference."""

    citation_ref: str
    role: str
    pass_number: int
    ordinal: int
    locator: str
    title: str | None
    source_kind: str
    provider_family: str | None

    def public_value(self) -> dict[str, Any]:
        """Return the inert public citation shape used by review/apply consumers."""

        return {
            "citation_ref": self.citation_ref,
            "locator": self.locator,
            "title": self.title,
            "source_kind": self.source_kind,
            "provider_family": self.provider_family,
        }


@dataclass(frozen=True)
class ClaimEvidenceRecord:
    """Evidence disposition for one validated research claim."""

    claim_id: str
    role: str
    section_id: str
    evidence_state: str
    citation_refs: tuple[str, ...]
    qualifiers: tuple[str, ...]
    issue_code: str | None

    @property
    def accepted(self) -> bool:
        """Return whether the claim may proceed to downstream quality review."""

        return self.evidence_state != "withheld"


@dataclass(frozen=True)
class ClaimEvidenceIndex:
    """Immutable claim evidence and its exact admitted citation catalog."""

    schema_version: str
    records: tuple[ClaimEvidenceRecord, ...]
    citations: tuple[CitationCatalogEntry, ...]
    index_digest: str

    def record(self, claim_id: str) -> ClaimEvidenceRecord | None:
        """Return one exact claim record without fuzzy matching."""

        return next((item for item in self.records if item.claim_id == claim_id), None)

    def citation(self, citation_ref: str) -> CitationCatalogEntry | None:
        """Return one exact catalog citation by adapter-derived reference."""

        return next(
            (item for item in self.citations if item.citation_ref == citation_ref),
            None,
        )

    @property
    def accepted_claim_ids(self) -> tuple[str, ...]:
        """Return accepted claim IDs in original deterministic order."""

        return tuple(item.claim_id for item in self.records if item.accepted)

    @property
    def withheld_claim_ids(self) -> tuple[str, ...]:
        """Return evidence-withheld claim IDs in original deterministic order."""

        return tuple(item.claim_id for item in self.records if not item.accepted)


def build_claim_evidence_index(
    *,
    role: str,
    pass_number: int,
    claims: Iterable[Mapping[str, Any]],
    citations: Iterable[CitationLike],
) -> ClaimEvidenceIndex:
    """Resolve claim locators against one role/pass admitted citation catalog."""

    role = _token(role, "claim_evidence_role_invalid")
    if type(pass_number) is not int or pass_number < 1:
        raise ClaimEvidenceError("claim_evidence_pass_number_invalid")

    catalog = _citation_catalog(role=role, pass_number=pass_number, citations=citations)
    by_locator: dict[str, list[CitationCatalogEntry]] = {}
    for entry in catalog:
        by_locator.setdefault(entry.locator, []).append(entry)

    records: list[ClaimEvidenceRecord] = []
    seen_claim_ids: set[str] = set()
    for raw in claims:
        if not isinstance(raw, Mapping):
            raise ClaimEvidenceError("claim_evidence_claim_invalid")
        claim_id = _token(raw.get("claim_id"), "claim_evidence_claim_id_invalid")
        if claim_id in seen_claim_ids:
            raise ClaimEvidenceError("claim_evidence_claim_id_duplicate")
        seen_claim_ids.add(claim_id)
        section_id = _token(raw.get("section_id"), "claim_evidence_section_id_invalid")

        evidence_kind = _token(raw.get("evidence_kind"), "claim_evidence_kind_invalid")
        inference = raw.get("inference")
        if evidence_kind not in {"grounded_external", "inference"}:
            raise ClaimEvidenceError("claim_evidence_kind_invalid")
        if type(inference) is not bool:
            raise ClaimEvidenceError("claim_evidence_inference_flag_invalid")
        if (evidence_kind == "inference") != inference:
            raise ClaimEvidenceError("claim_evidence_inference_flag_invalid")

        locators = _locator_list(raw.get("citation_locators", []))
        qualifiers = _qualifier_list(raw.get("evidence_qualifiers", []))
        matched: list[str] = []
        issue_code: str | None = None
        for locator in locators:
            options = by_locator.get(locator, [])
            if not options:
                issue_code = "claim_citation_locator_not_admitted"
                break
            if len(options) != 1:
                issue_code = "claim_citation_locator_ambiguous"
                break
            reference = options[0].citation_ref
            if reference not in matched:
                matched.append(reference)

        if issue_code is None and not matched:
            issue_code = "claim_citation_required"

        records.append(
            ClaimEvidenceRecord(
                claim_id=claim_id,
                role=role,
                section_id=section_id,
                evidence_state=(
                    "withheld"
                    if issue_code is not None
                    else "inference"
                    if evidence_kind == "inference"
                    else "supported"
                ),
                citation_refs=() if issue_code is not None else tuple(matched),
                qualifiers=qualifiers,
                issue_code=issue_code,
            )
        )

    return _index(tuple(records), catalog)


def merge_claim_evidence_indexes(
    indexes: Iterable[ClaimEvidenceIndex],
) -> ClaimEvidenceIndex:
    """Merge independent role/pass indexes without changing their evidence."""

    records: list[ClaimEvidenceRecord] = []
    citations: list[CitationCatalogEntry] = []
    seen_claims: set[str] = set()
    seen_citations: set[str] = set()

    for index in indexes:
        if not isinstance(index, ClaimEvidenceIndex):
            raise ClaimEvidenceError("claim_evidence_index_invalid")
        if index.schema_version != SCHEMA_VERSION:
            raise ClaimEvidenceError("claim_evidence_index_invalid")
        for record in index.records:
            if record.claim_id in seen_claims:
                raise ClaimEvidenceError("claim_evidence_claim_id_duplicate")
            seen_claims.add(record.claim_id)
            records.append(record)
        for citation in index.citations:
            if citation.citation_ref in seen_citations:
                continue
            seen_citations.add(citation.citation_ref)
            citations.append(citation)

    return _index(tuple(records), tuple(citations))


def citation_reference(citation: CitationLike) -> str:
    """Derive the exact runtime semantic citation key without URL normalization."""

    locator = _text(getattr(citation, "locator", None), "claim_citation_locator_invalid")
    title_raw = getattr(citation, "title", None)
    title = None if title_raw is None else _text(
        title_raw,
        "claim_citation_title_invalid",
    )
    return "citation:sha256:" + _sha({"locator": locator, "title": title})


def _citation_catalog(
    *,
    role: str,
    pass_number: int,
    citations: Iterable[CitationLike],
) -> tuple[CitationCatalogEntry, ...]:
    result: list[CitationCatalogEntry] = []
    seen_semantic: set[tuple[str, str | None]] = set()
    for ordinal, citation in enumerate(citations):
        locator = _text(
            getattr(citation, "locator", None),
            "claim_citation_locator_invalid",
        )
        title_raw = getattr(citation, "title", None)
        title = None if title_raw is None else _text(
            title_raw,
            "claim_citation_title_invalid",
        )
        semantic_key = (locator, title)
        if semantic_key in seen_semantic:
            continue
        seen_semantic.add(semantic_key)
        source_kind = _text(
            getattr(citation, "source_kind", None),
            "claim_citation_source_kind_invalid",
        )
        provider_raw = getattr(citation, "provider_family", None)
        provider_family = None if provider_raw is None else _text(
            provider_raw,
            "claim_citation_provider_family_invalid",
        )
        result.append(
            CitationCatalogEntry(
                citation_ref=citation_reference(citation),
                role=role,
                pass_number=pass_number,
                ordinal=ordinal,
                locator=locator,
                title=title,
                source_kind=source_kind,
                provider_family=provider_family,
            )
        )
    return tuple(result)


def _index(
    records: tuple[ClaimEvidenceRecord, ...],
    citations: tuple[CitationCatalogEntry, ...],
) -> ClaimEvidenceIndex:
    value = {
        "schema_version": SCHEMA_VERSION,
        "records": [
            {
                "claim_id": item.claim_id,
                "role": item.role,
                "section_id": item.section_id,
                "evidence_state": item.evidence_state,
                "citation_refs": list(item.citation_refs),
                "qualifiers": list(item.qualifiers),
                "issue_code": item.issue_code,
            }
            for item in records
        ],
        "citations": [
            {
                "citation_ref": item.citation_ref,
                "role": item.role,
                "pass_number": item.pass_number,
                "ordinal": item.ordinal,
                "locator": item.locator,
                "title": item.title,
                "source_kind": item.source_kind,
                "provider_family": item.provider_family,
            }
            for item in citations
        ],
    }
    return ClaimEvidenceIndex(
        schema_version=SCHEMA_VERSION,
        records=records,
        citations=citations,
        index_digest="sha256:" + _sha(value),
    )


def _locator_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ClaimEvidenceError("claim_citation_locators_invalid")
    if len(value) > MAX_CITATION_REFS_PER_CLAIM:
        raise ClaimEvidenceError("claim_citation_locators_invalid")
    result: list[str] = []
    for item in value:
        locator = _text(item, "claim_citation_locator_invalid")
        if locator not in result:
            result.append(locator)
    return tuple(result)


def _qualifier_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > MAX_QUALIFIERS_PER_CLAIM:
        raise ClaimEvidenceError("claim_evidence_qualifiers_invalid")
    result: list[str] = []
    for item in value:
        qualifier = _text(item, "claim_evidence_qualifier_invalid")
        if len(qualifier) > MAX_QUALIFIER_CHARS:
            raise ClaimEvidenceError("claim_evidence_qualifier_invalid")
        if qualifier not in result:
            result.append(qualifier)
    return tuple(result)


def _token(value: Any, code: str) -> str:
    text = _text(value, code)
    if len(text) > 192 or any(character.isspace() for character in text):
        raise ClaimEvidenceError(code)
    return text


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ClaimEvidenceError(code)
    text = value.strip()
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in text):
        raise ClaimEvidenceError(code)
    return text


def _sha(value: Any) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
