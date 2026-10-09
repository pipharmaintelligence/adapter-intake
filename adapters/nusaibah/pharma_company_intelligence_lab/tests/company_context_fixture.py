"""Synthetic fixture matching Company Scope 0.1.0's canonical output contract."""
import hashlib
import json


def sign(value):
    body = {k: v for k, v in value.items() if k != "digest"}
    value["digest"] = "sha256:" + hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return value


def handoff(records):
    contexts = [sign({
        "schema_version": "company_context.v1", "company_id": record.get("company_id", record.get("id")),
        "company_name": record.get("company_name", record.get("company")), "corporate_id": 1,
        "address_line1": record.get("address_line1"), "address_line2": record.get("address_line2"),
        "headquarters_country_id": record.get("headquarters_country_id"), "website": record.get("website"),
        "source_updated_at": record.get("source_updated_at"),
        "source": {"input_role": "companies", "source": "dlm_node", "lake_id": "synthetic-lake", "node_key": "companies", "retrieved_at": None, "schema_version": None},
    }) for record in records]
    scope = sign({"schema_version": "company_scope_result.v1", "selector_kind": "list",
        "requested_company_ids": [r["company_id"] for r in contexts], "duplicate_id_count": 0,
        "company_count": len(contexts), "corporate_id": 1, "complete": True,
        "validation_scope": "resolved_rows_only", "runtime_authority_verified": False, "records": contexts})
    return {"value": scope, "provenance": {"source": "retained_asset_output", "authority": "core_artifact",
        "run_uuid": "11111111-1111-4111-8111-111111111111", "asset_identity": "nusaibah.company_scope:0.1.0",
        "output_role": "company_scope_result", "checksum_sha256": "a" * 64}}
