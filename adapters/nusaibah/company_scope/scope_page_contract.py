"""Native full-dump page projection; no query, checkpoint, or resume authority."""
from __future__ import annotations

from typing import Any

if __package__:
    from .scope_contract import (
        CORPORATE_ID, MAX_COMPANY_ID, MAX_COMPANY_IDS, _ENVELOPE_FIELDS,
        _PROVENANCE_REQUIRED, _SAFE_REFERENCE, _fail,
        assemble_record_contexts, canonical_digest,
    )
else:
    from scope_contract import (
        CORPORATE_ID, MAX_COMPANY_ID, MAX_COMPANY_IDS, _ENVELOPE_FIELDS,
        _PROVENANCE_REQUIRED, _SAFE_REFERENCE, _fail,
        assemble_record_contexts, canonical_digest,
    )

PAGE_SCHEMA = "company_scope_page.v1"
_PAGE_PROVENANCE_FIELDS = _PROVENANCE_REQUIRED | {
    "input_mode", "page_index", "record_offset",
}


def build_scope_page(variables: Any, companies: Any) -> dict[str, Any]:
    """Validate one native page without claiming whole-run selection completion."""
    if not isinstance(variables, dict) or variables != {"selection": "all_authorized"}:
        _fail("selector_invalid")
    if not isinstance(companies, dict) or set(companies) != _ENVELOPE_FIELDS:
        _fail("source_invalid")
    records = companies["records"]
    if not isinstance(records, list) or len(records) > MAX_COMPANY_IDS:
        _fail("rows_invalid")
    if type(companies["row_count"]) is not int or companies["row_count"] != len(records):
        _fail("source_invalid")
    provenance = companies["provenance"]
    if not isinstance(provenance, dict) or set(provenance) != _PAGE_PROVENANCE_FIELDS:
        _fail("source_invalid")
    lake_id = provenance["lake_id"]
    if (provenance["source"] != "dlm_node" or provenance["authority"] != "dlm_node"
            or provenance["node_key"] != "companies"
            or not isinstance(lake_id, str) or _SAFE_REFERENCE.fullmatch(lake_id) is None
            or provenance["input_mode"] != "full_dump_async"
            or type(provenance["pages_read"]) is not int or provenance["pages_read"] != 1):
        _fail("source_invalid")
    page_index = provenance["page_index"]
    record_offset = provenance["record_offset"]
    if (type(page_index) is not int or not 0 <= page_index <= MAX_COMPANY_ID
            or type(record_offset) is not int or not 0 <= record_offset <= MAX_COMPANY_ID
            or (page_index == 0 and record_offset != 0)
            or (page_index > 0 and record_offset < page_index)):
        _fail("source_invalid")

    # Preserve native partial-source truth. Only normal continuation is accepted;
    # policy/time caps and ambiguous source states fail before output assembly.
    if companies["exactness"] == "exact" and companies["partial_reason"] is None:
        source_exhausted = True
    elif (companies["exactness"] == "partial"
          and companies["partial_reason"] == "more_pages_available" and records):
        source_exhausted = False
    else:
        _fail("source_incomplete")
    contexts = assemble_record_contexts(records, lake_id)
    result = {
        "schema_version": PAGE_SCHEMA,
        "selection": "all_authorized",
        "corporate_id": CORPORATE_ID,
        "company_count": len(contexts),
        "contexts": [item.to_dict() for item in contexts],
        "page": {"page_index": page_index, "record_offset": record_offset},
        "source_exactness": companies["exactness"],
        "source_partial_reason": companies["partial_reason"],
        "batch_complete": True,
        "source_exhausted": source_exhausted,
        # The stateless adapter cannot attest prior-page processing or retention.
        "selection_complete": None,
        "completion_scope": "current_page",
        "validation_scope": "resolved_page_only",
        "runtime_authority_verified": False,
    }
    result["digest"] = canonical_digest(result)
    return result
