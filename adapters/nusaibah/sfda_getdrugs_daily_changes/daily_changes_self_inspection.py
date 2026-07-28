"""Fail-closed, value-free inspection for the SFDA daily-changes output."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from jsonschema import exceptions as jsonschema_exceptions
from jsonschema.validators import validator_for


NODE_KEY = "sfda_getdrugs_daily_changes"
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_INSPECTION_ERRORS = 100
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class SchemaContractError(RuntimeError):
    """Raised when the runtime-delivered node schema cannot be trusted."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class InspectionError:
    field: str
    keyword: str
    expected: str
    record_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.record_index is None:
            payload.pop("record_index")
        return payload


@dataclass(frozen=True)
class InspectionReport:
    status: str
    payload_schema_version: str
    node_schema_version: str
    node_schema_sha256: str
    payload_sha256: str
    records_inspected: int
    records_failed: int
    error_count: int
    errors: tuple[InspectionError, ...] = field(default_factory=tuple)
    errors_truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "payload_schema_version": self.payload_schema_version,
            "node_schema_version": self.node_schema_version,
            "node_schema_sha256": self.node_schema_sha256,
            "payload_sha256": self.payload_sha256,
            "records_inspected": self.records_inspected,
            "records_failed": self.records_failed,
            "error_count": self.error_count,
            "errors": [error.to_dict() for error in self.errors],
            "errors_truncated": self.errors_truncated,
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_staged_payload(
    staged_payload: Path,
    schema_contract: dict[str, Any],
    *,
    max_errors: int = MAX_INSPECTION_ERRORS,
) -> InspectionReport:
    """Validate the exact serialized output against the Core-owned schema."""

    if max_errors <= 0:
        raise ValueError("max_errors must be positive")

    pointer = _mapping_at(schema_contract, "pointer")
    schema_document = _mapping_at(schema_contract, "schema")
    if _required_text(pointer, "node_key", "schema_node_key_missing") != NODE_KEY:
        raise SchemaContractError("schema_pointer_node_mismatch")

    payload_schema_version = _required_text(
        schema_document,
        "payload_schema_version",
        "payload_schema_version_missing",
    )
    schema_version = _required_text(pointer, "schema_version", "schema_version_missing")
    schema_sha256 = _required_sha256(pointer, "schema_sha256", "schema_hash_invalid")
    record_contract = _mapping_at(schema_document, "results", "contract")
    payload_contract = _mapping_at(schema_document, "payload_contract")

    _reject_external_refs(schema_document)
    record_validator = _validated_validator(record_contract, "record_schema_invalid")
    payload_validator = _validated_validator(payload_contract, "payload_schema_invalid")

    payload_sha256 = sha256_file(staged_payload)
    try:
        payload_size = staged_payload.stat().st_size
    except OSError:
        payload_size = 0
    if payload_size <= 0 or payload_size > MAX_PAYLOAD_BYTES:
        return InspectionReport(
            status="failed",
            payload_schema_version=payload_schema_version,
            node_schema_version=schema_version,
            node_schema_sha256=schema_sha256,
            payload_sha256=payload_sha256,
            records_inspected=0,
            records_failed=0,
            error_count=1,
            errors=(
                InspectionError(
                    field="payload",
                    keyword="size",
                    expected=f"1..{MAX_PAYLOAD_BYTES} bytes",
                ),
            ),
        )

    try:
        with staged_payload.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return InspectionReport(
            status="failed",
            payload_schema_version=payload_schema_version,
            node_schema_version=schema_version,
            node_schema_sha256=schema_sha256,
            payload_sha256=payload_sha256,
            records_inspected=0,
            records_failed=0,
            error_count=1,
            errors=(
                InspectionError(
                    field="payload",
                    keyword="parse",
                    expected="valid JSON object",
                ),
            ),
        )

    errors: list[InspectionError] = []
    total_errors = 0
    errors_truncated = False

    def capture(error: InspectionError) -> None:
        nonlocal total_errors, errors_truncated
        total_errors += 1
        if len(errors) < max_errors:
            errors.append(error)
        else:
            errors_truncated = True

    for validation_error in payload_validator.iter_errors(payload):
        capture(_safe_error(validation_error, record_index=None, prefix="payload"))

    changes = payload.get("changes") if isinstance(payload, dict) else None
    if isinstance(changes, list):
        for index, change in enumerate(changes):
            for validation_error in record_validator.iter_errors(change):
                capture(_safe_error(validation_error, record_index=index, prefix="changes"))

    records_inspected = 1 if isinstance(payload, dict) and payload else 0
    records_failed = 1 if records_inspected == 1 and total_errors > 0 else 0
    return InspectionReport(
        status="passed" if total_errors == 0 and records_inspected == 1 else "failed",
        payload_schema_version=payload_schema_version,
        node_schema_version=schema_version,
        node_schema_sha256=schema_sha256,
        payload_sha256=payload_sha256,
        records_inspected=records_inspected,
        records_failed=records_failed,
        error_count=min(total_errors, max_errors),
        errors=tuple(errors),
        errors_truncated=errors_truncated,
    )


def _safe_error(
    error: jsonschema_exceptions.ValidationError,
    *,
    record_index: int | None,
    prefix: str,
) -> InspectionError:
    parts = [str(part) for part in error.absolute_path]
    field_name = ".".join(parts) if parts else prefix
    if field_name != prefix:
        field_name = f"{prefix}.{field_name}"

    if error.validator == "required" and isinstance(error.instance, dict):
        required = error.validator_value if isinstance(error.validator_value, list) else []
        missing = next((str(key) for key in required if key not in error.instance), None)
        if missing:
            field_name = f"{field_name}.{missing}"

    return InspectionError(
        record_index=record_index,
        field=field_name,
        keyword=str(error.validator or "schema"),
        expected=_safe_expectation(error.validator, error.validator_value),
    )


def _safe_expectation(keyword: Any, validator_value: Any) -> str:
    if keyword == "type":
        if isinstance(validator_value, str):
            return validator_value
        if isinstance(validator_value, list):
            return " | ".join(str(value) for value in validator_value if isinstance(value, str))
        return "declared type"
    if keyword == "required":
        return "required field"
    if keyword == "additionalProperties":
        return "declared properties only"
    if keyword in {"minItems", "maxItems", "minLength", "maxLength", "minimum", "maximum"}:
        return str(validator_value) if isinstance(validator_value, (int, float)) else "configured bound"
    if keyword in {"enum", "const"}:
        return "allowed value"
    if keyword in {"anyOf", "oneOf", "allOf"}:
        return "declared schema combination"
    return "declared constraint"


def _reject_external_refs(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "$ref" and (not isinstance(nested, str) or not nested.startswith("#")):
                raise SchemaContractError("external_schema_ref_rejected")
            _reject_external_refs(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_external_refs(nested)


def _check_schema(schema: Mapping[str, Any], code: str) -> None:
    try:
        validator_for(schema).check_schema(schema)
    except jsonschema_exceptions.SchemaError as exc:
        raise SchemaContractError(code) from exc


def _validated_validator(schema: Mapping[str, Any], code: str) -> Any:
    _check_schema(schema, code)
    validator_class = validator_for(schema)
    return validator_class(schema)


def _mapping_at(value: Mapping[str, Any], *parts: str) -> dict[str, Any]:
    current: Any = value
    for part in parts:
        if not isinstance(current, dict) or not isinstance(current.get(part), dict):
            raise SchemaContractError("schema_contract_missing")
        current = current[part]
    return current


def _required_text(value: Mapping[str, Any], key: str, code: str) -> str:
    selected = value.get(key)
    if not isinstance(selected, str) or not selected.strip():
        raise SchemaContractError(code)
    return selected.strip()


def _required_sha256(value: Mapping[str, Any], key: str, code: str) -> str:
    selected = _required_text(value, key, code).lower()
    if selected.startswith("sha256:"):
        selected = selected[7:]
    if not _SHA256_RE.fullmatch(selected):
        raise SchemaContractError(code)
    return selected
