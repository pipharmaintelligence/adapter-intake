"""One real CompanyContext, retrieved by the generic retained-output boundary.

Database observations are evidence about the stored record, not verified public
research. Historical fixture contracts and runtime authority remain unchanged.
"""
from __future__ import annotations

import copy
import json
import re
import time
from typing import Any

if __package__:
    from . import supplied_source_scoped_review as scoped
    from .quote_review_orchestration import ReviewContract, run_review as execute_review
else:
    import supplied_source_scoped_review as scoped
    from quote_review_orchestration import ReviewContract, run_review as execute_review

digest = scoped.digest
_require = scoped.quote._require
PURPOSE = "company_context_review"
METHOD = {**copy.deepcopy(scoped.METHOD), "schema_version": "company_context_methodology.v1",
          "evidence_scope": "governed_database_observation"}
SCOPE_IDENTITY = "nusaibah.company_scope:0.1.0"


def _keys(value: Any, keys: set[str], rule: str) -> None:
    _require(isinstance(value, dict) and set(value) == keys, rule)


def _digest_valid(value: dict[str, Any]) -> bool:
    return value.get("digest") == digest({k: v for k, v in value.items() if k != "digest"})


def prepare_review(inputs: Any) -> dict[str, Any]:
    _keys(inputs, {"company_context", "variables"}, "input_roles_invalid")
    _keys(inputs["variables"], {"execution_purpose"}, "variables_invalid")
    _require(inputs["variables"]["execution_purpose"] == PURPOSE, "execution_purpose_invalid")
    handoff = inputs["company_context"]
    _keys(handoff, {"value", "provenance"}, "retained_company_context_required")
    provenance = handoff["provenance"]
    _keys(provenance, {"source", "authority", "run_uuid", "asset_identity", "output_role", "checksum_sha256"},
          "retained_provenance_invalid")
    _require(provenance["source"] == "retained_asset_output" and provenance["authority"] == "core_artifact"
             and provenance["asset_identity"] == SCOPE_IDENTITY
             and provenance["output_role"] == "company_scope_result"
             and isinstance(provenance["run_uuid"], str)
             and re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", provenance["run_uuid"]) is not None
             and isinstance(provenance["checksum_sha256"], str)
             and re.fullmatch(r"[a-f0-9]{64}", provenance["checksum_sha256"]) is not None,
             "retained_provenance_invalid")
    scope = handoff["value"]
    _keys(scope, {"schema_version", "selector_kind", "requested_company_ids", "duplicate_id_count", "company_count",
                  "corporate_id", "complete", "validation_scope", "runtime_authority_verified", "records", "digest"},
          "company_scope_invalid")
    _require(scope["schema_version"] == "company_scope_result.v1" and scope["complete"] is True
             and type(scope["company_count"]) is int and scope["company_count"] == 1
             and type(scope["corporate_id"]) is int and scope["corporate_id"] == 1
             and scope["validation_scope"] == "resolved_rows_only" and scope["runtime_authority_verified"] is False
             and isinstance(scope["records"], list) and len(scope["records"]) == 1
             and _digest_valid(scope), "one_complete_company_context_required")
    company = scope["records"][0]
    _keys(company, {"schema_version", "company_id", "company_name", "corporate_id", "address_line1", "address_line2",
                    "headquarters_country_id", "website", "source_updated_at", "source", "digest"}, "company_context_invalid")
    _require(company["schema_version"] == "company_context.v1" and type(company["company_id"]) is int
             and 0 < company["company_id"] <= 2**63-1 and type(company["corporate_id"]) is int
             and company["corporate_id"] == 1 and scope["requested_company_ids"] == [company["company_id"]]
             and _digest_valid(company), "company_context_identity_invalid")
    _require(isinstance(company["company_name"], str) and bool(company["company_name"].strip())
             and len(company["company_name"]) <= 160, "company_context_name_invalid")
    source = company["source"]
    _keys(source, {"input_role", "source", "lake_id", "node_key", "retrieved_at", "schema_version"}, "company_context_source_invalid")
    _require(source["input_role"] == "companies" and source["source"] == "dlm_node"
             and source["node_key"] == "companies" and isinstance(source["lake_id"], str)
             and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,189}", source["lake_id"]) is not None,
             "company_context_source_invalid")
    for key, limit in (("address_line1", 4096), ("address_line2", 4096), ("website", 2048), ("source_updated_at", 64)):
        _require(company[key] is None or (isinstance(company[key], str) and len(company[key]) <= limit),
                 "company_context_field_invalid")
    country = company["headquarters_country_id"]
    _require(country is None or (type(country) is int and 0 < country <= 2**63-1), "company_context_field_invalid")
    observation = {key: company[key] for key in ("company_id", "company_name", "corporate_id", "address_line1",
                   "address_line2", "headquarters_country_id", "website", "source_updated_at")}
    text = json.dumps(observation, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    _require(len(text) <= 6000, "company_context_chunk_limit_exceeded")
    entity_id = "company-" + str(company["company_id"])
    unit = {"locator": "company:" + str(company["company_id"]), "entity_id": entity_id, "text": text,
            "accessible": True, "related_locators": []}
    snapshot_id = digest({"schema_version": "company_context_snapshot.v1", "context_digest": company["digest"],
                          "handoff": provenance, "units": [unit]})
    material = {"snapshot_id": snapshot_id, "primary_locator": unit["locator"], "units": [unit],
                "chunk_policy": "intact_governed_company_observation.v1"}
    chunk = {**material, "chunk_id": digest(material)}
    plan = {"schema_version": "company_context_plan.v1", "snapshot_id": snapshot_id,
            "methodology_id": METHOD["schema_version"], "methodology_digest": digest(METHOD),
            "chunk_ids": [chunk["chunk_id"]], "roles": list(scoped.ROLES), "verifier_role": scoped.VERIFIER_ROLE,
            "logical_call_limit": 5, "max_concurrency": 3, "deadline_seconds": 1800, "repair_iterations": 0,
            "toolkit_identity": scoped.TOOL_IDENTITY, "child_call_limit": 1, "max_span_requests_per_chunk": 16}
    return {"case_id": "governed-" + entity_id, "entity_id": entity_id, "entity_name": company["company_name"],
            "snapshot_id": snapshot_id, "chunks": [chunk], "inventory": [{"locator": unit["locator"],
                "disposition": "assigned", "chunk_id": chunk["chunk_id"]}],
            "plan": {**plan, "plan_digest": digest(plan)}, "handoff": copy.deepcopy(provenance),
            "company_context_digest": company["digest"]}


def verification_material(finding: dict[str, Any], chunk: dict[str, Any]) -> dict[str, Any]:
    return {"finding": finding, "source_units": chunk["units"], "methodology_digest": digest(METHOD)}


CONTRACT = ReviewContract(METHOD, scoped.QUESTIONS, prepare_review, scoped._specialist_contract,
                          scoped._verifier_contract, verification_material)


def run_review(inputs: Any, *, clock: Any = time.monotonic) -> dict[str, Any]:
    prepared = prepare_review(inputs)
    result = execute_review(inputs, profile=CONTRACT, clock=clock)
    return {**result, "schema_version": "company_context_review_result.v1", "synthetic": False,
            "scope": "governed_company_record_review", "handoff": prepared["handoff"],
            "company_context_digest": prepared["company_context_digest"],
            "limitations": ["Evidence describes a governed database observation; external factual truth and freshness are unverified.",
                            "Country identifiers are not country names. Addresses do not prove sales markets.",
                            "Absent product, commercial and clinical evidence remains a gap; no web research was requested.",
                            "Semantic quality requires independent review. This is not a full dossier or WP1 release evaluation."]}
