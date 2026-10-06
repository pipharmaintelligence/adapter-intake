"""Closed deterministic operations; no Agent, transport, storage or scheduler."""

from __future__ import annotations

import json
from typing import Any

if __package__:
    from .source_chunks import build_source_inventory, chunk_inventory, stable_digest
    from .role_packets import GLOBAL_RULE_KEYS, build_role_packet
    from .evidence_verification import verify_finding
    from .reconciliation import reconcile_findings
    from .review_contracts import validate_finding, validate_review_result
else:
    from source_chunks import build_source_inventory, chunk_inventory, stable_digest
    from role_packets import GLOBAL_RULE_KEYS, build_role_packet
    from evidence_verification import verify_finding
    from reconciliation import reconcile_findings
    from review_contracts import validate_finding, validate_review_result


MAX_INPUT_BYTES = 131_072
MAX_RESULT_BYTES = 262_144
MAX_SOURCE_UNITS = 32
MAX_SOURCE_CHARS = 24_000
MAX_CHUNK_CHARS = 6_000
MAX_FINDINGS = 64
MAX_EVIDENCE = 128
OPERATIONS = (
    "prepare_sources", "prepare_packet", "verify_findings",
    "check_coverage", "reconcile_findings", "assemble_preview",
)
_AUTHORITY_KEYS = frozenset({
    "credentials", "credential", "api_key", "access_token", "refresh_token", "secret", "headers",
    "endpoint", "storage_path", "object_key", "callback", "callback_token",
    "provider_response", "provider_request", "raw_payload", "authorization", "password",
    "private_key", "shared_secret", "callback_url", "signed_url",
})


class ReviewToolError(ValueError):
    """Reject invalid data without echoing source values or authority material."""


def _object(value: Any, keys: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or (keys is not None and set(value) != keys):
        raise ReviewToolError("review_tool_object_invalid")
    return value


def _id(value: Any) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 128:
        raise ReviewToolError("review_tool_identity_invalid")
    return value


def _ids(value: Any, *, maximum: int = 64, empty: bool = True) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum or (not value and not empty):
        raise ReviewToolError("review_tool_identity_list_invalid")
    result = [_id(item) for item in value]
    if len(set(result)) != len(result):
        raise ReviewToolError("review_tool_duplicate_identity")
    return result


def _integer(value: Any, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ReviewToolError("review_tool_limit_invalid")
    return value


def _items(value: Any, maximum: int) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ReviewToolError("review_tool_collection_limit")
    return [_object(item) for item in value]


def _texts(value: Any, *, maximum: int = 64, unique: bool = True) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ReviewToolError("review_tool_text_list_invalid")
    if any(not isinstance(item, str) or not item.strip() or len(item) > 2_000 for item in value):
        raise ReviewToolError("review_tool_text_invalid")
    if unique and len({item.strip() for item in value}) != len(value):
        raise ReviewToolError("review_tool_duplicate_text")
    return value


def _json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise ReviewToolError("review_tool_json_invalid") from exc


def _reject_authority(value: Any, depth: int = 0) -> None:
    if depth > 12:
        raise ReviewToolError("review_tool_depth_limit")
    if isinstance(value, dict):
        if any(not isinstance(key, str) or key.lower() in _AUTHORITY_KEYS or key.startswith("_obs_")
               for key in value):
            raise ReviewToolError("review_tool_authority_forbidden")
        for child in value.values():
            _reject_authority(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _reject_authority(child, depth + 1)


def prepare_sources(arguments: dict[str, Any]) -> dict[str, Any]:
    _object(arguments, {"source", "policy"})
    source = _object(arguments["source"], {
        "entity_id", "source_id", "source_version", "extraction_version", "units",
    })
    for key in ("entity_id", "source_id", "source_version", "extraction_version"):
        _id(source[key])
    units = _items(source["units"], MAX_SOURCE_UNITS)
    if not units:
        raise ReviewToolError("review_tool_source_empty")
    total = 0
    for unit in units:
        if not {"locator", "text"} <= set(unit) or set(unit) - {
            "locator", "text", "kind", "quality_flags", "related_locators", "context_only",
        }:
            raise ReviewToolError("review_tool_source_unit_invalid")
        _id(unit["locator"])
        if not isinstance(unit["text"], str):
            raise ReviewToolError("review_tool_source_text_invalid")
        total += len(unit["text"])
        if total > MAX_SOURCE_CHARS:
            raise ReviewToolError("review_tool_source_size_limit")
        if "kind" in unit:
            _id(unit["kind"])
        if "context_only" in unit and type(unit["context_only"]) is not bool:
            raise ReviewToolError("review_tool_context_flag_invalid")
        _ids(unit.get("quality_flags", []), maximum=16)
        _ids(unit.get("related_locators", []), maximum=MAX_SOURCE_UNITS)
    policy = _object(arguments["policy"], {"max_chars", "neighbor_units"})
    _integer(policy["max_chars"], 1, MAX_CHUNK_CHARS)
    _integer(policy["neighbor_units"], 0, 4)
    inventory = build_source_inventory(**source)
    chunks = chunk_inventory(inventory, **policy)
    return {"inventory": inventory, "chunks": chunks,
            "inaccessible_ids": [unit["locator"] for unit in inventory["units"]
                                 if not unit["accessible"]]}


def _prepared(arguments: dict[str, Any]) -> dict[str, Any]:
    prepared = prepare_sources({"source": arguments["source"], "policy": arguments["policy"]})
    if arguments.get("source_hash") != prepared["inventory"]["source_hash"]:
        raise ReviewToolError("review_tool_source_digest_mismatch")
    return prepared


def _methodology(value: Any) -> dict[str, Any]:
    method = _object(value, {"ref", "version", "requirements"})
    _id(method["ref"])
    _id(method["version"])
    _ids(method["requirements"], empty=False)
    return method


def prepare_packet(arguments: dict[str, Any]) -> dict[str, Any]:
    _object(arguments, {"entity_id", "role", "requirement_ids", "allowed_section_ids",
                        "global_rules", "domain_rules", "memory_records", "evidence_refs",
                        "selected_memory_ids", "omitted_context_reasons"})
    _id(arguments["entity_id"])
    _id(arguments["role"])
    for key in ("requirement_ids", "allowed_section_ids", "evidence_refs", "selected_memory_ids"):
        _ids(arguments[key], empty=key not in {"requirement_ids", "allowed_section_ids"})
    for key in ("domain_rules", "omitted_context_reasons"):
        _texts(arguments[key])
    rules = _object(arguments["global_rules"], set(GLOBAL_RULE_KEYS))
    _texts(list(rules.values()), maximum=len(GLOBAL_RULE_KEYS), unique=False)
    for record in _items(arguments["memory_records"], 64):
        _object(record, {"memory_id", "entity_id", "text"})
        _id(record["memory_id"])
        _id(record["entity_id"])
        _texts([record["text"]], maximum=1)
    packet = build_role_packet(**arguments)
    if len(_json_bytes(packet)) > 16_384:
        raise ReviewToolError("review_tool_packet_size_limit")
    return {"packet": packet}


def verify_findings(arguments: dict[str, Any]) -> dict[str, Any]:
    _object(arguments, {"source", "policy", "source_hash", "methodology", "evidence",
                        "findings", "semantic_verdicts"})
    prepared = _prepared(arguments)
    inventory = prepared["inventory"]
    method = _methodology(arguments["methodology"])
    units = {unit["locator"]: unit for unit in inventory["units"]}
    evidence: dict[str, dict[str, Any]] = {}
    for span in _items(arguments["evidence"], MAX_EVIDENCE):
        _object(span, {"ref", "entity_id", "source_hash", "locator", "start", "end", "quote"})
        ref = _id(span["ref"])
        unit = units.get(span["locator"])
        if ref in evidence or unit is None or not unit["accessible"] or unit["context_only"]:
            raise ReviewToolError("review_tool_evidence_locator_invalid")
        if span["entity_id"] != inventory["entity_id"] or span["source_hash"] != inventory["source_hash"]:
            raise ReviewToolError("review_tool_evidence_identity_mismatch")
        start = _integer(span["start"], 0, len(unit["text"]))
        end = _integer(span["end"], start + 1, len(unit["text"]))
        if not isinstance(span["quote"], str) or unit["text"][start:end] != span["quote"]:
            raise ReviewToolError("review_tool_evidence_span_mismatch")
        evidence[ref] = {**span, "strength": "inspected_span"}
    findings = _items(arguments["findings"], MAX_FINDINGS)
    finding_ids = [_id(finding.get("finding_id")) for finding in findings]
    if len(set(finding_ids)) != len(finding_ids):
        raise ReviewToolError("review_tool_duplicate_finding")
    verdicts: dict[str, dict[str, Any]] = {}
    for verdict in _items(arguments["semantic_verdicts"], MAX_FINDINGS):
        _object(verdict, {"schema_version", "finding_id", "evidence_refs", "input_digest",
                          "state", "verifier_id", "reason_code"})
        _id(verdict["verifier_id"])
        _id(verdict["reason_code"])
        finding_id = _id(verdict["finding_id"])
        if finding_id in verdicts:
            raise ReviewToolError("review_tool_duplicate_verdict")
        verdicts[finding_id] = verdict
    if set(verdicts) != set(finding_ids):
        raise ReviewToolError("review_tool_verdict_accounting_mismatch")
    verified = []
    for finding in findings:
        validate_finding(finding, known_requirement_ids=set(method["requirements"]),
                         known_evidence_refs=set(evidence))
        for key in ("finding_id", "entity_id", "requirement_id", "section_id", "proposition_id"):
            _id(finding[key])
        for key in ("evidence_refs", "contradicting_evidence_refs"):
            _ids(finding[key], maximum=MAX_EVIDENCE)
        if finding["evidence_state"] == "supported" and finding["evidence_strength"] != "inspected_span":
            raise ReviewToolError("review_tool_finding_strength_mismatch")
        result = verify_finding(finding, entity_id=inventory["entity_id"],
                                evidence_index=evidence, semantic_verdict=verdicts[finding["finding_id"]])
        verified.append({**finding, **result})
    return {"verified_findings": verified, "methodology_digest": stable_digest(method),
            "source_hash": inventory["source_hash"],
            "semantic_authority_verified": False}


def check_coverage(arguments: dict[str, Any]) -> dict[str, Any]:
    _object(arguments, {"source", "policy", "source_hash", "methodology", "result"})
    prepared = _prepared(arguments)
    method = _methodology(arguments["methodology"])
    result = _object(arguments["result"])
    _items(result.get("coverage"), MAX_SOURCE_UNITS + 64)
    if result.get("persistence_state") != "preview_only":
        raise ReviewToolError("review_tool_mutation_forbidden")
    validated = validate_review_result(result,
        required_requirement_ids=set(method["requirements"]),
        in_scope_source_ids={unit["locator"] for unit in prepared["inventory"]["units"]})
    expected_state = {"review_complete": "completed", "review_complete_with_evidence_gaps": "completed",
                      "review_incomplete": "incomplete", "blocked": "blocked", "failed": "failed"}
    if validated["execution_state"] != expected_state[validated["review_outcome"]]:
        raise ReviewToolError("review_tool_execution_state_mismatch")
    _ids(validated["finding_ids"], maximum=MAX_FINDINGS)
    gaps = sum(item["status"] != "reviewed" or item["outcome"] in {"insufficient", "contradicted"}
               for item in validated["coverage"])
    if validated["review_outcome"] == "review_complete" and gaps:
        raise ReviewToolError("review_tool_false_complete")
    if validated["review_outcome"] == "review_complete_with_evidence_gaps" and not gaps:
        raise ReviewToolError("review_tool_false_gap_state")
    for item in validated["coverage"]:
        if item["obligation_type"] == "source_unit" and item["obligation_id"] in prepared["inaccessible_ids"]:
            if item["status"] != "inaccessible":
                raise ReviewToolError("review_tool_inaccessible_coverage_invalid")
    return {"result": validated, "coverage_count": len(validated["coverage"]), "gap_count": gaps}


def reconcile(arguments: dict[str, Any]) -> dict[str, Any]:
    verified = verify_findings(arguments)
    return {**verified, "ledger": reconcile_findings(verified["verified_findings"])}


def assemble_preview(arguments: dict[str, Any]) -> dict[str, Any]:
    _object(arguments, {"source", "policy", "source_hash", "methodology", "evidence",
                        "findings", "semantic_verdicts", "result"})
    verified = reconcile({key: value for key, value in arguments.items() if key != "result"})
    coverage = check_coverage({key: arguments[key] for key in (
        "source", "policy", "source_hash", "methodology", "result")})
    accepted = [finding for finding in verified["verified_findings"] if finding["accepted"]]
    withheld = [finding for finding in verified["verified_findings"] if not finding["accepted"]]
    if set(coverage["result"]["finding_ids"]) != {item["finding_id"] for item in accepted}:
        raise ReviewToolError("review_tool_accepted_finding_accounting_mismatch")
    complete = coverage["result"]["review_outcome"] in {
        "review_complete", "review_complete_with_evidence_gaps"}
    if complete and verified["ledger"]["blocking_conflict_count"]:
        raise ReviewToolError("review_tool_unresolved_conflict")
    by_requirement = {requirement: [] for requirement in arguments["methodology"]["requirements"]}
    for finding in accepted:
        by_requirement[finding["requirement_id"]].append(finding)
    source_coverage = {item["obligation_id"]: item for item in coverage["result"]["coverage"]
                       if item["obligation_type"] == "source_unit"}
    spans = {span["ref"]: span for span in arguments["evidence"]}
    for finding in accepted:
        for ref in finding["evidence_refs"]:
            disposition = source_coverage[spans[ref]["locator"]]
            if disposition["status"] != "reviewed" or disposition["outcome"] == "not_applicable":
                raise ReviewToolError("review_tool_accepted_source_coverage_mismatch")
    for item in coverage["result"]["coverage"]:
        if item["obligation_type"] == "requirement" and item["outcome"] == "supported":
            if not by_requirement[item["obligation_id"]]:
                raise ReviewToolError("review_tool_supported_coverage_without_finding")
            if any(finding["requirement_id"] == item["obligation_id"] for finding in withheld):
                raise ReviewToolError("review_tool_withheld_finding_gap_hidden")
        if item["obligation_type"] == "requirement" and by_requirement[item["obligation_id"]]:
            if item["status"] != "reviewed" or item["outcome"] == "not_applicable":
                raise ReviewToolError("review_tool_accepted_requirement_coverage_mismatch")
    # No generated synthesis: render exact accepted statements in stable ID order.
    dossier = [{key: finding[key] for key in (
        "finding_id", "requirement_id", "statement", "evidence_refs", "date", "jurisdiction",
        "verification_input_digest")} for finding in sorted(accepted, key=lambda item: item["finding_id"])]
    return {"source_hash": arguments["source_hash"],
            "methodology_digest": verified["methodology_digest"],
            "coverage": coverage["result"], "gap_count": coverage["gap_count"],
            "dossier": dossier, "withheld_finding_ids": sorted(item["finding_id"] for item in withheld),
            "ledger": verified["ledger"], "preview_only": True, "publication_allowed": False,
            "semantic_authority_verified": False, "external_truth_verified": False}


_EXECUTORS = dict(zip(OPERATIONS, (
    prepare_sources, prepare_packet, verify_findings, check_coverage, reconcile, assemble_preview,
)))


def execute_operation(request: Any) -> dict[str, Any]:
    _object(request, {"schema_version", "operation", "arguments"})
    if request["schema_version"] != "review_tool_request.v1" or not isinstance(request["operation"], str) or request["operation"] not in _EXECUTORS:
        raise ReviewToolError("review_tool_operation_not_supported")
    encoded = _json_bytes(request)
    if len(encoded) > MAX_INPUT_BYTES:
        raise ReviewToolError("review_tool_input_size_limit")
    # Snapshot once: caller mutation cannot change what is validated or hashed.
    copied = json.loads(encoded)
    _reject_authority(copied)
    try:
        output = _EXECUTORS[copied["operation"]](_object(copied["arguments"]))
    except ReviewToolError:
        raise
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        raise ReviewToolError("review_tool_contract_invalid") from exc
    result = {
        "schema_version": "review_tool_result.v1", "toolkit_version": "0.1.0",
        "operation": copied["operation"], "request_digest": stable_digest(copied),
        "validation_scope": "structural_and_supplied_verdict_only",
        "agent_call_count": 0, "mutable_call_count": 0, "output": output,
    }
    if len(_json_bytes(result)) > MAX_RESULT_BYTES:
        raise ReviewToolError("review_tool_result_size_limit")
    return result
