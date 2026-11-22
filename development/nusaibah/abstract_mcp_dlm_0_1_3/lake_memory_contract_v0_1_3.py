"""Closed, deterministic lake-memory contracts. Validation is not authorization."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

MAX_DOCUMENT_BYTES = 262144
MAX_RESULT_BYTES = 65536
MAX_RECORDS = 200
ID = {"type": "string", "pattern": r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"}
DIGEST = {"type": "string", "pattern": r"^sha256:[0-9a-f]{64}$"}
TEXT = {"type": "string", "minLength": 1, "maxLength": 4096}
LABEL = {"type": "string", "minLength": 1, "maxLength": 160}
TIME = {"type": "string", "format": "date-time"}
KINDS = ("knowledge", "engineering")
OPERATIONS = ("memory.context", "memory.knowledge.update", "memory.plan.upsert", "memory.plan.reconcile")
SECTIONS = {
    "identity_and_purpose": "Identity and purpose",
    "concepts_and_terminology": "Concepts and terminology",
    "sources_and_coverage": "Sources and coverage",
    "node_semantics": "Node semantics",
    "rules_and_interpretation": "Rules and interpretation",
    "decisions_and_rationale": "Decisions and rationale",
    "gaps_and_open_questions": "Gaps and open questions",
}
PROGRESS = ("planned", "in_progress", "blocked", "cancelled", "superseded")


class MemoryError(ValueError):
    """A safe public error code, without raw backend or validation payloads."""

    def __init__(self, code: str) -> None:
        self.code = self.failure_code = "dlm_memory_" + code
        super().__init__(self.code)


def obj(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    """Construct a closed object schema."""
    return {"type": "object", "properties": properties, "additionalProperties": False,
            "required": list(properties) if required is None else required}


def arr(items: dict[str, Any], maximum: int = 50) -> dict[str, Any]:
    """Construct a bounded collection schema."""
    return {"type": "array", "items": items, "maxItems": maximum}


def nullable(schema: dict[str, Any]) -> dict[str, Any]:
    """Represent unavailable values explicitly."""
    return {"anyOf": [schema, {"type": "null"}]}


REFERENCE = {"oneOf": [
    obj({"kind": {"const": "linear"}, "issue": {"type": "string", "pattern": r"^[A-Z][A-Z0-9]*-[1-9][0-9]*$"}}),
    obj({"kind": {"const": "github"}, "repository": {"type": "string", "pattern": r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"},
         "commit": {"type": "string", "pattern": r"^[0-9a-f]{40}$"}, "path": LABEL,
         "pull_request": {"type": ["integer", "null"], "minimum": 1}}, ["kind", "repository", "commit", "path"]),
    obj({"kind": {"enum": ["client_statement", "core_receipt"]}, "reference": ID}),
]}
ASSERTION = obj({"assertion_id": ID, "statement": TEXT,
    "source_kind": {"enum": ["client_stated", "proposed", "source_cited"]},
    "source_refs": arr(REFERENCE, 12), "confirmation_state": {"enum": ["unconfirmed", "client_confirmed", "disputed", "superseded"]},
    "as_of": nullable(TIME), "supersedes": nullable(ID)})
FIELD = obj({"name": ID, "type": LABEL, "description": TEXT, "required": {"type": "boolean"}})
RELATION = obj({"target_node_key": ID, "local_fields": arr(ID), "remote_fields": arr(ID), "description": TEXT})
NODE_SCHEMA = obj({"grain": TEXT, "format": LABEL, "fields": arr(FIELD, 100), "primary_key": arr(ID),
                   "partition_fields": arr(ID), "relationships": arr(RELATION), "quality_rules": arr(TEXT)})
CRITERION = obj({"criterion_id": ID, "description": TEXT,
                 "verification_kind": {"enum": ["schema", "readiness", "approved_evidence"]}})
PLAN = obj({"plan_id": ID, "capability_section": ID, "intent": {"enum": ["create", "update"]},
    "proposed_node_key": ID, "title": LABEL, "description": TEXT, "expected_outcome": TEXT,
    "acceptance_criteria": {**arr(CRITERION), "minItems": 1}, "proposed_schema": NODE_SCHEMA,
    "dependencies": arr(ID), "implementation_steps": arr(TEXT), "owner": nullable(LABEL),
    "priority": {"enum": ["low", "normal", "high"]}, "blockers": arr(TEXT), "next_action": nullable(TEXT),
    "evidence_refs": arr(REFERENCE, 20), "supersedes_plan_id": nullable(ID), "status": {"enum": list(PROGRESS)}})
APPROVAL = obj({"status": {"enum": ["approved", "not_approved", "not_required", "unavailable"]},
                "reference": nullable(ID), "plan_digest": DIGEST})
CHECK = obj({"criterion_id": ID, "status": {"enum": ["passed", "failed", "unavailable"]}, "reference": nullable(ID)})
OBSERVATION = obj({"schema_version": {"const": "dlm_node_implementation.v1"}, "client_id": ID,
    "lake_id": ID, "node_key": ID, "plan_id": ID, "plan_digest": DIGEST, "observed_at": TIME,
    "node_exists": {"type": "boolean"}, "schema_complete": {"type": "boolean"}, "actual_schema": nullable(NODE_SCHEMA),
    "core_revision": nullable(ID), "design_approval": APPROVAL, "core_approval": APPROVAL,
    "readiness": {"enum": ["ready", "not_ready", "unavailable"]}, "acceptance": arr(CHECK)})
MUTATION = {"mode": {"enum": ["preview", "apply"], "default": "preview"},
            "expected_digest": nullable(DIGEST), "proposal_digest": DIGEST}
REQUESTS = {
    "memory.context": obj({"operation": {"const": "memory.context"}, "lake_id": ID, "memory_kind": {"enum": list(KINDS)},
        "view": {"enum": ["brief", "detail", "history"], "default": "brief"}, "record_id": ID,
        "section_id": ID, "status": {"enum": list(PROGRESS) + ["implemented"]},
        "page": {"type": "integer", "minimum": 1, "maximum": 1000},
        "page_size": {"type": "integer", "minimum": 1, "maximum": 20}, "before_change_id": ID},
        ["operation", "lake_id", "memory_kind"]),
    "memory.knowledge.update": obj({"operation": {"const": "memory.knowledge.update"}, "lake_id": ID,
        "section_id": ID, "section_title": LABEL, "assertion": ASSERTION, **MUTATION},
        ["operation", "lake_id", "section_id", "section_title", "assertion"]),
    "memory.plan.upsert": obj({"operation": {"const": "memory.plan.upsert"}, "lake_id": ID,
        "plan": PLAN, **MUTATION}, ["operation", "lake_id", "plan"]),
    "memory.plan.reconcile": obj({"operation": {"const": "memory.plan.reconcile"}, "lake_id": ID,
        "plan_id": ID, "node_key": ID, **MUTATION}, ["operation", "lake_id", "plan_id", "node_key"]),
}
# PROPOSED server projection, not a current SDK or public input contract.
SCOPE = obj({"schema_version": {"const": "dlm_lake_memory_scope.v1"}, "client_id": ID, "actor_id": ID,
    "lake_id": ID, "operation": {"enum": list(OPERATIONS)}, "mode": {"enum": ["read", "preview", "apply"]},
    "request_digest": DIGEST, "read_selector_digest": DIGEST, "write_selector_digest": nullable(DIGEST),
    "allow_initialize": {"type": "boolean"}, "history_allowed": {"type": "boolean"},
    "visibility": {"const": "complete_authorized_lake"}})
_UNSAFE = re.compile(r"://|bearer\s+|-----BEGIN|(?:password|secret|api[_-]?key|access[_-]?token)\s*[:=]", re.I)


def canonical(value: Any) -> str:
    """Canonical UTF-8 JSON; reject NaN, unpaired surrogates and non-JSON data."""
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        text.encode("utf-8", errors="strict")
        return text
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise MemoryError("json_invalid") from None


def digest(value: Any) -> str:
    """Hash semantic JSON; this is not a Core-issued revision identifier."""
    return text_digest(canonical(value))


def text_digest(text: str) -> str:
    """Hash the exact admitted document bytes."""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate(value: Any, schema: dict[str, Any], code: str) -> None:
    """Reject invalid shapes without exposing data-bearing library exceptions."""
    if not Draft202012Validator(schema, format_checker=FormatChecker()).is_valid(value):
        raise MemoryError(code)


def safe_content(value: Any, depth: int = 0) -> None:
    """Protect the semantic surface from transport material and unsafe references."""
    if depth > 14:
        raise MemoryError("depth_exceeded")
    if isinstance(value, str):
        if _UNSAFE.search(value) or any(ord(c) < 32 and c not in "\n\t" for c in value):
            raise MemoryError("unsafe_content")
    elif isinstance(value, dict):
        for item in value.values():
            safe_content(item, depth + 1)
        if value.get("kind") == "github":
            path = value.get("path", "")
            if "\\" in path or any(part in ("", ".", "..") for part in path.split("/")):
                raise MemoryError("source_reference_invalid")
    elif isinstance(value, list):
        for item in value:
            safe_content(item, depth + 1)


def request_contract(request: Any) -> dict[str, Any]:
    """Accept one exact public operation; no tenant or storage-selector overrides."""
    if not isinstance(request, dict) or not isinstance(request.get("operation"), str) or request["operation"] not in REQUESTS:
        raise MemoryError("operation_unavailable")
    if len(canonical(request).encode("utf-8")) > MAX_RESULT_BYTES:
        raise MemoryError("request_limit_exceeded")
    validate(request, REQUESTS[request["operation"]], "request_invalid")
    safe_content(request)
    if request.get("mode") == "apply" and not {"expected_digest", "proposal_digest"} <= set(request):
        raise MemoryError("apply_requires_preview")
    if request["operation"] == "memory.context":
        history = request.get("view") == "history"
        if history and any(k in request for k in ("page", "section_id", "status")):
            raise MemoryError("history_filters_invalid")
        if not history and "before_change_id" in request:
            raise MemoryError("history_filters_invalid")
        if (request["memory_kind"] == "knowledge" and "status" in request
                or request["memory_kind"] == "engineering" and "section_id" in request):
            raise MemoryError("filter_invalid")
    return request


def memory_kind(request: dict[str, Any]) -> str:
    """Derive the memory class from the operation, not arbitrary role input."""
    return request["memory_kind"] if request["operation"] == "memory.context" else (
        "knowledge" if request["operation"] == "memory.knowledge.update" else "engineering")


def trusted_scope(context: Any, request: dict[str, Any]) -> dict[str, Any]:
    """Check the pending server-only projection. A dict is not authentication.

    Assets must construct and sign this projection, bind roles, and reject caller
    context injection. Until that integration exists this candidate fails closed.
    """
    scope = context.get("dlm_lake_memory_scope") if isinstance(context, dict) else None
    if scope is None:
        raise MemoryError("trusted_scope_unavailable")
    validate(scope, SCOPE, "trusted_scope_invalid")
    mode = "read" if request["operation"] == "memory.context" else request.get("mode", "preview")
    if (scope["lake_id"] != request["lake_id"] or scope["operation"] != request["operation"]
            or scope["mode"] != mode or scope["request_digest"] != digest(request)):
        raise MemoryError("scope_mismatch")
    if mode == "apply" and scope["write_selector_digest"] is None:
        raise MemoryError("write_not_admitted")
    return scope


def validate_schema(schema: dict[str, Any]) -> None:
    """Check schema references as well as JSON shape."""
    validate(schema, NODE_SCHEMA, "schema_invalid")
    names = [field["name"] for field in schema["fields"]]
    if not names or len(names) != len(set(names)):
        raise MemoryError("schema_fields_invalid")
    for key in ("primary_key", "partition_fields"):
        if len(set(schema[key])) != len(schema[key]) or not set(schema[key]) <= set(names):
            raise MemoryError("schema_keys_invalid")
    for rel in schema["relationships"]:
        if not rel["local_fields"] or len(rel["local_fields"]) != len(rel["remote_fields"]) or not set(rel["local_fields"]) <= set(names):
            raise MemoryError("schema_relationship_invalid")


def plan_digest(plan: dict[str, Any]) -> str:
    """Bind approval to design intent, excluding ordinary progress bookkeeping."""
    excluded = {"status", "blockers", "next_action", "owner", "priority", "evidence_refs"}
    return digest({key: value for key, value in plan.items() if key not in excluded})
