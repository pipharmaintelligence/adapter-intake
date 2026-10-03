from __future__ import annotations

import re
from typing import Any


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def safe_proof_failure_detail(value: Any) -> dict[str, Any] | None:
    """Mirror the generic value-free Agent-contract proof boundary for tests."""

    if not isinstance(value, dict):
        return None
    if value.get("schema_version") != "proof_failure_detail.v1":
        return None
    if value.get("proof_kind") != "agent_contract":
        return None

    allowed = {"schema_version", "proof_kind", "role", "stage", "rule", "field"}
    if set(value) - allowed:
        return None

    for key in ("role", "stage", "rule"):
        current = value.get(key)
        if not isinstance(current, str) or _IDENTIFIER.fullmatch(current) is None:
            return None

    field = value.get("field")
    if field is not None and (
        not isinstance(field, str) or _IDENTIFIER.fullmatch(field) is None
    ):
        return None

    result = {
        "schema_version": "proof_failure_detail.v1",
        "proof_kind": "agent_contract",
        "role": value["role"],
        "stage": value["stage"],
        "rule": value["rule"],
    }
    if field is not None:
        result["field"] = field
    return result
