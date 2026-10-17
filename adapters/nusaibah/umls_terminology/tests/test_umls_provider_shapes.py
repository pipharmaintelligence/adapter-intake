"""Provider-shape and bounded UMLS semantic regression checks.

These are synthetic, source-informed records; no live provider call is made.
"""
from __future__ import annotations

import pytest

from umls_terminology_adapter import UmlsTerminologyAdapter, SUPPORTED_OPERATIONS


def call(variables, records, *, status="ok", release="2026AA", truncated=False):
    return UmlsTerminologyAdapter().invoke({
        "variables": variables,
        "umls_response": {
            "operation": variables["operation"],
            "status": status,
            "records": records,
            "truncated": truncated,
            "provenance": {"release": release, "retrieved_at": "2026-10-17T18:00:00Z"},
        },
    }, {})["outputs"]["terminology_result"]


def test_concept_semantic_types_can_be_name_and_tui_uri():
    record = {
        "ui": "C0004057", "name": "Example gene", "semanticTypes": [{
            "name": "Gene or Genome",
            "uri": "/semantic-network/2026AA/TUI/T028",
        }],
    }
    result = call({"operation": "gene_get", "cui": "C0004057"}, [record])
    assert result["records"][0]["gene_terminology_match"] is True
    assert result["records"][0]["semantic_types"] == [{"name": "Gene or Genome", "tui": "T028"}]


def test_gene_search_uses_name_when_tui_is_unavailable():
    result = call({"operation": "gene_search", "text": "BRCA1"},
                  [{"ui": "C0001234", "semanticTypes": ["Gene or Genome"]}])
    assert result["records"][0]["gene_terminology_match"] is True
    assert result["query"]["semantic_type"] == "T028"


def test_unknown_semantic_type_is_not_false():
    result = call({"operation": "gene_get", "cui": "C0001234"}, [{"ui": "C0001234"}])
    assert result["records"][0]["gene_terminology_match"] is None


@pytest.mark.parametrize(("operation", "name"), [
    ("protein_search", "Amino Acid, Peptide, or Protein"),
    ("drug_search", "Pharmacologic Substance"),
])
def test_protein_and_drug_are_distinct_terms(operation, name):
    result = call({"operation": operation, "text": "example"},
                  [{"ui": "C0001234", "semanticTypes": [name]}])
    assert result["records"][0]["terminology_type_match"] is True


def test_relation_direction_boolean_fields_and_source_preserved():
    result = call({"operation": "mechanism_relations", "cui": "C0004057"}, [{
        "ui": "R123", "rootSource": "SNOMEDCT_US", "sourceUi": "0012",
        "sourceOriginated": False, "suppressible": False, "obsolete": False,
        "relationLabel": "PAR", "additionalRelationLabel": "inverse_isa",
        "relatedFromId": "/content/2026AA/source/SNOMEDCT_US/0002",
        "relatedId": "/content/2026AA/source/SNOMEDCT_US/0003",
    }])
    record = result["records"][0]
    assert record["sourceUi"] == "0012"
    assert record["sourceOriginated"] is False
    assert record["relatedFromId"].endswith("/0002")
    assert record["relatedId"].endswith("/0003")
    assert record["mechanism_label_observed"] is False


def test_preserve_opaque_code_with_colon_and_zeros():
    result = call({"operation": "source_get", "source": "HPO", "code": "HP:0001947"},
                  [{"ui": "HP:0001947", "rootSource": "HPO"}])
    assert result["query"]["code"] == "HP:0001947"


def test_crosswalk_only_asserts_candidate_not_clinical_equivalence():
    result = call({"operation": "crosswalk", "source": "HPO", "code": "HP:0001947",
                   "target_sources": ["SNOMEDCT_US"]}, [{"ui": "0042"}])
    assert result["records"][0]["mapping_basis"] == "shared_umls_cui_candidate"
    assert result["records"][0]["clinical_equivalence_verified"] is False


def test_200_record_page_can_be_bounded_and_is_partial():
    result = call({"operation": "search", "text": "pain", "limit": 20},
                  [{"ui": "C%07d" % index} for index in range(200)])
    assert len(result["records"]) == 20
    assert result["status"] == "partial"
    assert result["completeness"]["truncated"] is True


def test_more_than_200_records_fails_closed():
    with pytest.raises(ValueError, match="record_budget_exceeded"):
        call({"operation": "search", "text": "pain"}, [{"ui": "C0000001"}] * 201)


def test_release_must_be_resolved_not_current_placeholder():
    with pytest.raises(ValueError, match="release_unresolved"):
        call({"operation": "search", "text": "pain"}, [], release="current")


def test_not_found_with_nonempty_records_is_invalid():
    with pytest.raises(ValueError, match="not_found_conflict"):
        call({"operation": "search", "text": "pain"}, [{"ui": "C0000001"}], status="not_found")


@pytest.mark.parametrize(("operation", "selectors"), [
    ("concept_atoms", {"cui": "C0004057"}),
    ("concept_definitions", {"cui": "C0004057"}),
    ("concept_relations", {"cui": "C0004057"}),
    ("gene_relations", {"cui": "C0004057"}),
    ("source_atoms", {"source": "RXNORM", "code": "000052"}),
    ("source_relations", {"source": "RXNORM", "code": "000052"}),
    ("source_attributes", {"source": "RXNORM", "code": "000052"}),
    ("source_hierarchy", {"source": "SNOMEDCT_US", "code": "00052", "direction": "parents"}),
    ("atom_get", {"aui": "A8345234"}),
    ("atom_hierarchy", {"aui": "A8345234", "direction": "children"}),
    ("semantic_type_get", {"tui": "T028"}),
    ("vocabularies", {}),
])
def test_additional_operations_validate_and_return_bounded_envelope(operation, selectors):
    assert operation in SUPPORTED_OPERATIONS
    result = call({"operation": operation, **selectors}, [])
    assert result["operation"] == operation
    assert result["records"] == []
    assert result["provenance"]["release"] == "2026AA"


@pytest.mark.parametrize("variables", [
    {"operation": "crosswalk", "source": "HPO", "code": "HP:0001947"},
    {"operation": "source_hierarchy", "source": "HPO", "code": "HP:0001947", "direction": "up"},
    {"operation": "atom_get", "aui": "A??"},
    {"operation": "semantic_type_get", "tui": "gene"},
    {"operation": "search", "text": "gene", "sources": ["RXNORM", "RXNORM"]},
    {"operation": "search", "text": "gene", "search_type": "approximate"},
    {"operation": "vocabularies", "apiKey": "not-allowed"},
])
def test_invalid_or_sensitive_selectors_fail_before_source_fetch(variables):
    with pytest.raises(ValueError):
        call(variables, [])


def test_numeric_identifier_is_not_coerced():
    with pytest.raises(ValueError, match="umls_record_ui_invalid"):
        call({"operation": "source_get", "source": "HPO", "code": "0012"}, [{"ui": 12}])


def test_bad_provenance_fails_closed():
    with pytest.raises(ValueError, match="umls_provenance_retrieved_at_invalid"):
        UmlsTerminologyAdapter().invoke({
            "variables": {"operation": "search", "text": "gene"},
            "umls_response": {
                "operation": "search", "status": "ok", "records": [],
                "provenance": {"release": "2026AA", "retrieved_at": {"secret": "x"}},
            },
        }, {})
