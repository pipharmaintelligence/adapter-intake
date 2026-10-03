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

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for unit in units:
        locator = str(unit.get("locator", "")).strip()
        if not locator or locator in seen:
            raise ChunkingError("Source unit locators must be unique and non-empty.")
        seen.add(locator)
        text = unit.get("text")
        if not isinstance(text, str):
            raise ChunkingError("Source unit text must be a string.")
        flags = list(unit.get("quality_flags", []))
        normalized.append(
            {
                "locator": locator,
                "kind": str(unit.get("kind", "paragraph")),
                "text": text,
                "quality_flags": flags,
                "accessible": "inaccessible" not in flags and "ocr_failed" not in flags,
                "context_only": bool(unit.get("context_only", False)),
            }
        )

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
    """Create structure-aware chunks without dropping inventory units."""

    if max_chars < 1 or neighbor_units < 0:
        raise ChunkingError("Chunk limits must be positive and finite.")

    units = inventory["units"]
    chunks: list[dict[str, Any]] = []

    for index, unit in enumerate(units):
        if not unit["accessible"]:
            continue

        selected_indices = {index}
        for offset in range(1, neighbor_units + 1):
            if index - offset >= 0:
                selected_indices.add(index - offset)
            if index + offset < len(units):
                selected_indices.add(index + offset)

        selected = [units[i] for i in sorted(selected_indices)]
        rendered_parts: list[str] = []
        locators: list[str] = []
        context_only_locators: list[str] = []
        for candidate in selected:
            part = candidate["text"]
            if sum(len(item) for item in rendered_parts) + len(part) > max_chars:
                if candidate["locator"] == unit["locator"]:
                    raise ChunkingError("A source unit exceeds the hard chunk character cap.")
                continue
            rendered_parts.append(part)
            locators.append(candidate["locator"])
            if candidate["locator"] != unit["locator"] or candidate["context_only"]:
                context_only_locators.append(candidate["locator"])

        material = {
            "snapshot_hash": inventory["source_hash"],
            "primary_locator": unit["locator"],
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
                "chunk_digest": stable_digest({"material": material, "text": rendered_parts}),
                "locators": locators,
                "text": "\n".join(rendered_parts),
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
