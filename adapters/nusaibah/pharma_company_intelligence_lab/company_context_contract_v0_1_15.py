"""Validate the runtime-hydrated Company Scope handoff before any helper call.

Assets/Core owns artifact authorization, retention and checksum verification.
These structural/digest checks do not establish caller or storage authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCOPE_IDENTITY = "nusaibah.company_scope:0.1.0"
# These exact slots are injected by Assets from manifest runtime_skills.
# They remain opaque here; SDK dynamic_skill(...) owns their authority/content.
CALLER_INPUT_ROLES = frozenset({"company_context", "variables"})
RUNTIME_SKILL_ROLES = frozenset({
    "company_memory", "company_memory_update",
    "company_methodology", "company_methodology_update",
})
MAX_CONTEXT_COMPANIES = 5
MAX_ID = 2**63 - 1
BUSINESS_FIELDS = (
    "company_id", "company_name", "corporate_id", "address_line1", "address_line2",
    "headquarters_country_id", "website", "source_updated_at",
)


class CompanyContextContractError(ValueError):
    """Reuse the reviewed business-contract code and generic safe proof detail."""

    def __init__(self, rule: str) -> None:
        self.code = "pharma_agent_business_schema_invalid"
        self.proof_failure_detail = {
            "schema_version": "proof_failure_detail.v1", "proof_kind": "agent_contract",
            "role": "company_context", "stage": "input_contract", "rule": rule,
        }
        super().__init__("Retained CompanyContext violates the reviewed input contract.")


def _require(condition: bool, rule: str) -> None:
    if not condition:
        # Static rules only: never include source values or artifact locations.
        raise CompanyContextContractError(rule)


def _keys(value: Any, keys: set[str], rule: str) -> None:
    _require(isinstance(value, dict) and set(value) == keys, rule)


def _id(value: Any) -> bool:
    return type(value) is int and 0 < value <= MAX_ID


def _text(value: Any, limit: int, *, required: bool = False) -> bool:
    if value is None:
        return not required
    return isinstance(value, str) and bool(value.strip()) and value == value.strip() and "\x00" not in value and len(value) <= limit


def _digest_valid(value: dict[str, Any]) -> bool:
    encoded = json.dumps({k: v for k, v in value.items() if k != "digest"},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    return value["digest"] == "sha256:" + hashlib.sha256(encoded).hexdigest()


def resolve_company_context(inputs: Any, *, company_ids: tuple[int, ...]) -> list[dict[str, Any]]:
    """Return business observations only; never read Companies or infer geography.

    One complete Scope result must match the requested company set. The existing
    batch contract orders these validated records before research or mutation.
    """
    _require(isinstance(inputs, dict), "input_roles")
    roles = set(inputs)
    _require(CALLER_INPUT_ROLES <= roles <= CALLER_INPUT_ROLES | RUNTIME_SKILL_ROLES,
             "input_roles")
    handoff = inputs["company_context"]
    _keys(handoff, {"value", "provenance"}, "retained_handoff_required")
    provenance = handoff["provenance"]
    _keys(provenance, {"source", "authority", "run_uuid", "asset_identity", "output_role", "checksum_sha256"}, "provenance")
    _require(provenance["source"] == "retained_asset_output" and provenance["authority"] == "core_artifact"
             and provenance["asset_identity"] == SCOPE_IDENTITY and provenance["output_role"] == "company_scope_result"
             and isinstance(provenance["run_uuid"], str)
             and re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", provenance["run_uuid"]) is not None
             and isinstance(provenance["checksum_sha256"], str)
             and re.fullmatch(r"[a-f0-9]{64}", provenance["checksum_sha256"]) is not None, "provenance")
    scope = handoff["value"]
    _keys(scope, {"schema_version", "selector_kind", "requested_company_ids", "duplicate_id_count", "company_count",
                  "corporate_id", "complete", "validation_scope", "runtime_authority_verified", "records", "digest"}, "scope_shape")
    _require(scope["schema_version"] == "company_scope_result.v1" and scope["complete"] is True
             and type(scope["corporate_id"]) is int and scope["corporate_id"] == 1
             and scope["validation_scope"] == "resolved_rows_only" and scope["runtime_authority_verified"] is False,
             "complete_scope_required")
    ids, records = scope["requested_company_ids"], scope["records"]
    _require(isinstance(ids, list) and 1 <= len(ids) <= MAX_CONTEXT_COMPANIES
             and all(_id(item) for item in ids) and len(set(ids)) == len(ids), "scope_ids")
    _require(isinstance(records, list) and len(records) == len(ids)
             and type(scope["company_count"]) is int and scope["company_count"] == len(ids), "scope_count")
    _require(scope["selector_kind"] in ("single", "list", "range")
             and (scope["selector_kind"] != "single" or len(ids) == 1)
             and (scope["selector_kind"] != "range" or ids == list(range(ids[0], ids[0] + len(ids))))
             and type(scope["duplicate_id_count"]) is int and 0 <= scope["duplicate_id_count"] <= 25 - len(ids)
             and (scope["selector_kind"] == "list" or scope["duplicate_id_count"] == 0), "selector")
    for company in records:
        _keys(company, {"schema_version", *BUSINESS_FIELDS, "source", "digest"}, "context_shape")
        _require(company["schema_version"] == "company_context.v1" and _id(company["company_id"])
                 and type(company["corporate_id"]) is int and company["corporate_id"] == 1, "context_identity")
        _require(_text(company["company_name"], 512, required=True), "company_name")
        for field, limit in (("address_line1", 4096), ("address_line2", 4096), ("website", 2048), ("source_updated_at", 64)):
            _require(_text(company[field], limit), "context_field")
        _require(company["headquarters_country_id"] is None or _id(company["headquarters_country_id"]), "country_id")
        source = company["source"]
        _keys(source, {"input_role", "source", "lake_id", "node_key", "retrieved_at", "schema_version"}, "source_shape")
        _require(source["input_role"] == "companies" and source["source"] == "dlm_node" and source["node_key"] == "companies"
                 and isinstance(source["lake_id"], str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,189}", source["lake_id"]) is not None
                 and source["retrieved_at"] is None and source["schema_version"] is None, "source")
        _require(_digest_valid(company), "context_digest")
    _require([record["company_id"] for record in records] == ids, "scope_record_ids")
    _require(_digest_valid(scope), "scope_digest")
    _require(set(ids) == set(company_ids), "requested_company_ids")
    return [{field: company[field] for field in BUSINESS_FIELDS} for company in records]
