"""Bounded selector and DTO contracts; no runtime or data-query authority."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

MAX_COMPANY_IDS = 25
MAX_COMPANY_ID = 2**63 - 1
CORPORATE_ID = 1
CONTEXT_SCHEMA = "company_context.v1"
RESULT_SCHEMA = "company_scope_result.v1"
ROW_FIELDS = frozenset({
    "id", "company", "corporate_id", "address_line1", "address_line2",
    "headquarter", "website", "updated_at",
})
_REQUIRED_ROW_FIELDS = frozenset({"id", "company", "corporate_id"})
_ENVELOPE_FIELDS = frozenset({"records", "row_count", "exactness", "partial_reason", "provenance"})
_PROVENANCE_REQUIRED = frozenset({"source", "authority", "lake_id", "node_key", "pages_read"})
_PROVENANCE_FIELDS = _PROVENANCE_REQUIRED | {"input_mode"}
_SAFE_REFERENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,189}\Z")


class CompanyScopeError(ValueError):
    """A stable value-free failure code; never include source values in errors."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> None:
    raise CompanyScopeError("company_scope_" + code)


def _positive_id(value: Any) -> int:
    if type(value) is not int or not 0 < value <= MAX_COMPANY_ID:
        _fail("identifier_invalid")
    return value


@dataclass(frozen=True)
class ScopeRequest:
    company_ids: tuple[int, ...]
    selector_kind: str
    duplicate_id_count: int = 0


def normalize_selector(variables: Any) -> ScopeRequest:
    """Shared specification for pre-query preparation and defensive validation.

    Calling this in Python cannot change a query already prepared by Assets.
    Bounds are checked before range expansion or list normalization.
    """
    if not isinstance(variables, dict):
        _fail("selector_invalid")
    keys = set(variables)
    if keys == {"company_id"}:
        return ScopeRequest((_positive_id(variables["company_id"]),), "single")
    if keys == {"company_ids"}:
        values = variables["company_ids"]
        if not isinstance(values, list) or not values:
            _fail("selector_invalid")
        if len(values) > MAX_COMPANY_IDS:
            _fail("selector_limit_exceeded")
        ordered = tuple(dict.fromkeys(_positive_id(value) for value in values))
        return ScopeRequest(ordered, "list", len(values) - len(ordered))
    if keys == {"from_company_id", "to_company_id"}:
        first = _positive_id(variables["from_company_id"])
        last = _positive_id(variables["to_company_id"])
        if last < first:
            _fail("range_invalid")
        if last - first + 1 > MAX_COMPANY_IDS:
            _fail("selector_limit_exceeded")
        return ScopeRequest(tuple(range(first, last + 1)), "range")
    # Also rejects corporate_id, arbitrary fields/options, and mixed forms.
    _fail("selector_invalid")


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _text(value: Any, maximum: int, *, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or len(value) > maximum or "\x00" in value:
        _fail("row_value_invalid")
    value = value.strip()
    if not value:
        if required:
            _fail("row_value_invalid")
        return None
    return value


@dataclass(frozen=True)
class CompanyContext:
    company_id: int
    company_name: str
    corporate_id: int
    address_line1: str | None
    address_line2: str | None
    headquarters_country_id: int | None
    website: str | None
    source_updated_at: str | None
    lake_id: str

    def to_dict(self) -> dict[str, Any]:
        # Construct fresh objects per company and call: no shared mutable state.
        result = {
            "schema_version": CONTEXT_SCHEMA,
            "company_id": self.company_id,
            "company_name": self.company_name,
            "corporate_id": self.corporate_id,
            "address_line1": self.address_line1,
            "address_line2": self.address_line2,
            "headquarters_country_id": self.headquarters_country_id,
            "website": self.website,
            "source_updated_at": self.source_updated_at,
            "source": {
                "input_role": "companies", "source": "dlm_node",
                "lake_id": self.lake_id, "node_key": "companies",
                # The current safe node-query envelope supplies neither field.
                "retrieved_at": None, "schema_version": None,
            },
        }
        result["digest"] = canonical_digest(result)
        return result


def _source_envelope(companies: Any) -> tuple[list[Any], str]:
    """Validate the actual Assets safeDlmNodePythonInputPayload shape.

    Envelope conformance is not authentication. Assets/Core must establish
    binding origin, fixed query predicates, and projection before hydration.
    Assets/Core own page budgets; pages_read is metadata, not iteration.
    Complete bounded results may span several server-retrieved pages.
    """
    if not isinstance(companies, dict) or set(companies) != _ENVELOPE_FIELDS:
        _fail("source_invalid")
    records = companies["records"]
    if not isinstance(records, list) or len(records) > MAX_COMPANY_IDS:
        _fail("rows_invalid")
    if type(companies["row_count"]) is not int or companies["row_count"] != len(records):
        _fail("source_invalid")
    if companies["exactness"] != "exact" or companies["partial_reason"] is not None:
        _fail("source_incomplete")
    provenance = companies["provenance"]
    if (not isinstance(provenance, dict)
            or not _PROVENANCE_REQUIRED <= set(provenance) <= _PROVENANCE_FIELDS):
        _fail("source_invalid")
    lake_id = provenance["lake_id"]
    if (provenance["source"] != "dlm_node" or provenance["authority"] != "dlm_node"
            or provenance["node_key"] != "companies"
            or not isinstance(lake_id, str) or _SAFE_REFERENCE.fullmatch(lake_id) is None
            or type(provenance["pages_read"]) is not int or provenance["pages_read"] <= 0
            or provenance.get("input_mode") not in (None, "bounded_query")):
        _fail("source_invalid")
    return records, lake_id


def assemble_contexts(request: ScopeRequest, companies: Any) -> tuple[CompanyContext, ...]:
    records, lake_id = _source_envelope(companies)
    by_id: dict[int, CompanyContext] = {}
    requested_ids = set(request.company_ids)
    for row in records:
        if not isinstance(row, dict):
            _fail("rows_invalid")
        if not _REQUIRED_ROW_FIELDS <= set(row) <= ROW_FIELDS:
            _fail("row_fields_invalid")
        company_id = _positive_id(row["id"])
        if company_id in by_id:
            _fail("row_duplicate")
        if company_id not in requested_ids:
            _fail("result_set_mismatch")
        if type(row["corporate_id"]) is not int or row["corporate_id"] != CORPORATE_ID:
            _fail("corporate_scope_mismatch")
        headquarter = row.get("headquarter")
        if headquarter is not None:
            headquarter = _positive_id(headquarter)
        by_id[company_id] = CompanyContext(
            company_id=company_id,
            company_name=_text(row["company"], 512, required=True),
            corporate_id=CORPORATE_ID,
            address_line1=_text(row.get("address_line1"), 4096),
            address_line2=_text(row.get("address_line2"), 4096),
            headquarters_country_id=headquarter,
            website=_text(row.get("website"), 2048),
            source_updated_at=_text(row.get("updated_at"), 64),
            lake_id=lake_id,
        )
    if set(by_id) != requested_ids:
        _fail("result_set_mismatch")
    return tuple(by_id[company_id] for company_id in request.company_ids)


def build_scope_result(variables: Any, companies: Any) -> dict[str, Any]:
    request = normalize_selector(variables)
    contexts = assemble_contexts(request, companies)
    result = {
        "schema_version": RESULT_SCHEMA,
        "selector_kind": request.selector_kind,
        "requested_company_ids": list(request.company_ids),
        "duplicate_id_count": request.duplicate_id_count,
        "company_count": len(contexts),
        "corporate_id": CORPORATE_ID,
        "complete": True,
        "validation_scope": "resolved_rows_only",
        "runtime_authority_verified": False,
        "contexts": [company.to_dict() for company in contexts],
    }
    result["digest"] = canonical_digest(result)
    return result
