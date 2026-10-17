"""Deterministic, API-blind normalization for governed UMLS terminology records.

A trusted runtime supplies approved records. This adapter neither constructs
provider URLs nor handles credentials, network requests, storage or publication.
"""

from __future__ import annotations

import re
from typing import Any

from adapters.base import Adapter


ASSET_KEY = "umls_terminology"
ASSET_VERSION = "0.1.0"

SEARCH_TYPES = frozenset({
    "words", "exact", "leftTruncation", "rightTruncation",
    "normalizedString", "normalizedWords",
})
SEARCH_SEMANTIC_TYPES = {
    "gene_search": ("T028",),                 # Gene or Genome
    "protein_search": ("T116",),              # Amino Acid, Peptide, or Protein
    "drug_search": ("T121", "T200"),          # Pharmacologic Substance / Clinical Drug
}
CONCEPT_SEMANTIC_TYPES = {
    "gene_get": ("T028",),
    "protein_get": ("T116",),
    "drug_get": ("T121", "T200"),
}
SEARCH_OPERATIONS = frozenset({"search", *SEARCH_SEMANTIC_TYPES})
CONCEPT_OPERATIONS = frozenset({
    "concept_get", *CONCEPT_SEMANTIC_TYPES, "concept_atoms",
    "concept_definitions", "concept_relations", "gene_relations",
    "mechanism_relations",
})
SOURCE_OPERATIONS = frozenset({
    "source_get", "source_atoms", "source_relations", "source_attributes",
    "source_hierarchy", "crosswalk",
})
ATOM_OPERATIONS = frozenset({"atom_get", "atom_hierarchy"})
SUPPORTED_OPERATIONS = (
    "describe", "search", "gene_search", "protein_search", "drug_search",
    "concept_get", "gene_get", "protein_get", "drug_get",
    "concept_atoms", "concept_definitions", "concept_relations", "gene_relations",
    "mechanism_relations", "source_get", "source_atoms", "source_relations",
    "source_attributes", "source_hierarchy", "crosswalk",
    "atom_get", "atom_hierarchy", "semantic_type_get", "vocabularies",
)
RELATION_OPERATIONS = frozenset({
    "concept_relations", "gene_relations", "mechanism_relations", "source_relations",
})
ATOM_OUTPUT_OPERATIONS = frozenset({
    "concept_atoms", "source_atoms", "atom_get", "atom_hierarchy",
})
MECHANISM_TERMS = frozenset({
    "chemical_or_drug_affects_gene_product",
    "chemical_or_drug_has_mechanism_of_action",
    "gene_product_encoded_by_gene",
    "gene_plays_role_in_process",
})
CUI_RE = re.compile(r"C[0-9]{7}\Z")
AUI_RE = re.compile(r"A[0-9]+\Z")
TUI_RE = re.compile(r"T[0-9]{3}\Z")
SOURCE_RE = re.compile(r"[A-Z][A-Z0-9_]{0,39}\Z")
RELEASE_RE = re.compile(r"20[0-9]{2}(AA|AB)\Z")
TUI_URI_RE = re.compile(r"/TUI/(T[0-9]{3})/?\Z")
MAX_PROVIDER_RECORDS = 200
MAX_RESULT_RECORDS = 50
MAX_SELECTOR_LENGTH = 200
MAX_FIELD_LENGTH = 4096
HIERARCHY_DIRECTIONS = frozenset({"parents", "children", "ancestors", "descendants"})


def _required_text(value: Any, field: str, *, limit: int = MAX_SELECTOR_LENGTH) -> str:
    """Validate business text while preserving case, punctuation and leading zeros."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}_required")
    text = value.strip()
    if len(text) > limit or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise ValueError(f"{field}_invalid")
    return text


def _source_list(value: Any, field: str) -> list[str]:
    """Validate a bounded list of source-vocabulary abbreviations."""
    if not isinstance(value, list) or not 1 <= len(value) <= 5:
        raise ValueError(f"{field}_invalid")
    checked = []
    for item in value:
        source = _required_text(item, field, limit=40)
        if SOURCE_RE.fullmatch(source) is None or source in checked:
            raise ValueError(f"{field}_invalid")
        checked.append(source)
    return checked


def _validate_request(raw: Any) -> dict[str, Any]:
    """Select exactly one documented operation with bounded semantic selectors."""
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("variables_must_be_object")
    operation = raw.get("operation", "describe")
    if not isinstance(operation, str) or operation not in SUPPORTED_OPERATIONS:
        raise ValueError("operation_unsupported")
    if operation == "describe":
        if set(raw) - {"operation"}:
            raise ValueError("describe_does_not_accept_selectors")
        return {"operation": operation}

    request: dict[str, Any] = {"operation": operation}
    allowed = {"operation", "limit"}
    if operation in SEARCH_OPERATIONS:
        request["text"] = _required_text(raw.get("text"), "text")
        allowed.update({"text", "search_type", "sources"})
        search_type = raw.get("search_type", "words")
        if not isinstance(search_type, str) or search_type not in SEARCH_TYPES:
            raise ValueError("search_type_invalid")
        request["search_type"] = search_type
        if "sources" in raw:
            request["sources"] = _source_list(raw["sources"], "sources")
        if operation in SEARCH_SEMANTIC_TYPES:
            request["semantic_types"] = list(SEARCH_SEMANTIC_TYPES[operation])
            if operation == "gene_search":
                request["semantic_type"] = "T028"  # Original 0.1.0 alias
    elif operation in CONCEPT_OPERATIONS:
        cui = _required_text(raw.get("cui"), "cui", limit=8)
        if CUI_RE.fullmatch(cui) is None:
            raise ValueError("cui_invalid")
        request["cui"] = cui
        allowed.add("cui")
    elif operation in SOURCE_OPERATIONS:
        source = _required_text(raw.get("source"), "source", limit=40)
        if SOURCE_RE.fullmatch(source) is None:
            raise ValueError("source_invalid")
        request["source"] = source
        request["code"] = _required_text(raw.get("code"), "code")
        allowed.update({"source", "code"})
        if operation == "crosswalk":
            request["target_sources"] = _source_list(raw.get("target_sources"), "target_sources")
            allowed.add("target_sources")
    elif operation in ATOM_OPERATIONS:
        aui = _required_text(raw.get("aui"), "aui", limit=20)
        if AUI_RE.fullmatch(aui) is None:
            raise ValueError("aui_invalid")
        request["aui"] = aui
        allowed.add("aui")
    elif operation == "semantic_type_get":
        tui = _required_text(raw.get("tui"), "tui", limit=4)
        if TUI_RE.fullmatch(tui) is None:
            raise ValueError("tui_invalid")
        request["tui"] = tui
        allowed.add("tui")
    # vocabularies has no business selector; a requested result limit still applies.
    if operation in {"source_hierarchy", "atom_hierarchy"}:
        direction = raw.get("direction")
        if not isinstance(direction, str) or direction not in HIERARCHY_DIRECTIONS:
            raise ValueError("hierarchy_direction_invalid")
        request["direction"] = direction
        allowed.add("direction")
    if set(raw) - allowed:
        raise ValueError("selector_unsupported")
    limit = raw.get("limit", 20)
    if type(limit) is not int or not 1 <= limit <= MAX_RESULT_RECORDS:
        raise ValueError("limit_out_of_range")
    request["limit"] = limit
    return request


def _source_payload(inputs: dict[str, Any], operation: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Validate a pre-normalized trusted input; do not reinterpret raw HTTP envelopes."""
    payload = inputs.get("umls_response")
    if not isinstance(payload, dict):
        raise ValueError("umls_response_not_resolved")
    if payload.get("operation") != operation:
        raise ValueError("umls_response_operation_mismatch")
    records = payload.get("records")
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise ValueError("umls_response_records_invalid")
    if len(records) > MAX_PROVIDER_RECORDS:
        raise ValueError("umls_response_record_budget_exceeded")
    status = payload.get("status")
    if not isinstance(status, str) or status not in {"ok", "not_found", "partial"}:
        raise ValueError("umls_response_status_invalid")
    if status == "not_found" and records:
        raise ValueError("umls_response_not_found_conflict")
    if "truncated" in payload and type(payload["truncated"]) is not bool:
        raise ValueError("umls_response_truncated_invalid")
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("umls_response_provenance_missing")
    release = provenance.get("release")
    if not isinstance(release, str) or not release.strip():
        raise ValueError("umls_response_release_missing")
    if RELEASE_RE.fullmatch(release) is None:
        raise ValueError("umls_response_release_unresolved")
    return payload, records


def _optional_provenance(provenance: dict[str, Any], field: str) -> str | None:
    """Accept only bounded, scalar provenance metadata."""
    value = provenance.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 100:
        raise ValueError(f"umls_provenance_{field}_invalid")
    return value

def _field(record: dict[str, Any], name: str) -> str | bool | int | None:
    """Project scalar UMLS fields only; never forward arbitrary provider objects."""
    value = record.get(name)
    if value is None:
        return None
    if isinstance(value, str):
        if len(value) > MAX_FIELD_LENGTH or any(ord(ch) in {0, 127} for ch in value):
            raise ValueError(f"umls_record_{name}_invalid")
        return value
    if type(value) is bool and name in {"obsolete", "suppressible", "sourceOriginated"}:
        return value
    if type(value) is int and name in {"atomCount", "relationCount", "attributeCount", "restrictionLevel"}:
        return value
    raise ValueError(f"umls_record_{name}_invalid")


def _semantic_types(record: dict[str, Any]) -> list[dict[str, str | None]] | None:
    """Read NLM search-name arrays and concept name/URI objects without loss."""
    raw = record.get("semanticTypes", record.get("semantic_types"))
    if raw is None:
        return None  # Not returned by this endpoint != known absence.
    if not isinstance(raw, list) or len(raw) > 32:
        raise ValueError("umls_semantic_types_invalid")
    normalized = []
    for item in raw:
        name: str | None = None
        tui: str | None = None
        if isinstance(item, str):
            if item.startswith("T") and TUI_RE.fullmatch(item):
                tui = item
            else:
                name = item
        elif isinstance(item, dict):
            name = item.get("name")
            uri = item.get("uri")
            if name is not None and not isinstance(name, str):
                raise ValueError("umls_semantic_type_name_invalid")
            if uri is not None:
                if not isinstance(uri, str):
                    raise ValueError("umls_semantic_type_uri_invalid")
                match = TUI_URI_RE.search(uri)
                if match is None:
                    raise ValueError("umls_semantic_type_uri_invalid")
                tui = match.group(1)
        else:
            raise ValueError("umls_semantic_types_invalid")
        if name is not None and len(name) > 200:
            raise ValueError("umls_semantic_type_name_invalid")
        if name is None and tui is None:
            raise ValueError("umls_semantic_types_invalid")
        normalized.append({"name": name, "tui": tui})
    return normalized


def _matches_semantic_type(
    semantic_types: list[dict[str, str | None]] | None, operation: str
) -> bool | None:
    """Return None when type data was not returned, not a false classification."""
    expected = CONCEPT_SEMANTIC_TYPES.get(operation) or SEARCH_SEMANTIC_TYPES.get(operation)
    if expected is None or semantic_types is None:
        return None
    labels = {
        "T028": "Gene or Genome",
        "T116": "Amino Acid, Peptide, or Protein",
        "T121": "Pharmacologic Substance",
        "T200": "Clinical Drug",
    }
    return any(
        entry["tui"] in expected
        or any(entry["name"] == labels[tui] for tui in expected)
        for entry in semantic_types
    )


def _project_record(record: dict[str, Any], operation: str) -> dict[str, Any]:
    """Preserve needed terminology/source evidence without unbounded raw payloads."""
    fields = (
        "ui", "name", "uri", "rootSource", "classType", "sourceUi",
        "obsolete", "suppressible",
    )
    if operation in RELATION_OPERATIONS:
        fields += (
            "relationLabel", "additionalRelationLabel", "relatedFromId",
            "relatedFromIdName", "relatedId", "relatedIdName", "sourceOriginated",
            "groupId", "attributeCount",
        )
    elif operation in ATOM_OUTPUT_OPERATIONS:
        fields += ("termType", "language", "code", "concept", "sourceConcept", "sourceDescriptor")
    elif operation == "concept_definitions":
        fields += ("value",)
    elif operation == "source_attributes":
        fields += ("value", "attributeCount")
    elif operation == "semantic_type_get":
        fields += ("definition", "treeNumber", "abbreviation", "usageNote")
    elif operation == "vocabularies":
        fields += ("abbreviation", "restrictionLevel", "family", "language")
    elif operation in {"concept_get", "gene_get", "protein_get", "drug_get", "source_get"}:
        fields += ("atomCount", "relationCount", "attributeCount", "status")
    projected = {name: _field(record, name) for name in fields if name in record}
    semantic_types = _semantic_types(record) if operation in (
        SEARCH_OPERATIONS | {"concept_get", *CONCEPT_SEMANTIC_TYPES}
    ) else None
    if semantic_types is not None:
        projected["semantic_types"] = semantic_types
    if operation in SEARCH_SEMANTIC_TYPES | CONCEPT_SEMANTIC_TYPES.keys():
        projected["terminology_type_match"] = _matches_semantic_type(semantic_types, operation)
        if operation.startswith("gene_"):
            projected["gene_terminology_match"] = projected["terminology_type_match"]
    if operation in RELATION_OPERATIONS:
        label = projected.get("additionalRelationLabel")
        projected["mechanism_label_observed"] = (
            isinstance(label, str) and label in MECHANISM_TERMS
        )
        # The record's direction and source must be retained; no efficacy inference.
    if operation == "crosswalk":
        projected["mapping_basis"] = "shared_umls_cui_candidate"
        projected["clinical_equivalence_verified"] = False
    return projected


class UmlsTerminologyAdapter(Adapter):
    """Normalize one bounded operation result with exact release provenance."""

    key = ASSET_KEY
    version = ASSET_VERSION

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Validate business selectors, then consume runtime-supplied records."""
        request = _validate_request(inputs.get("variables"))
        operation = request["operation"]
        if operation == "describe":
            result: dict[str, Any] = {
                "operation": "describe", "status": "ok", "query": {},
                "records": [], "capabilities": list(SUPPORTED_OPERATIONS),
                "provenance": None,
                "completeness": {"returned_count": 0, "truncated": False},
            }
        else:
            payload, records = _source_payload(inputs, operation)
            projected = [_project_record(record, operation) for record in records[:request["limit"]]]
            truncated = len(records) > request["limit"] or payload.get("truncated", False)
            upstream_status = payload["status"]
            status = "partial" if truncated and upstream_status == "ok" else upstream_status
            provenance = payload["provenance"]
            result = {
                "operation": operation,
                "status": status,
                "query": request,
                "records": projected,
                "provenance": {
                    "provider": "UMLS",
                    "release": provenance["release"],
                    "retrieved_at": _optional_provenance(provenance, "retrieved_at"),
                    "source_vocabulary": _optional_provenance(provenance, "source_vocabulary"),
                },
                "completeness": {
                    "returned_count": len(projected),
                    "truncated": bool(truncated),
                },
            }
        return {
            "response_version": "1",
            "status": "success",
            "outputs": {"terminology_result": result},
            "logs": [],
            "metrics": {"record_count": len(result["records"])},
        }
