"""Provider-blind UMLS terminology adapter.

Consumes exact governed UMLS records. This module performs no HTTP,
credentials, DLM/Core access, storage writes or provider retries.
"""

from __future__ import annotations

import re
from typing import Any

from adapters.base import Adapter


ASSET_KEY = "nusaibah.umls_terminology"
ASSET_VERSION = "0.1.0"
SUPPORTED_OPERATIONS = (
    "describe",
    "search",
    "gene_search",
    "concept_get",
    "gene_get",
    "concept_relations",
    "mechanism_relations",
)
GENE_SEMANTIC_TYPE = "T028"  # Gene or Genome
CUI_PATTERN = re.compile(r"^C[0-9]{7}$")
MAX_RECORDS = 50
MAX_TEXT = 200
MECHANISM_TERMS = (
    "chemical_or_drug_affects_gene_product",
    "chemical_or_drug_has_mechanism_of_action",
    "gene_product_encoded_by_gene",
    "gene_plays_role_in_process",
)


def _required_text(value: Any, field: str, *, max_length: int = MAX_TEXT) -> str:
    """Validate semantic caller values without changing identifier spelling."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}_required")
    text = value.strip()
    if len(text) > max_length or any(ord(char) < 32 for char in text):
        raise ValueError(f"{field}_invalid")
    return text


def _validate_request(raw: Any) -> dict[str, Any]:
    """Validate operation and required selector before governed record access."""
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("variables_must_be_object")
    operation = raw.get("operation", "describe")
    if operation not in SUPPORTED_OPERATIONS:
        raise ValueError("operation_unsupported")
    validated: dict[str, Any] = {"operation": operation}
    if operation == "describe":
        if set(raw) - {"operation"}:
            raise ValueError("describe_does_not_accept_selectors")
        return validated
    if operation in {"search", "gene_search"}:
        validated["text"] = _required_text(raw.get("text"), "text")
    else:
        cui = _required_text(raw.get("cui"), "cui", max_length=8)
        if CUI_PATTERN.fullmatch(cui) is None:
            raise ValueError("cui_invalid")
        validated["cui"] = cui
    allowed = {"operation", "text" if "text" in validated else "cui", "limit"}
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError("selector_unsupported")
    limit = raw.get("limit", 20)
    if isinstance(limit, bool) or not isinstance(limit, int) or not (1 <= limit <= MAX_RECORDS):
        raise ValueError("limit_out_of_range")
    validated["limit"] = limit
    if operation == "gene_search":
        validated["semantic_type"] = GENE_SEMANTIC_TYPE
    return validated


def _source_records(inputs: dict[str, Any], operation: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Require records resolved by runtime and matching the requested operation."""
    payload = inputs.get("umls_response")
    if not isinstance(payload, dict):
        raise ValueError("umls_response_not_resolved")
    if payload.get("operation") != operation:
        raise ValueError("umls_response_operation_mismatch")
    records = payload.get("records")
    if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
        raise ValueError("umls_response_records_invalid")
    if len(records) > MAX_RECORDS:
        raise ValueError("umls_response_record_budget_exceeded")
    if payload.get("status") not in {"ok", "not_found", "partial"}:
        raise ValueError("umls_response_status_invalid")
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("umls_response_provenance_missing")
    release = provenance.get("release")
    if not isinstance(release, str) or not release.strip():
        raise ValueError("umls_response_release_missing")
    return records, provenance


def _projection(record: dict[str, Any], operation: str) -> dict[str, Any]:
    """Return bounded terminology fields, keeping relation labels source-asserted."""
    identifier = record.get("ui", record.get("cui"))
    if identifier is not None and not isinstance(identifier, str):
        raise ValueError("umls_record_identifier_invalid")
    name = record.get("name")
    if name is not None and (not isinstance(name, str) or len(name) > 1000):
        raise ValueError("umls_record_name_invalid")
    normalized: dict[str, Any] = {
        "ui": identifier,
        "name": name,
        "root_source": record.get("rootSource") if isinstance(record.get("rootSource"), str) else None,
        "uri": record.get("uri") if isinstance(record.get("uri"), str) else None,
    }
    if operation in {"gene_search", "gene_get"}:
        semtypes = record.get("semantic_types", record.get("semanticTypes", []))
        if not isinstance(semtypes, list):
            raise ValueError("umls_record_semantic_types_invalid")
        normalized["semantic_types"] = [
            item for item in semtypes[:20] if isinstance(item, str) and len(item) <= 100
        ]
        normalized["gene_terminology_match"] = GENE_SEMANTIC_TYPE in normalized["semantic_types"]
    if operation in {"concept_relations", "mechanism_relations"}:
        for field in ("relationLabel", "additionalRelationLabel", "relatedId", "relatedIdName",
                      "relation_source", "source_ui", "suppressible"):
            value = record.get(field)
            if value is not None and (not isinstance(value, str) or len(value) > 1000):
                raise ValueError(f"umls_relation_{field}_invalid")
            normalized[field] = value
        # Raw source label is evidence. Do not manufacture a mechanism conclusion.
        label = normalized.get("additionalRelationLabel")
        normalized["mechanism_label_observed"] = (
            label in MECHANISM_TERMS if isinstance(label, str) else False
        )
    return normalized


class UmlsTerminologyAdapter(Adapter):
    """Normalize bounded, source-attributed UMLS records into one result role."""

    key = ASSET_KEY
    version = ASSET_VERSION

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Return a complete safe result or fail closed for invalid governed input."""
        request = _validate_request(inputs.get("variables"))
        operation = request["operation"]
        if operation == "describe":
            result = {
                "operation": "describe",
                "status": "ok",
                "query": {},
                "records": [],
                "capabilities": list(SUPPORTED_OPERATIONS),
                "provenance": None,
                "completeness": {"returned_count": 0, "truncated": False},
            }
        else:
            records, provenance = _source_records(inputs, operation)
            limit = request["limit"]
            projected = [_projection(record, operation) for record in records[:limit]]
            result = {
                "operation": operation,
                "status": inputs["umls_response"]["status"],
                "query": request,
                "records": projected,
                "provenance": {
                    "provider": "UMLS",
                    "release": provenance["release"],
                    "retrieved_at": provenance.get("retrieved_at"),
                },
                "completeness": {
                    "returned_count": len(projected),
                    "truncated": len(records) > limit or bool(inputs["umls_response"].get("truncated")),
                },
            }
        return {
            "response_version": "1",
            "status": "success",
            "outputs": {"terminology_result": result},
            "logs": [],
            "metrics": {"record_count": len(result["records"])},
        }
