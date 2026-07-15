"""Fail-closed, value-free inspection for the SFDA staged dataset payload."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from jsonschema import exceptions as jsonschema_exceptions
from jsonschema.validators import validator_for


NODE_KEY = "aws_sfda_getdrugs_daily_snapshot"
PAYLOAD_SCHEMA_VERSION = "sfda_getdrugs.records.v1"
MAX_POINTER_BYTES = 64 * 1024
MAX_SCHEMA_BYTES = 1024 * 1024
MAX_INSPECTION_ERRORS = 100
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class SchemaContractError(RuntimeError):
    """Raised when the read-only node schema cannot be trusted."""

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

    @classmethod
    def failed_contract(
        cls,
        *,
        code: str,
        node_schema_version: str = "unknown",
        node_schema_sha256: str = "",
        payload_sha256: str = "",
    ) -> "InspectionReport":
        return cls(
            status="failed",
            payload_schema_version=PAYLOAD_SCHEMA_VERSION,
            node_schema_version=node_schema_version,
            node_schema_sha256=node_schema_sha256,
            payload_sha256=payload_sha256,
            records_inspected=0,
            records_failed=0,
            error_count=1,
            errors=(InspectionError(field="schema", keyword="contract", expected=code),),
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_node_schema(node_root: Path) -> dict[str, Any]:
    """Load and verify the current schema pointer without calling DLM Core."""

    schema_root = node_root.resolve() / "schema"
    snapshots_root = (schema_root / "snapshots").resolve()
    pointer_path = schema_root / "current.json"
    pointer = _read_json_object(
        pointer_path,
        max_bytes=MAX_POINTER_BYTES,
        missing_code="schema_pointer_missing",
        invalid_code="schema_pointer_invalid",
    )
    if pointer.get("node_key") != NODE_KEY:
        raise SchemaContractError("schema_pointer_node_mismatch")

    schema_version = _required_text(pointer, "schema_version", "schema_version_missing")
    schema_file = _required_text(pointer, "schema_file", "schema_file_missing")
    declared_sha256 = _required_text(pointer, "schema_sha256", "schema_hash_missing").lower()
    if not _SHA256_RE.fullmatch(declared_sha256):
        raise SchemaContractError("schema_hash_invalid")

    relative = Path(schema_file)
    if relative.is_absolute() or ".." in relative.parts:
        raise SchemaContractError("schema_path_outside_snapshots")

    selected_path = (schema_root / relative).resolve()
    try:
        selected_path.relative_to(snapshots_root)
    except ValueError as exc:
        raise SchemaContractError("schema_path_outside_snapshots") from exc

    schema_bytes = _read_bounded_bytes(
        selected_path,
        max_bytes=MAX_SCHEMA_BYTES,
        missing_code="schema_file_missing",
        oversize_code="schema_file_too_large",
    )
    actual_sha256 = hashlib.sha256(schema_bytes).hexdigest()
    if not hmac.compare_digest(actual_sha256, declared_sha256):
        raise SchemaContractError("schema_hash_mismatch")

    try:
        schema_document = json.loads(schema_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SchemaContractError("schema_file_invalid_json") from exc
    if not isinstance(schema_document, dict):
        raise SchemaContractError("schema_file_not_object")

    record_contract = _mapping_at(schema_document, "results", "contract")
    payload_contract = _mapping_at(schema_document, "payload_contract")
    if schema_document.get("payload_schema_version") != PAYLOAD_SCHEMA_VERSION:
        raise SchemaContractError("payload_schema_version_mismatch")

    _reject_external_refs(schema_document)
    _check_schema(record_contract, "record_schema_invalid")
    _check_schema(payload_contract, "payload_schema_invalid")

    return {
        "pointer": {
            "node_key": NODE_KEY,
            "schema_version": schema_version,
            "schema_file": schema_file,
            "schema_sha256": actual_sha256,
            "validation_mode": str(pointer.get("validation_mode") or "nullable_tolerant"),
        },
        "schema": schema_document,
    }


def inspect_staged_payload(
    staged_payload: Path,
    schema_contract: dict[str, Any],
    *,
    max_errors: int = MAX_INSPECTION_ERRORS,
) -> InspectionReport:
    """Validate every record from the exact serialized staging file."""

    if max_errors <= 0:
        raise ValueError("max_errors must be positive")

    pointer = _mapping_at(schema_contract, "pointer")
    schema_document = _mapping_at(schema_contract, "schema")
    schema_version = _required_text(pointer, "schema_version", "schema_version_missing")
    schema_sha256 = _required_text(pointer, "schema_sha256", "schema_hash_missing")
    record_contract = _mapping_at(schema_document, "results", "contract")
    payload_contract = _mapping_at(schema_document, "payload_contract")

    _reject_external_refs(schema_document)
    record_validator = _validated_validator(record_contract, "record_schema_invalid")
    payload_validator = _validated_validator(payload_contract, "payload_schema_invalid")

    payload_sha256 = sha256_file(staged_payload)
    try:
        with staged_payload.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return InspectionReport(
            status="failed",
            payload_schema_version=PAYLOAD_SCHEMA_VERSION,
            node_schema_version=schema_version,
            node_schema_sha256=schema_sha256,
            payload_sha256=payload_sha256,
            records_inspected=0,
            records_failed=0,
            error_count=1,
            errors=(InspectionError(field="payload", keyword="parse", expected="valid JSON object"),),
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

    records = payload.get("records", []) if isinstance(payload, dict) else []
    records_inspected = 0
    records_failed = 0
    if isinstance(records, list):
        for index, record in enumerate(records):
            records_inspected += 1
            failed = False
            for validation_error in record_validator.iter_errors(record):
                failed = True
                capture(_safe_error(validation_error, record_index=index))
            if failed:
                records_failed += 1

    status = "passed" if total_errors == 0 else "failed"
    return InspectionReport(
        status=status,
        payload_schema_version=PAYLOAD_SCHEMA_VERSION,
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
    prefix: str = "",
) -> InspectionError:
    parts = [str(part) for part in error.absolute_path]
    field_name = ".".join(parts) if parts else "record"
    if prefix:
        field_name = f"{prefix}.{field_name}" if field_name != "record" else prefix

    if error.validator == "required" and isinstance(error.instance, dict):
        required = error.validator_value if isinstance(error.validator_value, list) else []
        missing = next((str(key) for key in required if key not in error.instance), None)
        if missing:
            field_name = f"{field_name}.{missing}" if field_name not in {"record", "payload"} else missing

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


def _read_json_object(
    path: Path,
    *,
    max_bytes: int,
    missing_code: str,
    invalid_code: str,
) -> dict[str, Any]:
    raw = _read_bounded_bytes(
        path,
        max_bytes=max_bytes,
        missing_code=missing_code,
        oversize_code=invalid_code,
    )
    try:
        decoded = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SchemaContractError(invalid_code) from exc
    if not isinstance(decoded, dict):
        raise SchemaContractError(invalid_code)
    return decoded


def _read_bounded_bytes(
    path: Path,
    *,
    max_bytes: int,
    missing_code: str,
    oversize_code: str,
) -> bytes:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise SchemaContractError(missing_code) from exc
    if size <= 0 or size > max_bytes:
        raise SchemaContractError(oversize_code)
    try:
        return path.read_bytes()
    except OSError as exc:
        raise SchemaContractError(missing_code) from exc
