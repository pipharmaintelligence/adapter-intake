"""Consume prepared source-adapter results without calling or importing those adapters.

The optional ``clinical_evidence`` role is binding-owned. Its digest checks are
integrity checks, not signatures or admission. Assets/Core must independently
prepare the authorized handoff. Source retrieval, provider calls and writes are
not performed by this module.
"""
from __future__ import annotations

from calendar import monthrange
from copy import deepcopy
from datetime import date, datetime
import re
from typing import Any, Iterator

if __package__:
    from .contracts_v0_1_9 import (ContractError, canonical_bytes, digest, identifier,
        identifiers, iso_date, object_fields, require, safe_json, text, text_digest)
else:
    from contracts_v0_1_9 import (ContractError, canonical_bytes, digest, identifier,
        identifiers, iso_date, object_fields, require, safe_json, text, text_digest)

BUNDLE_SCHEMA = "clinical_evidence_bundle.v1"
SOURCE_CONTRACTS = {
    "nusaibah.clinical_trials_lookup": ("0.1.1", "trial_result", "clinical_trials_lookup.v1"),
    "nusaibah.pubmed_evidence": ("0.1.0", "literature_result", "pubmed_evidence.v1"),
    "umls_terminology": ("0.1.1", "terminology_result", None),
}
MAX_BUNDLE_BYTES = 4_194_304  # Warning threshold; runtime owns transport ceilings.
MAX_SOURCE_RESULTS = 24
MAX_RECORDS = 50
MAX_WINDOWS = 512  # Bounded complete-window index; never an Agent prompt allowance.
MAX_EVIDENCE_BYTES = 1_048_576  # Cover verified large registry results; defer if exceeded.
MAX_WINDOW_BYTES = 16_000
MAX_WINDOW_CHARS = 12_000
_NCT = re.compile(r"NCT[0-9]{8}\Z")
_PMID = re.compile(r"[1-9][0-9]{0,11}\Z")
_CUI = re.compile(r"C[0-9]{7}\Z")


def publication_interval(value: Any, precision: str = "day") -> dict:
    """Preserve date precision; interval bounds do not fabricate a publication day."""
    unknown = {"precision": "unknown", "reported": value, "start": None, "end": None}
    if value is None:
        return unknown
    require(isinstance(value, str) and len(value) <= 80, "clinical_source_date_invalid")
    try:
        if precision == "day":
            first = last = date.fromisoformat(iso_date(value))
        elif precision == "month" and re.fullmatch(r"[0-9]{4}-[0-9]{2}", value):
            year, month = map(int, value.split("-"))
            first, last = date(year, month, 1), date(year, month, monthrange(year, month)[1])
        elif precision == "year" and re.fullmatch(r"[0-9]{4}", value):
            first, last = date(int(value), 1, 1), date(int(value), 12, 31)
        elif precision == "unknown":
            return unknown
        else:
            raise ValueError
    except (ValueError, TypeError):
        raise ContractError("clinical_source_date_invalid") from None
    return {"precision": precision, "reported": value,
            "start": first.isoformat(), "end": last.isoformat()}


def _pointer(key: str | int) -> str:
    return str(key).replace("~", "~0").replace("/", "~1")


def source_windows(value: Any, pointer: str) -> Iterator[tuple[str, str | None, dict | None]]:
    """Split at structured fields or complete paragraphs, never slice a sentence.

    Structured windows use canonical JSON with a JSON pointer. Their text is an
    exact deterministic representation, not an invented quote from an article.
    Oversized scalar paragraphs remain explicit omissions with their own digest.
    """
    rendered = value if isinstance(value, str) else canonical_bytes(value).decode("utf-8")
    if not rendered.strip():
        return
    if len(rendered) <= MAX_WINDOW_CHARS and len(rendered.encode("utf-8")) <= MAX_WINDOW_BYTES:
        yield pointer, rendered, None
    elif isinstance(value, dict):
        for key in sorted(value):
            yield from source_windows(value[key], pointer + "/" + _pointer(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from source_windows(item, pointer + "/" + str(index))
    elif isinstance(value, str) and "\n\n" in value:
        # Preserve original offsets through the source pointer extension.
        position = 0
        for paragraph in value.split("\n\n"):
            path = pointer + "#chars=" + str(position) + ":" + str(position + len(paragraph))
            yield from source_windows(paragraph, path)
            position += len(paragraph) + 2
    else:
        yield pointer, None, {"code": "clinical_source_scalar_requires_partitioning",
            "source_pointer": pointer, "characters": len(rendered),
            "bytes": len(rendered.encode("utf-8")), "text_digest": text_digest(rendered)}


def validate_bundle(value: Any, request: dict) -> dict:
    """Validate a closed, exact-subject handoff before any Agent or Skill call."""
    bundle = object_fields(value, {"schema_version", "bundle_id", "subject_id", "product_id",
                                  "event_ids", "sources"})
    safe_json(bundle)
    require(bundle["schema_version"] == BUNDLE_SCHEMA, "clinical_source_bundle_schema_invalid")
    identifier(bundle["bundle_id"])
    require(bundle["subject_id"] == request["subject_id"] and
            bundle["product_id"] == request["context"]["subject"]["product_id"],
            "clinical_source_bundle_subject_mismatch")
    require(set(identifiers(bundle["event_ids"], maximum=32)) == set(request["event_ids"]),
            "clinical_source_bundle_event_mismatch")
    require(isinstance(bundle["sources"], list) and len(bundle["sources"]) <= MAX_SOURCE_RESULTS,
            "clinical_source_bundle_count_invalid")
    seen: set[str] = set()
    for source in bundle["sources"]:
        object_fields(source, {"source_result_id", "asset_key", "asset_version", "output_role",
                               "purpose", "result", "result_digest"}, {"execution_ref"})
        sid = identifier(source["source_result_id"])
        require(sid not in seen, "clinical_source_result_duplicate")
        seen.add(sid)
        asset = source["asset_key"]
        require(isinstance(asset, str) and asset in SOURCE_CONTRACTS,
                "clinical_source_asset_not_declared")
        version, role, schema = SOURCE_CONTRACTS[asset]
        require(source["asset_version"] == version and source["output_role"] == role,
                "clinical_source_contract_mismatch")
        require(isinstance(source["purpose"], str) and source["purpose"] in {
            "case", "comparator", "mechanism", "terminology"}, "clinical_source_purpose_invalid")
        if source.get("execution_ref") is not None:
            identifier(source["execution_ref"])
        result = source["result"]
        require(isinstance(result, dict) and source["result_digest"] == digest(result),
                "clinical_source_result_digest_mismatch")
        if schema is not None:
            require(result.get("schema_version") == schema, "clinical_source_result_schema_invalid")
        operation = result.get("operation")
        require(isinstance(operation, str), "clinical_source_operation_missing")
        rows = result.get("records", [])
        require(isinstance(rows, list) and len(rows) <= MAX_RECORDS and
                all(isinstance(row, dict) for row in rows), "clinical_source_records_invalid")
        if "record_count" in result:
            require(type(result["record_count"]) is int and result["record_count"] == len(rows),
                    "clinical_source_record_count_mismatch")
        allowed_status = {"ok", "partial", "not_found"} if asset == "umls_terminology" else {"completed", "no_match"}
        require(isinstance(result.get("status"), str) and result["status"] in allowed_status,
                "clinical_source_result_not_terminal")
        if result["status"] in {"no_match", "not_found"}:
            require(not rows, "clinical_source_empty_status_conflict")
    return deepcopy(bundle)


class _Collector:
    """Bounded canonical windows and explicit omitted-work records."""
    def __init__(self, request: dict) -> None:
        self.request = request
        self.windows: list[dict] = []
        self.omissions: list[dict] = []
        self.byte_count = 0
        self._seen: dict[str, int] = {}
        self.duplicate_windows = 0
        # Share oversized provenance receipts rather than replicate them per
        # scientific evidence window. Internal index sets are range-compressed.
        self._deferred_receipt_groups: dict[tuple[str, str], dict] = {}

    def add(self, entry: dict, source_id: str, content: Any, pointer: str, *, source_type: str,
            extent: str, trial_ids: list[str], interval: dict, use: str,
            identifiers_value: dict, integrity: str = "not_assessed",
            source_revision: str | None = None) -> None:
        for field_pointer, raw_text, omitted in source_windows(content, pointer):
            if omitted:
                self.omissions.append({"source_result_id": entry["source_result_id"], **omitted})
                continue
            assert raw_text is not None
            content_hash = text_digest(raw_text)
            revision = source_revision or entry["result_digest"]
            identity = digest([source_id, field_pointer, content_hash, entry["purpose"],
                               revision, interval, use, integrity])
            if identity in self._seen:
                # Multiple lookup operations may reference the SAME native
                # study. Their distinct receipts are not independent evidence.
                index = self._seen[identity]
                existing = self.windows[index]
                receipt = {"source_result_id": entry["source_result_id"],
                           "source_result_digest": entry["result_digest"]}
                context = existing["source_context"]
                primary = {key: context[key] for key in receipt}
                if receipt != primary and receipt not in context.get("equivalent_source_results", []):
                    # Count serialized growth BEFORE mutating a retained row;
                    # setdefault() on a nested object is itself a byte change.
                    candidate = deepcopy(existing)
                    candidate["source_context"].setdefault("equivalent_source_results", []).append(receipt)
                    delta = len(canonical_bytes(candidate)) - len(canonical_bytes(existing))
                    require(delta > 0, "clinical_duplicate_receipt_size_invalid")
                    if self.byte_count + delta <= MAX_EVIDENCE_BYTES:
                        existing["source_context"] = candidate["source_context"]
                        self.byte_count += delta
                    else:
                        self._defer_duplicate_receipt(entry, index)
                self.duplicate_windows += 1
                continue
            earliest, latest = interval["start"], interval["end"]
            cutoff = self.request["as_of_date"]
            temporal = ("unknown" if latest is None else "eligible_by_source_date" if latest <= cutoff
                        else "after_cutoff" if earliest > cutoff else "overlaps_cutoff")
            # Preserve later source observations in metadata, never as historical evidence.
            if temporal == "after_cutoff":
                self.omissions.append({"source_result_id": entry["source_result_id"],
                    "code": "clinical_source_after_cutoff", "source_pointer": field_pointer,
                    "text_digest": content_hash})
                continue
            window = {
                "evidence_id": "SRC_" + identity.split(":")[1][:28], "source_id": source_id,
                "subject_id": self.request["subject_id"], "source_type": source_type,
                "source_version": revision,
                "published_on": earliest if interval["precision"] == "day" else None,
                "accessible_extent": extent, "text": raw_text, "trial_ids": trial_ids,
                "source_context": {
                    "source_asset": entry["asset_key"] + "@" + entry["asset_version"],
                    "source_result_id": entry["source_result_id"],
                    "source_result_digest": entry["result_digest"], "source_pointer": field_pointer,
                    "identifiers": identifiers_value, "purpose": entry["purpose"],
                    "evidence_use": use, "publication_interval": interval,
                    "temporal_status": temporal, "integrity_status": integrity,
                    "acquisition": "prepared_source_result", "text_representation":
                        "source_text" if isinstance(content, str) else "canonical_json",
                },
            }
            size = len(canonical_bytes(window))
            if len(self.windows) >= MAX_WINDOWS or self.byte_count + size > MAX_EVIDENCE_BYTES:
                self.omissions.append({"source_result_id": entry["source_result_id"],
                    "code": "clinical_source_window_budget", "source_pointer": field_pointer,
                    "text_digest": content_hash, "bytes": size,
                    "budget_constraint": "window_count" if len(self.windows) >= MAX_WINDOWS else "evidence_bytes"})
                continue
            self._seen[identity] = len(self.windows)
            self.windows.append(window)
            self.byte_count += size

    def _defer_duplicate_receipt(self, entry: dict, index: int) -> None:
        """Retain exact source lineage in a bounded shared reference index.

        Grouped omissions report inline-receipt deferral, not scientific text
        loss. Window indexes refer to the deterministic prepared evidence list.
        """
        key = (entry["source_result_id"], entry["result_digest"])
        group = self._deferred_receipt_groups.get(key)
        if group is None:
            group = {"source_result_id": key[0], "source_result_digest": key[1],
                     "window_indexes": set()}
            self._deferred_receipt_groups[key] = group
            self.omissions.append({"code": "clinical_source_duplicate_receipt_budget",
                "source_result_id": key[0], "source_result_digest": key[1],
                "deferred_windows": 0})
        if index not in group["window_indexes"]:
            group["window_indexes"].add(index)
            for omission in self.omissions:
                if (omission["code"] == "clinical_source_duplicate_receipt_budget"
                        and omission["source_result_id"] == key[0]
                        and omission["source_result_digest"] == key[1]):
                    omission["deferred_windows"] = len(group["window_indexes"])
                    break

    def receipt_groups(self) -> list[dict]:
        """Encode exact window memberships as half-open index ranges."""
        groups = []
        for group in self._deferred_receipt_groups.values():
            ranges: list[list[int]] = []
            for index in sorted(group["window_indexes"]):
                if ranges and ranges[-1][1] == index:
                    ranges[-1][1] = index + 1
                else:
                    ranges.append([index, index + 1])
            groups.append({"source_result_id": group["source_result_id"],
                           "source_result_digest": group["source_result_digest"],
                           "window_index_ranges": ranges,
                           "deferred_windows": len(group["window_indexes"])})
        return groups


def _trial(entry: dict, collector: _Collector, summary: dict) -> None:
    result = entry["result"]
    op = result["operation"]
    require(op in {"describe", "study_search", "study_get", "study_batch", "arms_get",
                   "outcomes_get", "results_get"}, "clinical_trial_operation_unrecognized")
    require(entry["purpose"] in {"case", "comparator"}, "clinical_source_purpose_invalid")
    expected = set(collector.request["context"]["subject"]["trial_ids"])
    rows = result.get("records", [])
    ids = [row.get("nct_id") for row in rows]
    require(all(isinstance(value, str) and _NCT.fullmatch(value) for value in ids)
            and len(ids) == len(set(ids)), "clinical_trial_result_identity_invalid")
    summary["coverage"] = deepcopy(result.get("pagination", {}))
    for row in rows:
        nct = row["nct_id"]
        matched = nct in expected
        if entry["purpose"] == "case" and op not in {"study_search", "describe"} and expected:
            require(matched, "clinical_trial_case_identity_mismatch")
        if entry["purpose"] == "case" and not matched:
            summary["discovery_candidates"].append({"nct_id": nct, "match_status": "unresolved"})
            continue
        source_date = row.get("registry_update_date")
        interval = publication_interval(source_date)
        summary_data = row.get("summary", {})
        require(isinstance(summary_data, dict), "clinical_trial_summary_invalid")
        study = row.get("registry_study")
        require(study is None or isinstance(study, dict), "clinical_trial_study_invalid")
        # Lookup 0.1.1 exposes the exact native study digest. Validate it
        # independently of the prepared result-envelope checksum so that a
        # modified study cannot be passed off as an unchanged registry revision.
        native_revision = row.get("content_digest")
        if native_revision is not None:
            require(isinstance(native_revision, str) and study is not None and
                    native_revision == digest(study),
                    "clinical_trial_native_digest_mismatch")
        if isinstance(study, dict):
            native_revision = native_revision or digest(study)
        policy = result.get("size_policy")
        if policy is not None:
            require(isinstance(policy, dict) and
                    policy.get("action") == "preserved_complete" and
                    type(policy.get("threshold_exceeded")) is bool,
                    "clinical_trial_source_not_complete")
            if policy['threshold_exceeded']:
                summary['size_warning']=deepcopy(policy)
        base_id = "ctgov:" + nct
        identifiers_value = {"nct_id": nct}
        def add(value: Any, pointer: str, use: str) -> None:
            collector.add(entry, base_id, value, pointer, source_type="trial_registry",
                extent="registry_record", trial_ids=[nct], interval=interval,
                use=use, identifiers_value=identifiers_value,
                source_revision=native_revision)
        if study:
            protocol = study.get("protocolSection", {})
            results = study.get("resultsSection", {})
            require(isinstance(protocol, dict) and isinstance(results, dict), "clinical_trial_modules_invalid")
            identification = protocol.get("identificationModule") or {}
            require(isinstance(identification, dict), "clinical_trial_modules_invalid")
            nested_id = identification.get("nctId")
            require(nested_id is None or nested_id == nct, "clinical_trial_case_identity_mismatch")
            if op == "results_get" and result.get("results_state") == "posted":
                require(bool(results), "clinical_trial_posted_results_missing")
            for name in sorted(results):
                require(isinstance(results[name], dict), "clinical_trial_results_module_invalid")
                use = ("safety_results" if name == "adverseEventsModule" else
                       "posted_results" if name == "outcomeMeasuresModule" else "result_context")
                add(results[name], "/registry_study/resultsSection/" + _pointer(name), use)
            # Preserve scientific priority even when the canonical window allowance
            # is reached: contacts/locations must not crowd out outcomes or safety.
            for name in sorted(protocol, key=lambda key: (key == 'contactsLocationsModule', key)):
                add(protocol[name], "/registry_study/protocolSection/" + _pointer(name), "protocol")
            # Documents and derived content remain separately identified, not silently discarded.
            for name in sorted(set(study) - {"protocolSection", "resultsSection"}):
                add(study[name], "/registry_study/" + _pointer(name), "registry_metadata")
        else:
            add(summary_data, "/summary", "protocol")
        arms = summary_data.get("arm_groups") or []
        require(isinstance(arms, list) and all(isinstance(arm, dict) for arm in arms),
                "clinical_trial_arm_groups_invalid")
        summary["observations"].append({"nct_id": nct,
            "registry_update_date": source_date, "results_state": result.get("results_state"),
            "protocol_arm_labels": [arm.get("label") for arm in arms],
            "results_group_join": "not_inferred", "product_attribution": "requires_case_review"})


def _publication_index(entries: list[dict]) -> dict[str, dict]:
    """Join metadata/history/integrity by PMID, merging only compatible fields."""
    index: dict[str, dict] = {}
    scalar_keys = ("publication_dates", "doi", "pmcid")
    list_keys = ("publication_types", "integrity_signals", "nct_ids_in_record")
    for entry in entries:
        if entry["asset_key"] != "nusaibah.pubmed_evidence":
            continue
        for row in entry["result"].get("records", []):
            pmid = row.get("pmid")
            if pmid is None:
                require(entry["result"]["operation"] not in {"article_get", "article_batch", "abstract_get",
                    "publication_profile", "publication_history", "integrity_get"},
                    "clinical_pubmed_identity_invalid")
                continue
            require(isinstance(pmid, str) and _PMID.fullmatch(pmid), "clinical_pubmed_identity_invalid")
            if not any(key in row for key in (*scalar_keys, *list_keys, "integrity_state")):
                continue
            selected = index.setdefault(pmid, {})
            for key in scalar_keys:
                if row.get(key) is None:
                    continue
                if key == "publication_dates":
                    require(isinstance(row[key], dict), "clinical_pubmed_metadata_invalid")
                    dates = selected.setdefault(key, {})
                    for name, value in row[key].items():
                        require(isinstance(value, dict), "clinical_pubmed_metadata_invalid")
                        prior = dates.get(name)
                        if prior is not None and prior.get("iso") is not None and value.get("iso") is not None:
                            require(prior.get("iso") == value.get("iso") and prior.get("precision") == value.get("precision"),
                                    "clinical_pubmed_metadata_conflict")
                        if prior is None or prior.get("iso") is None:
                            dates[name] = deepcopy(value)
                else:
                    require(key not in selected or selected[key] == row[key], "clinical_pubmed_metadata_conflict")
                    selected[key] = deepcopy(row[key])
            for key in list_keys:
                if row.get(key) is None:
                    continue
                require(isinstance(row[key], list) and all(isinstance(value, str) for value in row[key]),
                        "clinical_pubmed_metadata_invalid")
                selected[key] = sorted(set(selected.get(key, [])) | set(row[key]))
            state = row.get("integrity_state")
            if state is not None:
                require(isinstance(state, str), "clinical_pubmed_metadata_invalid")
                if selected.get("integrity_state") != "notice_reported":
                    selected["integrity_state"] = state
    return index


def _pubmed(entry: dict, collector: _Collector, metadata: dict, summary: dict) -> None:
    result = entry["result"]
    op = result["operation"]
    require(op in {"describe", "database_info", "article_search", "advanced_search", "article_count",
        "trial_publications", "article_get", "article_batch", "abstract_get", "publication_profile",
        "publication_history", "integrity_get", "identifier_resolve", "related_articles",
        "citation_links", "cross_database_links", "export_citations"}, "clinical_pubmed_operation_unrecognized")
    require(entry["purpose"] in {"case", "comparator", "mechanism"}, "clinical_source_purpose_invalid")
    summary["coverage"] = deepcopy(result.get("coverage", {}))
    for row in result.get("records", []):
        pmid = row.get("pmid")
        if pmid is None:
            summary["observations"].append({"operation": op, "interpretation": "metadata_only"})
            continue
        require(isinstance(pmid, str) and _PMID.fullmatch(pmid), "clinical_pubmed_identity_invalid")
        meta = metadata.get(pmid, {})
        if op != "abstract_get":
            summary["discovery_candidates"].append({"pmid": pmid, "operation": op,
                "evidence_level": "metadata_only" if meta else "discovery_only"})
            continue
        sections = row.get("sections", [])
        require(isinstance(sections, list) and len(sections) <= 100,
                "clinical_pubmed_sections_invalid")
        dates = meta.get("publication_dates") or {}
        electronic = dates.get("epubdate") or {}
        date_kind = "epubdate" if electronic.get("iso") is not None else "pubdate"
        reported = dates.get(date_kind) or {}
        require(isinstance(reported, dict), "clinical_source_date_invalid")
        interval = publication_interval(reported.get("iso"), reported.get("precision", "unknown"))
        pubtypes = meta.get("publication_types") or []
        signals = meta.get("integrity_signals") or []
        require(isinstance(pubtypes, list) and isinstance(signals, list) and
                all(isinstance(t, str) for t in pubtypes + signals), "clinical_pubmed_metadata_invalid")
        integrity = "notice_reported" if signals or meta.get("integrity_state") == "notice_reported" else "not_established"
        is_review = any(isinstance(t, str) and "review" in t.casefold() for t in pubtypes)
        is_original = any(isinstance(t, str) and t.casefold() in {
            "clinical trial", "randomized controlled trial", "controlled clinical trial",
            "clinical trial, phase i", "clinical trial, phase ii", "clinical trial, phase iii",
            "clinical trial, phase iv"} for t in pubtypes)
        source_type = "review" if is_review else "original_research" if is_original else "publication"
        metadata_trials = meta.get("nct_ids_in_record") or []
        require(isinstance(metadata_trials, list) and all(isinstance(t, str) and _NCT.fullmatch(t)
                for t in metadata_trials), "clinical_pubmed_trial_reference_invalid")
        for index, section in enumerate(sections):
            require(isinstance(section, dict) and isinstance(section.get("text"), str),
                    "clinical_pubmed_section_invalid")
            body = section["text"]
            require(section.get("offset") is None or
                    type(section["offset"]) is int and section["offset"] >= 0,
                    "clinical_pubmed_offset_invalid")
            mentioned = sorted(set(metadata_trials) | set(re.findall(r"\bNCT[0-9]{8}\b", body)))
            # Mentioning an NCT establishes a link candidate, not a clinical result.
            collector.add(entry, "pubmed:" + pmid, body, "/records/" + pmid + "/sections/" + str(index),
                source_type=source_type, extent="abstract", trial_ids=mentioned, interval=interval,
                use="publication_text", identifiers_value={"pmid": pmid, "doi": meta.get("doi"),
                    "pmcid": meta.get("pmcid"), "nct_link_status": "mentioned_not_adjudicated",
                    "publication_types": pubtypes, "publication_date_kind": date_kind,
                    "upstream_offset": section.get("offset")}, integrity=integrity)
        summary["observations"].append({"pmid": pmid, "publication_date_joined": interval["start"] is not None,
            "date_precision": interval["precision"], "integrity_state": integrity,
            "accessible_extent": "abstract", "full_text_read": False})


def _terminology(entry: dict, summary: dict) -> list[dict]:
    result = entry["result"]
    require(result["operation"] in {"describe", "search"}, "clinical_umls_operation_not_qualified")
    require(entry["purpose"] == "terminology", "clinical_source_purpose_invalid")
    provenance = result.get("provenance") or {}
    require(isinstance(provenance, dict), "clinical_umls_provenance_invalid")
    receipt = terminology_attestation(result)
    summary["runtime_fetch_attestation"] = receipt
    summary["coverage"] = deepcopy(result.get("completeness", {}))
    candidates = []
    for row in result.get("records", []):
        cui = row.get("ui")
        require(isinstance(cui, str) and _CUI.fullmatch(cui), "clinical_umls_cui_invalid")
        semantic = row.get("semantic_types")
        require(semantic is None or isinstance(semantic, list) and
                all(isinstance(item, dict) for item in semantic), "clinical_umls_semantic_types_invalid")
        require(row.get("name") is None or isinstance(row["name"], str) and len(row["name"]) <= 4096,
                "clinical_umls_term_invalid")
        candidates.append({"cui": cui, "preferred_name": row.get("name"),
            "semantic_types": deepcopy(semantic), "source_vocabulary": row.get("rootSource"),
            "release": provenance.get("release"), "source_result_id": entry["source_result_id"],
            "query_attested": result.get("query_attested") is True,
            "fetch_id": receipt["fetch_id"] if receipt is not None else None,
            "mapping_status": "candidate", "clinical_equivalence_verified": False,
            "may_support_outcome": False, "license_status": "not_attested"})
    return candidates


def terminology_attestation(result: dict) -> dict | None:
    """Consume the pinned producer's receipt without claiming to authenticate it.

    UMLS 0.1.1 and its admitted worker validate the *full fetched* record digest
    before local limiting. A clinical consumer cannot reconstruct that digest
    from the projected records. Retained-output admission authenticates the
    producer; this check preserves the closed receipt and selector commitment.
    Neither the receipt nor its completion time certifies a UMLS release,
    provider retrieval time, complete results, or clinical equivalence.
    """
    if result.get("operation") == "describe":
        require(not result.get("records"), "clinical_umls_describe_records_invalid")
        return None
    require(result.get("query_attested") is True, "clinical_umls_attestation_required")
    provenance = result.get("provenance")
    require(isinstance(provenance, dict), "clinical_umls_provenance_invalid")
    receipt = object_fields(provenance.get("runtime_fetch_evidence"), {
        "schema_version", "fetch_id", "source_id", "capability_ref", "operation",
        "effective_selectors_digest", "response_digest", "record_count", "completed_at_utc"})
    require(receipt["schema_version"] == "runtime_source_fetch_evidence.v1" and
            receipt["capability_ref"] == "umls.terminology.search" and receipt["operation"] == "search",
            "clinical_umls_attestation_identity_invalid")
    require(isinstance(receipt["fetch_id"], str) and
            re.fullmatch(r"rsf_[0-9a-f]{32}", receipt["fetch_id"]) is not None and
            isinstance(receipt["source_id"], str) and
            re.fullmatch(r"[A-Za-z0-9_.:@-]{1,191}", receipt["source_id"]) is not None,
            "clinical_umls_attestation_identity_invalid")
    for field in ("effective_selectors_digest", "response_digest"):
        require(isinstance(receipt[field], str) and
                re.fullmatch(r"sha256:[0-9a-f]{64}", receipt[field]) is not None,
                "clinical_umls_attestation_digest_invalid")
    query = result.get("query")
    require(isinstance(query, dict) and query.get("operation") == "search" and
            isinstance(query.get("text"), str) and query.get("search_type") in {"exact", "words", "normalizedString", "normalizedWords", "rightTruncation", "leftTruncation"},
            "clinical_umls_attestation_query_invalid")
    selectors = {"string": query["text"], "searchType": query["search_type"]}
    if "sources" in query:
        require(isinstance(query["sources"], list) and all(isinstance(s, str) for s in query["sources"]),
                "clinical_umls_attestation_query_invalid")
        selectors["sabs"] = ",".join(query["sources"])
    require(receipt["effective_selectors_digest"] == digest([selectors]),
            "clinical_umls_attestation_selector_mismatch")
    require(type(receipt["record_count"]) is int and receipt["record_count"] >= len(result["records"]),
            "clinical_umls_attestation_count_invalid")
    completed = receipt["completed_at_utc"]
    require(isinstance(completed, str) and
            re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", completed) is not None,
            "clinical_umls_attestation_time_invalid")
    try:
        datetime.strptime(completed, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        raise ContractError("clinical_umls_attestation_time_invalid") from None
    return deepcopy(receipt)


def source_provenance(result: dict) -> list[dict]:
    """Keep existing source provenance fields; never invent a retrieval timestamp."""
    supplied = result.get("provenance")
    if supplied is None:
        return []
    rows = [supplied] if isinstance(supplied, dict) else supplied
    require(isinstance(rows, list) and len(rows) <= 16 and all(isinstance(row, dict) for row in rows),
            "clinical_prepared_provenance_invalid")
    known = {"source", "acquisition", "retrieved_at", "query_digest", "record_digest", "source_role",
             "role", "source_ref", "release", "source_vocabulary", "provider", "registry_snapshot_kind"}
    projected = []
    for row in rows:
        item = {key: deepcopy(value) for key, value in row.items() if key in known}
        require(all(value is None or isinstance(value, (str, int, bool)) for value in item.values()),
                "clinical_prepared_provenance_invalid")
        require(len(canonical_bytes(item)) <= 8192, "clinical_prepared_provenance_invalid")
        projected.append(item)
    return projected


def prepare_bundle(value: Any, request: dict) -> dict:
    """Normalize admitted source-result shapes into evidence windows and lineage.

    This deliberately does not execute a source adapter, infer a new trial ID,
    certify a source's deployment, or turn a terminology match into evidence.
    """
    if value is None:
        return {"status": "not_supplied", "bundle_id": None, "bundle_digest": None,
            "evidence": [], "terminology": [], "sources": [], "issues": [], "omissions": []}
    bundle = validate_bundle(value, request)
    collector = _Collector(request)
    publication_metadata = _publication_index(bundle["sources"])
    sources, terminology = [], []
    # Stable ordering also makes primary/equivalent source receipts reproducible
    # when a governed orchestrator submits lookup operations in either order.
    for entry in sorted(bundle["sources"], key=lambda row: row["source_result_id"]):
        summary = {"source_result_id": entry["source_result_id"],
            "source_asset": entry["asset_key"] + "@" + entry["asset_version"],
            "operation": entry["result"]["operation"], "purpose": entry["purpose"],
            "result_digest": entry["result_digest"], "source_status": entry["result"]["status"],
            "execution_ref": entry.get("execution_ref"), "discovery_candidates": [],
            "observations": [], "coverage": {}, "source_provenance": source_provenance(entry["result"])}
        if entry["asset_key"] == "nusaibah.clinical_trials_lookup":
            _trial(entry, collector, summary)
        elif entry["asset_key"] == "nusaibah.pubmed_evidence":
            _pubmed(entry, collector, publication_metadata, summary)
        else:
            terminology.extend(_terminology(entry, summary))
        sources.append(summary)
    shared = collector.receipt_groups()
    # This receipt must exactly represent the final serialized evidence rows.
    # Shared receipt links have a separate compact index, not a hidden mutation.
    require(collector.byte_count == sum(len(canonical_bytes(row)) for row in collector.windows),
            "clinical_retained_evidence_budget_mismatch")
    bundle_bytes=len(canonical_bytes(bundle))
    warnings=([{'code':'clinical_source_bundle_size_warning','size_bytes':bundle_bytes,
                'warning_threshold_bytes':MAX_BUNDLE_BYTES}] if bundle_bytes>MAX_BUNDLE_BYTES else [])
    return {"status": "partial" if collector.omissions else "normalized",
        "bundle_id": bundle["bundle_id"], "bundle_digest": digest(bundle),
        "evidence": collector.windows, "terminology": terminology, "sources": sources,
        "issues": warnings, "omissions": collector.omissions,
        "equivalent_source_receipt_groups": shared,
        "coverage_receipt": {
            "retained_windows": len(collector.windows),
            "omitted_windows": len(collector.omissions),
            "duplicate_native_windows": collector.duplicate_windows,
            "deferred_duplicate_receipt_windows": sum(x["deferred_windows"] for x in shared),
            "retained_evidence_bytes": collector.byte_count,
            "source_result_count": len(bundle["sources"]),
        },
        "authority": "binding_preparation_required_not_proven_by_digest"}
