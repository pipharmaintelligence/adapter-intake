"""Focused deterministic UMLS terminology tests; provider and Core are not contacted."""

from __future__ import annotations

import pytest

from umls_terminology_adapter import UmlsTerminologyAdapter


def invoke(variables=None, payload=None):
    inputs = {}
    if variables is not None:
        inputs["variables"] = variables
    if payload is not None:
        inputs["umls_response"] = payload
    return UmlsTerminologyAdapter().invoke(inputs, {})["outputs"]["terminology_result"]


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
    with pytest.raises(ValueError, match="not_resolved"):
        invoke({"operation": "concept_get", "cui": "C0004057"})


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


def test_manifest_requires_server_reference_only_guard():
    """Do not weaken the role before Assets has a reference-only admission gate."""
    import json
    from pathlib import Path

    manifest = json.loads(
        (Path(__file__).resolve().parents[1] / "umls_terminology.asset.json").read_text(encoding="utf-8")
    )
    assert manifest["key"] == "umls_terminology"
    assert manifest["default"] == "0.1.0"
    assert manifest["versions"]["0.1.0"]["inputs"]["umls_response"]["source"] == "direct"
    ref = manifest["versions"]["0.1.0"]["inputs"]["umls_response"]["contract"]["source"]["reference"]
    assert ref["runtime_source_reference_only"] is True
    assert ref["runtime_source_operation"] == "search"
    assert ref["runtime_source_capability_ref"] == "umls.terminology.search"
