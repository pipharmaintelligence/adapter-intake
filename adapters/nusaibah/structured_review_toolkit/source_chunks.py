from __future__ import annotations

import hashlib
import json
from typing import Any


class ChunkingError(ValueError):
    """Raised when source inventory or chunk construction is unsafe."""


def stable_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _text_list(value: Any, *, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ChunkingError(f"{field} must be a list.")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ChunkingError(f"{field} must contain non-empty text.")
        result.append(item.strip())
    if len(result) != len(set(result)):
        raise ChunkingError(f"{field} must contain unique values.")
    return result


def build_source_inventory(
    *,
    entity_id: str,
    source_id: str,
    source_version: str,
    extraction_version: str,
    units: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a complete structural inventory before routing or chunking."""

    if not all(str(value).strip() for value in (entity_id, source_id, source_version, extraction_version)):
        raise ChunkingError("Source identity fields are required.")
    if not isinstance(units, list) or not units:
        raise ChunkingError("At least one source unit is required.")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for unit in units:
        if not isinstance(unit, dict):
            raise ChunkingError("Source units must be objects.")
        locator = str(unit.get("locator", "")).strip()
        if not locator or locator in seen:
            raise ChunkingError("Source unit locators must be unique and non-empty.")
        seen.add(locator)
        text = unit.get("text")
        if not isinstance(text, str):
            raise ChunkingError("Source unit text must be a string.")
        flags = _text_list(unit.get("quality_flags", []), field=f"{locator}.quality_flags")
        related = _text_list(unit.get("related_locators", []), field=f"{locator}.related_locators")
        normalized.append(
            {
                "locator": locator,
                "kind": str(unit.get("kind", "paragraph")).strip() or "paragraph",
                "text": text,
                "quality_flags": flags,
                "related_locators": related,
                "accessible": "inaccessible" not in flags and "ocr_failed" not in flags,
                "context_only": bool(unit.get("context_only", False)),
            }
        )

    known = {unit["locator"] for unit in normalized}
    for unit in normalized:
        related = set(unit["related_locators"])
        if unit["locator"] in related:
            raise ChunkingError("A source unit cannot relate to itself.")
        if not related.issubset(known):
            raise ChunkingError("Related locators must belong to the source inventory.")

    snapshot_material = {
        "entity_id": entity_id,
        "source_id": source_id,
        "source_version": source_version,
        "extraction_version": extraction_version,
        "units": normalized,
    }
    return {
        "schema_version": "review_source_inventory.v1",
        **snapshot_material,
        "source_hash": stable_digest(snapshot_material),
    }


def chunk_inventory(
    inventory: dict[str, Any],
    *,
    max_chars: int,
    neighbor_units: int = 0,
) -> list[dict[str, Any]]:
    """Create structure-aware chunks without dropping source obligations.

    Explicit structural relationships such as table-header/footnote links are
    mandatory context. Neighbors are optional bounded context. Inaccessible
    units remain visible in the inventory but never enter chunk text.
    """

    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 1:
        raise ChunkingError("max_chars must be a positive integer.")
    if isinstance(neighbor_units, bool) or not isinstance(neighbor_units, int) or neighbor_units < 0:
        raise ChunkingError("neighbor_units must be a non-negative integer.")

    units = inventory["units"]
    index_by_locator = {unit["locator"]: index for index, unit in enumerate(units)}
    chunks: list[dict[str, Any]] = []

    for index, unit in enumerate(units):
        if not unit["accessible"]:
            continue

        required_indices = {index}
        pending = [index]
        # Resolve transitive structural dependencies; cycles visit each unit once.
        while pending:
            required_index = pending.pop()
            for locator in units[required_index].get("related_locators", []):
                related_index = index_by_locator[locator]
                related_unit = units[related_index]
                if not related_unit["accessible"]:
                    raise ChunkingError(
                        "An accessible unit depends on inaccessible required structural context."
                    )
                if related_index not in required_indices:
                    required_indices.add(related_index)
                    pending.append(related_index)

        optional_indices: set[int] = set()
        for offset in range(1, neighbor_units + 1):
            if index - offset >= 0:
                optional_indices.add(index - offset)
            if index + offset < len(units):
                optional_indices.add(index + offset)
        optional_indices -= required_indices

        selected: list[dict[str, Any]] = []

        def serialized_length(items: list[dict[str, Any]]) -> int:
            return len("\n".join(item["text"] for item in items))
        for candidate_index in sorted(required_indices):
            candidate = units[candidate_index]
            if not candidate["accessible"]:
                continue
            next_chars = serialized_length([*selected, candidate])
            if next_chars > max_chars:
                raise ChunkingError(
                    "Required source structure exceeds the hard chunk character cap."
                )
            selected.append(candidate)

        for candidate_index in sorted(optional_indices):
            candidate = units[candidate_index]
            if not candidate["accessible"]:
                continue
            next_chars = serialized_length([*selected, candidate])
            if next_chars > max_chars:
                continue
            selected.append(candidate)

        selected.sort(key=lambda item: index_by_locator[item["locator"]])
        locators = [candidate["locator"] for candidate in selected]
        required_locators = {
            units[item_index]["locator"] for item_index in required_indices
        }
        context_only_locators = [
            candidate["locator"]
            for candidate in selected
            if candidate["locator"] not in required_locators or candidate["context_only"]
        ]

        material = {
            "snapshot_hash": inventory["source_hash"],
            "primary_locator": unit["locator"],
            "required_locators": sorted(required_locators),
            "locators": locators,
            "extraction_version": inventory["extraction_version"],
            "policy": {"max_chars": max_chars, "neighbor_units": neighbor_units},
        }
        chunks.append(
            {
                "schema_version": "review_source_chunk.v1",
                "chunk_id": f"chunk:{stable_digest(material)}",
                "snapshot_id": f"{inventory['source_id']}@{inventory['source_version']}",
                "entity_id": inventory["entity_id"],
                "source_hash": inventory["source_hash"],
                "chunk_digest": stable_digest(
                    {"material": material, "text": [candidate["text"] for candidate in selected]}
                ),
                "locators": locators,
                "text": "\n".join(candidate["text"] for candidate in selected),
                "quality_flags": sorted(
                    {
                        flag
                        for candidate in selected
                        for flag in candidate["quality_flags"]
                    }
                ),
                "context_only_locators": context_only_locators,
            }
        )

    accounted = {unit["locator"] for unit in units}
    represented = {
        locator for chunk in chunks for locator in chunk["locators"]
    }
    inaccessible = {
        unit["locator"] for unit in units if not unit["accessible"]
    }
    if accounted != represented | inaccessible:
        raise ChunkingError("Chunking silently dropped source units.")
    return chunks
