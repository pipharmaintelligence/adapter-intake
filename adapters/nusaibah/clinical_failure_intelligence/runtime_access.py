"""Thin runtime calls, strict terminal decoding and same-input in-memory reuse."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
import threading
from typing import Any
if __package__:
    from .contracts import ROLE_SCHEMA, ROLES, ContractError, canonical_bytes, digest, identifier, identifiers, object_fields, require, safe_json, strict_object
    from .policies import Budget, DeferredWork, recoverable_availability, trusted_output_exhaustion
    from .prompt_catalog import PROMPTS, COMMON_PROMPT, PROMPT_VERSION
else:
    from contracts import ROLE_SCHEMA, ROLES, ContractError, canonical_bytes, digest, identifier, identifiers, object_fields, require, safe_json, strict_object
    from policies import Budget, DeferredWork, recoverable_availability, trusted_output_exhaustion
    from prompt_catalog import PROMPTS, COMMON_PROMPT, PROMPT_VERSION


@dataclass
class StageResult:
    """A task result; its presence is not proof of durable retention."""
    task_id: str
    role: str
    status: str
    input_digest: str
    payload: dict | None
    semantic_metadata: dict
    code: str | None = None
    cache_hit: bool = False

    def summary(self) -> dict:
        """Return status and the actual safe provider metadata, never invented usage."""
        return {"task_id": self.task_id, "role": self.role, "status": self.status,
            "input_digest": self.input_digest, "output_digest": digest(self.payload),
            "prompt_version": PROMPT_VERSION, "code": self.code, "cache_hit": self.cache_hit,
            "semantic_metadata": deepcopy(self.semantic_metadata)}


def response_contract(role: str) -> dict:
    """Describe the adapter response rather than inventing a provider API contract."""
    require(role in ROLES, "clinical_agent_role_invalid")
    return {"schema_version": ROLE_SCHEMA, "required_fields": ["schema_version", "task_id",
        "subject_id", "role", "coverage", "items", "followup_requests"],
        "max_items": 32, "coverage_statuses": ["completed", "unresolved"],
        "instructions": "Return assigned identity and obligations exactly; never invent missing evidence."}


def semantic_metadata(response: Any) -> dict:
    """Preserve safe evidence even when the model's business JSON is malformed."""
    if not isinstance(response, dict) or not isinstance(response.get("result"), dict):
        return {}
    result = response["result"]
    safe_json(result)
    return {key: deepcopy(result[key]) for key in
            ("model", "usage", "metadata", "provider_metadata") if key in result}


def decode_terminal(response: Any) -> tuple[dict, dict]:
    """Accept completed typed JSON/text without dropping provider semantic metadata."""
    require(isinstance(response, dict) and response.get("status") == "completed", "clinical_agent_not_completed")
    result = response.get("result")
    require(isinstance(result, dict), "clinical_agent_result_invalid")
    metadata = semantic_metadata(response)
    if result.get("schema_version") == "agent_result.v1":
        content = result.get("content")
        require(isinstance(content, list) and len(content) == 1 and isinstance(content[0], dict),
                "clinical_agent_content_invalid")
        block = content[0]
        if block.get("type") == "json":
            require(result.get("kind") == "json" and isinstance(block.get("value"), dict),
                    "clinical_agent_content_invalid")
            payload = deepcopy(block["value"])
        else:
            require(block.get("type") == "text" and result.get("kind") == "text"
                    and isinstance(block.get("text"), str), "clinical_agent_content_invalid")
            payload = strict_object(block["text"])
    else:
        require(isinstance(result.get("text"), str), "clinical_agent_result_schema_invalid")
        payload = strict_object(result["text"])
    safe_json(payload)
    return payload, metadata


class AgentRunner:
    """Run declared roles with exact dependency keys and no hidden provider retries."""
    def __init__(self, inputs: Any, budget: Budget) -> None:
        self.inputs = inputs
        self.budget = budget
        self._cache: dict[str, StageResult] = {}
        self._lock = threading.Lock()
        self._key_locks: dict[str, threading.Lock] = {}

    def packet(self, role: str, request: dict, *, task_id: str, obligations: list[str],
               packet_data: dict) -> dict:
        """Build the exact request for sizing before any call is reserved."""
        require(role in ROLES, "clinical_agent_role_invalid")
        identifier(task_id)
        identifiers(obligations, allow_empty=False)
        reserved = {"schema_version", "task_id", "role", "analysis_mode", "subject", "as_of_date",
                    "assigned_obligation_ids", "response_contract", "instructions", "prompt_version", "enable_pharmacological_class"}
        require(not set(packet_data) & reserved, "clinical_packet_override_forbidden")
        return {"schema_version": "clinical_agent_packet.v1", "task_id": task_id,
            "role": role, "analysis_mode": request["analysis_mode"],
            "subject": request["context"]["subject"], "as_of_date": request["as_of_date"],
            "enable_pharmacological_class": request.get("enable_pharmacological_class", False),
            "assigned_obligation_ids": obligations, "response_contract": response_contract(role),
            "instructions": COMMON_PROMPT + "\n\n" + PROMPTS[role],
            "prompt_version": PROMPT_VERSION, **deepcopy(packet_data)}
    def call(self, role: str, request: dict, *, task_id: str, obligations: list[str],
             packet_data: dict, downstream_reserve: int = 0) -> StageResult:
        """Execute once; reserve shared calls before dispatch and keep task identity fixed."""
        packet = self.packet(role, request, task_id=task_id, obligations=obligations, packet_data=packet_data)
        key = digest(packet)
        with self._lock:
            key_lock = self._key_locks.setdefault(key, threading.Lock())
        # Different tasks may execute concurrently. Identical in-flight work does not.
        with key_lock:
            return self._call_once(role, request, task_id, obligations, packet, key, downstream_reserve)

    def _call_once(self, role: str, request: dict, task_id: str, obligations: list[str],
                   packet: dict, key: str, downstream_reserve: int) -> StageResult:
        with self._lock:
            if key in self._cache:
                saved = deepcopy(self._cache[key])
                saved.cache_hit = True
                return saved
        if (len(canonical_bytes(packet)) > self.budget.policy.max_packet_bytes
                or len(packet.get("evidence_packet", [])) > 64):
            return StageResult(task_id, role, "deferred", key, None, {}, "clinical_packet_requires_partitioning")
        try:
            self.budget.reserve(minimum_calls_remaining=downstream_reserve)
        except DeferredWork as exc:
            return StageResult(task_id, role, "deferred", key, None, {}, exc.code)
        require(callable(getattr(self.inputs, "invoke_agent", None)), "clinical_agent_capability_unavailable")
        try:
            response = self.inputs.invoke_agent(role, input=packet, on_error="raise")
        except Exception as exc:
            if trusted_output_exhaustion(exc):
                return StageResult(task_id, role, "failed", key, None, {}, "clinical_agent_output_exhausted")
            if recoverable_availability(exc):
                return StageResult(task_id, role, "failed", key, None, {}, "clinical_agent_availability_exhausted")
            raise ContractError("clinical_agent_runtime_blocked") from None
        metadata = semantic_metadata(response)
        try:
            payload, metadata = decode_terminal(response)
            object_fields(payload, {"schema_version", "task_id", "subject_id", "role", "coverage",
                                    "items", "followup_requests"})
            require(payload["schema_version"] == ROLE_SCHEMA, "clinical_agent_schema_mismatch")
            require(payload["task_id"] == task_id and payload["subject_id"] == request["subject_id"]
                    and payload["role"] == role, "clinical_agent_identity_mismatch")
            require(isinstance(payload["items"], list) and len(payload["items"]) <= self.budget.policy.max_task_items,
                    "clinical_agent_items_invalid")
            require(isinstance(payload["followup_requests"], list) and len(payload["followup_requests"]) <= 8,
                    "clinical_agent_followup_invalid")
            coverage = payload["coverage"]
            require(isinstance(coverage, list), "clinical_agent_coverage_invalid")
            seen = []
            for entry in coverage:
                object_fields(entry, {"obligation_id", "status"})
                seen.append(identifier(entry["obligation_id"]))
                require(isinstance(entry["status"], str) and entry["status"] in {"completed", "unresolved"},
                        "clinical_agent_coverage_invalid")
            require(len(seen) == len(set(seen)) and set(seen) == set(obligations), "clinical_agent_coverage_incomplete")
            status = "completed" if all(x["status"] == "completed" for x in coverage) else "partial"
            stage = StageResult(task_id, role, status, key, payload, metadata)
        except ContractError as exc:
            if exc.code in {"clinical_agent_identity_mismatch", "clinical_authority_material_forbidden"}:
                raise
            # Full wrappers were tried. There is no paid model repair in this release.
            return StageResult(task_id, role, "failed", key, None, metadata, exc.code)
        with self._lock:
            self._cache[key] = deepcopy(stage)
        return stage
