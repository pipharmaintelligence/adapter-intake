from __future__ import annotations
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from adapters.base import Adapter


class EpoBiblioLookupAdapter(Adapter):
    """Summarize normalized EPO bibliographic Runtime Source records.

    The adapter is intentionally API-blind. It does not know the EPO request
    connection, authentication, transport, storage, or raw-response details.
+    On ``local_worker`` or ECS, trusted Runtime Source
    infrastructure resolves the provider call first and injects normalized
    records into ``inputs["epo_response"]``.
    """

    key = "nusaibah.epo_biblio_lookup"
    version = "0.1.0"

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Return a bounded bibliographic summary from resolved records."""

        records = _records(inputs, "epo_response")
        publication_numbers = _collect_named_text(records, {"doc-number", "doc_number"}, limit=10)
        titles = _collect_named_text(records, {"invention-title", "invention_title"}, limit=10)
        countries = _collect_named_text(records, {"country"}, limit=10)
        kinds = _collect_named_text(records, {"kind"}, limit=10)

        root_keys = sorted({str(key) for record in records for key in record.keys()})[:40]

        return {
            "response_version": "1",
            "status": "success",
            "outputs": {
                "biblio": {
                    "record_count": len(records),
                    "publication_numbers": publication_numbers,
                    "titles": titles,
                    "countries": countries,
                    "kinds": kinds,
                    "root_keys": root_keys,
                    "input_authority": "runtime_source_resolved_records",
                }
            },
            "logs": [
                {
                    "level": "info",
                    "message": "EPO bibliographic Runtime Source records summarized.",
                }
            ],
            "metrics": {
                "record_count": len(records),
                "publication_number_count": len(publication_numbers),
                "title_count": len(titles),
            },
        }


def _records(inputs: dict[str, Any], role: str) -> list[dict[str, Any]]:
    value = inputs.get(role)
    if not isinstance(value, dict):
        raise ValueError(f"{role} input must be an object.")

    records = value.get("records")
    if not isinstance(records, list):
        raise ValueError(f"{role}.records must be a list.")

    return [record for record in records if isinstance(record, dict)]


def _collect_named_text(
    records: Iterable[dict[str, Any]],
    names: set[str],
    *,
    limit: int,
) -> list[str]:
    """Collect unique bounded text values for local-name-equivalent keys."""

    wanted = {_normalized_name(name) for name in names}
    values: list[str] = []
    seen: set[str] = set()

    for record in records:
        for key, value in _walk(record):
            if _normalized_name(key) not in wanted:
                continue
            text = _text(value)
            if text is None or text in seen:
                continue
            seen.add(text)
            values.append(text)
            if len(values) >= limit:
                return values
    return values


def _walk(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, nested in value.items():
            yield str(key), nested
            yield from _walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk(nested)


def _normalized_name(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def _text(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, dict):
        # XML normalization may preserve element text as ``#text`` when the
        # element also has attributes or children.
        text = value.get("#text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    return None
