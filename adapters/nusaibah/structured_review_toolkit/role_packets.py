from __future__ import annotations

from typing import Any


class RolePacketError(ValueError):
    """Raised when a deterministic specialist packet violates context policy."""


GLOBAL_RULE_KEYS = (
    "entity_isolation",
    "evidence_attribution",
    "uncertainty",
    "mutation_prohibition",
)


def _unique_text(values: list[Any], *, field: str, allow_empty: bool = True) -> list[str]:
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise RolePacketError(f"{field} must contain non-empty text.")
        normalized.append(value.strip())
    if not allow_empty and not normalized:
        raise RolePacketError(f"{field} must not be empty.")
    if len(normalized) != len(set(normalized)):
        raise RolePacketError(f"{field} must contain unique values.")
    return normalized


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

    if not isinstance(entity_id, str) or not entity_id.strip():
        raise RolePacketError("entity_id is required.")
    if not isinstance(role, str) or not role.strip():
        raise RolePacketError("role is required.")

    requirement_ids = _unique_text(
        requirement_ids,
        field="requirement_ids",
        allow_empty=False,
    )
    allowed_section_ids = _unique_text(
        allowed_section_ids,
        field="allowed_section_ids",
        allow_empty=False,
    )
    domain_rules = _unique_text(domain_rules, field="domain_rules")
    evidence_refs = _unique_text(evidence_refs, field="evidence_refs")
    selected_memory_ids = _unique_text(
        selected_memory_ids,
        field="selected_memory_ids",
    )
    omitted_context_reasons = _unique_text(
        omitted_context_reasons,
        field="omitted_context_reasons",
    )

    missing = [
        key
        for key in GLOBAL_RULE_KEYS
        if not isinstance(global_rules.get(key), str) or not global_rules[key].strip()
    ]
    if missing:
        raise RolePacketError(f"Missing global rules: {missing}")

    by_id: dict[str, dict[str, Any]] = {}
    for record in memory_records:
        if not isinstance(record, dict):
            raise RolePacketError("Every memory record must be an object.")
        record_id = str(record.get("memory_id", "")).strip()
        if not record_id:
            raise RolePacketError("Every memory record needs memory_id.")
        if record_id in by_id:
            raise RolePacketError("Memory record IDs must be unique.")
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
        "entity_id": entity_id.strip(),
        "role": role.strip(),
        "requirement_ids": requirement_ids,
        "allowed_section_ids": allowed_section_ids,
        "global_rules": {key: global_rules[key].strip() for key in GLOBAL_RULE_KEYS},
        "domain_rules": domain_rules,
        "selected_memory": selected,
        "evidence_refs": evidence_refs,
        "selection_explanation": {
            "selected_memory_ids": selected_memory_ids,
            "omitted_context_reasons": omitted_context_reasons,
        },
    }
