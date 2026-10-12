"""Resource-neutral checks and bounded name resolution for reviewed MCP reads.

Contracts and projections are supplied by adapter code, never by caller input.
This module does not execute transport, admit roles, or establish authority.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Callable


_INVOCATION_ID = re.compile(
    r"^mti_(?:[a-f0-9]{32}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$"
)
ErrorFactory = Callable[[str], Exception]


@dataclass(frozen=True)
class ReadContract:
    """One reviewed role/capability tuple and its record ceiling."""

    role: str
    capability_ref: str
    tool_handle: str
    tool_server_ref: str
    max_records: int


@dataclass(frozen=True)
class NameProfile:
    """Fields from an adapter's safe projection, independent of resource type."""

    id_key: str
    candidate_keys: tuple[str, ...]
    name_key: str = "name"
    ignored_nouns: tuple[str, ...] = ()


def validate_read_result(
    result: Any, contract: ReadContract, error: ErrorFactory,
    *, requested_limit: int | None = None,
) -> None:
    """Check the trusted envelope without mistaking it for admission proof."""
    if not isinstance(result, dict):
        raise error("tool_envelope_invalid")
    if result.get("status") != "completed":
        raise error("tool_not_completed")
    if (
        result.get("operation") != "invoke"
        or result.get("capability_ref") != contract.capability_ref
        or result.get("tool_handle") != contract.tool_handle
        or result.get("tool_server_ref") != contract.tool_server_ref
    ):
        raise error("tool_identity_mismatch")
    records = result.get("records")
    if not isinstance(records, list):
        raise error("records_invalid")
    proof = result.get("provenance")
    if not isinstance(proof, dict):
        raise error("tool_provenance_invalid")
    invocation_id = proof.get("invocation_id")
    if (
        proof.get("runtime_mcp_tool") is not True
        or proof.get("role") != contract.role
        or not isinstance(invocation_id, str)
        or _INVOCATION_ID.fullmatch(invocation_id) is None
        or type(proof.get("record_count")) is not int
        or proof["record_count"] != len(records)
        or type(proof.get("cache_hit")) is not bool
        or type(proof.get("duration_ms")) is not int
        or proof["duration_ms"] < 0
    ):
        raise error("tool_provenance_invalid")
    ceiling = contract.max_records
    if requested_limit is not None:
        ceiling = min(ceiling, requested_limit)
    if len(records) > ceiling:
        raise error("response_limit_exceeded")


def coverage(result: dict[str, Any], error: ErrorFactory) -> str:
    """Missing pagination is unknown; row count never proves completeness."""
    if "has_more" not in result:
        return "unknown"
    more = result["has_more"]
    if type(more) is not bool or (more and not result["records"]):
        raise error("pagination_invalid")
    return "partial" if more else "complete"


def search_text(value: str, profile: NameProfile) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    words = re.sub(r"[\W_]+", " ", text, flags=re.UNICODE).strip().split()
    if words and words[0] in profile.ignored_nouns:
        words = words[1:]
    if words and words[-1] in profile.ignored_nouns:
        words = words[:-1]
    return " ".join(words)


def rank_names(
    term: str, records: list[dict[str, Any]], profile: NameProfile,
) -> list[dict[str, Any]]:
    """At most three deterministic spelling candidates from safe records."""
    scored = []
    for record in records:
        identifier = record[profile.id_key]
        name = record.get(profile.name_key, identifier)
        normalized = [search_text(identifier, profile), search_text(name, profile)]
        normalized.extend(token for token in normalized[-1].split() if len(token) >= 4)
        if term in normalized:
            priority, similarity, kind = 0, 1.0, "exact"
        elif len(term) >= 3 and any(term in item for item in normalized):
            priority, similarity, kind = 1, 1.0, "partial_name"
        else:
            similarity = max(
                (SequenceMatcher(None, term, item).ratio()
                 for item in normalized if len(term) >= 4 and len(item) >= 4),
                default=0.0,
            )
            if similarity < 0.74:
                continue
            priority, kind = 2, "close_spelling"
        safe = {key: record[key] for key in profile.candidate_keys if key in record}
        safe[profile.name_key] = name
        safe["match_type"] = kind
        scored.append((priority, -similarity, name.casefold(), identifier, safe))
    scored.sort(key=lambda item: item[:4])
    return [item[-1] for item in scored[:3]]


def resolve_names(
    *, query: str, records: list[dict[str, Any]], result: dict[str, Any],
    contract: ReadContract, profile: NameProfile, invoke_tool: Callable[..., Any],
    project: Callable[[list[Any], dict[str, Any]], list[dict[str, Any]]],
    fallback_input: dict[str, Any] | None, error: ErrorFactory,
) -> dict[str, Any]:
    """Search one approved scope; optional discovery failure stays unresolved.

    The adapter builds the fallback selectors and checks scope in its projection.
    The same reviewed role is used for both calls. No extra paging or retries.
    """
    sample = records
    source = "filtered_search"
    completeness = coverage(result, error)
    term = search_text(query, profile)
    if not records and len(term) >= 4 and fallback_input is not None:
        try:
            discovered = invoke_tool(contract.role, input=dict(fallback_input), on_error="raise")
            validate_read_result(discovered, contract, error)
            completeness = coverage(discovered, error)
            sample = project(discovered["records"], fallback_input)
            source = "bounded_catalogue"
        except Exception:
            return {
                "query": query.strip(), "status": "unresolved",
                "requires_confirmation": True, "coverage": "unknown",
                "source": "discovery_unavailable", "candidates": [],
            }
    ranked = rank_names(term, sample, profile)
    exact = [row for row in ranked if row["match_type"] == "exact"]
    if len(exact) > 1:
        status = "ambiguous"
    elif exact:
        status = "exact"
    elif ranked:
        status = "suggestions"
    else:
        status = "no_match" if completeness == "complete" else "unresolved"
    resolved_id = None
    if status == "exact":
        identifier = exact[0][profile.id_key]
        if search_text(identifier, profile) == term or completeness == "complete":
            resolved_id = identifier
    output = {
        "query": query.strip(), "status": status,
        "requires_confirmation": resolved_id is None,
        "coverage": completeness, "source": source,
        "candidates": (exact or ranked)[:3],
    }
    if resolved_id is not None:
        output["resolved_id"] = resolved_id
    return output
