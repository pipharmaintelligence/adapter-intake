"""Provider-free 0.1.0 PubMed normalization and intake contract checks."""
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import re
import sys
import types
import unittest
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
ASSET = ROOT / "adapters" / "nusaibah" / "pubmed_evidence"
try:
    from adapters.base import Adapter  # noqa: F401
except ImportError:
    package = types.ModuleType("adapters")
    package.__path__ = []
    parent = types.ModuleType("adapters.base")
    parent.Adapter = type("Adapter", (), {})
    sys.modules.setdefault("adapters", package)
    sys.modules.setdefault("adapters.base", parent)

spec = importlib.util.spec_from_file_location("pubmed_evidence_under_test", ASSET / "pubmed_evidence_adapter.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

ALL_ROLES = (module.SEARCH_ROLE, module.SUMMARY_ROLE, module.ABSTRACT_ROLE,
             module.LINK_ROLE, module.IDENTITY_ROLE, module.INFO_ROLE)


class FakeInputs(dict):
    """Simulate one worker-admitted source role without external calls."""

    def __init__(self, data: dict[str, Any] | None = None, *, fail: bool = False, roles: tuple[str, ...] = ALL_ROLES) -> None:
        super().__init__({name: {"records": []} for name in roles})
        self.data = copy.deepcopy(data or {"records": []})
        self.fail = fail
        self.calls: list[tuple[str, dict[str, Any], str]] = []

    def invoke(self, role: str, *, variables: dict[str, Any], on_error: str = "raise") -> dict[str, Any]:
        self.calls.append((role, copy.deepcopy(variables), on_error))
        if self.fail:
            raise RuntimeError("synthetic_transport_failure")
        return copy.deepcopy(self.data)


def envelope(obj: dict[str, Any] | None) -> dict[str, Any]:
    return {"records": [] if obj is None else [copy.deepcopy(obj)],
            "metadata": {"retrieved_at": "2026-10-18T00:00:00Z", "source_version": "synthetic-v1"}}


def search(ids: list[str] | None = None, *, count: int = 1, offset: int = 0, retmax: int = 10) -> dict[str, Any]:
    return envelope({"esearchresult": {"count": str(count), "retstart": str(offset),
        "retmax": str(retmax), "idlist": list(ids if ids is not None else ["12345"]),
        "querytranslation": "synthetic translated query"}})


SUMMARY_1 = {
    "uid": "12345", "title": "Synthetic randomized trial", "fulljournalname": "Research Journal",
    "pubdate": "2024 Jan 9", "epubdate": "2023 Dec", "sortpubdate": "2024/01/09 00:00",
    "pubtype": ["Randomized Controlled Trial"],
    "authors": [{"name": "Smith A"}, {"name": "Jones B"}],
    "articleids": [{"idtype": "doi", "value": "10.1000/example"},
                   {"idtype": "pmc", "value": "PMC4567"}],
    "meshheadinglist": ["Signal Transduction"],
}
SUMMARY_2 = {
    "uid": "67890", "title": "Synthetic withdrawal", "source": "Additional Journal",
    "pubdate": "2022", "epubdate": "", "pubtype": ["Retracted Publication"],
    "authors": [{"name": "Writer C"}],
    "articleids": [],
}


def summary(*items: dict[str, Any]) -> dict[str, Any]:
    return envelope({"result": {"uids": [x["uid"] for x in items], **{x["uid"]: copy.deepcopy(x) for x in items}}})


def abstract(pmid: str = "12345", *, passages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if passages is None:
        passages = [{"offset": 0, "infons": {"section_type": "BACKGROUND"}, "text": "Background text."},
                    {"offset": 17, "infons": {"section_type": "RESULTS"}, "text": "Observed results."}]
    return envelope({"source": "PubMed", "documents": [{"id": pmid, "passages": passages}]})


def link(pmid: str = "12345", *, relation: str = "pubmed_pubmed", entries: list[str] | None = None) -> dict[str, Any]:
    return envelope({"linksets": [{"dbfrom": "pubmed", "ids": [pmid],
        "linksetdbs": [{"dbto": "pubmed", "linkname": relation, "links": entries or ["67890"]}]}]})


def call(variables: dict[str, Any], response: dict[str, Any]) -> tuple[dict[str, Any], FakeInputs]:
    fake = FakeInputs(response)
    fake["variables"] = variables
    return module.PubMedEvidenceAdapter().invoke(fake, {})["outputs"]["literature_result"], fake


class PubMedEvidenceTests(unittest.TestCase):
    def test_default_describe_no_fetch(self) -> None:
        fake = FakeInputs()
        ans = module.PubMedEvidenceAdapter().invoke(fake, {})["outputs"]["literature_result"]
        self.assertEqual("describe", ans["operation"])
        self.assertEqual(17, len(ans["operations"]))
        self.assertEqual([], fake.calls)
        self.assertEqual("completed", ans["status"])

    def test_explicit_describe_no_fetch(self) -> None:
        ans, fake = call({"operation": "describe"}, envelope(None))
        self.assertEqual([], fake.calls)
        self.assertEqual([], ans["provenance"])

    def test_search_basic_count_and_translation(self) -> None:
        ans, fake = call({"text": "drug beta", "page_size": 2}, search(["12345"], count=23, retmax=2))
        self.assertEqual("article_search", ans["operation"])
        self.assertEqual("12345", ans["records"][0]["pmid"])
        self.assertEqual(23, ans["coverage"]["reported_count"])
        self.assertTrue(ans["coverage"]["has_more"])
        self.assertEqual("synthetic translated query", ans["query_translation"])
        self.assertEqual(module.SEARCH_ROLE, fake.calls[0][0])
        self.assertEqual("drug beta", fake.calls[0][1]["term"])
        self.assertEqual("raise", fake.calls[0][2])
        self.assertTrue(ans["provenance"][0]["record_digest"].startswith("sha256:"))

    def test_advanced_search_typed_facets(self) -> None:
        variables = {"operation": "advanced_search", "drug": "drug beta", "condition": "myeloma",
                     "mesh": "Neoplasms", "publication_type": "Clinical Trial",
                     "aliases": ["Alias One", "Alias Two"], "advanced_query": "humans[MeSH Terms]",
                     "published_from": "2022-01-01", "published_to": "2024-12-31", "sort": "pub_date"}
        _, fake = call(variables, search([], count=0))
        params = fake.calls[0][1]
        self.assertIn("(drug beta)[Title/Abstract]", params["term"])
        self.assertIn("(Neoplasms)[MeSH Terms]", params["term"])
        self.assertIn(" OR ", params["term"])
        self.assertEqual("pdat", params["datetype"])
        self.assertEqual("2024-12-31", params["maxdate"])
        self.assertEqual("pub_date", params["sort"])

    def test_article_count_only(self) -> None:
        ans, fake = call({"operation": "article_count", "text": "myeloma"}, search([], count=12000, retmax=0))
        self.assertEqual([], ans["records"])
        self.assertEqual("completed", ans["status"])
        self.assertEqual(12_000, ans["coverage"]["reported_count"])
        self.assertTrue(ans["coverage"]["retrieval_incomplete"])
        self.assertEqual(0, fake.calls[0][1]["retmax"])

    def test_trial_publications_candidate_only(self) -> None:
        ans, _ = call({"operation": "trial_publications", "nct_id": "nct00000001"}, search(["12345"], count=1))
        self.assertEqual("candidate_nct_search", ans["records"][0]["relation"])
        self.assertEqual("discovery_only", ans["records"][0]["evidence_level"])
        self.assertEqual("not_inspected", ans["publication_evidence"])

    def test_esearch_can_return_fewer_items_than_requested(self) -> None:
        answer, _ = call({"text": "x", "page_size": 10}, search(["12345"], count=1, retmax=1))
        self.assertEqual(["12345"], [x["pmid"] for x in answer["records"]])

    def test_search_at_window_boundary(self) -> None:
        ans, _ = call({"operation": "article_search", "text": "x", "offset": 9999, "page_size": 1},
                      search(["12345"], count=12000, offset=9999, retmax=1))
        self.assertFalse(ans["coverage"]["has_more"])
        self.assertTrue(ans["coverage"]["retrieval_incomplete"])

    def test_search_empty_not_false_no_match_when_more_count(self) -> None:
        ans, _ = call({"operation": "article_search", "text": "x"}, search([], count=50))
        self.assertEqual(50, ans["coverage"]["reported_count"])
        self.assertEqual([], ans["records"])
        self.assertIn(ans["status"], ("completed", "no_match"))

    def test_date_window_conflict_no_fetch(self) -> None:
        fake = FakeInputs(search())
        fake["variables"] = {"text": "x", "published_from": "2024-01-01", "published_to": "2025-12-31",
                             "updated_from": "2024-01-01", "updated_to": "2025-01-01"}
        with self.assertRaisesRegex(ValueError, "pubmed_date_type_conflict"):
            module.PubMedEvidenceAdapter().invoke(fake, {})
        self.assertEqual([], fake.calls)

    def test_search_rejects_bad_scope_and_controls_before_fetch(self) -> None:
        bad = [({"operation": "article_search"}, "pubmed_search_selector_required"),
               ({"text": "x", "page_size": 41}, "pubmed_page_size_invalid"),
               ({"text": "x", "offset": 9999, "page_size": 2}, "pubmed_window_exceeded"),
               ({"text": "x", "aliases": ["Same", "same"]}, "pubmed_aliases_duplicate"),
               ({"text": "x", "sort": "arbitrary"}, "pubmed_sort_invalid"),
               ({"text": "x", "unknown_field": "no"}, "pubmed_variable_not_allowed"),
               ({"text": "x", "advanced_query": "x"}, "pubmed_advanced_query_operation_required"),
               ({"operation": "trial_publications", "text": "x"}, "pubmed_nct_id_required")]
        for val, code in bad:
            with self.subTest(code=code):
                fake = FakeInputs(search())
                fake["variables"] = val
                with self.assertRaisesRegex(ValueError, code):
                    module.PubMedEvidenceAdapter().invoke(fake, {})
                self.assertEqual([], fake.calls)

    def test_sensitive_values_and_invalid_dates(self) -> None:
        values = ["not permitted\nquery", "http://example.invalid", "Bearer fakevalue", "file: local", "a" * 501]
        for item in values:
            with self.subTest(item=item[:30]):
                fake = FakeInputs(search())
                fake["variables"] = {"text": item}
                with self.assertRaisesRegex(ValueError, "pubmed_text_invalid"):
                    module.PubMedEvidenceAdapter().invoke(fake, {})
                self.assertEqual([], fake.calls)
        fake = FakeInputs(search())
        fake["variables"] = {"text": "x", "published_from": "2026-02-30", "published_to": "2026-03-02"}
        with self.assertRaisesRegex(ValueError, "pubmed_date_invalid"):
            module.PubMedEvidenceAdapter().invoke(fake, {})

    def test_summary_exact_identity_and_metadata(self) -> None:
        ans, fake = call({"operation": "article_get", "pmid": "12345"}, summary(SUMMARY_1))
        record = ans["records"][0]
        self.assertEqual("10.1000/example", record["doi"])
        self.assertEqual("PMC4567", record["pmcid"])
        self.assertEqual("2024-01-09", record["publication_dates"]["pubdate"]["iso"])
        self.assertEqual("day", record["publication_dates"]["pubdate"]["precision"])
        self.assertEqual("month", record["publication_dates"]["epubdate"]["precision"])
        self.assertEqual("metadata_only", record["article_extent"])
        self.assertEqual(["12345"], ans["returned_ids"])
        self.assertEqual(module.SUMMARY_ROLE, fake.calls[0][0])
        self.assertEqual("12345", fake.calls[0][1]["id"])

    def test_summary_research_view_preserves_all_fields(self) -> None:
        ans, _ = call({"operation": "article_get", "pmid": "12345", "view": "research"}, summary(SUMMARY_1))
        self.assertEqual("Synthetic randomized trial", ans["records"][0]["source_record"]["title"])

    def test_summary_batch_missing_ids(self) -> None:
        ans, fake = call({"operation": "article_batch", "pmids": ["12345", "67890"]}, summary(SUMMARY_1))
        self.assertEqual(["67890"], ans["missing_ids"])
        self.assertEqual("12345,67890", fake.calls[0][1]["id"])
        self.assertEqual(1, ans["record_count"])

    def test_summary_empty_is_no_match(self) -> None:
        ans, _ = call({"operation": "article_get", "pmid": "12345"}, summary())
        self.assertEqual("no_match", ans["status"])
        self.assertEqual(["12345"], ans["missing_ids"])

    def test_summary_wrong_id_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "pubmed_summary_identity_mismatch"):
            call({"operation": "article_get", "pmid": "12345"}, summary(SUMMARY_2))
        obj = copy.deepcopy(SUMMARY_1)
        obj["uid"] = "67890"
        with self.assertRaisesRegex(ValueError, "pubmed_summary_identity_mismatch"):
            call({"operation": "article_get", "pmid": "12345"}, summary(obj))

    def test_profile_history_and_integrity_projections(self) -> None:
        profile, _ = call({"operation": "publication_profile", "pmid": "12345"}, summary(SUMMARY_1))
        self.assertEqual(["Smith A", "Jones B"], profile["records"][0]["authors"])
        history, _ = call({"operation": "publication_history", "pmid": "67890"}, summary(SUMMARY_2))
        self.assertEqual("year", history["records"][0]["publication_dates"]["pubdate"]["precision"])
        notices, _ = call({"operation": "integrity_get", "pmid": "67890"}, summary(SUMMARY_2))
        self.assertEqual("notice_reported", notices["records"][0]["integrity_state"])
        self.assertEqual(["Retracted Publication"], notices["records"][0]["integrity_signals"])
        clean, _ = call({"operation": "integrity_get", "pmid": "12345"}, summary(SUMMARY_1))
        self.assertEqual("unknown_from_summary_only", clean["records"][0]["integrity_state"])

    def test_temporal_cutoff_requires_exact_date(self) -> None:
        newer, _ = call({"operation": "article_get", "pmid": "12345", "as_of_date": "2023-12-31"}, summary(SUMMARY_1))
        self.assertEqual("after_cutoff", newer["records"][0]["temporal_status"])
        earlier, _ = call({"operation": "article_get", "pmid": "12345", "as_of_date": "2024-01-10"}, summary(SUMMARY_1))
        self.assertEqual("eligible_by_publication_date", earlier["records"][0]["temporal_status"])
        partial, _ = call({"operation": "article_get", "pmid": "67890", "as_of_date": "2025-01-01"}, summary(SUMMARY_2))
        self.assertEqual("unqualified_missing_or_partial_date", partial["records"][0]["temporal_status"])

    def test_abstract_sections_and_dates_unqualified(self) -> None:
        ans, fake = call({"operation": "abstract_get", "pmid": "12345"}, abstract())
        record = ans["records"][0]
        self.assertEqual("abstract", record["accessible_extent"])
        self.assertEqual("RESULTS", record["sections"][1]["section"])
        self.assertEqual(17, record["sections"][1]["offset"])
        self.assertTrue(record["sections"][0]["text_digest"].startswith("sha256:"))
        self.assertEqual("unqualified_without_publication_date", record["temporal_status"])
        self.assertEqual(module.ABSTRACT_ROLE, fake.calls[0][0])

    def test_abstract_missing_or_wrong_id(self) -> None:
        empty, _ = call({"operation": "abstract_get", "pmid": "12345"}, envelope({"documents": []}))
        self.assertEqual("no_match", empty["status"])
        with self.assertRaisesRegex(ValueError, "pubmed_abstract_identity_mismatch"):
            call({"operation": "abstract_get", "pmid": "12345"}, abstract("67890"))
        with self.assertRaisesRegex(ValueError, "pubmed_text_length_invalid"):
            call({"operation": "abstract_get", "pmid": "12345"}, abstract(passages=[{"text": "x" * 12001}]))

    def test_identity_id_converter_mapping_and_scope(self) -> None:
        ans, fake = call({"operation": "identifier_resolve", "pmid": "12345"},
                         envelope({"records": [{"pmid": 12345, "pmcid": "PMC4567", "doi": "10.1000/example", "requested-id": "12345"}]}))
        self.assertEqual("PMC4567", ans["records"][0]["pmcid"])
        self.assertEqual("PMC-linked records only; absence does not mean no PubMed article", ans["coverage_note"])
        self.assertEqual("12345", fake.calls[0][1]["ids"])
        unresolved, _ = call({"operation": "identifier_resolve", "doi": "10.1000/example"}, envelope({"records": []}))
        self.assertEqual("no_match", unresolved["status"])
        with self.assertRaisesRegex(ValueError, "pubmed_identifier_selector_invalid"):
            call({"operation": "identifier_resolve", "pmid": "12345", "doi": "10.1000/example"}, envelope({"records": []}))
        with self.assertRaisesRegex(ValueError, "pubmed_identity_mismatch"):
            call({"operation": "identifier_resolve", "pmcid": "PMC4567"}, envelope({"records": [{"requested-id": "PMCOTHER"}]}))

    def test_elink_related_and_named_citation_links(self) -> None:
        ans, fake = call({"operation": "related_articles", "pmid": "12345"}, link())
        self.assertEqual(["67890"], ans["records"][0]["linked_ids"])
        self.assertEqual("pubmed_pubmed", fake.calls[0][1]["linkname"])
        citations, fake = call({"operation": "citation_links", "pmid": "12345", "relationship": "cited_by"},
                               link(relation="pubmed_pubmed_citedin"))
        self.assertEqual("cited_by", citations["records"][0]["relation"])
        self.assertEqual("pubmed_pubmed_citedin", fake.calls[0][1]["linkname"])
        refs, _ = call({"operation": "citation_links", "pmid": "12345", "relationship": "references"},
                       link(relation="pubmed_pubmed_refs"))
        self.assertEqual("references", refs["records"][0]["relation"])

    def test_elink_cross_database_and_bad_relation(self) -> None:
        ans, _ = call({"operation": "cross_database_links", "pmid": "12345", "relationship": "gene"},
                      link(relation="pubmed_gene"))
        self.assertEqual("gene", ans["records"][0]["relation"])
        with self.assertRaisesRegex(ValueError, "pubmed_link_relation_invalid"):
            call({"operation": "related_articles", "pmid": "12345", "relationship": "gene"}, link())
        with self.assertRaisesRegex(ValueError, "pubmed_link_identity_mismatch"):
            call({"operation": "related_articles", "pmid": "12345"}, link("67890"))

    def test_database_info_fixed_pubmed_identity(self) -> None:
        ans, fake = call({"operation": "database_info"}, envelope({"einforesult": {
            "dbinfo": {"db": "pubmed", "count": "400", "lastupdate": "2026-01-01",
                       "fieldlist": [{"name": "ALL"}], "linklist": []}}}))
        self.assertEqual("pubmed", ans["records"][0]["database"])
        self.assertEqual({}, fake.calls[0][1])
        with self.assertRaisesRegex(ValueError, "pubmed_info_invalid"):
            call({"operation": "database_info"}, envelope({"einforesult": {"dbinfo": {"db": "gene"}}}))

    def test_export_citations_is_no_save_and_bounded(self) -> None:
        ans, _ = call({"operation": "export_citations", "pmids": ["12345"]}, summary(SUMMARY_1))
        self.assertIn("PMID 12345", ans["records"][0]["citation"])
        self.assertNotIn("file_path", ans["records"][0])

    def test_fake_source_failure_returns_safe_reason(self) -> None:
        fake = FakeInputs(summary(SUMMARY_1), fail=True)
        fake["variables"] = {"operation": "article_get", "pmid": "12345"}
        with self.assertRaisesRegex(ValueError, "pubmed_source_failed"):
            module.PubMedEvidenceAdapter().invoke(fake, {})
        fake = FakeInputs(summary(SUMMARY_1), roles=())
        fake["variables"] = {"operation": "article_get", "pmid": "12345"}
        with self.assertRaisesRegex(ValueError, "pubmed_source_not_admitted"):
            module.PubMedEvidenceAdapter().invoke(fake, {})

    def test_invalid_source_shape_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "pubmed_source_shape_invalid"):
            call({"operation": "article_get", "pmid": "12345"}, {"records": "bad"})
        with self.assertRaisesRegex(ValueError, "pubmed_root_record_count_invalid"):
            call({"operation": "article_get", "pmid": "12345"}, {"records": [{"result": {}}, {"result": {}}]})
        with self.assertRaisesRegex(ValueError, "pubmed_search_root_invalid"):
            call({"operation": "article_search", "text": "x"}, envelope({"ids": []}))

    def test_bad_summary_data_and_oversize_rejected(self) -> None:
        wrong = copy.deepcopy(SUMMARY_1)
        wrong["pubtype"] = "not a list"
        with self.assertRaisesRegex(ValueError, "pubmed_publication_types_invalid"):
            call({"operation": "article_get", "pmid": "12345"}, summary(wrong))
        excessive = copy.deepcopy(SUMMARY_1)
        excessive["title"] = "x" * 240_000
        with self.assertRaises(ValueError):
            call({"operation": "article_get", "pmid": "12345", "view": "research"}, summary(excessive))

    def test_unexpected_input_types_rejected(self) -> None:
        for payload in ([], "wrong", None):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    module.PubMedEvidenceAdapter().invoke({"variables": payload}, {})
        with self.assertRaisesRegex(ValueError, "pubmed_pmids_invalid"):
            call({"operation": "article_batch", "pmids": []}, summary())
        with self.assertRaisesRegex(ValueError, "pubmed_pmids_duplicate"):
            call({"operation": "article_batch", "pmids": ["12345", "12345"]}, summary())

    def test_manifest_identity_and_both_substrates(self) -> None:
        doc = json.loads((ASSET / "pubmed_evidence.asset.json").read_text())
        self.assertEqual(module.ASSET_KEY, doc["key"])
        self.assertEqual("0.1.0", doc["default"])
        self.assertEqual(["local_worker", "ecs"], doc["execution"]["allowed_substrates"])
        self.assertEqual("local_worker", doc["execution"]["default_substrate"])
        body = doc["versions"]["0.1.0"]
        self.assertEqual(False, body["inputs"]["variables"]["required"])
        self.assertEqual("literature_result", body["callable"]["result_key"])
        self.assertEqual(set(ALL_ROLES), set(body["inputs"]) - {"variables"})

    def test_all_public_templates_match_implementation(self) -> None:
        content = json.loads((ASSET / "capabilities.v0.1.0.json").read_text())
        self.assertEqual("templates_only", content["publication_status"])
        specs = content["capabilities"]
        self.assertEqual(set(module.OPERATIONS), {v["operation"] for v in specs.values()})
        try:
            import jsonschema
        except ImportError:
            jsonschema = None
        for ref, detail in specs.items():
            with self.subTest(operation=ref):
                self.assertEqual("object", detail["remote_mcp"]["input_schema"]["type"])
                self.assertEqual("object", detail["remote_mcp"]["output_schema"]["type"])
                if jsonschema is not None:
                    jsonschema.Draft202012Validator.check_schema(detail["remote_mcp"]["input_schema"])
                    jsonschema.Draft202012Validator.check_schema(detail["remote_mcp"]["output_schema"])
                self.assertFalse(detail["remote_mcp"]["annotations"]["destructiveHint"])

    def test_declared_files_have_no_transport_url_literals(self) -> None:
        paths = ["adapter.yaml", "adapter.dependencies.json", "pubmed_evidence.asset.json",
                 "pubmed_evidence_adapter.py", "capabilities.v0.1.0.json", "README.md",
                 "CAPABILITY_MATRIX.md", "DLM_RUNTIME_SOURCE_CONTRACT.md", "PROMOTION_CHECKLIST.md"]
        for name in paths:
            with self.subTest(file=name):
                contents = (ASSET / name).read_text()
                self.assertIsNone(re.search(r"https?://|s3://", contents, re.I))

    def test_python_package_boundary_terms_absent(self) -> None:
        forbidden = ("ProviderVault", "DLM_API_KEY", "service_account_json", "raw_payload",
                     "provider_payload", "provider_request", "provider_response", "mcp_token",
                     "auth_header", "authorization", "headers", "endpoint", "base_url")
        contents = (ASSET / "pubmed_evidence_adapter.py").read_text()
        for marker in forbidden:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, contents)


if __name__ == "__main__":
    unittest.main()
