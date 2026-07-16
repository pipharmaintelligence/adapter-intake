from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import pytest


ASSET_ROOT = Path(__file__).resolve().parents[1]
if str(ASSET_ROOT) not in sys.path:
    sys.path.insert(0, str(ASSET_ROOT))

from yfinance_market_data_adapter import (  # noqa: E402
    YFinanceMarketDataAdapter,
    YFinanceMarketDataClient,
)


class FakeClient:
    def fetch_snapshot(
        self,
        symbol: str,
        operation: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        if operation == "history":
            return {
                "records": [
                    {"Date": "2026-01-01", "Close": 1.1111111},
                    {"Date": "2026-01-02", "Close": 2.2222222},
                    {"Date": "2026-01-03", "Close": 3.3333333},
                ],
                "query_context": {
                    "period": variables.get("period", "1mo"),
                    "interval": variables.get("interval", "1d"),
                    "provider_url": "must-not-project",
                },
                "provenance": {
                    "source": "fake",
                    "symbol": symbol,
                    "data_kind": "history",
                },
            }
        if operation in {"snapshot", "attribute"}:
            return {
                "records": [
                    {
                        "market_cap": 123,
                        "currency": "USD",
                        "timezone": "must-not-project",
                    }
                ],
                "provenance": {
                    "source": "fake",
                    "symbol": symbol,
                    "data_kind": "attributes",
                },
            }
        return {
            "records": [
                {
                    "line_item": "Total Revenue",
                    "values": [
                        {"period_end": "2025-12-31", "value": 10.4},
                        {"period_end": "2024-12-31", "value": math.nan},
                    ],
                },
                {
                    "line_item": "Operating Income",
                    "values": [{"period_end": "2025-12-31", "value": 4.2}],
                },
            ],
            "query_context": {
                "statement": variables.get("statement", "income_statement"),
                "frequency": variables.get("frequency", "annual"),
            },
            "provenance": {
                "source": "fake",
                "symbol": symbol,
                "data_kind": "financial_statement",
            },
        }


def test_history_is_bounded_and_json_safe() -> None:
    adapter = YFinanceMarketDataAdapter(client=FakeClient())

    result = adapter.invoke(
        {
            "variables": {
                "symbol": "NVS",
                "operation": "history",
                "period": "5d",
                "max_rows": 2,
                "round_digits": 2,
            }
        },
        {"execution_substrate": "local_worker"},
    )

    market_data = result["outputs"]["market_data"]
    assert market_data["data"]["records"] == [
        {"date": "2026-01-02", "close": 2.22},
        {"date": "2026-01-03", "close": 3.33},
    ]
    assert market_data["data"]["query"] == {
        "period": "5d",
        "interval": "1d",
    }
    json.dumps(result, allow_nan=False)


def test_snapshot_and_attribute_use_allowlist() -> None:
    adapter = YFinanceMarketDataAdapter(client=FakeClient())

    snapshot = adapter.invoke(
        {"variables": {"symbol": "NVS", "operation": "snapshot"}},
        {},
    )
    attribute = adapter.invoke(
        {
            "variables": {
                "symbol": "NVS",
                "operation": "attribute",
                "attribute": "market_cap",
            }
        },
        {},
    )

    attributes = snapshot["outputs"]["market_data"]["data"]["attributes"]
    assert attributes["market_cap"] == 123
    assert "timezone" not in attributes
    assert attribute["outputs"]["market_data"]["data"] == {
        "attribute": "market_cap",
        "value": 123,
    }


def test_financial_statement_filters_and_sanitizes_values() -> None:
    adapter = YFinanceMarketDataAdapter(client=FakeClient())

    result = adapter.invoke(
        {
            "variables": {
                "symbol": "NVS",
                "operation": "financial_statement",
                "statement": "income_statement",
                "frequency": "annual",
                "line_item": "total_revenue",
                "max_periods": 2,
                "max_line_items": 10,
            }
        },
        {},
    )

    data = result["outputs"]["market_data"]["data"]
    assert len(data["line_items"]) == 1
    assert data["line_items"][0]["key"] == "total_revenue"
    assert data["line_items"][0]["values"][1]["value"] is None
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize(
    ("variables", "message"),
    [
        ({"symbol": "NVS;DROP", "operation": "history"}, "unsupported characters"),
        ({"symbol": "NVS", "operation": "delete"}, "must be history"),
    ],
)
def test_symbol_and_operation_validation_fail_before_provider(
    variables: dict[str, Any],
    message: str,
) -> None:
    adapter = YFinanceMarketDataAdapter(client=FakeClient())

    with pytest.raises(ValueError, match=message):
        adapter.invoke({"variables": variables}, {})


def test_provider_client_converts_history_without_returning_sdk_objects() -> None:
    ticker = FakeTicker()
    client = YFinanceMarketDataClient(yfinance_module=FakeYFinance(ticker))

    snapshot = client.fetch_snapshot(
        "NVS",
        "history",
        {
            "period": "5d",
            "interval": "1d",
            "max_rows": 1,
            "provider_timeout_seconds": 9,
        },
    )

    assert snapshot["records"] == [{"Date": "2026-01-02", "Close": 2.0}]
    assert ticker.history_kwargs["timeout"] == 9
    assert "url" not in json.dumps(snapshot).lower()


class FakeYFinance:
    def __init__(self, ticker: Any) -> None:
        self.ticker = ticker

    def Ticker(self, symbol: str) -> Any:  # noqa: N802
        assert symbol == "NVS"
        return self.ticker


class FakeTicker:
    def __init__(self) -> None:
        self.history_kwargs: dict[str, Any] = {}
        self.fast_info = {"marketCap": 123}
        self.info = {}

    def history(self, **kwargs: Any) -> Any:
        self.history_kwargs = kwargs
        return FakeHistoryFrame(
            [
                {"Date": "2026-01-01", "Close": 1.0},
                {"Date": "2026-01-02", "Close": 2.0},
            ]
        )


class FakeHistoryFrame:
    empty = False

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records

    def tail(self, count: int) -> "FakeHistoryFrame":
        return FakeHistoryFrame(self.records[-count:])

    def copy(self) -> "FakeHistoryFrame":
        return self

    def reset_index(self) -> "FakeHistoryFrame":
        return self

    def to_dict(self, *, orient: str) -> list[dict[str, Any]]:
        assert orient == "records"
        return self.records
