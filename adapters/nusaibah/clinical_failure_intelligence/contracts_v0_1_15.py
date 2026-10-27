"""Closed business contracts. Runtime authority never comes from business input."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
import math
import re
from typing import Any

JsonObject = dict[str, Any]
ASSET_KEY = "nusaibah.clinical_failure_intelligence"
VERSION = "0.1.15"
SCHEMA = "clinical_failure_intelligence.v1"
REQUEST_SCHEMA = "clinical_analysis_request.v1"
ROLE_SCHEMA = "clinical_agent_response.v1"
RESEARCH_ROLES = ("trial_researcher", "literature_researcher", "event_researcher")
ROLES = (
    *RESEARCH_ROLES,
    "outcome_adjudicator",
    "hypothesis_analyst",
    "evidence_critic",
    "product_memory_editor",
    "input_reconciler",
)
REASON_CODES = frozenset(
    {
        "efficacy",
        "safety_tolerability",
        "pk_pd_exposure_dose",
        "target_moa_biology",
        "design_statistics_endpoint",
        "recruitment_execution",
        "manufacturing_quality",
        "regulatory_benefit_risk",
        "strategic_commercial",
        "undetermined",
    }
)
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
DIGEST_RE = re.compile(r"sha256:[a-f0-9]{64}\Z")
# Detect authority material, not ordinary scientific words or bibliographic identifiers.
FORBIDDEN_AUTHORITY_KEYS = frozenset(
    {
        "authorization",
        "headers",
        "access_token",
        "refresh_token",
        "api_key",
        "password",
        "credentials",
        "client_secret",
        "presigned_url",
        "provider_state",
        "runtime_location",
        "raw_provider_response",
        "raw_dlm_response",
        "raw_obs_response",
    }
)


class ContractError(ValueError):
    """A stable value-free adapter contract rejection."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def require(condition: bool, code: str) -> None:
    """Reject a failed invariant without copying input values into the exception."""
    if not condition:
        raise ContractError(code)


def safe_json(value: Any, depth: int = 0) -> None:
    """Reject non-JSON values, nonfinite numbers and execution authority fields."""
    require(depth <= 32, "clinical_json_depth_invalid")
    if isinstance(value, dict):
        for key, child in value.items():
            require(isinstance(key, str), "clinical_json_key_invalid")
            require(
                key.casefold() not in FORBIDDEN_AUTHORITY_KEYS,
                "clinical_authority_material_forbidden",
            )
            safe_json(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            safe_json(child, depth + 1)
    elif isinstance(value, float):
        require(math.isfinite(value), "clinical_json_number_invalid")
    else:
        require(
            value is None or isinstance(value, (str, int, bool)),
            "clinical_json_value_invalid",
        )


def canonical_bytes(value: Any) -> bytes:
    """Encode exact semantic state for deterministic IDs and dependency hashes."""
    safe_json(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    """Return a SHA-256 identity of canonical semantic JSON."""
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def text_digest(value: str) -> str:
    """Hash exact UTF-8 text, preserving whitespace, signs and qualifications."""
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def object_fields(
    value: Any, required: set[str], optional: set[str] | None = None
) -> JsonObject:
    """Validate a closed object before reading nested fields."""
    require(isinstance(value, dict), "clinical_object_required")
    require(
        required <= set(value) <= required | (optional or set()),
        "clinical_fields_invalid",
    )
    return value


def text(value: Any, *, maximum: int = 8000) -> str:
    """Require actual nonblank text; never silently truncate scientific content."""
    require(
        isinstance(value, str) and bool(value.strip()) and len(value) <= maximum,
        "clinical_text_invalid",
    )
    return value


def identifier(value: Any) -> str:
    """Validate a logical identity, not a URL or physical storage address."""
    require(
        isinstance(value, str) and ID_RE.fullmatch(value) is not None,
        "clinical_id_invalid",
    )
    return value


def identifiers(
    value: Any, *, maximum: int = 128, allow_empty: bool = True
) -> list[str]:
    """Validate an ordered set of logical IDs."""
    require(
        isinstance(value, list) and len(value) <= maximum, "clinical_id_list_invalid"
    )
    values = [identifier(item) for item in value]
    require(
        len(set(values)) == len(values) and (allow_empty or bool(values)),
        "clinical_id_list_invalid",
    )
    return values


def iso_date(value: Any) -> str:
    """Require an exact calendar date rather than inferring an unknown date."""
    require(
        isinstance(value, str)
        and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is not None,
        "clinical_date_invalid",
    )
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ContractError("clinical_date_invalid") from None
    return value


def strict_object(text_value: str) -> JsonObject:
    """Decode complete JSON and explicit whole-answer fences; never evaluate code."""

    def pairs(items: list[tuple[str, Any]]) -> JsonObject:
        out: JsonObject = {}
        for key, value in items:
            require(key not in out, "clinical_duplicate_json_key")
            out[key] = value
        return out

    def invalid_constant(_: str) -> None:
        raise ContractError("clinical_json_number_invalid")

    require(isinstance(text_value, str), "clinical_response_text_required")
    candidate = text_value.strip()
    for _ in range(3):
        fence = re.fullmatch(r"```(?:json)?\s*\n([\s\S]*?)\n```", candidate, flags=re.I)
        if fence:
            candidate = fence.group(1).strip()
        try:
            value = json.loads(
                candidate, object_pairs_hook=pairs, parse_constant=invalid_constant
            )
        except (json.JSONDecodeError, RecursionError):
            raise ContractError("clinical_response_json_invalid") from None
        if isinstance(value, str):
            candidate = value.strip()
            continue
        require(isinstance(value, dict), "clinical_response_object_required")
        safe_json(value)
        return value
    raise ContractError("clinical_response_json_invalid")


def parse_request(inputs: Any) -> JsonObject:
    """Validate the request and resolved context before spending Agent calls."""
    require(isinstance(inputs, dict), "clinical_inputs_invalid")
    if __package__:
        from .retained_sources_v0_1_15 import SOURCE_ROLES, prepare_retained_bundle
    else:
        from retained_sources_v0_1_15 import SOURCE_ROLES, prepare_retained_bundle
    require(
        {"variables", "clinical_context"}
        <= set(inputs)
        <= {"variables", "clinical_context", "clinical_evidence", *SOURCE_ROLES},
        "clinical_input_roles_invalid",
    )
    values = object_fields(
        inputs["variables"],
        {
            "schema_version",
            "request_id",
            "analysis_mode",
            "subject_id",
            "as_of_date",
            "event_ids",
        },
        {
            "memory_mode",
            "enable_refinement",
            "enable_pharmacological_class",
            "product_id",
            "indication_id",
            "trial_id",
            "source_object_id",
            "preflight_only",
            "supplementary_search",
            "prepare_result_for_persistence",
            "agent_parallelism",
            "max_agent_calls",
            "max_product_seconds",
        },
    )
    safe_json(values)
    require(
        values["schema_version"] == REQUEST_SCHEMA, "clinical_request_schema_invalid"
    )
    require(
        isinstance(values["analysis_mode"], str)
        and values["analysis_mode"] in {"mechanistic_case", "cohort_pattern"},
        "clinical_mode_invalid",
    )
    identifier(values["request_id"])
    identifier(values["subject_id"])
    iso_date(values["as_of_date"])
    identifiers(values["event_ids"], maximum=32)
    require(
        type(values.get("agent_parallelism", 20)) is int
        and 1 <= values.get("agent_parallelism", 20) <= 20,
        "clinical_parallelism_invalid",
    )
    require(
        type(values.get("max_agent_calls", 64)) is int
        and 1 <= values.get("max_agent_calls", 64) <= 64,
        "clinical_call_budget_invalid",
    )
    require(
        type(values.get("max_product_seconds", 3600)) is int
        and 1501 <= values.get("max_product_seconds", 3600) <= 3600,
        "clinical_product_time_budget_invalid",
    )
    memory_mode = values.get("memory_mode", "preview")
    # Callable mutation and retention-before-apply are not admitted in this release.
    require(
        isinstance(memory_mode, str) and memory_mode in {"off", "preview"},
        "clinical_memory_apply_not_admitted",
    )
    require(
        type(values.get("enable_refinement", True)) is bool,
        "clinical_refinement_flag_invalid",
    )
    require(
        type(values.get("prepare_result_for_persistence", False)) is bool,
        "clinical_persistence_prepare_flag_invalid",
    )
    require(
        not (
            values.get("preflight_only", False)
            and values.get("prepare_result_for_persistence", False)
        ),
        "clinical_persistence_preflight_forbidden",
    )
    for selector in ("product_id", "indication_id", "trial_id"):
        if values.get(selector) is not None:
            identifier(values[selector])
    if values.get("source_object_id") is not None:
        require(
            type(values["source_object_id"]) is int and values["source_object_id"] > 0,
            "clinical_source_object_selector_invalid",
        )
    source_input = inputs["clinical_context"]
    if isinstance(source_input, dict) and set(source_input) == {
        "records",
        "provenance",
    }:
        if __package__:
            from .source_events_v0_1_15 import normalize_event_records
        else:
            from source_events_v0_1_15 import normalize_event_records
        source_input = normalize_event_records(values, source_input)
    for flag in ("preflight_only", "supplementary_search"):
        require(
            type(values.get(flag, flag == "supplementary_search")) is bool,
            "clinical_execution_flag_invalid",
        )
    context = object_fields(
        source_input,
        {
            "schema_version",
            "context_id",
            "subject",
            "event_ids",
            "source_assertions",
            "evidence",
            "cohort",
        },
        {"case_scope", "source_event_metadata"},
    )
    safe_json(context)
    require(
        context["schema_version"] == "clinical_context.v1",
        "clinical_context_schema_invalid",
    )
    identifier(context["context_id"])
    subject = object_fields(
        context["subject"],
        {
            "subject_id",
            "product_id",
            "product_name",
            "pharmacological_group_id",
            "indication",
            "regimen",
            "trial_ids",
        },
    )
    require(subject["subject_id"] == values["subject_id"], "clinical_subject_mismatch")
    if values.get("product_id") is not None:
        require(
            subject["product_id"] == values["product_id"],
            "clinical_source_product_scope_mismatch",
        )
    for key in ("product_id", "pharmacological_group_id"):
        if subject[key] is not None:
            identifier(subject[key])
    for key in ("product_name", "indication", "regimen"):
        if subject[key] is not None:
            text(subject[key], maximum=512)
    identifiers(subject["trial_ids"], maximum=32)
    if values["analysis_mode"] == "mechanistic_case":
        require(
            subject["product_id"] is not None and subject["indication"] is not None,
            "clinical_case_subject_incomplete",
        )
    require(
        set(identifiers(context["event_ids"], maximum=32)) == set(values["event_ids"]),
        "clinical_event_scope_mismatch",
    )
    class_enabled = values.get("enable_pharmacological_class", False)
    require(type(class_enabled) is bool, "clinical_class_flag_invalid")
    if class_enabled:
        require(
            subject["pharmacological_group_id"] is not None,
            "clinical_class_identity_required",
        )
    if values["analysis_mode"] == "mechanistic_case" and memory_mode != "off":
        scope = object_fields(
            context.get("case_scope"),
            {"indication_id", "trial_id", "regimen_id"},
            {"event_id"},
        )
        identifier(scope["indication_id"])
        for field in ("trial_id", "regimen_id"):
            if scope[field] is not None:
                identifier(scope[field])
        if scope["trial_id"] is None:
            require(
                subject["trial_ids"] == []
                and len(context["event_ids"]) == 1
                and scope.get("event_id") == context["event_ids"][0],
                "clinical_memory_unreported_trial_requires_event_scope",
            )
        else:
            require(
                subject["trial_ids"] == [scope["trial_id"]],
                "clinical_memory_requires_single_trial_scope",
            )
        if values.get("indication_id") is not None:
            require(
                values["indication_id"] == scope["indication_id"],
                "clinical_source_indication_scope_mismatch",
            )
        if values.get("trial_id") is not None:
            require(
                values["trial_id"] == scope["trial_id"],
                "clinical_source_trial_scope_mismatch",
            )
    elif "case_scope" in context:
        scope = object_fields(
            context["case_scope"],
            {"indication_id", "trial_id", "regimen_id"},
            {"event_id"},
        )
        identifier(scope["indication_id"])
        for field in ("trial_id", "regimen_id"):
            if scope[field] is not None:
                identifier(scope[field])
    require(
        isinstance(context["source_assertions"], list)
        and len(context["source_assertions"]) <= 32,
        "clinical_source_assertions_invalid",
    )
    seen: set[str] = set()
    for seed in context["source_assertions"]:
        object_fields(
            seed,
            {"assertion_id", "statement", "source_ref"},
            {
                "general_research_observation",
                "example_drugs",
                "indicators_to_measure_and_validate",
            },
        )
        sid = identifier(seed["assertion_id"])
        require(sid not in seen, "clinical_seed_duplicate")
        seen.add(sid)
        text(seed["statement"])
        text(seed["source_ref"], maximum=512)
        observation = seed.get("general_research_observation")
        if observation is not None:
            text(observation)
        for field in ("example_drugs", "indicators_to_measure_and_validate"):
            values_list = seed.get(field, [])
            require(
                isinstance(values_list, list) and len(values_list) <= 32,
                "clinical_seed_details_invalid",
            )
            for value in values_list:
                text(value, maximum=2000)
    require(
        isinstance(context["evidence"], list) and len(context["evidence"]) <= 64,
        "clinical_evidence_list_invalid",
    )
    require(
        context["cohort"] is None or isinstance(context["cohort"], dict),
        "clinical_cohort_invalid",
    )
    require(
        len(canonical_bytes(context)) <= 256 * 1024,
        "clinical_context_requires_partitioning",
    )
    request = {
        **deepcopy(values),
        "memory_mode": memory_mode,
        "max_agent_calls": values.get("max_agent_calls", 64),
        "max_product_seconds": values.get("max_product_seconds", 3600),
        "agent_parallelism": values.get("agent_parallelism", 20),
        "enable_refinement": values.get("enable_refinement", True),
        "enable_pharmacological_class": class_enabled,
        "context": deepcopy(context),
    }

    if __package__:
        from .source_bundle_v0_1_15 import prepare_bundle
    else:
        from source_bundle_v0_1_15 import prepare_bundle
    request["preflight_only"] = values.get("preflight_only", False)
    request["supplementary_search"] = values.get("supplementary_search", True)
    retained = prepare_retained_bundle(inputs, request)
    request["prepared_sources"] = prepare_bundle(
        retained if retained is not None else inputs.get("clinical_evidence"), request
    )
    return request
