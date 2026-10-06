"""Bounded literal-quote resolution over an explicitly admitted source snapshot."""
from __future__ import annotations

from typing import Any

if __package__:
    from . import tool_operations as base
else:
    import tool_operations as base

MAX_REQUESTS = 16
MAX_QUOTE_CHARS = 600


def resolve_exact_spans(arguments: dict[str, Any]) -> dict[str, Any]:
    base._object(arguments, {"entity_id", "snapshot_id", "source_units", "source_digest", "requests"})
    for key in ("entity_id", "snapshot_id"):
        base._id(arguments[key])
    units = base._items(arguments["source_units"], base.MAX_SOURCE_UNITS)
    if not units:
        raise base.ReviewToolError("review_tool_source_empty")
    index = {}
    total = 0
    for unit in units:
        base._object(unit, {"locator", "entity_id", "text", "accessible"})
        locator = base._id(unit["locator"])
        base._id(unit["entity_id"])
        if locator in index:
            raise base.ReviewToolError("review_tool_duplicate_locator")
        if not isinstance(unit["text"], str) or type(unit["accessible"]) is not bool:
            raise base.ReviewToolError("review_tool_source_unit_invalid")
        total += len(unit["text"])
        if total > base.MAX_SOURCE_CHARS or len(unit["text"]) > base.MAX_CHUNK_CHARS:
            raise base.ReviewToolError("review_tool_source_size_limit")
        index[locator] = unit
    material = {key: arguments[key] for key in ("entity_id", "snapshot_id", "source_units")}
    if arguments["source_digest"] != base.stable_digest(material):
        raise base.ReviewToolError("review_tool_source_digest_mismatch")
    requests = base._items(arguments["requests"], MAX_REQUESTS)
    seen = set()
    reason = None
    rejected_index = None
    # Validate the entire closed request batch before looking for any quote.
    for request_index, request in enumerate(requests):
        base._object(request, {"request_id", "locator", "quote"})
        request_id = base._id(request["request_id"])
        if request_id in seen:
            raise base.ReviewToolError("review_tool_duplicate_request")
        seen.add(request_id)
        locator = base._id(request["locator"])
        unit = index.get(locator)
        if unit is None:
            reason = reason or "evidence_locator_invalid"
        elif unit["entity_id"] != arguments["entity_id"]:
            reason = reason or "evidence_entity_mismatch"
        elif not unit["accessible"]:
            reason = reason or "evidence_inaccessible"
        if reason is not None and rejected_index is None:
            rejected_index = request_index
        quote = request["quote"]
        if not isinstance(quote, str) or not quote.strip() or len(quote) > MAX_QUOTE_CHARS:
            raise base.ReviewToolError("review_tool_evidence_quote_invalid")
    common = {"entity_id": arguments["entity_id"], "snapshot_id": arguments["snapshot_id"],
              "source_digest": arguments["source_digest"], "semantic_authority_verified": False}
    if reason is not None:
        return {**common, "status": "rejected", "reason_code": reason,
                "rejected_request_index": rejected_index, "spans": []}
    spans = []
    for request_index, request in enumerate(requests):
        quote, locator = request["quote"], request["locator"]
        unit = index[locator]
        text = unit["text"]
        start = text.find(quote)
        if start < 0:
            return {**common, "status": "rejected", "reason_code": "evidence_quote_missing",
                    "rejected_request_index": request_index, "spans": []}
        # Search from start+1, not end: overlapping occurrences are ambiguous too.
        if text.find(quote, start + 1) >= 0:
            return {**common, "status": "rejected", "reason_code": "evidence_quote_ambiguous",
                    "rejected_request_index": request_index, "spans": []}
        spans.append({"request_id": request["request_id"], "locator": locator,
                      "start": start, "end": start + len(quote), "quote": quote})
    return {**common, "status": "resolved", "reason_code": None,
            "rejected_request_index": None, "spans": spans}
