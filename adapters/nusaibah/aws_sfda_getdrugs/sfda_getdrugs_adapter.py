from __future__ import annotations

from pathlib import Path
from typing import Any

from adapters.base import Adapter
from system.native_file import NativeFileInputError, get_native_file_input

try:
    from .sfda_self_inspection import InspectionReport, inspect_staged_payload
except ImportError:  # Loaded as a reviewed standalone adapter module.
    from sfda_self_inspection import InspectionReport, inspect_staged_payload


class SfdaGetDrugsAdapter(Adapter):
    """Normalize resolved SFDA GetDrugs records into a stable output contract.

    This adapter does not call SFDA directly and does not paginate HTTP pages.
    A governed crawler/runtime source should resolve page data, then inject safe
    records under ``inputs["sfda_response"]`` either inline or as a
    ``python_native_file`` runtime payload.

    The adapter never calls DLM Core. It emits the normalized payload and can
    inspect the exact serialized staging file before the Assets runtime requests
    provider publication.
    """

    key = "aws.sfda.getdrugs"
    version = "0.1.0"

    def self_inspect(
        self,
        staged_payload: Path,
        schema_contract: dict[str, Any],
    ) -> InspectionReport:
        """Validate the exact staged payload without exposing record values."""

        return inspect_staged_payload(staged_payload, schema_contract)

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        records, metadata = _sfda_records_and_metadata(inputs)

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
        """Preserve one SFDA row and add stable convenience field names."""

        normalized = {
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
                or _path(record, "drugAgents", 0, "agent", "nameEn")
                or _path(record, "company", "nameEn")
            ),
            "manufacturer_name": _clean_text(
                _first_present(record, "ManufacturerName", "Manufacturer Name", "manufacturer_name")
                or _path(record, "drugManufacturers", 0, "manufacture", "nameEn")
                or _path(record, "company", "nameEn")
            ),
            "registration_number": _clean_text(
                _first_present(
                    record,
                    "RegNo",
                    "RegistrationNo",
                    "registration_number",
                    "reg_no",
                    "registerNumber",
                    "oldRegisterNumber",
                    "referenceNumber",
                )
            ),
        }
        preserved = _json_safe_record(record)
        preserved.update(normalized)
        return preserved


def _sfda_records_and_metadata(inputs: dict[str, Any]) -> tuple[list[Any], dict[str, Any]]:
    sfda_response = inputs.get("sfda_response", {})
    if not isinstance(sfda_response, dict):
        return [], {}

    metadata = sfda_response.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    if sfda_response.get("mode") == "python_native_file":
        try:
            native = get_native_file_input(inputs, "sfda_response", allowed_formats={"jsonl", "ndjson", "json"})
        except NativeFileInputError:
            return [], metadata

        if native.format == "json":
            decoded = native.read_json()
            if isinstance(decoded, dict):
                records = decoded.get("records", [])
                decoded_metadata = decoded.get("metadata", {})
                if isinstance(decoded_metadata, dict) and not metadata:
                    metadata = decoded_metadata
                return records if isinstance(records, list) else [], metadata
            if isinstance(decoded, list):
                return decoded, metadata
            return [], metadata

        return [record for record in native.iter_jsonl_objects() if isinstance(record, dict)], metadata

    records = sfda_response.get("records", [])
    return records if isinstance(records, list) else [], metadata


def _json_safe_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe shallow source record copy for output records."""

    safe: dict[str, Any] = {}
    for key, value in record.items():
        if isinstance(key, str):
            safe[key] = _json_safe_value(value)
    return safe


def _json_safe_value(value: Any) -> Any:
    """Keep source data values that can be represented safely as JSON."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe_value(nested) for key, nested in value.items() if isinstance(key, str)}
    return str(value)


def _first_present(record: dict[str, Any], *keys: str) -> Any:
    """Return the first non-empty value from a row using possible source keys."""

    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value

    return ""


def _path(source: Any, *parts: Any) -> Any:
    """Read a small nested value from a live crawler-resolved record."""

    current = source
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and isinstance(part, int) and 0 <= part < len(current):
            current = current[part]
        else:
            return ""
    return current if current not in (None, "") else ""


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
