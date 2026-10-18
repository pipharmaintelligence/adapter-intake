"""Consume prepared source-adapter results without calling or importing those adapters.

The optional ``clinical_evidence`` role is binding-owned. Its digest checks are
integrity checks, not signatures or admission. Assets/Core must independently
prepare the authorized handoff. Source retrieval, provider calls and writes are
not performed by this module.
"""
from __future__ import annotations

from calendar import monthrange
from collections import deque
from copy import deepcopy
from datetime import date
import re
from typing import Any, Iterator

if __package__:
    from .contracts import (ContractError, canonical_bytes, digest, identifier,
        identifiers, iso_date, object_fields, require, safe_json, text, text_digest)
else:
    from contracts import (ContractError, canonical_bytes, digest, identifier,
        identifiers, iso_date, object_fields, require, safe_json, text, text_digest)

BUNDLE_SCHEMA = "clinical_evidence_bundle.v1"
SOURCE_CONTRACTS = {
    "nusaibah.clinical_trials_lookup": (("0.1.0", "0.1.1"), "trial_result", "clinical_trials_lookup.v1"),
    "nusaibah.pubmed_evidence": (("0.1.0",), "literature_result", "pubmed_evidence.v1"),
    "umls_terminology": (("0.1.0",), "terminology_result", None),
}
BUNDLE_WARNING_BYTES = 2 * 1024 * 1024
MAX_SOURCE_RESULTS = 24
MAX_RECORDS = 50
EVIDENCE_WARNING_BYTES = 2 * 1024 * 1024
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
        versions, role, schema = SOURCE_CONTRACTS[asset]
        require(source["asset_version"] in versions and source["output_role"] == role,
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
        self._seen: set[str] = set()

    def add(self, entry: dict, source_id: str, content: Any, pointer: str, *, source_type: str,
            extent: str, trial_ids: list[str], interval: dict, use: str,
            identifiers_value: dict, integrity: str = "not_assessed") -> None:
        for field_pointer, raw_text, omitted in source_windows(content, pointer):
            if omitted:
                self.omissions.append({"source_result_id": entry["source_result_id"], **omitted})
                continue
            assert raw_text is not None
            content_hash = text_digest(raw_text)
            identity = digest([source_id, field_pointer, content_hash, entry["purpose"],
                               entry["result_digest"], interval, use, integrity])
            if identity in self._seen:
                continue
            self._seen.add(identity)
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
                "source_version": entry["result_digest"],
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
            self.windows.append(window)
            self.byte_count += size


def evidence_priority(row: dict) -> int:
    """Spend model attention on outcomes/safety before administrative metadata."""
    context = row.get("source_context") or {}
    use = context.get("evidence_use")
    pointer = context.get("source_pointer", "")
    if not isinstance(pointer, str):
        pointer = ""
    if use in {"posted_results", "publication_text"}:
        return 0
    if use == "safety_results":
        return 1
    if "contactsLocationsModule" in pointer:
        return 9
    if use == "result_context" or any(name in pointer for name in
            ("armsInterventionsModule", "outcomesModule", "statusModule", "designModule")):
        return 2
    return 3


def prioritize_evidence(rows: list[dict]) -> list[dict]:
    """Interleave endpoint and safety evidence before lower-priority metadata."""
    buckets = {key: deque() for key in ("posted_results", "safety_results", "publication_text")}
    other = []
    for row in rows:
        use = (row.get("source_context") or {}).get("evidence_use")
        if use in buckets:
            buckets[use].append(row)
        else:
            other.append(row)
    ordered = []
    while any(buckets.values()):
        for bucket in buckets.values():
            if bucket:
                ordered.append(bucket.popleft())
    return ordered + sorted(other, key=evidence_priority)


def _validate_trial_references(row: dict) -> None:
    """Resolve only local JSON Pointers and verify their exact native content."""
    if "results_reference_schema" not in row:
        return
    require(row["results_reference_schema"] == "clinical_trials_results_refs.v1",
            "clinical_trial_reference_schema_invalid")
    groups = row.get("results_group_module_refs")
    require(isinstance(groups, dict) and all(isinstance(fields, dict) for fields in groups.values()),
            "clinical_trial_result_reference_invalid")
    references = [(ref, "/registry_study/resultsSection/" + _pointer(module) + "/" + _pointer(field))
                  for module, fields in groups.items() for field, ref in fields.items()]
    if row.get("results_outcome_measures_ref") is not None:
        references.append((row["results_outcome_measures_ref"],
                           "/registry_study/resultsSection/outcomeMeasuresModule/outcomeMeasures"))
    for ref, expected in references:
        object_fields(ref, {"json_pointer", "content_digest"})
        pointer = ref["json_pointer"]
        require(isinstance(pointer, str) and pointer == expected,
                "clinical_trial_result_reference_invalid")
        value = row
        for token in pointer[1:].split("/"):
            # Strict RFC 6901 tokens; an external address is never interpreted.
            require(re.search(r"~(?![01])", token) is None, "clinical_trial_result_reference_invalid")
            token = token.replace("~1", "/").replace("~0", "~")
            require(isinstance(value, dict) and token in value, "clinical_trial_result_reference_invalid")
            value = value[token]
        require(isinstance(value, list) and ref["content_digest"] == digest(value),
                "clinical_trial_result_reference_invalid")


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
        _validate_trial_references(row)
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
        base_id = "ctgov:" + nct
        identifiers_value = {"nct_id": nct}
        def add(value: Any, pointer: str, use: str) -> None:
            collector.add(entry, base_id, value, pointer, source_type="trial_registry",
                extent="registry_record", trial_ids=[nct], interval=interval,
                use=use, identifiers_value=identifiers_value)
        if study:
            protocol = study.get("protocolSection", {})
            results = study.get("resultsSection", {})
            require(isinstance(protocol, dict) and isinstance(results, dict), "clinical_trial_modules_invalid")
            identification = protocol.get("identificationModule") or {}
            require(isinstance(identification, dict), "clinical_trial_modules_invalid")
            nested_id = identification.get("nctId")
            require(nested_id is None or nested_id == nct, "clinical_trial_case_identity_mismatch")
            for name in sorted(results):
                require(isinstance(results[name], dict), "clinical_trial_results_module_invalid")
                use = ("safety_results" if name == "adverseEventsModule" else
                       "posted_results" if name == "outcomeMeasuresModule" else "result_context")
                add(results[name], "/registry_study/resultsSection/" + _pointer(name), use)
            for name in sorted(protocol):
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
            "mapping_status": "candidate", "clinical_equivalence_verified": False,
            "may_support_outcome": False, "license_status": "not_attested"})
    return candidates


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
    for entry in bundle["sources"]:
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
    issues = []
    for code, size, threshold in (
            ("clinical_source_bundle_size_warning", len(canonical_bytes(bundle)), BUNDLE_WARNING_BYTES),
            ("clinical_prepared_evidence_size_warning", collector.byte_count, EVIDENCE_WARNING_BYTES)):
        if size > threshold:
            issues.append({"code": code, "bytes": size, "warning_threshold_bytes": threshold,
                           "action": "preserved_complete"})
    return {"status": "partial" if collector.omissions else "normalized",
        "bundle_id": bundle["bundle_id"], "bundle_digest": digest(bundle),
        "evidence": prioritize_evidence(collector.windows), "terminology": terminology, "sources": sources,
        "issues": issues, "omissions": collector.omissions,
        "authority": "binding_preparation_required_not_proven_by_digest"}
