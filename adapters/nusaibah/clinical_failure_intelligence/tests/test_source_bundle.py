"""Synthetic contracts for results prepared by independently validated source adapters."""
from copy import deepcopy
import unittest

from fakes import FakeInputs, example_inputs
from clinical_failure_intelligence.contracts import ContractError, canonical_bytes, digest, parse_request
from clinical_failure_intelligence.evidence import EvidenceLedger
from clinical_failure_intelligence.source_bundle import (prepare_bundle, source_windows, publication_interval,
    MAX_BUNDLE_BYTES, MAX_EVIDENCE_BYTES)

NCT = "NCT00000001"
OTHER_NCT = "NCT00000002"


def case_inputs():
    """Use a syntactically valid synthetic trial, never provider records."""
    value = example_inputs()
    value["clinical_context"]["subject"]["trial_ids"] = [NCT]
    value["clinical_context"]["case_scope"]["trial_id"] = NCT
    for row in value["clinical_context"]["evidence"]:
        row["trial_ids"] = [NCT]
    return value


def entry(result, family="trials", *, purpose="case", key=None):
    identities = {"trials": ("nusaibah.clinical_trials_lookup", "trial_result"),
                  "pubmed": ("nusaibah.pubmed_evidence", "literature_result"),
                  "umls": ("umls_terminology", "terminology_result")}
    asset, output = identities[family]
    return {"source_result_id": key or family + "_" + result["operation"],
        "asset_key": asset, "asset_version": "0.1.1" if family == "trials" else "0.1.0",
        "output_role": output,
        "purpose": purpose, "result": deepcopy(result), "result_digest": digest(result)}


def bundle(*sources):
    return {"schema_version": "clinical_evidence_bundle.v1", "bundle_id": "BUNDLE_SYN",
        "subject_id": "CASE_SYN", "product_id": "PRODUCT_SYN", "event_ids": ["EVENT_SYN"],
        "sources": list(sources)}


def trial_result(*, nct=NCT, operation="study_get", date_value="2025-01-01", results=True):
    study = {"protocolSection": {
        "identificationModule": {"nctId": nct},
        "armsInterventionsModule": {"armGroups": [{"label": "COMBINATION", "type": "EXPERIMENTAL"}],
            "interventions": [{"name": "Synthetic product Alpha", "armGroupLabels": ["COMBINATION"]}]},
        "outcomesModule": {"primaryOutcomes": [{"measure": "Synthetic functional score", "timeFrame": "Week 8"}]},
        "statusModule": {"overallStatus": "COMPLETED"}}, "hasResults": results}
    if results:
        study["resultsSection"] = {"outcomeMeasuresModule": {"outcomeMeasures": [
            {"title": "Synthetic functional score", "groups": [{"id": "AG1", "title": "Analysis group"}],
             "analyses": [{"paramType": "MEAN_DIFFERENCE", "paramValue": "0.1"}]}]},
             "adverseEventsModule": {"eventGroups": [{"id": "AE1", "title": "Safety population"}]}}
    return {"schema_version": "clinical_trials_lookup.v1", "operation": operation, "status": "completed",
        "records": [{"nct_id": nct, "summary": {"arm_groups": [{"label": "COMBINATION"}],
            "overall_status": "COMPLETED"}, "registry_study": study, "registry_update_date": date_value}],
        "record_count": 1, "pagination": {"has_more": False, "coverage": "exact_id"},
        "provenance": {"source": "clinicaltrials_gov_api_v2", "retrieved_at": None},
        "results_state": "posted" if results else "not_posted"}


def metadata(*, pmid="12345", date_value="2025-01-02", precision="day", notice=False, types=None):
    return {"schema_version": "pubmed_evidence.v1", "operation": "article_get", "status": "completed",
        "record_count": 1, "records": [{"pmid": pmid, "title": "Synthetic study report", "doi": None,
            "pmcid": None, "publication_types": types if types is not None else ["Randomized Controlled Trial"],
            "publication_dates": {"pubdate": {"iso": date_value, "precision": precision}},
            "nct_ids_in_record": [NCT], "integrity_signals": ["Retracted Publication"] if notice else [],
            "integrity_state": "notice_reported" if notice else "unknown_from_summary_only"}]}


def abstract(*, pmid="12345", content="Synthetic outcome did not establish a clinically meaningful benefit."):
    return {"schema_version": "pubmed_evidence.v1", "operation": "abstract_get", "status": "completed",
        "record_count": 1, "records": [{"pmid": pmid, "accessible_extent": "abstract", "published_on": None,
        "sections": [{"section": "RESULTS", "offset": 100, "text": content}],
        "temporal_status": "unqualified_without_publication_date"}]}


def terminology():
    return {"operation": "search", "status": "ok", "records": [
        {"ui": "C0000001", "name": "Synthetic term", "rootSource": "SYNTH",
         "semantic_types": [{"tui": "T121", "name": "Pharmacologic Substance"}]}],
        "query_attested": False, "provenance": {"release": None, "retrieved_at": None},
        "completeness": {"returned_count": 1, "truncated": None}}


class PreparedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.request = parse_request(FakeInputs(case_inputs()))

    def normalize(self, *sources):
        return prepare_bundle(bundle(*sources), self.request)

    def assert_blocked(self, code, value):
        with self.assertRaises(ContractError) as caught:
            prepare_bundle(value, self.request)
        self.assertEqual(code, caught.exception.code)

    def ledger(self, value):
        return EvidenceLedger("CASE_SYN", "2025-02-01", value["evidence"])

    def test_optional_bundle_does_not_change_legacy_context(self):
        raw = case_inputs()
        request = parse_request(FakeInputs(raw))
        self.assertEqual(raw["clinical_context"], request["context"])
        self.assertEqual("not_supplied", request["prepared_sources"]["status"])

    def test_trial_protocol_and_results_remain_separate(self):
        value = self.normalize(entry(trial_result()))
        roles = {row["source_context"]["evidence_use"] for row in value["evidence"]}
        self.assertTrue({"protocol", "posted_results", "safety_results"} <= roles)
        self.assertEqual("not_inferred", value["sources"][0]["observations"][0]["results_group_join"])
        self.assertEqual("requires_case_review", value["sources"][0]["observations"][0]["product_attribution"])

    def test_protocol_cannot_prove_endpoint_success_or_failure(self):
        value = self.normalize(entry(trial_result(results=False)))
        ledger = self.ledger(value)
        with self.assertRaisesRegex(ContractError, "result_evidence_required"):
            ledger.assert_usable(list(ledger.items), outcome_dimension="primary_endpoint_result")
        self.assertEqual("not_posted", value["sources"][0]["observations"][0]["results_state"])

    def test_posted_results_are_usable_not_automatically_accepted(self):
        value = self.normalize(entry(trial_result()))
        ledger = self.ledger(value)
        refs = [r["evidence_id"] for r in value["evidence"] if r["source_context"]["evidence_use"] == "posted_results"]
        ledger.assert_usable(refs, outcome_dimension="primary_endpoint_result")
        self.assertTrue(all(row["verification"] == "source_available" for row in ledger.rows()))

    def test_wrong_exact_nct_fails_before_models(self):
        self.assert_blocked("clinical_trial_case_identity_mismatch", bundle(entry(trial_result(nct=OTHER_NCT))))

    def test_comparator_cannot_become_case_outcome(self):
        value = self.normalize(entry(trial_result(nct=OTHER_NCT), purpose="comparator"))
        ledger = self.ledger(value)
        with self.assertRaisesRegex(ContractError, "comparator_not_case"):
            ledger.assert_usable(list(ledger.items), outcome_dimension="primary_endpoint_result")

    def test_unidentified_trial_is_a_candidate_not_auto_replacement(self):
        self.request["context"]["subject"]["trial_ids"] = []
        value = self.normalize(entry(trial_result(operation="study_search")))
        self.assertEqual([], value["evidence"])
        self.assertEqual("unresolved", value["sources"][0]["discovery_candidates"][0]["match_status"])
        self.assertEqual([], self.request["context"]["subject"]["trial_ids"])

    def test_pubmed_exact_pmid_date_join(self):
        value = self.normalize(entry(metadata(), "pubmed"), entry(abstract(), "pubmed"))
        row = value["evidence"][0]
        self.assertEqual("original_research", row["source_type"])
        self.assertEqual("2025-01-02", row["published_on"])
        self.assertEqual("12345", row["source_context"]["identifiers"]["pmid"])
        self.assertEqual(100, row["source_context"]["identifiers"]["upstream_offset"])
        self.assertEqual("abstract", row["accessible_extent"])
        self.assertEqual("mentioned_not_adjudicated", row["source_context"]["identifiers"]["nct_link_status"])

    def test_metadata_and_abstract_order_does_not_change_windows(self):
        first, second = entry(metadata(), "pubmed"), entry(abstract(), "pubmed")
        self.assertEqual(self.normalize(first, second)["evidence"], self.normalize(second, first)["evidence"])

    def test_abstract_without_metadata_is_not_date_qualified(self):
        value = self.normalize(entry(abstract(), "pubmed"))
        row = value["evidence"][0]
        self.assertEqual("publication", row["source_type"])
        self.assertIsNone(row["published_on"])
        with self.assertRaisesRegex(ContractError, "unverified"):
            self.ledger(value).assert_usable([row["evidence_id"]])

    def test_different_pmid_metadata_cannot_date_qualify_abstract(self):
        value = self.normalize(entry(metadata(pmid="67890"), "pubmed"), entry(abstract(), "pubmed"))
        self.assertIsNone(value["evidence"][0]["published_on"])

    def test_month_precision_remains_month_no_fabricated_day(self):
        value = self.normalize(entry(metadata(date_value="2024-11", precision="month"), "pubmed"), entry(abstract(), "pubmed"))
        row = value["evidence"][0]
        self.assertIsNone(row["published_on"])
        self.assertEqual("2024-11-30", row["source_context"]["publication_interval"]["end"])
        self.ledger(value).assert_usable([row["evidence_id"]])

    def test_partial_date_overlapping_cutoff_is_not_definitive(self):
        value = self.normalize(entry(metadata(date_value="2025-02", precision="month"), "pubmed"), entry(abstract(), "pubmed"))
        row = value["evidence"][0]
        self.assertEqual("overlaps_cutoff", row["source_context"]["temporal_status"])
        with self.assertRaisesRegex(ContractError, "unverified"):
            self.ledger(value).assert_usable([row["evidence_id"]])

    def test_retraction_or_notice_keeps_text_but_withholds_definitive_use(self):
        value = self.normalize(entry(metadata(notice=True), "pubmed"), entry(abstract(), "pubmed"))
        self.assertTrue(value["evidence"])
        with self.assertRaisesRegex(ContractError, "notice_requires_review"):
            self.ledger(value).assert_usable([value["evidence"][0]["evidence_id"]])

    def test_review_classification_uses_publication_type_not_hostname(self):
        value = self.normalize(entry(metadata(types=["Review"]), "pubmed"), entry(abstract(), "pubmed"))
        self.assertEqual("review", value["evidence"][0]["source_type"])

    def test_future_publication_has_omission_receipt_not_temporal_leak(self):
        value = self.normalize(entry(metadata(date_value="2025-03-01"), "pubmed"), entry(abstract(), "pubmed"))
        self.assertEqual([], value["evidence"])
        self.assertEqual("clinical_source_after_cutoff", value["omissions"][0]["code"])

    def test_umls_never_becomes_clinical_outcome_evidence(self):
        value = self.normalize(entry(terminology(), "umls", purpose="terminology"))
        self.assertEqual([], value["evidence"])
        self.assertFalse(value["terminology"][0]["clinical_equivalence_verified"])
        self.assertFalse(value["terminology"][0]["may_support_outcome"])
        self.assertEqual("candidate", value["terminology"][0]["mapping_status"])

    def test_unconnected_umls_operation_is_not_advertised_as_usable(self):
        result = terminology(); result["operation"] = "mechanism_relations"
        self.assert_blocked("clinical_umls_operation_not_qualified", bundle(entry(result, "umls", purpose="terminology")))

    def test_source_contract_version_and_key_match_exactly(self):
        value = bundle(entry(trial_result())); value["sources"][0]["asset_version"] = "0.1.0"
        self.assert_blocked("clinical_source_contract_mismatch", value)
        value = bundle(entry(terminology(), "umls", purpose="terminology")); value["sources"][0]["asset_key"] = "nusaibah.umls_terminology"
        self.assert_blocked("clinical_source_asset_not_declared", value)

    def test_wrong_subject_or_event_is_hard_failure(self):
        for field, replacement, code in [("subject_id", "OTHER", "clinical_source_bundle_subject_mismatch"),
                ("product_id", "OTHER", "clinical_source_bundle_subject_mismatch"),
                ("event_ids", ["OTHER"], "clinical_source_bundle_event_mismatch")]:
            value = bundle(entry(trial_result())); value[field] = replacement
            self.assert_blocked(code, value)

    def test_tampered_result_digest_fails(self):
        value = bundle(entry(trial_result())); value["sources"][0]["result"]["status"] = "no_match"
        self.assert_blocked("clinical_source_result_digest_mismatch", value)

    def test_duplicate_result_identity_fails(self):
        row = entry(trial_result())
        self.assert_blocked("clinical_source_result_duplicate", bundle(row, deepcopy(row)))

    def test_conflicting_publication_metadata_not_first_or_last_wins(self):
        self.assert_blocked("clinical_pubmed_metadata_conflict", bundle(entry(metadata(), "pubmed", key="m1"),
            entry(metadata(date_value="2024-01-01"), "pubmed", key="m2")))

    def test_empty_result_is_a_source_outcome_not_a_failure(self):
        result = trial_result(); result.update(status="no_match", records=[], record_count=0)
        value = self.normalize(entry(result))
        self.assertEqual("no_match", value["sources"][0]["source_status"])
        self.assertEqual([], value["evidence"])

    def test_source_record_count_mismatch_is_not_tolerated(self):
        result = trial_result(); result["record_count"] = 2
        self.assert_blocked("clinical_source_record_count_mismatch", bundle(entry(result)))

    def test_search_pagination_is_not_full_coverage(self):
        result = trial_result(operation="study_search")
        result["pagination"] = {"has_more": True, "total_count": 200}
        value = self.normalize(entry(result))
        self.assertTrue(value["sources"][0]["coverage"]["has_more"])

    def test_authority_fields_rejected_before_model_work(self):
        value = bundle(entry(trial_result())); value["sources"][0]["result"]["credentials"] = "forbidden"
        with self.assertRaisesRegex(ContractError, "authority_material"):
            prepare_bundle(value, self.request)

    def test_source_windows_preserve_paragraphs_and_offsets(self):
        text = "A" * 10000 + "\n\n" + "B" * 10000
        windows = list(source_windows(text, "/abstract"))
        self.assertEqual(2, len(windows))
        self.assertEqual("/abstract#chars=10002:20002", windows[1][0])
        self.assertEqual("B" * 10000, windows[1][1])

    def test_oversize_scalar_has_digest_not_truncated_science(self):
        windows = list(source_windows("x" * 16001, "/paragraph"))
        self.assertIsNone(windows[0][1]); self.assertEqual(16001, windows[0][2]["characters"])

    def test_utf8_byte_bounds_are_not_character_bounds(self):
        windows = list(source_windows("\u0623" * 9000, "/paragraph"))
        self.assertIsNone(windows[0][1]); self.assertEqual(18000, windows[0][2]["bytes"])

    def test_invalid_dates_fail_with_contract_code(self):
        for value, precision in [("2025-02-30", "day"), ("2025-13", "month"), ("0000", "year")]:
            with self.assertRaises(ContractError): publication_interval(value, precision)


    def test_integrity_operation_merges_notice_into_metadata(self):
        notice = {"schema_version": "pubmed_evidence.v1", "operation": "integrity_get",
            "status": "completed", "record_count": 1, "records": [{"pmid": "12345",
                "integrity_signals": ["Retracted Publication"], "integrity_state": "notice_reported"}]}
        value = self.normalize(entry(metadata(), "pubmed"), entry(notice, "pubmed"), entry(abstract(), "pubmed"))
        self.assertEqual("notice_reported", value["evidence"][0]["source_context"]["integrity_status"])
        with self.assertRaisesRegex(ContractError, "notice_requires_review"):
            self.ledger(value).assert_usable([value["evidence"][0]["evidence_id"]])

    def test_electronic_date_is_not_replaced_with_later_print_date(self):
        meta = metadata(date_value="2025-03-01")
        meta["records"][0]["publication_dates"]["epubdate"] = {"iso": "2025-01-01", "precision": "day"}
        value = self.normalize(entry(meta, "pubmed"), entry(abstract(), "pubmed"))
        row = value["evidence"][0]
        self.assertEqual("2025-01-01", row["published_on"])
        self.assertEqual("epubdate", row["source_context"]["identifiers"]["publication_date_kind"])

    def test_missing_upstream_retrieval_time_stays_missing(self):
        value = self.normalize(entry(trial_result()))
        self.assertIsNone(value["sources"][0]["source_provenance"][0]["retrieved_at"])

    def test_actual_retrieval_time_survives_provenance_projection(self):
        result = trial_result()
        result["provenance"]["retrieved_at"] = "2025-02-01T12:00:00Z"
        value = self.normalize(entry(result))
        self.assertEqual("2025-02-01T12:00:00Z", value["sources"][0]["source_provenance"][0]["retrieved_at"])

    def test_eighty_full_abstract_sections_preserved_without_slicing(self):
        result = abstract()
        result["records"][0]["sections"] = [
            {"section": "RESULTS", "offset": i * 5000, "text": str(i) + ":" + "x" * 4500}
            for i in range(80)]
        value = self.normalize(entry(metadata(), "pubmed"), entry(result, "pubmed"))
        self.assertEqual("normalized", value["status"])
        self.assertEqual(80, len(value["evidence"]))
        self.assertEqual([], value["omissions"])
        self.assertTrue(all(len(row["text"]) >= 4502 for row in value["evidence"]))

    def test_window_cap_reports_every_omitted_piece_without_slicing(self):
        entries = []
        for index in range(5):
            pmid = str(10000 + index)
            entries.append(entry(metadata(pmid=pmid), "pubmed", key="meta" + pmid))
            record = abstract(pmid=pmid)
            record["records"][0]["sections"] = [
                {"section": "RESULTS", "offset": i * 150, "text": "Synthetic passage " + str(i) + ("x" * 100)}
                for i in range(90)]
            entries.append(entry(record, "pubmed", key="abstract" + pmid))
        value = self.normalize(*entries)
        self.assertEqual("partial", value["status"])
        self.assertEqual(384, len(value["evidence"]))
        self.assertEqual(450, len(value["evidence"]) + len(value["omissions"]))
        self.assertTrue(all("text_digest" in row for row in value["omissions"]))

    def test_duplicate_native_windows_charge_all_inline_receipt_bytes(self):
        first = trial_result(operation="study_get")
        first["records"][0]["content_digest"] = digest(first["records"][0]["registry_study"])
        second = deepcopy(first)
        second["operation"] = "results_get"
        value = self.normalize(entry(first, key="study"), entry(second, key="results"))
        self.assertEqual("normalized", value["status"])
        self.assertEqual([], value["omissions"])
        self.assertEqual([], value["equivalent_source_receipt_groups"])
        self.assertEqual(len(value["evidence"]), value["coverage_receipt"]["duplicate_native_windows"])
        self.assertEqual(sum(len(canonical_bytes(row)) for row in value["evidence"]),
                         value["coverage_receipt"]["retained_evidence_bytes"])
        self.assertTrue(all(len(row["source_context"]["equivalent_source_results"]) == 1
                            for row in value["evidence"]))
        self.assertLessEqual(value["coverage_receipt"]["retained_evidence_bytes"], MAX_EVIDENCE_BYTES)

    def test_duplicate_receipts_at_exact_budget_use_shared_index(self):
        first = trial_result()
        first["records"][0]["content_digest"] = digest(first["records"][0]["registry_study"])
        second = deepcopy(first)
        second["operation"] = "results_get"
        from unittest.mock import patch
        from clinical_failure_intelligence import source_bundle
        baseline = self.normalize(entry(first, key="study"))
        initial_bytes = baseline["coverage_receipt"]["retained_evidence_bytes"]
        with patch.object(source_bundle, "MAX_EVIDENCE_BYTES", initial_bytes):
            value = self.normalize(entry(first, key="study"), entry(second, key="results"))
        self.assertEqual("partial", value["status"])
        self.assertEqual(initial_bytes, value["coverage_receipt"]["retained_evidence_bytes"])
        self.assertEqual(sum(len(canonical_bytes(row)) for row in value["evidence"]),
                         value["coverage_receipt"]["retained_evidence_bytes"])
        self.assertEqual(1, len(value["equivalent_source_receipt_groups"]))
        group = value["equivalent_source_receipt_groups"][0]
        self.assertEqual(len(value["evidence"]), group["deferred_windows"])
        self.assertEqual([[0, len(value["evidence"])]], group["window_index_ranges"])
        self.assertEqual(1, len(value["omissions"]))
        self.assertEqual("clinical_source_duplicate_receipt_budget", value["omissions"][0]["code"])

    def test_many_immutable_duplicate_receipts_do_not_exceed_prepared_budget(self):
        # All 24 source-result receipts refer to the same synthetic 301-window
        # study; the bundle itself is smaller than its 1 MiB input allowance.
        source = trial_result(results=False)
        study = source["records"][0]["registry_study"]
        study.pop("hasResults", None)
        study["protocolSection"] = {"identificationModule": {"nctId": NCT}}
        study["protocolSection"].update({
            "module_" + str(i): {"value": "Synthetic registry field " + str(i)}
            for i in range(300)})
        source["records"][0]["content_digest"] = digest(study)
        receipts = [entry(source, key="copy_" + str(i).zfill(2)) for i in range(24)]
        supplied = bundle(*receipts)
        self.assertLess(len(canonical_bytes(supplied)), MAX_BUNDLE_BYTES)
        value = self.normalize(*receipts)
        self.assertEqual("partial", value["status"])
        self.assertEqual(301, len(value["evidence"]))
        self.assertGreater(value["coverage_receipt"]["deferred_duplicate_receipt_windows"], 0)
        self.assertTrue(value["equivalent_source_receipt_groups"])
        self.assertTrue(all(x["code"] == "clinical_source_duplicate_receipt_budget"
                            for x in value["omissions"]))
        self.assertLessEqual(len(value["omissions"]), len(receipts))
        self.assertEqual(sum(len(canonical_bytes(row)) for row in value["evidence"]),
                         value["coverage_receipt"]["retained_evidence_bytes"])
        self.assertLessEqual(value["coverage_receipt"]["retained_evidence_bytes"], MAX_EVIDENCE_BYTES)
        self.assertEqual(301 * 23, value["coverage_receipt"]["duplicate_native_windows"])
        # Deferred receipts remain traceable to exact returned evidence indexes
        # without claiming the duplicate study is independent corroboration.
        sources = {x["source_result_id"]: x["result_digest"] for x in value["sources"]}
        for group in value["equivalent_source_receipt_groups"]:
            self.assertEqual(sources[group["source_result_id"]], group["source_result_digest"])
            indexes = [i for low, high in group["window_index_ranges"] for i in range(low, high)]
            self.assertEqual(len(indexes), group["deferred_windows"])
            self.assertEqual(len(indexes), len(set(indexes)))
            self.assertTrue(all(0 <= i < len(value["evidence"]) for i in indexes))
        # End-to-end provider-free preflight must retain scientific text without
        # failing only because duplicate receipt metadata expanded after count.
        from clinical_failure_intelligence.orchestration import run_analysis
        data = case_inputs()
        data["clinical_evidence"] = supplied
        data["variables"]["preflight_only"] = True
        data["variables"]["memory_mode"] = "off"
        output = run_analysis(FakeInputs(data))["outputs"]["clinical_intelligence"]
        self.assertEqual("preflight", output["quality"]["status"])
        self.assertEqual("partial", output["prepared_sources"]["status"])
        self.assertFalse(output["memory_update"]["write_attempted"])

    def test_malformed_result_status_is_typed_not_unhashable_crash(self):
        for status in ([], {}, None, True):
            result = trial_result(); result["status"] = status
            self.assert_blocked("clinical_source_result_not_terminal", bundle(entry(result)))

    def test_malformed_registry_modules_have_explicit_contract_failures(self):
        result = trial_result(); result["records"][0]["registry_study"]["protocolSection"] = []
        self.assert_blocked("clinical_trial_modules_invalid", bundle(entry(result)))
        result = trial_result(); result["records"][0]["registry_study"]["protocolSection"]["identificationModule"] = "bad"
        self.assert_blocked("clinical_trial_modules_invalid", bundle(entry(result)))
        result = trial_result(); result["records"][0]["registry_study"]["resultsSection"]["outcomeMeasuresModule"] = False
        self.assert_blocked("clinical_trial_results_module_invalid", bundle(entry(result)))

    def test_bioc_missing_pmid_and_invalid_offsets_are_typed(self):
        result = abstract(); result["records"][0].pop("pmid")
        self.assert_blocked("clinical_pubmed_identity_invalid", bundle(entry(result, "pubmed")))
        for offset in (-1, "20", True):
            result = abstract(); result["records"][0]["sections"][0]["offset"] = offset
            self.assert_blocked("clinical_pubmed_offset_invalid", bundle(entry(result, "pubmed")))

    def test_baseline_characteristics_do_not_prove_endpoint_result(self):
        result = trial_result()
        result["records"][0]["registry_study"]["resultsSection"] = {"baselineCharacteristicsModule": {"enrollment": 100}}
        value = self.normalize(entry(result)); ledger = self.ledger(value)
        with self.assertRaisesRegex(ContractError, "result_evidence_required"):
            ledger.assert_usable(list(ledger.items), outcome_dimension="primary_endpoint_result")

    def test_conflicting_nested_nct_is_rejected(self):
        result = trial_result()
        result["records"][0]["registry_study"]["protocolSection"]["identificationModule"]["nctId"] = OTHER_NCT
        self.assert_blocked("clinical_trial_case_identity_mismatch", bundle(entry(result)))

    def test_false_temporal_label_cannot_override_interval(self):
        value = self.normalize(entry(metadata(date_value="2025-02", precision="month"), "pubmed"), entry(abstract(), "pubmed"))
        value["evidence"][0]["source_context"]["temporal_status"] = "eligible_by_source_date"
        with self.assertRaisesRegex(ContractError, "temporal_leak"):
            self.ledger(value)

    def test_nonobject_bundle_entries_are_not_accepted(self):
        for malformed in (None, [], "value", True):
            value = bundle(malformed)
            with self.assertRaises(ContractError): prepare_bundle(value, self.request)


if __name__ == "__main__": unittest.main()
