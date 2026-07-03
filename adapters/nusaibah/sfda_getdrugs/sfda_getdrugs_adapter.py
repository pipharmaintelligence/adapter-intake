from __future__ import annotations

from typing import Any

from adapters.base import Adapter


class SfdaGetDrugsAdapter(Adapter):
    """Normalize resolved SFDA GetDrugs records into a stable output contract.

    This adapter does not call SFDA directly and does not paginate HTTP pages.
    A governed crawler runtime should POST page-by-page to the source, stop at
    the last page, and inject accumulated safe records under
    inputs["sfda_response"]["records"].

    Saving is intentionally not implemented here. The adapter only emits safe
    structured outputs for later Assets/Core validation and publishing.
    """

    key = "sfda.getdrugs"
    version = "0.1.0"

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        sfda_response = inputs.get("sfda_response", {})
        records = sfda_response.get("records", [])
        metadata = sfda_response.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        normalized_records = [
            self._normalize_record(record, index=index)
            for index, record in enumerate(records, start=1)
            if isinstance(record, dict)
        ]

        page_summary = {
            "start_page": _read_optional_int(metadata, "start_page"),
            "last_page": _read_optional_int(metadata, "last_page"),
            "pages_crawled": _read_optional_int(metadata, "pages_crawled"),
            "last_page_detected": _read_bool(metadata, "last_page_detected"),
            "pagination_truncated": _read_bool(metadata, "pagination_truncated"),
            "stop_reason": _clean_text(metadata.get("stop_reason", "")),
            "input_record_count": len(records),
            "normalized_record_count": len(normalized_records),
        }

        return {
            "response_version": "1",
            "status": "success",
            "outputs": {
                "drugs": {
                    "records": normalized_records,
                    "page_summary": page_summary,
                }
            },
            "logs": [
                {
                    "level": "info",
                    "message": "SFDA GetDrugs records normalized",
                }
            ],
            "metrics": {
                "input_record_count": len(records),
                "normalized_record_count": len(normalized_records),
                "pages_crawled": page_summary["pages_crawled"] or 0,
            },
        }

    @staticmethod
    def _normalize_record(record: dict[str, Any], index: int) -> dict[str, Any]:
        """Convert one SFDA row into stable field names."""

        return {
            "row_number": index,
            "source_page": _read_optional_int(record, "source_page", "page", "Page"),
            "trade_name": _clean_text(
                _first_present(record, "TradeName", "Trade Name", "tradeName", "trade_name")
            ),
            "scientific_name": _clean_text(
                _first_present(record, "scientificName", "ScientificName", "scientific_name")
            ),
            "agent": _clean_text(
                _first_present(record, "Agent", "agent")
            ),
            "manufacturer_name": _clean_text(
                _first_present(record, "ManufacturerName", "Manufacturer Name", "manufacturer_name")
            ),
            "registration_number": _clean_text(
                _first_present(record, "RegNo", "RegistrationNo", "registration_number", "reg_no")
            ),
        }


def _first_present(record: dict[str, Any], *keys: str) -> Any:
    """Return the first non-empty value from a row using possible source keys."""

    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value

    return ""


def _clean_text(value: Any) -> str:
    """Normalize text while preserving Arabic, English, and scientific strings."""

    if value is None:
        return ""

    return " ".join(str(value).strip().split())


def _read_optional_int(source: dict[str, Any], *keys: str) -> int | None:
    """Read an optional integer from a metadata or record dictionary."""

    value = _first_present(source, *keys)

    if isinstance(value, int):
        return value

    if isinstance(value, str) and value.isdigit():
        return int(value)

    return None


def _read_bool(source: dict[str, Any], key: str) -> bool:
    """Read a conservative boolean from safe metadata."""

    value = source.get(key)

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}

    return False
