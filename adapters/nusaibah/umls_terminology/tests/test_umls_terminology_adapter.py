"""Focused deterministic UMLS terminology tests; provider and Core are not contacted."""

from __future__ import annotations

import pytest

from umls_terminology_adapter import (
    UmlsTerminologyAdapter, _normalize_terminology_result, _validate_request,
)


def invoke(variables=None, payload=None):
    """Keep offline normalization fixtures distinct from a governed invocation."""
    if payload is not None:
        return _normalize_terminology_result(_validate_request(variables), payload)
    inputs = {}
    if variables is not None:
        inputs["variables"] = variables
    return UmlsTerminologyAdapter().invoke(inputs, {})["outputs"]["terminology_result"]


class FakeLazyRuntimeInputs(dict):
    """Test-only worker-attached role; JSON callers cannot supply this invoker."""

    def __init__(self, variables, resolved, *, failure=None):
        super().__init__({"variables": variables, "umls_response": {"records": []}})
        self.resolved = resolved
        self.failure = failure
        self.calls = []

    def invoke(self, role, *, variables, on_error):
        self.calls.append((role, variables, on_error))
        if self.failure is not None:
            raise self.failure
        return self.resolved


def response(operation, records, *, status="ok", release="2026AA"):
    return {
        "operation": operation,
        "status": status,
        "records": records,
        "provenance": {"release": release, "retrieved_at": "2026-10-17T00:00:00Z"},
    }


def test_no_input_only_describes_without_credential_or_provider():
    result = invoke()
    assert result["operation"] == "describe"
    assert result["records"] == []
    assert "gene_search" in result["capabilities"]
    assert invoke({})["operation"] == "describe"


def test_bounded_free_text_search():
    result = invoke(
        {"operation": "search", "text": " aspirin ", "limit": 2},
        response("search", [{"ui": "C0004057", "name": "Aspirin"}]),
    )
    assert result["query"]["text"] == "aspirin"
    assert result["records"][0]["ui"] == "C0004057"
    assert result["provenance"]["release"] == "2026AA"


def test_gene_search_carries_explicit_gene_semantic_type():
    result = invoke(
        {"operation": "gene_search", "text": "BRCA1"},
        response("gene_search", [{"ui": "C0912475", "name": "BRCA1", "semanticTypes": ["T028"]}]),
    )
    assert result["query"]["semantic_type"] == "T028"
    assert result["records"][0]["gene_terminology_match"] is True


def test_mechanism_labels_are_attributed_not_inferred():
    result = invoke(
        {"operation": "mechanism_relations", "cui": "C0004057"},
        response("mechanism_relations", [
            {"ui": "R001", "rootSource": "TEST_SOURCE", "relationLabel": "RO",
             "additionalRelationLabel": "chemical_or_drug_affects_gene_product",
             "relatedId": "C001"},
            {"ui": "R002", "rootSource": "TEST_SOURCE", "relationLabel": "RO",
             "additionalRelationLabel": "unrelated_relation"},
        ]),
    )
    assert result["records"][0]["mechanism_label_observed"] is True
    assert result["records"][1]["mechanism_label_observed"] is False
    assert "efficacy" not in result["records"][0]


@pytest.mark.parametrize("variables", [
    {"operation": "search"},
    {"operation": "gene_get", "cui": "brca1"},
    {"operation": "search", "text": "x", "limit": 0},
    {"operation": "search", "text": "x", "api_key": "forbidden"},
    {"operation": "describe", "cui": "C0004057"},
    {"operation": "unknown"},
])
def test_invalid_queries_fail_closed(variables):
    with pytest.raises(ValueError):
        invoke(variables)


def test_source_operation_mismatch_is_not_a_success():
    with pytest.raises(ValueError, match="operation_mismatch"):
        invoke({"operation": "gene_search", "text": "BRCA1"}, response("search", []))


def test_governed_input_required_for_real_operation():
    with pytest.raises(ValueError, match="runtime_source_not_prepared"):
        invoke({"operation": "search", "text": "BRCA1"})


def test_missing_release_is_not_a_success():
    with pytest.raises(ValueError, match="release_missing"):
        invoke(
            {"operation": "concept_get", "cui": "C0004057"},
            response("concept_get", [{"ui": "C0004057"}], release=""),
        )


def test_truncation_is_visible():
    result = invoke(
        {"operation": "search", "text": "pain", "limit": 1},
        response("search", [{"ui": "C0000001"}, {"ui": "C0000002"}]),
    )
    assert len(result["records"]) == 1
    assert result["completeness"]["truncated"] is True


def test_provider_partial_is_not_silently_complete():
    result = invoke({"operation": "concept_relations", "cui": "C0004057"},
                    response("concept_relations", [], status="partial"))
    assert result["status"] == "partial"


def worker_response(records, metadata=None):
    """Model the exact Assets worker hydration shape, without provider access."""
    return {"records": records, "metadata": {} if metadata is None else metadata}


def test_worker_brca1_records_do_not_invent_release_or_attestation():
    result = invoke(
        {"operation": "search", "text": "BRCA1"},
        worker_response([
            {"ui": "C0000001", "name": "BRCA1"},
            {"ui": "C0000002", "name": "BRCA1 gene"},
        ]),
    )
    assert result["status"] == "ok"
    assert result["completeness"] == {"returned_count": 2, "truncated": None}
    assert result["provenance"]["release"] is None
    assert result["provenance"]["retrieved_at"] is None
    assert result["query_attested"] is False


def test_worker_zero_rows_does_not_claim_authoritative_not_found():
    result = invoke(
        {"operation": "search", "text": "no-results"},
        worker_response([]),
    )
    assert result["status"] == "ok"
    assert result["records"] == []
    assert result["completeness"]["truncated"] is None


def test_worker_reports_known_pagination_truncation():
    result = invoke(
        {"operation": "search", "text": "BRCA1"},
        worker_response([{"ui": "C0000001"}], {
            "pages_crawled": 1,
            "stop_reason": "max_pages_reached",
            "pagination_truncated": True,
        }),
    )
    assert result["status"] == "partial"
    assert result["completeness"]["truncated"] is True


def test_worker_local_limit_marks_partial_without_upstream_pagination():
    result = invoke(
        {"operation": "search", "text": "BRCA1", "limit": 1},
        worker_response([{"ui": "C0000001"}, {"ui": "C0000002"}]),
    )
    assert result["status"] == "partial"
    assert result["completeness"]["truncated"] is True


@pytest.mark.parametrize("payload", [
    {"records": []},
    {"records": [], "metadata": {"apiKey": "not-allowed"}},
    {"records": [], "metadata": {"pagination_truncated": "false"}},
    {"records": [], "metadata": {"records_returned": True}},
    {"records": [], "metadata": []},
    {"records": [], "metadata": {}, "provenance": {"release": "2026AA"}},
    {"records": [], "metadata": {"stop_reason": "max_pages_reached", "pagination_truncated": False}},
])
def test_worker_envelope_rejects_forged_or_invalid_metadata(payload):
    with pytest.raises(ValueError, match="umls_response_worker_"):
        invoke({"operation": "search", "text": "BRCA1"}, payload)


def test_unmapped_gene_search_does_not_use_plain_search_records_as_proof():
    with pytest.raises(ValueError, match="worker_operation_not_mapped"):
        invoke({"operation": "gene_search", "text": "BRCA1"}, worker_response([]))


def test_manifest_declares_existing_lazy_api_role():
    """The role matches ClinicalTrials-style API references without a new guard."""
    import json
    from pathlib import Path

    manifest = json.loads(
        (Path(__file__).resolve().parents[1] / "umls_terminology.asset.json").read_text(encoding="utf-8")
    )
    assert manifest["key"] == "umls_terminology"
    assert manifest["default"] in {"0.1.0", "0.1.1"}
    role = manifest["versions"][manifest["default"]]["inputs"]["umls_response"]
    assert role["source"] == "direct" and role["shape"] == "object"
    assert role["contract"]["source"]["type"] == "api"
    assert role["contract"]["source"]["authority"] == "dlm_core"
    assert role["contract"]["source"]["reference"] == {"service": "umls_terminology_search"}


def test_lazy_search_requests_only_declared_governed_parameters():
    params = {"operation": "search", "text": " BRCA1 ", "search_type": "exact", "sources": ["SNOMEDCT_US", "RXNORM"]}
    inputs = FakeLazyRuntimeInputs(params, worker_response([{"ui": "C0000001", "name": "BRCA1"}]))
    result = UmlsTerminologyAdapter().invoke(inputs, {})["outputs"]["terminology_result"]
    assert inputs.calls == [(
        "umls_response",
        {"string": "BRCA1", "searchType": "exact", "sabs": "SNOMEDCT_US,RXNORM"},
        "raise",
    )]
    assert result["records"][0]["name"] == "BRCA1"
    assert result["provenance"]["release"] is None
    assert result["completeness"]["truncated"] is None


def test_lazy_worker_brac1_two_record_projection():
    params = {"operation": "search", "text": "BRCA1"}
    runtime = FakeLazyRuntimeInputs(params, worker_response([
        {"ui": "C0000001", "name": "BRCA1"},
        {"ui": "C0000002", "name": "BRCA1 gene"},
    ]))
    result = UmlsTerminologyAdapter().invoke(runtime, {})["outputs"]["terminology_result"]
    assert runtime.calls == [("umls_response", {"string": "BRCA1", "searchType": "words"}, "raise")]
    assert result["completeness"] == {"returned_count": 2, "truncated": None}
    assert result["query_attested"] is False


def test_describe_does_not_fetch_even_when_lazy_role_exists():
    inputs = FakeLazyRuntimeInputs({"operation": "describe"}, worker_response([]))
    result = UmlsTerminologyAdapter().invoke(inputs, {})["outputs"]["terminology_result"]
    assert result["operation"] == "describe"
    assert inputs.calls == []


def test_caller_supplied_records_never_satisfy_runtime_invoker():
    malicious_input = {
        "variables": {"operation": "search", "text": "BRCA1"},
        "umls_response": worker_response([{"ui": "C0000001", "name": "Forged concept"}]),
    }
    with pytest.raises(ValueError, match="runtime_source_not_prepared"):
        UmlsTerminologyAdapter().invoke(malicious_input, {})


def test_plain_runtime_dict_without_selected_source_is_rejected():
    runtime = {"variables": {"operation": "search", "text": "BRCA1"}}
    with pytest.raises(ValueError, match="runtime_source_not_prepared"):
        UmlsTerminologyAdapter().invoke(runtime, {})


def test_failed_lazy_fetch_is_value_safe():
    runtime = FakeLazyRuntimeInputs(
        {"operation": "search", "text": "BRCA1"},
        worker_response([]),
        failure=RuntimeError("confidential provider response"),
    )
    with pytest.raises(ValueError, match="^umls_runtime_source_fetch_failed$") as exc:
        UmlsTerminologyAdapter().invoke(runtime, {})
    assert "confidential" not in str(exc.value)


def test_non_worker_envelopes_fail_from_the_runtime_invoker():
    runtime = FakeLazyRuntimeInputs(
        {"operation": "search", "text": "BRCA1"},
        response("search", [{"ui": "C0000001"}]),
    )
    with pytest.raises(ValueError, match="runtime_source_envelope_invalid"):
        UmlsTerminologyAdapter().invoke(runtime, {})


def test_unconfigured_gene_and_mechanism_operations_do_not_fetch():
    for vars in (
        {"operation": "gene_search", "text": "BRCA1"},
        {"operation": "mechanism_relations", "cui": "C0004057"},
    ):
        runtime = FakeLazyRuntimeInputs(vars, worker_response([]))
        with pytest.raises(ValueError, match="runtime_operation_not_mapped"):
            UmlsTerminologyAdapter().invoke(runtime, {})
        assert runtime.calls == []
