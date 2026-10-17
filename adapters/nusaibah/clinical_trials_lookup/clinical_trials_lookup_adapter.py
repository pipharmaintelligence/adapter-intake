"""ClinicalTrials.gov v2 study retrieval without provider-owned transport.

The trusted Runtime Source resolves declared source roles. This adapter owns
only bounded semantic parameters, NCT identity checks, curated public registry
snapshots, and truthful coverage/provenance. It does not judge registration,
scientific outcomes, product lineage, approval, or stopping causality.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import date
from typing import Any, Mapping

from adapters.base import Adapter


ASSET_KEY = "nusaibah.clinical_trials_lookup"
SCHEMA_VERSION = "clinical_trials_lookup.v1"
SEARCH_ROLE = "trials_search_runtime"
PHASE3_ROLE = "trials_phase3_runtime"
DETAIL_ROLE = "trials_detail_runtime"
OPERATIONS = ("describe", "study_search", "study_get", "study_batch", "arms_get", "outcomes_get", "results_get")
MAX_PAGE_SIZE = 50
MAX_BATCH_IDS = 50
MAX_RESULT_BYTES = 240_000
NCT_ID_RE = re.compile(r"^NCT\d{8}$")
SAFE_ENUM_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,49}$")
SAFE_CURSOR_RE = re.compile(r"^[A-Za-z0-9._~+\-=/]{1,2048}$")

SEARCH_TERMS = {
    "text": "query.term",
    "condition": "query.cond",
    "intervention": "query.intr",
    "title": "query.titles",
    "outcome": "query.outc",
    "sponsor": "query.spons",
    "lead_sponsor": "query.lead",
    "location": "query.locn",
    "study_identifier": "query.id",
    "patient_text": "query.patient",
}
SEARCH_OPTIONS = set(SEARCH_TERMS) | {
    "operation", "intervention_terms", "phase", "status", "study_type",
    "sponsor_class", "country", "updated_from", "updated_to",
    "advanced_filter", "page_size", "page_token", "sort", "count_total",
    "view", "preset",
}


class ClinicalTrialsLookupAdapter(Adapter):
    """Provide standalone study reads suitable for later research adapters."""

    key = ASSET_KEY
    version = "0.1.0"

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Run one bounded operation against previously admitted source roles.

        Args:
            inputs: Optional direct ``variables`` and source-role placeholders
                resolved by the trusted runtime. No direct API addresses or
                credentials are accepted.
            context: Opaque safe execution context, never used for transport.

        Returns:
            Standard adapter output with a single ``trial_result`` object.

        Raises:
            ValueError: Contract, identity, result-shape, or size failure.
        """
        if not isinstance(inputs, dict) or not isinstance(context, dict):
            raise ValueError("clinical_trials_input_envelope_invalid")
        variables = inputs.get("variables", {})
        if not isinstance(variables, dict):
            raise ValueError("clinical_trials_variables_invalid")
        # Direct callers may omit an operation only when its selector uniquely
        # identifies a retrieval mode. Public MCP templates still fix it.
        operation = variables.get("operation")
        if operation is None:
            if not variables:
                operation = "describe"
            elif "nct_id" in variables:
                operation = "study_get"
            elif "nct_ids" in variables:
                operation = "study_batch"
            else:
                operation = "study_search"
        if operation not in OPERATIONS:
            raise ValueError("clinical_trials_operation_invalid")

        if operation == "describe":
            _keys(variables, {"operation"})
            result = {
                "schema_version": SCHEMA_VERSION,
                "operation": operation,
                "status": "completed",
                "capabilities": list(OPERATIONS),
                "search_keys": sorted(SEARCH_OPTIONS - {"operation"}),
                "source_execution": "governed_runtime_source_only",
                "evidence_scope": "registered_study_facts_not_registration_adjudication",
            }
        elif operation == "study_search":
            _keys(variables, SEARCH_OPTIONS)
            result = _study_search(inputs, variables)
        elif operation == "study_batch":
            _keys(variables, {"operation", "nct_ids", "view", "page_token"})
            result = _study_batch(inputs, variables)
        else:
            if operation == "study_get":
                _keys(variables, {"operation", "nct_id", "view"})
            else:
                _keys(variables, {"operation", "nct_id"})
            result = _study_detail(inputs, variables, operation=operation)

        _bound(result, MAX_RESULT_BYTES, "clinical_trials_result_too_large")
        return {"outputs": {"trial_result": result}, "metrics": {
            "study_count": len(result.get("records", [])),
            "runtime_fetches": 0 if operation == "describe" else 1,
        }}


def _study_search(inputs: dict[str, Any], variables: dict[str, Any]) -> dict[str, Any]:
    """Fetch exactly one query page; never perform a provider-wide scan."""
    preset = variables.get("preset")
    if preset not in {None, "phase3_interventional"}:
        raise ValueError("clinical_trials_preset_invalid")
    if preset is not None:
        # The approved source definition owns this fixed query. Do not allow
        # Python to rewrite its advanced filter or to misrepresent its scope.
        conflicting = {"advanced_filter", "country", "updated_from", "updated_to", "sponsor_class"}
        if any(name in variables for name in conflicting):
            raise ValueError("clinical_trials_preset_filter_conflict")
        if variables.get("phase", "PHASE3") != "PHASE3" or variables.get("study_type", "INTERVENTIONAL") != "INTERVENTIONAL":
            raise ValueError("clinical_trials_preset_filter_conflict")

    params: dict[str, Any] = {}
    for user_key, source_key in SEARCH_TERMS.items():
        if user_key in variables:
            params[source_key] = _text(variables[user_key], user_key, 500)

    aliases = variables.get("intervention_terms")
    if aliases is not None:
        if not isinstance(aliases, list) or not 1 <= len(aliases) <= 8:
            raise ValueError("clinical_trials_intervention_terms_invalid")
        terms = [_text(value, "intervention_terms", 120) for value in aliases]
        if "intervention" in variables:
            terms.insert(0, params["query.intr"])
        if len({term.casefold() for term in terms}) != len(terms):
            raise ValueError("clinical_trials_intervention_terms_duplicate")
        # These are caller-declared alternatives; this tool does not infer
        # equivalence. Preserve provider Essie syntax for the governed layer.
        if any('"' in term or "\\" in term for term in terms):
            raise ValueError("clinical_trials_intervention_terms_invalid")
        params["query.intr"] = " OR ".join('"' + term + '"' for term in terms)

    advanced: list[str] = []
    for field, area in (("phase", "Phase"), ("study_type", "StudyType"),
                        ("sponsor_class", "LeadSponsorClass")):
        if field in variables and not (preset and field in {"phase", "study_type"}):
            value = _enum(variables[field], field)
            # Let the authoritative registry decide whether a future enum is
            # valid. Reject only unsafe structural values here.
            advanced.append(f"AREA[{area}]{value}")

    if "country" in variables:
        advanced.append("AREA[LocationCountry]" + _text(variables["country"], "country", 90))
    if "updated_from" in variables or "updated_to" in variables:
        first = _date_value(variables.get("updated_from"), "updated_from")
        last = _date_value(variables.get("updated_to"), "updated_to")
        if first != "MIN" and last != "MAX" and first > last:
            raise ValueError("clinical_trials_updated_range_invalid")
        advanced.append(f"AREA[LastUpdatePostDate]RANGE[{first},{last}]")

    if "advanced_filter" in variables:
        candidate = _text(variables["advanced_filter"], "advanced_filter", 600)
        if candidate.count("[") != candidate.count("]"):
            raise ValueError("clinical_trials_advanced_filter_invalid")
        advanced.append("(" + candidate + ")")
    if advanced:
        params["filter.advanced"] = " AND ".join(advanced)

    if "status" in variables:
        statuses = _enums(variables["status"], "status", 8)
        params["filter.overallStatus"] = ",".join(statuses)

    # Disallow broad default scans; each provider request needs real constraints.
    if not any(key.startswith(("query.", "filter.")) for key in params):
        raise ValueError("clinical_trials_search_selector_required")
    page_size = _page_size(variables.get("page_size", 10))
    params.update({"pageSize": page_size, "countTotal": "true" if variables.get("count_total", True) is True else "false"})
    if not isinstance(variables.get("count_total", True), bool):
        raise ValueError("clinical_trials_count_total_invalid")
    if "page_token" in variables:
        params["pageToken"] = _cursor(variables["page_token"])
    if "sort" in variables:
        params["sort"] = _sort(variables["sort"])

    view = _view(variables.get("view", "summary"))
    page = _source(inputs, PHASE3_ROLE if preset else SEARCH_ROLE, params)
    studies, pagination = _search_page(page, page_size)
    if preset:
        for study in studies:
            protocol = _mapping(study.get("protocolSection"))
            phases = _mapping(protocol.get("designModule")).get("phases")
            if (not isinstance(phases, list) or "PHASE3" not in phases
                    or _mapping(protocol.get("designModule")).get("studyType") != "INTERVENTIONAL"):
                raise ValueError("clinical_trials_preset_result_scope_mismatch")
    curated = [_study(study, view=view) for study in studies]
    return _result("study_search", curated, pagination, page, params)


def _study_batch(inputs: dict[str, Any], variables: dict[str, Any]) -> dict[str, Any]:
    """Find up to 25 explicitly requested NCT IDs in one governed page."""
    ids = _ids(variables.get("nct_ids"))
    view = _view(variables.get("view", "summary"))
    params: dict[str, Any] = {"filter.ids": ",".join(ids), "pageSize": len(ids), "countTotal": "true"}
    if "page_token" in variables:
        params["pageToken"] = _cursor(variables["page_token"])
    page = _source(inputs, SEARCH_ROLE, params)
    studies, pagination = _search_page(page, len(ids))
    curated = [_study(study, view=view) for study in studies]
    returned = {record["nct_id"] for record in curated}
    if not returned.issubset(ids):
        raise ValueError("clinical_trials_batch_unexpected_id")
    result = _result("study_batch", curated, pagination, page, params)
    result["requested_ids"] = ids
    result["returned_ids"] = sorted(returned)
    # Missing IDs can be definitive only if the response has no continuation.
    result["missing_ids"] = [value for value in ids if value not in returned] if pagination["has_more"] is False else None
    return result


def _study_detail(inputs: dict[str, Any], variables: dict[str, Any], *, operation: str) -> dict[str, Any]:
    """Fetch an exact study and expose a source-only view of its public modules."""
    nct_id = _id(variables.get("nct_id"))
    view = _view(variables.get("view", "research")) if operation == "study_get" else {
        "arms_get": "arms", "outcomes_get": "outcomes", "results_get": "results",
    }[operation]
    page = _source(inputs, DETAIL_ROLE, {"nct_id": nct_id})
    records = page["records"]
    if len(records) > 1:
        raise ValueError("clinical_trials_detail_ambiguous")
    curated = []
    if records:
        record = _study(records[0], view=view)
        if record["nct_id"] != nct_id:
            raise ValueError("clinical_trials_detail_identity_mismatch")
        curated.append(record)
    result = _result(operation, curated,
                     {"has_more": False, "next_page_token": None, "total_count": len(curated), "coverage": "exact_id"},
                     page, {"nct_id": nct_id})
    if operation == "results_get" and curated:
        original = records[0]
        if isinstance(original.get("resultsSection"), dict):
            result["results_state"] = "posted"
        elif original.get("hasResults") is False:
            result["results_state"] = "not_posted"
        else:
            result["results_state"] = "not_present_in_record"
    return result


def _source(inputs: dict[str, Any], role: str, params: dict[str, Any]) -> dict[str, Any]:
    """Invoke only a declared worker-owned Runtime Source input role."""
    invoker = getattr(inputs, "invoke", None)
    if role not in inputs or not callable(invoker):
        raise ValueError("clinical_trials_runtime_source_not_prepared")
    if not isinstance(inputs[role], dict):
        raise ValueError("clinical_trials_runtime_source_role_invalid")
    try:
        resolved = invoker(role, variables=params, on_error="raise")
    except Exception as exc:
        # These are exact safe runtime codes, not arbitrary provider text.
        known = {
            "runtime_source_dynamic_role_not_declared": "clinical_trials_source_role_unavailable",
            "runtime_source_dynamic_invocation_timed_out": "clinical_trials_source_timeout",
            "runtime_source_provider_forbidden": "clinical_trials_source_forbidden",
            "runtime_source_egress_provider_rejected": "clinical_trials_provider_rejected",
            "runtime_source_egress_records_invalid": "clinical_trials_provider_records_invalid",
        }
        reason = exc.args[0] if len(exc.args) == 1 else None
        code = known.get(reason, "clinical_trials_runtime_source_failed") if isinstance(reason, str) else "clinical_trials_runtime_source_failed"
        raise ValueError(code) from None
    if not isinstance(resolved, dict) or not isinstance(resolved.get("records"), list):
        raise ValueError("clinical_trials_runtime_source_shape_invalid")
    if any(not isinstance(item, dict) for item in resolved["records"]):
        raise ValueError("clinical_trials_runtime_source_record_invalid")
    return resolved


def _search_page(source: Mapping[str, Any], page_size: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Require a root-page envelope so nextPageToken cannot be silently lost."""
    records = source["records"]
    if len(records) != 1 or not isinstance(records[0].get("studies"), list):
        raise ValueError("clinical_trials_search_root_page_required")
    page = records[0]
    studies = page["studies"]
    if len(studies) > page_size or any(not isinstance(study, dict) for study in studies):
        raise ValueError("clinical_trials_page_records_invalid")
    continuation = page.get("nextPageToken")
    if continuation is not None:
        continuation = _cursor(continuation)
    total = page.get("totalCount")
    if total is not None and (type(total) is not int or total < 0):
        raise ValueError("clinical_trials_total_count_invalid")
    return studies, {
        "has_more": continuation is not None,
        "next_page_token": continuation,
        "total_count": total,
        "coverage": "one_page",
    }


def _study(value: dict[str, Any], *, view: str) -> dict[str, Any]:
    """Expose registry-declared arms, intervention links and reported results.

    Never infer that a protocol arm is the same as a results-analysis group.
    Full research mode preserves the source object, including future modules.
    """
    protocol = value.get("protocolSection")
    if not isinstance(protocol, dict):
        raise ValueError("clinical_trials_protocol_missing")
    identification = protocol.get("identificationModule")
    if not isinstance(identification, dict):
        raise ValueError("clinical_trials_identification_missing")
    nct_id = _id(identification.get("nctId"))
    for section in ("resultsSection", "derivedSection", "documentSection", "annotationSection"):
        if section in value and not isinstance(value[section], dict):
            raise ValueError("clinical_trials_section_invalid")
    if "hasResults" in value and value["hasResults"] is not None and type(value["hasResults"]) is not bool:
        raise ValueError("clinical_trials_results_flag_invalid")

    status = _mapping(protocol.get("statusModule"))
    design = _mapping(protocol.get("designModule"))
    sponsors = _mapping(protocol.get("sponsorCollaboratorsModule"))
    conditions = _mapping(protocol.get("conditionsModule"))
    arms = _mapping(protocol.get("armsInterventionsModule"))
    outcomes = _mapping(protocol.get("outcomesModule"))
    if "armsInterventionsModule" in protocol and not isinstance(protocol["armsInterventionsModule"], dict):
        raise ValueError("clinical_trials_arms_module_invalid")
    if "outcomesModule" in protocol and not isinstance(protocol["outcomesModule"], dict):
        raise ValueError("clinical_trials_outcomes_module_invalid")
    arm_groups = _public_objects(arms, "armGroups")
    interventions = _public_objects(arms, "interventions")
    arm_index = {item.get("label").casefold(): item for item in arm_groups
                 if isinstance(item.get("label"), str) and item["label"].strip()}
    links: list[dict[str, Any]] = []
    missing_labels: list[str] = []
    for intervention in interventions:
        for label in _public_names(intervention, "armGroupLabels"):
            arm = arm_index.get(label.casefold())
            if arm is None:
                missing_labels.append(label)
            # Only declared armGroupLabels are links; names/text alone cannot
            # establish assignment or identify a comparator.
            links.append({
                "intervention_name": intervention.get("name"),
                "intervention_type": intervention.get("type"),
                "arm_group_label": label,
                "arm_group_type": arm.get("type") if arm is not None else None,
                "link_source": "intervention.armGroupLabels",
                "arm_label_found": arm is not None,
            })

    summary = {
        "nct_id": nct_id,
        "brief_title": identification.get("briefTitle"),
        "official_title": identification.get("officialTitle"),
        "organization_study_id": _mapping(identification.get("orgStudyIdInfo")).get("id"),
        "secondary_ids": identification.get("secondaryIdInfos"),
        "overall_status": status.get("overallStatus"),
        "why_stopped": status.get("whyStopped"),
        "phases": design.get("phases"),
        "study_type": design.get("studyType"),
        "enrollment": _mapping(design.get("enrollmentInfo")).get("count"),
        "enrollment_type": _mapping(design.get("enrollmentInfo")).get("type"),
        "design_info": copy.deepcopy(design.get("designInfo")),
        "lead_sponsor": _mapping(sponsors.get("leadSponsor")).get("name"),
        "lead_sponsor_class": _mapping(sponsors.get("leadSponsor")).get("class"),
        "conditions": conditions.get("conditions"),
        "keywords": conditions.get("keywords"),
        "arm_groups": [{
            "label": item.get("label"), "type": item.get("type"),
            "description": item.get("description"),
            "intervention_names": copy.deepcopy(item.get("interventionNames")),
        } for item in arm_groups],
        "interventions": [{
            "name": item.get("name"), "type": item.get("type"),
            "description": item.get("description"),
            "other_names": copy.deepcopy(item.get("otherNames")),
            "arm_group_labels": copy.deepcopy(item.get("armGroupLabels")),
        } for item in interventions],
        "declared_arm_links": links,
        "unmatched_arm_labels": sorted(set(missing_labels)),
        "primary_outcomes": copy.deepcopy(outcomes.get("primaryOutcomes")),
        "secondary_outcomes": copy.deepcopy(outcomes.get("secondaryOutcomes")),
        "other_outcomes": copy.deepcopy(outcomes.get("otherOutcomes")),
        "is_fda_regulated_drug": _mapping(protocol.get("oversightModule")).get("isFdaRegulatedDrug"),
        "last_update_posted": _mapping(status.get("lastUpdatePostDateStruct")).get("date"),
        "primary_completion_date": _mapping(status.get("primaryCompletionDateStruct")).get("date"),
        "has_results": value.get("hasResults"),
    }
    record: dict[str, Any] = {
        "nct_id": nct_id,
        "summary": summary,
        "content_digest": "sha256:" + hashlib.sha256(_json(value)).hexdigest(),
        "registry_update_date": summary["last_update_posted"],
        "sections_available": [key for key in ("protocolSection", "resultsSection", "derivedSection", "documentSection", "annotationSection") if key in value],
    }
    if view == "research":
        # Preserve every original public section/module, not only the initial
        # whitelist. This is source evidence, not interpreted registration data.
        record["registry_study"] = copy.deepcopy(value)
    elif view in {"arms", "outcomes"}:
        module = "armsInterventionsModule" if view == "arms" else "outcomesModule"
        record["registry_study"] = {"protocolSection": {
            "identificationModule": copy.deepcopy(identification),
            module: copy.deepcopy(protocol.get(module, {})),
        }}
    elif view == "results":
        record["registry_study"] = {
            "protocolSection": {"identificationModule": copy.deepcopy(identification)},
            **({"resultsSection": copy.deepcopy(value["resultsSection"])} if "resultsSection" in value else {}),
            **({"hasResults": value["hasResults"]} if "hasResults" in value else {}),
        }
        # Results groups are analysis/reporting group definitions, distinct
        # from the protocol's randomized armGroups. Keep them source-native.
        results = _mapping(value.get("resultsSection"))
        record["results_group_modules"] = {
            module: {
                field: copy.deepcopy(entries)
                for field, entries in detail.items()
                if isinstance(field, str) and (field == "groups" or field.endswith("Groups"))
                   and isinstance(entries, list)
            }
            for module, detail in results.items() if isinstance(detail, dict)
        }
        record["results_outcome_measures"] = copy.deepcopy(
            _mapping(results.get("outcomeMeasuresModule")).get("outcomeMeasures", [])
        )
    return record


def _public_objects(container: Mapping[str, Any], field: str) -> list[dict[str, Any]]:
    """Read optional provider lists without pretending malformed data is empty."""
    values = container.get(field, [])
    if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
        raise ValueError("clinical_trials_registry_list_invalid")
    return values


def _public_names(container: Mapping[str, Any], field: str) -> list[str]:
    """Preserve declared names as strings; absent relationships are not errors."""
    values = container.get(field, [])
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        raise ValueError("clinical_trials_registry_names_invalid")
    return values

def _result(operation: str, records: list[dict[str, Any]], pagination: dict[str, Any],
            source: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
    """Build a source-safe output without echoing raw provider transport."""
    ids = [record["nct_id"] for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("clinical_trials_duplicate_nct_id")
    metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
    retrieved_at = metadata.get("retrieved_at")
    if retrieved_at is not None and (not isinstance(retrieved_at, str) or len(retrieved_at) > 64):
        retrieved_at = None
    return {
        "schema_version": SCHEMA_VERSION,
        "operation": operation,
        "status": "completed" if records or pagination.get("has_more") is True else "no_match",
        "records": records,
        "record_count": len(records),
        "pagination": pagination,
        "provenance": {
            "source": "clinicaltrials_gov_api_v2",
            "acquisition": "governed_runtime_source",
            "retrieved_at": retrieved_at,
            "query_digest": "sha256:" + hashlib.sha256(_json(dict(sorted(params.items())))).hexdigest(),
            "registry_snapshot_kind": "public_study_record",
        },
        "interpretation": "registry_facts_only",
    }


def _keys(value: Mapping[str, Any], allowed: set[str]) -> None:
    if not set(value).issubset(allowed):
        raise ValueError("clinical_trials_variable_not_allowed")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _id(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("clinical_trials_nct_id_invalid")
    normalized = value.strip().upper()
    if not NCT_ID_RE.fullmatch(normalized):
        raise ValueError("clinical_trials_nct_id_invalid")
    return normalized


def _ids(value: Any) -> list[str]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_BATCH_IDS:
        raise ValueError("clinical_trials_nct_ids_invalid")
    ids = [_id(item) for item in value]
    if len(ids) != len(set(ids)):
        raise ValueError("clinical_trials_nct_ids_duplicate")
    return ids


def _text(value: Any, name: str, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("clinical_trials_" + name + "_invalid")
    text = value.strip()
    if (len(text) > max_length or any(ord(c) < 32 or ord(c) == 127 for c in text)
            or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", text)
            or re.search(r"(?i)\b(?:bearer\s+|token\s*=|secret\s*=|api_key\s*=|authorization\s*:)", text)):
        raise ValueError("clinical_trials_" + name + "_invalid")
    return text


def _enum(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError("clinical_trials_" + name + "_invalid")
    normalized = value.strip().upper()
    if not SAFE_ENUM_RE.fullmatch(normalized):
        raise ValueError("clinical_trials_" + name + "_invalid")
    return normalized


def _enums(value: Any, name: str, maximum: int) -> list[str]:
    values = value if isinstance(value, list) else [value]
    if not 1 <= len(values) <= maximum:
        raise ValueError("clinical_trials_" + name + "_invalid")
    result = [_enum(item, name) for item in values]
    if len(result) != len(set(result)):
        raise ValueError("clinical_trials_" + name + "_duplicate")
    return result


def _page_size(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= MAX_PAGE_SIZE:
        raise ValueError("clinical_trials_page_size_invalid")
    return value


def _cursor(value: Any) -> str:
    if not isinstance(value, str) or not SAFE_CURSOR_RE.fullmatch(value):
        raise ValueError("clinical_trials_page_token_invalid")
    return value


def _date_value(value: Any, field: str) -> str:
    if value is None:
        return "MIN" if field.endswith("from") else "MAX"
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("clinical_trials_" + field + "_invalid")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError("clinical_trials_" + field + "_invalid") from None
    return value


def _sort(value: Any) -> str:
    """Validate sort syntax; allowed date/numeric fields are registry-owned."""
    if not isinstance(value, str) or not value or len(value) > 120:
        raise ValueError("clinical_trials_sort_invalid")
    fields = [field.strip() for field in value.split(",")]
    if len(fields) > 2 or any(
        not re.fullmatch(r"(?:@[Rr]elevance|[A-Za-z][A-Za-z0-9]*)(?::(?:asc|desc))?", field)
        for field in fields
    ):
        raise ValueError("clinical_trials_sort_invalid")
    return ",".join(fields)


def _view(value: Any) -> str:
    if value not in {"summary", "research"}:
        raise ValueError("clinical_trials_view_invalid")
    return value


def _json(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        raise ValueError("clinical_trials_serialization_invalid") from None


def _bound(value: Any, maximum: int, code: str) -> None:
    if len(_json(value)) > maximum:
        raise ValueError(code)


__all__ = ["ClinicalTrialsLookupAdapter"]
