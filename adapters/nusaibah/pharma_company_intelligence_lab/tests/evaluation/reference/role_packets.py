from __future__ import annotations

from typing import Any


class RolePacketError(ValueError):
    """Raised when a deterministic specialist packet violates context policy."""


GLOBAL_RULE_KEYS = (
    "company_isolation",
    "evidence_attribution",
    "uncertainty",
    "mutation_prohibition",
)


def build_role_packet(
    *,
    entity_id: str,
    role: str,
    requirement_ids: list[str],
    allowed_section_ids: list[str],
    global_rules: dict[str, str],
    domain_rules: list[str],
    memory_records: list[dict[str, Any]],
    evidence_refs: list[str],
    selected_memory_ids: list[str],
    omitted_context_reasons: list[str],
) -> dict[str, Any]:
    """Build a deterministic, bounded role packet without changing authority."""

    if not entity_id or not role:
        raise RolePacketError("entity_id and role are required.")
    if not requirement_ids:
        raise RolePacketError("At least one requirement is required.")
    if not allowed_section_ids:
        raise RolePacketError("At least one allowed section is required.")

    missing = [key for key in GLOBAL_RULE_KEYS if not str(global_rules.get(key, "")).strip()]
    if missing:
        raise RolePacketError(f"Missing global rules: {missing}")

    by_id: dict[str, dict[str, Any]] = {}
    for record in memory_records:
        record_id = str(record.get("memory_id", "")).strip()
        if not record_id:
            raise RolePacketError("Every memory record needs memory_id.")
        if record.get("entity_id") != entity_id:
            raise RolePacketError("Cross-entity memory is forbidden.")
        by_id[record_id] = record

    selected: list[dict[str, Any]] = []
    for memory_id in selected_memory_ids:
        if memory_id not in by_id:
            raise RolePacketError("Selected memory ID is unavailable.")
        selected.append(dict(by_id[memory_id]))

    return {
        "schema_version": "review_role_packet.v1",
        "entity_id": entity_id,
        "role": role,
        "requirement_ids": list(dict.fromkeys(requirement_ids)),
        "allowed_section_ids": list(dict.fromkeys(allowed_section_ids)),
        "global_rules": {key: global_rules[key] for key in GLOBAL_RULE_KEYS},
        "domain_rules": list(domain_rules),
        "selected_memory": selected,
        "evidence_refs": list(dict.fromkeys(evidence_refs)),
        "selection_explanation": {
            "selected_memory_ids": list(selected_memory_ids),
            "omitted_context_reasons": list(omitted_context_reasons),
        },
    }


def assert_formatter_packet_minimal(
    *,
    role_packet: dict[str, Any],
    evidence_notes: list[str],
    raw_search_payload_present: bool,
) -> dict[str, Any]:
    """Build the formatting continuation without replaying unnecessary source context."""

    if raw_search_payload_present:
        raise RolePacketError("Formatter packet must not receive raw provider payloads.")
    if not evidence_notes:
        raise RolePacketError("Formatter requires bounded evidence notes.")
    return {
        "schema_version": "review_formatter_packet.v1",
        "entity_id": role_packet["entity_id"],
        "role": role_packet["role"],
        "requirement_ids": list(role_packet["requirement_ids"]),
        "allowed_section_ids": list(role_packet["allowed_section_ids"]),
        "evidence_refs": list(role_packet["evidence_refs"]),
        "evidence_notes": list(evidence_notes),
    }
