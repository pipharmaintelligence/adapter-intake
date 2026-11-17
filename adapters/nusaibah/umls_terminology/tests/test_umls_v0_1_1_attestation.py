"""Provider-free tests of UMLS 0.1.1's closed fetch evidence contract."""

import copy
import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from umls_terminology_v0_1_1_adapter import UmlsTerminologyV011Adapter, _digest

ROWS = [{"ui": "C0000001", "name": "BRCA1"}, {"ui": "C0000002", "name": "BRCA1 gene"}]
SELECTORS = {"string": "BRCA1", "searchType": "exact"}


def receipt(rows=ROWS, selectors=SELECTORS):
    return {
        "schema_version": "runtime_source_fetch_evidence.v1",
        "fetch_id": "rsf_" + uuid4().hex,
        "source_id": "rt_src_synthetic",
        "capability_ref": "umls.terminology.search",
        "operation": "search",
        "effective_selectors_digest": _digest([selectors]),
        "response_digest": _digest(rows),
        "record_count": len(rows),
        "completed_at_utc": "2026-10-19T13:30:03.996Z",
    }


class WorkerInputs(dict):
    def __init__(self, rows=ROWS, evidence=None, variables=None):
        super().__init__({
            "variables": variables or {"operation": "search", "text": "BRCA1", "search_type": "exact"},
            "umls_response": {"records": []},
        })
        self.rows = rows
        self.evidence = receipt(rows=rows) if evidence is None else evidence
        self.calls = []

    def invoke(self, role, *, variables, include_evidence, on_error):
        self.calls.append((role, variables, include_evidence, on_error))
        return {"records": self.rows, "metadata": {}, "evidence": self.evidence}


def invoke(runtime):
    return UmlsTerminologyV011Adapter().invoke(runtime, {})["outputs"]["terminology_result"]


def test_success_attests_only_actual_search_query():
    runtime = WorkerInputs()
    result = invoke(runtime)
    assert result["query_attested"] is True
    assert result["provenance"]["runtime_fetch_evidence"]["record_count"] == 2
    assert result["provenance"]["release"] is None
    assert result["provenance"]["retrieved_at"] is None
    assert result["provenance"]["source_vocabulary"] is None
    assert result["completeness"]["truncated"] is None
    assert runtime.calls == [("umls_response", SELECTORS, True, "raise")]


def test_record_digest_is_checked_before_limit_projection():
    runtime = WorkerInputs(variables={"operation": "search", "text": "BRCA1", "search_type": "exact", "limit": 1})
    result = invoke(runtime)
    assert len(result["records"]) == 1
    assert result["query_attested"] is True
    assert result["provenance"]["runtime_fetch_evidence"]["record_count"] == 2
    assert result["completeness"]["truncated"] is True


@pytest.mark.parametrize("change", [
    lambda e: e.pop("fetch_id"),
    lambda e: e.update({"schema_version": "runtime_source_fetch_evidence.v2"}),
    lambda e: e.update({"capability_ref": "other"}),
    lambda e: e.update({"operation": "read"}),
    lambda e: e.update({"source_id": ""}),
    lambda e: e.update({"record_count": 1}),
    lambda e: e.update({"record_count": True}),
    lambda e: e.update({"response_digest": "sha256:" + "0" * 64}),
    lambda e: e.update({"effective_selectors_digest": "sha256:" + "0" * 64}),
    lambda e: e.update({"completed_at_utc": "not-a-time"}),
    lambda e: e.update({"unknown": "untrusted"}),
])
def test_bad_receipt_fails_closed(change):
    e = receipt()
    change(e)
    with pytest.raises(ValueError, match="umls_attestation_"):
        invoke(WorkerInputs(evidence=e))


def test_missing_evidence_and_default_envelope_fail_closed():
    class NoEvidence(WorkerInputs):
        def invoke(self, *args, **kwargs):
            return {"records": ROWS, "metadata": {}}
    with pytest.raises(ValueError, match="umls_attestation_envelope_invalid"):
        invoke(NoEvidence())


def test_mutated_records_fail_closed():
    e = receipt()
    with pytest.raises(ValueError, match="umls_attestation_count_mismatch"):
        invoke(WorkerInputs(rows=[{"ui": "C0000003"}], evidence=e))


def test_selector_mismatch_fails_closed():
    e = receipt(selectors={"string": "OTHER", "searchType": "exact"})
    with pytest.raises(ValueError, match="umls_attestation_selectors_mismatch"):
        invoke(WorkerInputs(evidence=e))


def test_describe_never_calls_worker():
    runtime = WorkerInputs(variables={"operation": "describe"})
    result = invoke(runtime)
    assert result["operation"] == "describe"
    assert runtime.calls == []


def test_unmapped_gene_operation_does_not_fetch():
    runtime = WorkerInputs(variables={"operation": "gene_search", "text": "BRCA1"})
    with pytest.raises(ValueError, match="umls_runtime_operation_not_mapped"):
        invoke(runtime)
    assert runtime.calls == []


def test_canonicalizer_rejects_ambiguous_values():
    from umls_terminology_v0_1_1_adapter import _digest
    with pytest.raises(ValueError, match="umls_attestation_json_invalid"):
        _digest({"number": float("nan")})
