"""Bounded PubMed literature reads through governed Runtime Source roles.

This module owns semantic validation, provenance and normalized evidence views.
The trusted worker exclusively owns the external request and access policy.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import date, datetime
from typing import Any, Mapping

from adapters.base import Adapter


ASSET_KEY = "nusaibah.pubmed_evidence"
SCHEMA_VERSION = "pubmed_evidence.v1"
SEARCH_ROLE = "pubmed_search_runtime"
SUMMARY_ROLE = "pubmed_summary_runtime"
ABSTRACT_ROLE = "pubmed_abstract_runtime"
LINK_ROLE = "pubmed_link_runtime"
IDENTITY_ROLE = "pmc_identity_runtime"
INFO_ROLE = "pubmed_info_runtime"
OPERATIONS = (
    "describe", "database_info", "article_search", "advanced_search",
    "article_count", "trial_publications", "article_get", "article_batch",
    "abstract_get", "publication_profile", "publication_history", "integrity_get",
    "identifier_resolve", "related_articles", "citation_links",
    "cross_database_links", "export_citations",
)
SEARCH_OPERATIONS = {"article_search", "advanced_search", "article_count", "trial_publications"}
SUMMARY_OPERATIONS = {"article_get", "article_batch", "publication_profile", "publication_history", "integrity_get", "export_citations"}
LINK_OPERATIONS = {"related_articles", "citation_links", "cross_database_links"}
MAX_PAGE_SIZE = 40
MAX_BATCH_IDS = 20
MAX_TEXT_CHARS = 12_000
MAX_OUTPUT_BYTES = 230_000
MAX_ES_SEARCH_WINDOW = 10_000
PMID_RE = re.compile(r"^[1-9][0-9]{0,11}$")
NCT_RE = re.compile(r"^NCT[0-9]{8}$", re.IGNORECASE)
PMCID_RE = re.compile(r"^PMC[0-9]{1,12}(?:\.[1-9][0-9]*)?$", re.IGNORECASE)
DOI_RE = re.compile(r"^10\.[0-9]{4,9}/[-._;()/:A-Za-z0-9]+$", re.IGNORECASE)
NCT_IN_TEXT = re.compile(r"\bNCT[0-9]{8}\b", re.IGNORECASE)
SAFE_TEXT = re.compile(r"^[\w\s .,:@()+\-/\[\]'\"*]+$", re.UNICODE)
DENIED_FRAGMENTS = ("https:", "http:", "file:", "<script", "bearer ", "basic ", "-----begin")
SEARCH_FIELDS = {
    "text": None,
    "drug": "Title/Abstract",
    "condition": "Title/Abstract",
    "outcome": "Title/Abstract",
    "author": "Author",
    "journal": "Journal",
    "mesh": "MeSH Terms",
    "publication_type": "Publication Type",
    "language": "Language",
    "nct_id": "All Fields",
}
SEARCH_KEYS = set(SEARCH_FIELDS) | {
    "operation", "aliases", "published_from", "published_to", "updated_from",
    "updated_to", "page_size", "offset", "sort", "view", "as_of_date", "advanced_query",
}
LINK_NAMES = {
    "related": "pubmed_pubmed",
    "cited_by": "pubmed_pubmed_citedin",
    "references": "pubmed_pubmed_refs",
    "pmc": "pubmed_pmc",
    "gene": "pubmed_gene",
    "clinvar": "pubmed_clinvar",
    "gds": "pubmed_gds",
}
SIGNAL_TYPES = (
    "Retracted Publication", "Retraction of Publication", "Published Erratum",
    "Expression of Concern", "Corrected and Republished Article",
    "Duplicate Publication",
)


class PubMedEvidenceAdapter(Adapter):
    """Return observed biomedical publication evidence without adjudicating it."""

    key = ASSET_KEY
    version = "0.1.0"

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Execute one bounded semantic operation through declared source roles."""
        if not isinstance(inputs, dict) or not isinstance(context, dict):
            raise ValueError("pubmed_input_envelope_invalid")
        variables = inputs.get("variables", {})
        if not isinstance(variables, dict):
            raise ValueError("pubmed_variables_invalid")
        operation = variables.get("operation")
        if operation is None:
            if not variables:
                operation = "describe"
            elif "pmids" in variables:
                operation = "article_batch"
            elif "pmid" in variables:
                operation = "article_get"
            else:
                operation = "article_search"
        if not isinstance(operation, str) or operation not in OPERATIONS:
            raise ValueError("pubmed_operation_invalid")

        if operation == "describe":
            _only(variables, {"operation"})
            result = _result(operation, [], [], {"known_limitations": [
                "Source access and execution admission are separate release gates.",
                "PubMed indexing and abstracts do not establish clinical causality.",
                "Full text and some citation services have separate source policies.",
            ], "operations": list(OPERATIONS), "source_execution": "governed_only"})
        elif operation == "database_info":
            _only(variables, {"operation"})
            result = _database_info(inputs)
        elif operation in SEARCH_OPERATIONS:
            _only(variables, SEARCH_KEYS)
            result = _search(inputs, variables, operation)
        elif operation in SUMMARY_OPERATIONS:
            allowed = {"operation", "view", "as_of_date", "pmids"} if operation in {"article_batch", "export_citations"} else {"operation", "view", "as_of_date", "pmid"}
            _only(variables, allowed)
            result = _summary(inputs, variables, operation)
        elif operation == "abstract_get":
            _only(variables, {"operation", "pmid", "as_of_date"})
            result = _abstract(inputs, variables)
        elif operation == "identifier_resolve":
            _only(variables, {"operation", "pmid", "pmcid", "doi"})
            result = _identity(inputs, variables)
        else:
            _only(variables, {"operation", "pmid", "relationship"})
            result = _links(inputs, variables, operation)

        _bound(result)
        return {"outputs": {"literature_result": result}, "metrics": {
            "record_count": result.get("record_count", 0),
            "runtime_fetches": 0 if operation == "describe" else 1,
        }}


def _search(inputs: dict[str, Any], variables: dict[str, Any], operation: str) -> dict[str, Any]:
    page_size = _positive(variables.get("page_size", 10), "pubmed_page_size_invalid", MAX_PAGE_SIZE)
    offset = _offset(variables.get("offset", 0), page_size)
    as_of = _date(variables.get("as_of_date"), "pubmed_as_of_date_invalid")
    term_parts: list[str] = []
    for name, field in SEARCH_FIELDS.items():
        if name not in variables:
            continue
        if name == "nct_id":
            item = _nct(variables[name])
        else:
            item = _text(variables[name], name, 400)
        if field is None:
            term_parts.append(item)
        else:
            term_parts.append(f"({item})[{field}]")
    if "aliases" in variables:
        aliases = _strings(variables["aliases"], "aliases", 8, 100)
        if not aliases:
            raise ValueError("pubmed_aliases_invalid")
        term_parts.append("(" + " OR ".join(f"({a})[Title/Abstract]" for a in aliases) + ")")
    advanced = variables.get("advanced_query")
    if advanced is not None:
        if operation != "advanced_search":
            raise ValueError("pubmed_advanced_query_operation_required")
        term_parts.append(_text(advanced, "advanced_query", 500))
    if operation == "trial_publications" and "nct_id" not in variables:
        raise ValueError("pubmed_nct_id_required")
    if not term_parts:
        raise ValueError("pubmed_search_selector_required")
    parameters: dict[str, Any] = {
        "term": " AND ".join(term_parts),
        "retmax": 0 if operation == "article_count" else page_size,
        "retstart": offset,
        "retmode": "json",
    }
    if "sort" in variables:
        value = variables["sort"]
        if value not in {"relevance", "pub_date", "most_recent", "first_author", "journal"}:
            raise ValueError("pubmed_sort_invalid")
        parameters["sort"] = value
    for prefix, flag in (("published", "pdat"), ("updated", "edat")):
        start = _date(variables.get(f"{prefix}_from"), "pubmed_date_invalid")
        end = _date(variables.get(f"{prefix}_to"), "pubmed_date_invalid")
        if start is not None or end is not None:
            if start is None or end is None or start > end:
                raise ValueError("pubmed_date_range_invalid")
            if "datetype" in parameters:
                raise ValueError("pubmed_date_type_conflict")
            parameters.update({"datetype": flag, "mindate": start, "maxdate": end})
    source = _source(inputs, SEARCH_ROLE, parameters)
    page = _one_root(source, "esearchresult", "pubmed_search_root_invalid")
    count = _nonnegative(page.get("count"), "pubmed_search_count_invalid")
    ids = page.get("idlist")
    if not isinstance(ids, list):
        raise ValueError("pubmed_search_ids_invalid")
    pmids = [_pmid(item) for item in ids]
    if len(pmids) != len(set(pmids)) or len(pmids) > page_size:
        raise ValueError("pubmed_search_ids_invalid")
    source_start = _nonnegative(page.get("retstart", offset), "pubmed_search_offset_invalid")
    if source_start != offset:
        raise ValueError("pubmed_search_offset_mismatch")
    actual = _nonnegative(page.get("retmax", page_size), "pubmed_page_size_invalid")
    if actual > MAX_PAGE_SIZE:
        raise ValueError("pubmed_page_size_invalid")
    if actual > page_size or len(pmids) > actual:
        raise ValueError("pubmed_search_page_mismatch")
    if operation == "article_count" and pmids:
        raise ValueError("pubmed_count_should_have_no_records")
    records = [] if operation == "article_count" else [
        {"pmid": item, "relation": "candidate_nct_search" if operation == "trial_publications" else "search_match",
         "evidence_level": "discovery_only"} for item in pmids
    ]
    window_count = min(count, MAX_ES_SEARCH_WINDOW)
    coverage = {"reported_count": count, "returned_count": len(pmids),
                "offset": offset, "page_size": page_size, "accessible_id_window": MAX_ES_SEARCH_WINDOW,
                "has_more": operation != "article_count" and offset + len(pmids) < window_count,
                "retrieval_incomplete": count > MAX_ES_SEARCH_WINDOW or offset + len(pmids) < count}
    extras: dict[str, Any] = {"coverage": coverage, "query_translation": _optional_text(page.get("querytranslation"), 4000),
                              "as_of_date": as_of, "publication_evidence": "not_inspected"}
    if count > 0:
        extras["status"] = "completed"
    return _result(operation, records, [(SEARCH_ROLE, source)], extras)


def _summary(inputs: dict[str, Any], variables: dict[str, Any], operation: str) -> dict[str, Any]:
    if operation in {"article_batch", "export_citations"}:
        ids = _pmids(variables.get("pmids"))
    else:
        ids = [_pmid(variables.get("pmid"))]
    view = _view(variables.get("view", "summary"))
    as_of = _date(variables.get("as_of_date"), "pubmed_as_of_date_invalid")
    source = _source(inputs, SUMMARY_ROLE, {"id": ",".join(ids), "retmode": "json", "version": "2.0"})
    root = _one_root(source, "result", "pubmed_summary_root_invalid")
    uids = root.get("uids")
    if not isinstance(uids, list):
        raise ValueError("pubmed_summary_uids_invalid")
    returned_ids = [_pmid(item) for item in uids]
    if len(set(returned_ids)) != len(returned_ids) or set(returned_ids) - set(ids):
        raise ValueError("pubmed_summary_identity_mismatch")
    records: list[dict[str, Any]] = []
    for pmid in returned_ids:
        obj = root.get(pmid)
        if not isinstance(obj, dict) or str(obj.get("uid", pmid)) != pmid:
            raise ValueError("pubmed_summary_record_invalid")
        record = _publication(obj, pmid, as_of, view)
        if operation == "publication_profile":
            record = {k: record[k] for k in ("pmid", "doi", "pmcid", "title", "authors", "journal",
                "publication_types", "mesh_terms", "source_digest", "temporal_status")}
        elif operation == "publication_history":
            record = {k: record[k] for k in ("pmid", "publication_dates", "temporal_status", "source_digest")}
        elif operation == "integrity_get":
            record = {k: record[k] for k in ("pmid", "publication_types", "integrity_signals", "integrity_state", "source_digest")}
        elif operation == "export_citations":
            record = {"pmid": pmid, "citation": _citation(record), "source_digest": record["source_digest"]}
        records.append(record)
    if operation != "article_batch" and operation != "export_citations" and len(records) > 1:
        raise ValueError("pubmed_summary_identity_mismatch")
    return _result(operation, records, [(SUMMARY_ROLE, source)], {"requested_ids": ids,
        "returned_ids": returned_ids, "missing_ids": [item for item in ids if item not in returned_ids],
        "as_of_date": as_of})


def _abstract(inputs: dict[str, Any], variables: dict[str, Any]) -> dict[str, Any]:
    pmid = _pmid(variables.get("pmid"))
    as_of = _date(variables.get("as_of_date"), "pubmed_as_of_date_invalid")
    source = _source(inputs, ABSTRACT_ROLE, {"pmid": pmid})
    root = _one_root(source, None, "pubmed_abstract_root_invalid")
    documents = root.get("documents")
    if not isinstance(documents, list):
        raise ValueError("pubmed_abstract_documents_invalid")
    if len(documents) > 1:
        raise ValueError("pubmed_abstract_identity_mismatch")
    records: list[dict[str, Any]] = []
    for doc in documents:
        if not isinstance(doc, dict) or _pmid(doc.get("id")) != pmid:
            raise ValueError("pubmed_abstract_identity_mismatch")
        passages = doc.get("passages", [])
        if not isinstance(passages, list):
            raise ValueError("pubmed_abstract_passages_invalid")
        sections: list[dict[str, Any]] = []
        for passage in passages:
            if not isinstance(passage, dict):
                raise ValueError("pubmed_abstract_passages_invalid")
            text = passage.get("text")
            if text is None or text == "":
                continue
            if not isinstance(text, str) or len(text) > MAX_TEXT_CHARS:
                raise ValueError("pubmed_text_length_invalid")
            metadata = passage.get("infons")
            if metadata is not None and not isinstance(metadata, dict):
                raise ValueError("pubmed_abstract_passages_invalid")
            offset = passage.get("offset")
            if offset is not None and (type(offset) is not int or offset < 0):
                raise ValueError("pubmed_abstract_offset_invalid")
            sections.append({"section": _optional_text((metadata or {}).get("section_type"), 120),
                "offset": offset, "text": text, "text_digest": _digest(text)})
        combined = "\n".join(s["text"] for s in sections)
        if len(combined) > MAX_TEXT_CHARS:
            raise ValueError("pubmed_text_length_invalid")
        records.append({"pmid": pmid, "accessible_extent": "abstract" if sections else "metadata_only",
            "sections": sections, "text_digest": _digest(combined) if sections else None,
            "published_on": None, "temporal_status": "unqualified_without_publication_date",
            "as_of_date": as_of})
    return _result("abstract_get", records, [(ABSTRACT_ROLE, source)],
        {"text_extent": "abstract_only", "publication_date_requires_summary": True})


def _identity(inputs: dict[str, Any], variables: dict[str, Any]) -> dict[str, Any]:
    provided = [k for k in ("pmid", "pmcid", "doi") if k in variables]
    if len(provided) != 1:
        raise ValueError("pubmed_identifier_selector_invalid")
    kind = provided[0]
    value = _pmid(variables[kind]) if kind == "pmid" else _pmcid(variables[kind]) if kind == "pmcid" else _doi(variables[kind])
    source = _source(inputs, IDENTITY_ROLE, {"ids": value, "format": "json"})
    root = _one_root(source, None, "pubmed_identity_root_invalid")
    records_data = root.get("records")
    if not isinstance(records_data, list) or len(records_data) > 1:
        raise ValueError("pubmed_identity_records_invalid")
    records = []
    for item in records_data:
        if not isinstance(item, dict):
            raise ValueError("pubmed_identity_records_invalid")
        requested = item.get("requested-id", value)
        if not isinstance(requested, str) or requested.casefold() != value.casefold():
            raise ValueError("pubmed_identity_mismatch")
        record = {"requested_id": value, "requested_kind": kind,
            "pmid": _pmid(item["pmid"]) if item.get("pmid") else None,
            "pmcid": _pmcid(item["pmcid"]) if item.get("pmcid") else None,
            "doi": _doi(item["doi"]) if item.get("doi") else None,
            "version_info": _safe_array(item.get("versions"), 20),
            "pmc_availability": item.get("live") if type(item.get("live")) is bool else None,
            "source_digest": _digest(item)}
        records.append(record)
    return _result("identifier_resolve", records, [(IDENTITY_ROLE, source)],
        {"coverage_note": "PMC-linked records only; absence does not mean no PubMed article"})


def _links(inputs: dict[str, Any], variables: dict[str, Any], operation: str) -> dict[str, Any]:
    pmid = _pmid(variables.get("pmid"))
    default = "related" if operation == "related_articles" else "cited_by" if operation == "citation_links" else "pmc"
    relation = variables.get("relationship", default)
    permitted = {"related"} if operation == "related_articles" else {"cited_by", "references"} if operation == "citation_links" else {"pmc", "gene", "clinvar", "gds"}
    if relation not in permitted:
        raise ValueError("pubmed_link_relation_invalid")
    source = _source(inputs, LINK_ROLE, {"id": pmid, "linkname": LINK_NAMES[relation], "retmode": "json"})
    root = _one_root(source, None, "pubmed_link_root_invalid")
    links = root.get("linksets")
    if not isinstance(links, list):
        raise ValueError("pubmed_linksets_invalid")
    records: list[dict[str, Any]] = []
    for block in links:
        if not isinstance(block, dict) or block.get("ids") != [pmid]:
            raise ValueError("pubmed_link_identity_mismatch")
        groups = block.get("linksetdbs", [])
        if not isinstance(groups, list):
            raise ValueError("pubmed_linksets_invalid")
        for group in groups:
            if not isinstance(group, dict) or group.get("linkname") != LINK_NAMES[relation]:
                raise ValueError("pubmed_link_relation_mismatch")
            matches = group.get("links", [])
            if not isinstance(matches, list) or len(matches) > 40:
                raise ValueError("pubmed_link_records_invalid")
            ids = []
            for item in matches:
                value = str(item)
                if not value.isdigit() or len(value) > 12:
                    raise ValueError("pubmed_link_records_invalid")
                ids.append(value)
            records.append({"pmid": pmid, "relation": relation,
                "linkname": LINK_NAMES[relation], "target_database": _optional_text(group.get("dbto"), 60),
                "linked_ids": ids, "meaning": "source_reported_link_not_clinical_causation"})
    return _result(operation, records, [(LINK_ROLE, source)], {"queried_pmid": pmid, "relationship": relation})


def _database_info(inputs: dict[str, Any]) -> dict[str, Any]:
    source = _source(inputs, INFO_ROLE, {})
    root = _one_root(source, "einforesult", "pubmed_info_root_invalid")
    info = root.get("dbinfo")
    if not isinstance(info, dict) or info.get("db") != "pubmed":
        raise ValueError("pubmed_info_invalid")
    record = {"database": "pubmed", "count": info.get("count"),
        "last_update": _optional_text(info.get("lastupdate"), 60),
        "fields": _safe_array(info.get("fieldlist"), 150),
        "links": _safe_array(info.get("linklist"), 150),
        "source_digest": _digest(info)}
    return _result("database_info", [record], [(INFO_ROLE, source)], {})


def _publication(data: dict[str, Any], pmid: str, as_of: str | None, view: str) -> dict[str, Any]:
    title = _optional_text(data.get("title"), 4000)
    journal = _optional_text(data.get("fulljournalname") or data.get("source"), 2000)
    ids = data.get("articleids", [])
    if not isinstance(ids, list):
        raise ValueError("pubmed_article_identifiers_invalid")
    identifiers: dict[str, str] = {}
    for item in ids:
        if isinstance(item, dict) and isinstance(item.get("idtype"), str) and isinstance(item.get("value"), str):
            tag = item["idtype"].lower()
            if tag in {"doi", "pmc", "pmcid", "pubmed"}:
                identifiers[tag] = item["value"]
    raw_pubtypes = data.get("pubtype", [])
    if not isinstance(raw_pubtypes, list):
        raise ValueError("pubmed_publication_types_invalid")
    types = [_optional_text(value, 180) for value in raw_pubtypes]
    if any(value is None for value in types):
        raise ValueError("pubmed_publication_types_invalid")
    authors = data.get("authors", [])
    if not isinstance(authors, list) or len(authors) > 300:
        raise ValueError("pubmed_authors_invalid")
    names = [_optional_text(a.get("name"), 250) for a in authors if isinstance(a, dict)]
    dates = _publication_dates(data)
    available_date = dates["pubdate"]
    temporal = "not_assessed" if as_of is None else "unqualified_missing_or_partial_date"
    if as_of is not None and available_date["precision"] == "day":
        temporal = "eligible_by_publication_date" if available_date["iso"] <= as_of else "after_cutoff"
    signals = [value for value in types if value is not None and any(flag.casefold() == value.casefold() for flag in SIGNAL_TYPES)]
    signal_state = "notice_reported" if signals else "unknown_from_summary_only"
    record: dict[str, Any] = {
        "pmid": pmid, "doi": identifiers.get("doi"), "pmcid": identifiers.get("pmc") or identifiers.get("pmcid"),
        "title": title, "journal": journal, "authors": names,
        "publication_types": types, "mesh_terms": _safe_array(data.get("meshheadinglist"), 200),
        "publication_dates": dates, "temporal_status": temporal,
        "integrity_signals": signals, "integrity_state": signal_state,
        "article_ids": identifiers, "article_extent": "metadata_only",
        "nct_ids_in_record": sorted({x.upper() for x in NCT_IN_TEXT.findall(json.dumps(data, ensure_ascii=False))}),
        "source_digest": _digest(data),
    }
    if view == "research":
        record["source_record"] = copy.deepcopy(data)
    return record


def _publication_dates(data: Mapping[str, Any]) -> dict[str, dict[str, str | None]]:
    return {"pubdate": _date_parts(data.get("pubdate")),
            "epubdate": _date_parts(data.get("epubdate")),
            "sortpubdate": _date_parts(data.get("sortpubdate"))}


def _date_parts(value: Any) -> dict[str, str | None]:
    text = _optional_text(value, 80)
    result: dict[str, str | None] = {"reported": text, "iso": None, "precision": "unknown"}
    if text is None:
        return result
    for fmt, precision in (("%Y %b %d", "day"), ("%Y %B %d", "day"), ("%Y-%m-%d", "day"),
                           ("%Y %b", "month"), ("%Y %B", "month"), ("%Y", "year")):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        result["precision"] = precision
        result["iso"] = parsed.date().isoformat() if precision == "day" else parsed.strftime("%Y-%m") if precision == "month" else parsed.strftime("%Y")
        break
    return result


def _citation(record: dict[str, Any]) -> str:
    names = ", ".join(n for n in record["authors"][:5] if n)
    year = record["publication_dates"]["pubdate"]["reported"] or "date not reported"
    return f"{names}. {record['title'] or 'Untitled'}. {record['journal'] or 'Journal unknown'}. {year}. PMID {record['pmid']}."


def _source(inputs: dict[str, Any], role: str, params: dict[str, Any]) -> dict[str, Any]:
    if role not in inputs or not callable(getattr(inputs, "invoke", None)):
        raise ValueError("pubmed_source_not_admitted")
    for item in params.values():
        if item is not None and (isinstance(item, bool) or not isinstance(item, (str, int))):
            raise ValueError("pubmed_source_parameters_invalid")
    try:
        response = inputs.invoke(role, variables=params, on_error="raise")
    except Exception:
        raise ValueError("pubmed_source_failed") from None
    if not isinstance(response, dict) or not isinstance(response.get("records"), list):
        raise ValueError("pubmed_source_shape_invalid")
    if len(response["records"]) > 1:
        raise ValueError("pubmed_root_record_count_invalid")
    if "metadata" in response and not isinstance(response["metadata"], dict):
        raise ValueError("pubmed_source_metadata_invalid")
    return response


def _one_root(source: Mapping[str, Any], key: str | None, code: str) -> dict[str, Any]:
    records = source["records"]
    if not records:
        return {} if key is None else {key: {}}
    item = records[0]
    if not isinstance(item, dict):
        raise ValueError(code)
    if key is None:
        return item
    nested = item.get(key)
    if not isinstance(nested, dict):
        raise ValueError(code)
    return nested


def _result(operation: str, records: list[dict[str, Any]], sources: list[tuple[str, dict[str, Any]]],
            extras: dict[str, Any]) -> dict[str, Any]:
    source_refs = []
    for role, response in sources:
        metadata = response.get("metadata") or {}
        source_refs.append({"role": role, "retrieved_at": _optional_text(metadata.get("retrieved_at"), 90),
            "source_version": _optional_text(metadata.get("source_version"), 90),
            "record_digest": _digest(response["records"])})
    return {"schema_version": SCHEMA_VERSION, "operation": operation,
        "status": "completed" if records or operation in {"describe", "article_count"} else "no_match",
        "records": records, "record_count": len(records), "provenance": source_refs,
        **extras}


def _pmid(value: Any) -> str:
    item = str(value) if type(value) is int else value
    if not isinstance(item, str) or not PMID_RE.fullmatch(item):
        raise ValueError("pubmed_pmid_invalid")
    return item


def _pmids(value: Any) -> list[str]:
    if not isinstance(value, list) or not (1 <= len(value) <= MAX_BATCH_IDS):
        raise ValueError("pubmed_pmids_invalid")
    result = [_pmid(item) for item in value]
    if len(result) != len(set(result)):
        raise ValueError("pubmed_pmids_duplicate")
    return result


def _pmcid(value: Any) -> str:
    if not isinstance(value, str) or not PMCID_RE.fullmatch(value):
        raise ValueError("pubmed_pmcid_invalid")
    return value.upper()


def _doi(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 180 or not DOI_RE.fullmatch(value):
        raise ValueError("pubmed_doi_invalid")
    return value


def _nct(value: Any) -> str:
    if not isinstance(value, str) or not NCT_RE.fullmatch(value):
        raise ValueError("pubmed_nct_id_invalid")
    return value.upper()


def _text(value: Any, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError("pubmed_text_invalid")
    clean = value.strip()
    if (not SAFE_TEXT.fullmatch(clean) or any(item in clean.casefold() for item in DENIED_FRAGMENTS)
            or "\n" in clean or "\r" in clean or "\t" in clean):
        raise ValueError("pubmed_text_invalid")
    return clean


def _optional_text(value: Any, limit: int) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError("pubmed_source_text_invalid")
    return value


def _strings(value: Any, field: str, count: int, limit: int) -> list[str]:
    if not isinstance(value, list) or len(value) > count:
        raise ValueError("pubmed_" + field + "_invalid")
    items = [_text(item, field, limit) for item in value]
    if len(items) != len({item.casefold() for item in items}):
        raise ValueError("pubmed_" + field + "_duplicate")
    return items


def _only(values: Mapping[str, Any], allowed: set[str]) -> None:
    if any(not isinstance(item, str) or item not in allowed for item in values):
        raise ValueError("pubmed_variable_not_allowed")


def _positive(value: Any, code: str, maximum: int, *, allow_zero: bool = False) -> int:
    if type(value) is not int or value < (0 if allow_zero else 1) or value > maximum:
        raise ValueError(code)
    return value


def _nonnegative(value: Any, code: str) -> int:
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    if type(value) is not int or value < 0:
        raise ValueError(code)
    return value


def _offset(value: Any, page_size: int) -> int:
    pos = _nonnegative(value, "pubmed_offset_invalid")
    if pos + page_size > MAX_ES_SEARCH_WINDOW:
        raise ValueError("pubmed_window_exceeded")
    return pos


def _date(value: Any, code: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError(code)
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError(code) from None
    return value


def _view(value: Any) -> str:
    if value not in ("summary", "research"):
        raise ValueError("pubmed_view_invalid")
    return value


def _safe_array(value: Any, maximum: int) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError("pubmed_source_list_invalid")
    return copy.deepcopy(value)


def _digest(value: Any) -> str:
    if isinstance(value, str):
        content = value.encode("utf-8")
    else:
        try:
            content = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        except (TypeError, ValueError):
            raise ValueError("pubmed_source_serialization_invalid") from None
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _bound(result: Mapping[str, Any]) -> None:
    try:
        size = len(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError):
        raise ValueError("pubmed_result_invalid") from None
    if size > MAX_OUTPUT_BYTES:
        raise ValueError("pubmed_result_too_large")
