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
