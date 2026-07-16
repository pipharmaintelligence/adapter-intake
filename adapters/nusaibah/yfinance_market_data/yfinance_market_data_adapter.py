from __future__ import annotations

import math
import re
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from adapters.base import Adapter


_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.^=-]{1,32}$")
_LINE_ITEM_PATTERN = re.compile(r"^[a-z0-9_]{1,128}$")
_ALLOWED_OPERATIONS = {"history", "snapshot", "attribute", "financial_statement"}
_ALLOWED_ATTRIBUTES = {
    "currency",
    "exchange",
    "quote_type",
    "last_price",
    "previous_close",
    "open",
    "day_high",
    "day_low",
    "year_high",
    "year_low",
    "market_cap",
    "shares",
    "last_volume",
    "short_name",
    "long_name",
    "sector",
    "industry",
    "country",
}
_ALLOWED_STATEMENTS = {"income_statement", "balance_sheet", "cash_flow"}
_ALLOWED_FREQUENCIES = {"annual", "quarterly"}


class YFinanceMarketDataAdapter(Adapter):
    """Prepare safe market and financial output from a resolved snapshot.

    The adapter does not call Yahoo Finance, OBS, DLM Core, storage, or HTTP.
    A local developer tool or an approved runtime-owned source must supply
    ``market_data_snapshot`` before invocation.
    """

    key = "nusaibah.yfinance_market_data"
    version = "0.1.0"

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Validate one snapshot and return a stable JSON-safe result."""

        variables = inputs.get("variables", {})
        if not isinstance(variables, dict):
            raise ValueError("variables must be an object when provided.")

        snapshot = _require_object(inputs, "market_data_snapshot")
        symbol = _read_symbol(variables)
        operation = _read_operation(variables)
        _validate_snapshot_identity(snapshot, symbol, operation)

        row_count = 0
        line_item_count = 0
        if operation == "history":
            data, row_count = _prepare_history(snapshot, variables)
        elif operation == "snapshot":
            data = {"attributes": _prepare_attributes(snapshot)}
        elif operation == "attribute":
            attribute = _read_attribute(variables)
            attributes = _prepare_attributes(snapshot)
            data = {"attribute": attribute, "value": attributes.get(attribute)}
        else:
            data, line_item_count = _prepare_financial_statement(snapshot, variables)

        output = {
            "symbol": symbol,
            "operation": operation,
            "data": data,
            "metadata": {
                "source_kind": "runtime_resolved_api_snapshot",
                "library_family": "yfinance",
                "row_count": row_count,
                "line_item_count": line_item_count,
            },
        }
        return {
            "response_version": "1",
            "status": "success",
            "outputs": {"market_data": output},
            "logs": [
                {
                    "level": "info",
                    "message": f"Prepared {operation} market data for {symbol}.",
                }
            ],
            "metrics": {
                "operation_count": 1,
                "history_row_count": row_count,
                "financial_line_item_count": line_item_count,
            },
        }


def _require_object(inputs: dict[str, Any], role: str) -> dict[str, Any]:
    value = inputs.get(role)
    if not isinstance(value, dict):
        raise ValueError(f"{role} input must be an object.")
    return value


def _read_symbol(variables: dict[str, Any]) -> str:
    value = variables.get("symbol")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("variables.symbol must be a non-empty string.")
    symbol = value.strip().upper()
    if not _SYMBOL_PATTERN.fullmatch(symbol):
        raise ValueError("variables.symbol contains unsupported characters.")
    return symbol


def _read_operation(variables: dict[str, Any]) -> str:
    value = variables.get("operation", "history")
    if not isinstance(value, str) or value not in _ALLOWED_OPERATIONS:
        raise ValueError(
            "variables.operation must be history, snapshot, attribute, or financial_statement."
        )
    return value


def _read_attribute(variables: dict[str, Any]) -> str:
    value = variables.get("attribute")
    if not isinstance(value, str) or value not in _ALLOWED_ATTRIBUTES:
        allowed = ", ".join(sorted(_ALLOWED_ATTRIBUTES))
        raise ValueError(f"variables.attribute must be one of: {allowed}.")
    return value


def _read_statement(variables: dict[str, Any]) -> str:
    value = variables.get("statement", "income_statement")
    if not isinstance(value, str) or value not in _ALLOWED_STATEMENTS:
        allowed = ", ".join(sorted(_ALLOWED_STATEMENTS))
        raise ValueError(f"variables.statement must be one of: {allowed}.")
    return value


def _read_frequency(variables: dict[str, Any]) -> str:
    value = variables.get("frequency", "annual")
    if not isinstance(value, str) or value not in _ALLOWED_FREQUENCIES:
        allowed = ", ".join(sorted(_ALLOWED_FREQUENCIES))
        raise ValueError(f"variables.frequency must be one of: {allowed}.")
    return value


def _read_line_item_filter(variables: dict[str, Any]) -> str | None:
    value = variables.get("line_item")
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError("variables.line_item must be a string when provided.")
    normalized = _snake_case(value)
    if not _LINE_ITEM_PATTERN.fullmatch(normalized):
        raise ValueError("variables.line_item contains unsupported characters.")
    return normalized


def _validate_snapshot_identity(snapshot: dict[str, Any], symbol: str, operation: str) -> None:
    provenance = snapshot.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("market_data_snapshot.provenance must be an object.")

    # The packaged profile runner owns provenance for local_file inputs.
    # It intentionally replaces fixture-provided provenance with a safe
    # local-file marker, while the ticker and operation remain validated
    # through the profile variables. Keep this exception narrowly scoped
    # to the expected role so ordinary runtime inputs remain strict.
    if provenance.get("source") == "local_file_fixture":
        if provenance.get("role") != "market_data_snapshot":
            raise ValueError(
                "Local fixture provenance role must be market_data_snapshot."
            )
        return

    if provenance.get("symbol") != symbol:
        raise ValueError("market_data_snapshot provenance symbol must match variables.symbol.")

    expected_kind = {
        "history": "history",
        "snapshot": "attributes",
        "attribute": "attributes",
        "financial_statement": "financial_statement",
    }[operation]
    if provenance.get("data_kind") != expected_kind:
        raise ValueError(
            f"market_data_snapshot provenance data_kind must be {expected_kind}."
        )


def _prepare_history(
    snapshot: dict[str, Any],
    variables: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    raw_records = snapshot.get("records")
    if not isinstance(raw_records, list):
        raise ValueError("market_data_snapshot.records must be a list.")

    max_rows = _read_bounded_int(
        variables,
        "max_rows",
        default=100,
        minimum=1,
        maximum=1000,
    )
    round_digits = _read_bounded_int(
        variables,
        "round_digits",
        default=6,
        minimum=0,
        maximum=10,
    )

    records: list[dict[str, Any]] = []
    for raw_record in raw_records[-max_rows:]:
        if not isinstance(raw_record, dict):
            raise ValueError("Every market_data_snapshot record must be an object.")
        prepared: dict[str, Any] = {}
        for raw_key, raw_value in raw_record.items():
            if isinstance(raw_key, str):
                prepared[_snake_case(raw_key)] = _round_number(
                    _json_safe_value(raw_value),
                    round_digits,
                )
        records.append(prepared)

    query_context = snapshot.get("query_context", {})
    if not isinstance(query_context, dict):
        query_context = {}
    return {"records": records, "query": _safe_query_projection(query_context)}, len(records)


def _prepare_attributes(snapshot: dict[str, Any]) -> dict[str, Any]:
    records = snapshot.get("records")
    if not isinstance(records, list) or not records or not isinstance(records[0], dict):
        raise ValueError("market_data_snapshot.records must contain one attribute object.")
    raw_attributes = records[0]
    return {
        name: _json_safe_value(raw_attributes.get(name))
        for name in sorted(_ALLOWED_ATTRIBUTES)
        if name in raw_attributes
    }


def _prepare_financial_statement(
    snapshot: dict[str, Any],
    variables: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    statement = _read_statement(variables)
    frequency = _read_frequency(variables)
    line_item_filter = _read_line_item_filter(variables)
    max_periods = _read_bounded_int(
        variables,
        "max_periods",
        default=4,
        minimum=1,
        maximum=8,
    )
    max_line_items = _read_bounded_int(
        variables,
        "max_line_items",
        default=80,
        minimum=1,
        maximum=200,
    )
    round_digits = _read_bounded_int(
        variables,
        "round_digits",
        default=2,
        minimum=0,
        maximum=10,
    )

    query_context = snapshot.get("query_context")
    if not isinstance(query_context, dict):
        raise ValueError("market_data_snapshot.query_context must be an object.")
    if query_context.get("statement") != statement:
        raise ValueError("market_data_snapshot statement must match variables.statement.")
    if query_context.get("frequency") != frequency:
        raise ValueError("market_data_snapshot frequency must match variables.frequency.")

    raw_records = snapshot.get("records")
    if not isinstance(raw_records, list):
        raise ValueError("market_data_snapshot.records must be a list.")

    line_items: list[dict[str, Any]] = []
    periods: list[str] = []
    for raw_record in raw_records[:max_line_items]:
        if not isinstance(raw_record, dict):
            raise ValueError("Every financial statement record must be an object.")
        raw_label = raw_record.get("line_item")
        raw_values = raw_record.get("values")
        if not isinstance(raw_label, str) or not raw_label.strip():
            raise ValueError("Every financial statement record must contain line_item.")
        if not isinstance(raw_values, list):
            raise ValueError("Every financial statement record must contain values as a list.")

        key = _snake_case(raw_label)
        if line_item_filter is not None and key != line_item_filter:
            continue

        values: list[dict[str, Any]] = []
        for raw_value in raw_values[:max_periods]:
            if not isinstance(raw_value, dict):
                raise ValueError("Every financial statement value must be an object.")
            period_end = _json_safe_value(raw_value.get("period_end"))
            value = _round_number(_json_safe_value(raw_value.get("value")), round_digits)
            if not isinstance(period_end, str) or not period_end:
                raise ValueError("Every financial statement value must contain period_end.")
            if period_end not in periods:
                periods.append(period_end)
            values.append({"period_end": period_end, "value": value})

        line_items.append({"key": key, "label": raw_label.strip(), "values": values})

    if line_item_filter is not None and not line_items:
        raise ValueError(
            f"Requested financial statement line item was not found: {line_item_filter}."
        )

    return {
        "statement": statement,
        "frequency": frequency,
        "periods": periods,
        "line_items": line_items,
    }, len(line_items)


def _safe_query_projection(query: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "period",
        "interval",
        "start",
        "end",
        "auto_adjust",
        "prepost",
        "include_actions",
    }
    return {
        key: _json_safe_value(value)
        for key, value in query.items()
        if key in allowed
    }


def _read_bounded_int(
    source: dict[str, Any],
    key: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    value = source.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"variables.{key} must be an integer.")
    if value < minimum or value > maximum:
        raise ValueError(f"variables.{key} must be between {minimum} and {maximum}.")
    return value


def _snake_case(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return normalized or "value"


def _round_number(value: Any, digits: int) -> Any:
    return round(value, digits) if isinstance(value, float) else value


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item") and callable(value.item):
        try:
            return _json_safe_value(value.item())
        except (TypeError, ValueError):
            pass
    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            pass
    if isinstance(value, Mapping):
        return {str(key): _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe_value(item) for item in value]
    return str(value)
