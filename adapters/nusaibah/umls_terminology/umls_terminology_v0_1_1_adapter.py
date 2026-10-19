"""Versioned UMLS search consumer of runtime-authenticated fetch receipts.

The worker authenticates receipt origin and matches its admitted Core source.
This adapter independently verifies its declared selectors and full records.
It never obtains provider credentials, endpoints, or raw worker transport data.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import re
from typing import Any

from adapters.base import Adapter

if __package__:
    from .umls_terminology_adapter import (
        _normalize_terminology_result,
        _validate_request,
        SUPPORTED_OPERATIONS,
    )
else:
    from umls_terminology_adapter import (
        _normalize_terminology_result,
        _validate_request,
        SUPPORTED_OPERATIONS,
    )


_KEYS = frozenset({
    "schema_version", "fetch_id", "source_id", "capability_ref", "operation",
    "effective_selectors_digest", "response_digest", "record_count",
    "completed_at_utc",
})
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_FETCH_ID = re.compile(r"rsf_[0-9a-f]{32}\Z")
_REF = re.compile(r"[A-Za-z0-9_.:@-]{1,191}\Z")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z\Z")


def _digest(value: Any) -> str:
    """Mirror the reviewed runtime JSON canonicalization, without network access."""
    try:
        encoded = json.dumps(
            value, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        )
        round_trip = json.loads(encoded)
        raw = encoded.encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError):
        raise ValueError("umls_attestation_json_invalid") from None
    if round_trip != value or type(round_trip) is not type(value):
        raise ValueError("umls_attestation_json_invalid")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _selectors(request: dict[str, Any]) -> dict[str, str]:
    """Reconstruct only the admitted, pre-auth business search selectors."""
    selectors = {
        "string": request["text"],
        "searchType": request["search_type"],
    }
    if "sources" in request:
        selectors["sabs"] = ",".join(request["sources"])
    return selectors


def _verified_receipt(
    value: Any,
    *,
    records: Any,
    selectors: dict[str, str],
) -> dict[str, Any]:
    """Check closed receipt contents; worker alone authenticates its origin."""
    if not isinstance(value, dict) or set(value) != _KEYS:
        raise ValueError("umls_attestation_shape_invalid")
    if value.get("schema_version") != "runtime_source_fetch_evidence.v1":
        raise ValueError("umls_attestation_version_invalid")
    if not isinstance(value.get("fetch_id"), str) or not _FETCH_ID.fullmatch(value["fetch_id"]):
        raise ValueError("umls_attestation_fetch_id_invalid")
    for name in ("source_id", "capability_ref", "operation"):
        actual = value.get(name)
        if not isinstance(actual, str) or not _REF.fullmatch(actual):
            raise ValueError("umls_attestation_identity_invalid")
    if value["capability_ref"] != "umls.terminology.search" or value["operation"] != "search":
        raise ValueError("umls_attestation_identity_invalid")
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        raise ValueError("umls_attestation_records_invalid")
    count = value.get("record_count")
    if type(count) is not int or count != len(records):
        raise ValueError("umls_attestation_count_mismatch")
    for name in ("effective_selectors_digest", "response_digest"):
        digest = value.get(name)
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise ValueError("umls_attestation_digest_invalid")
    if value["response_digest"] != _digest(records):
        raise ValueError("umls_attestation_records_mismatch")
    if value["effective_selectors_digest"] != _digest([selectors]):
        raise ValueError("umls_attestation_selectors_mismatch")
    completed = value.get("completed_at_utc")
    if not isinstance(completed, str) or not _UTC.fullmatch(completed):
        raise ValueError("umls_attestation_timestamp_invalid")
    try:
        datetime.strptime(completed, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        raise ValueError("umls_attestation_timestamp_invalid") from None
    return dict(value)


class UmlsTerminologyV011Adapter(Adapter):
    """UMLS plain-search consumer requiring a trusted worker fetch receipt."""

    key = "umls_terminology"
    version = "0.1.1"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        """Invoke only the governed role and attest its full fetch before projection."""
        del context
        request = _validate_request(inputs.get("variables"))
        if request["operation"] == "describe":
            result = {
                "operation": "describe", "status": "ok", "query": {},
                "records": [], "capabilities": list(SUPPORTED_OPERATIONS),
                "provenance": None,
                "completeness": {"returned_count": 0, "truncated": False},
            }
        else:
            if request["operation"] != "search":
                raise ValueError("umls_runtime_operation_not_mapped")
            if not isinstance(inputs.get("umls_response"), dict):
                raise ValueError("umls_runtime_source_not_prepared")
            invoker = getattr(inputs, "invoke", None)
            if not callable(invoker):
                raise ValueError("umls_runtime_source_not_prepared")
            selectors = _selectors(request)
            try:
                fetched = invoker(
                    "umls_response", variables=selectors,
                    include_evidence=True, on_error="raise",
                )
            except Exception:
                raise ValueError("umls_runtime_source_fetch_failed") from None
            if not isinstance(fetched, dict) or set(fetched) != {"records", "metadata", "evidence"}:
                raise ValueError("umls_attestation_envelope_invalid")
            # Validate all fetched records before the normalizer's local result limit.
            receipt = _verified_receipt(
                fetched["evidence"], records=fetched["records"], selectors=selectors,
            )
            trusted_envelope = {
                "records": fetched["records"], "metadata": fetched["metadata"],
            }
            result = _normalize_terminology_result(request, trusted_envelope)
            result["query_attested"] = True
            # Distinguish runtime fetch evidence from UMLS provider release metadata.
            result["provenance"]["runtime_fetch_evidence"] = receipt
        return {
            "response_version": "1",
            "status": "success",
            "outputs": {"terminology_result": result},
            "logs": [],
            "metrics": {"record_count": len(result["records"])},
        }
