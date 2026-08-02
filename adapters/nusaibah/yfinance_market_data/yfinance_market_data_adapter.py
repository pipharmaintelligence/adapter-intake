from __future__ import annotations

import importlib
import math
import re
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from adapters.base import Adapter


_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.^=-]{1,32}$")
_COMPANY_NAME_MAX_LENGTH = 160
_COMPANY_SEARCH_LIMIT = 8
_COMPANY_SUFFIXES = {
    "ag", "corp", "corporation", "inc", "incorporated", "limited",
    "llc", "ltd", "nv", "plc", "sa", "se", "spa",
}
_LINE_ITEM_PATTERN = re.compile(r"^[a-z0-9_]{1,128}$")
_ALLOWED_OPERATIONS = {
    "history",
    "snapshot",
    "attribute",
    "financial_statement",
    "company_profile",
    "company_mapping",
}
_ALLOWED_PERIODS = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}
_ALLOWED_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"}
_PROVIDER_FREQUENCIES = {"annual": "yearly", "quarterly": "quarterly"}
_ATTRIBUTE_SOURCES: dict[str, tuple[str, str]] = {
    "currency": ("fast_info", "currency"),
    "exchange": ("fast_info", "exchange"),
    "quote_type": ("fast_info", "quoteType"),
    "last_price": ("fast_info", "lastPrice"),
    "previous_close": ("fast_info", "previousClose"),
    "open": ("fast_info", "open"),
    "day_high": ("fast_info", "dayHigh"),
    "day_low": ("fast_info", "dayLow"),
    "year_high": ("fast_info", "yearHigh"),
    "year_low": ("fast_info", "yearLow"),
    "market_cap": ("fast_info", "marketCap"),
    "shares": ("fast_info", "shares"),
    "last_volume": ("fast_info", "lastVolume"),
    "short_name": ("info", "shortName"),
    "long_name": ("info", "longName"),
    "sector": ("info", "sector"),
    "industry": ("info", "industry"),
    "country": ("info", "country"),
}
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
_COMPANY_PROFILE_SOURCES: dict[str, str] = {
    "quote_type": "quoteType",
    "short_name": "shortName",
    "long_name": "longName",
    "exchange_code": "exchange",
    "full_exchange_name": "fullExchangeName",
    "market": "market",
    "currency": "currency",
    "country": "country",
    "sector": "sector",
    "sector_key": "sectorKey",
    "industry": "industry",
    "industry_key": "industryKey",
    "website": "website",
    "market_cap": "marketCap",
}
_COMPANY_PROFILE_FIELDS = (
    "symbol",
    "verified",
    "quote_type",
    "short_name",
    "long_name",
    "exchange_code",
    "full_exchange_name",
    "market",
    "currency",
    "country",
    "sector",
    "sector_key",
    "industry",
    "industry_key",
    "website",
    "market_cap",
)
_ALLOWED_STATEMENTS = {"income_statement", "balance_sheet", "cash_flow"}
_ALLOWED_FREQUENCIES = {"annual", "quarterly"}

_COMPANY_IDENTIFIER_KEYS = (
    "cik",
    "sec_ticker",
    "yahoo_symbol",
    "company_name",
)


def _read_company_mapping_identifier(
    variables: dict[str, Any],
) -> tuple[str, str]:
    """Return exactly one validated company-mapping identifier."""

    supplied: list[tuple[str, str]] = []

    for key in _COMPANY_IDENTIFIER_KEYS:
        value = variables.get(key)

        if value in (None, ""):
            continue

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"variables.{key} must be a non-empty string when provided."
            )

        supplied.append((key, value.strip()))

    if not supplied:
        raise ValueError(
            "company_mapping requires exactly one of variables.cik, "
            "variables.sec_ticker, variables.yahoo_symbol, or "
            "variables.company_name."
        )

    if len(supplied) > 1:
        raise ValueError(
            "company_mapping accepts exactly one company identifier."
        )

    kind, value = supplied[0]

    if kind == "cik":
        normalized = value.lstrip("0") or "0"
        if not normalized.isdigit() or len(normalized) > 10:
            raise ValueError(
                "variables.cik must contain at most 10 digits."
            )
        return kind, normalized.zfill(10)

    if kind in {"sec_ticker", "yahoo_symbol"}:
        normalized = value.upper()
        if not _SYMBOL_PATTERN.fullmatch(normalized):
            raise ValueError(
                f"variables.{kind} contains unsupported characters."
            )
        return kind, normalized

    return kind, _read_company_name(value)

def _read_optional_provider_text(
    source: Mapping[str, Any],
    *keys: str,
) -> str | None:
    """Return the first bounded non-empty provider text value."""

    for key in keys:
        value = source.get(key)

        if not isinstance(value, str):
            continue

        normalized = " ".join(value.split())
        if not normalized:
            continue

        # Prevent unexpectedly large provider fields from entering output.
        return normalized[:256]

    return None
class YFinanceProviderError(RuntimeError):
    """Value-safe provider failure raised without response material."""


class YFinanceMarketDataClient:
    """Bounded provider layer for the isolated yfinance dependency."""

    def __init__(self, yfinance_module: Any | None = None) -> None:
        self._yfinance_module = yfinance_module

    def search_company_candidates(
            self,
            company_name: str,
            *,
            max_results: int = 8,
            timeout_seconds: int = 15,
    ) -> list[dict[str, Any]]:
        """Return bounded exact-name Yahoo equity candidates.

        The method preserves provider ranking and returns every exact canonical
        company-name match. It does not select a canonical security and does not
        claim that any candidate represents a verified SEC registrant.
        """

        normalized_name = _read_company_name(company_name)

        if isinstance(max_results, bool) or not isinstance(max_results, int):
            raise ValueError("max_results must be an integer.")
        if max_results < 1 or max_results > 25:
            raise ValueError("max_results must be between 1 and 25.")

        if isinstance(timeout_seconds, bool) or not isinstance(
                timeout_seconds,
                int,
        ):
            raise ValueError("timeout_seconds must be an integer.")
        if timeout_seconds < 1 or timeout_seconds > 60:
            raise ValueError("timeout_seconds must be between 1 and 60.")

        try:
            search = self._module().Search(
                normalized_name,
                max_results=max_results,
                news_count=0,
                lists_count=0,
                include_cb=False,
                include_nav_links=False,
                include_research=False,
                include_cultural_assets=False,
                enable_fuzzy_query=False,
                recommended=0,
                timeout=timeout_seconds,
                raise_errors=True,
            )
            raw_quotes = search.quotes
        except Exception:
            raise YFinanceProviderError(
                "company_candidate_search_failed"
            ) from None

        if not isinstance(raw_quotes, list):
            raise YFinanceProviderError("company_candidate_search_failed")

        expected_name = _canonical_company_name(normalized_name)
        candidates: list[dict[str, Any]] = []
        seen_listing_keys: set[tuple[str, str | None]] = set()

        for raw_quote in raw_quotes[:max_results]:
            if not isinstance(raw_quote, Mapping):
                continue

            quote_type = str(
                raw_quote.get("quoteType")
                or raw_quote.get("quote_type")
                or ""
            ).strip().upper()

            if quote_type and quote_type != "EQUITY":
                continue

            raw_symbol = raw_quote.get("symbol")
            if not isinstance(raw_symbol, str):
                continue

            symbol = raw_symbol.strip().upper()
            if not _SYMBOL_PATTERN.fullmatch(symbol):
                continue

            short_name = _read_optional_provider_text(
                raw_quote,
                "shortname",
                "shortName",
            )
            long_name = _read_optional_provider_text(
                raw_quote,
                "longname",
                "longName",
            )
            display_name = _read_optional_provider_text(
                raw_quote,
                "displayName",
            )

            candidate_names = (
                short_name,
                long_name,
                display_name,
            )
            if not any(
                    isinstance(name, str)
                    and _canonical_company_name(name) == expected_name
                    for name in candidate_names
            ):
                continue

            exchange_code = _read_optional_provider_text(
                raw_quote,
                "exchange",
                "exchangeCode",
            )
            exchange_name = _read_optional_provider_text(
                raw_quote,
                "exchDisp",
                "exchangeDisplay",
                "fullExchangeName",
            )

            listing_key = (symbol, exchange_code)
            if listing_key in seen_listing_keys:
                continue
            seen_listing_keys.add(listing_key)

            candidates.append(
                {
                    "symbol": symbol,
                    "quote_type": quote_type or "EQUITY",
                    "short_name": short_name,
                    "long_name": long_name,
                    "display_name": display_name,
                    "exchange_code": exchange_code,
                    "exchange_name": exchange_name,
                    "match_basis": "exact_company_name",
                    "match_status": "candidate",
                }
            )

        return candidates

    def resolve_company_name(
        self,
        company_name: str,
        *,
        timeout_seconds: int = 15,
    ) -> str:
        """Resolve one company name to Yahoo's highest-ranked exact equity match.

        Returned quote names must match the requested canonical company name
        exactly. When the same company has several listings, provider result
        order is used only after exact-name and equity-type validation.
        """

        try:
            search = self._module().Search(
                company_name,
                max_results=_COMPANY_SEARCH_LIMIT,
                news_count=0,
                lists_count=0,
                include_cb=False,
                include_nav_links=False,
                include_research=False,
                include_cultural_assets=False,
                enable_fuzzy_query=False,
                recommended=0,
                timeout=timeout_seconds,
                raise_errors=True,
            )
            raw_quotes = search.quotes
        except Exception:
            raise YFinanceProviderError("company_name_resolution_failed") from None

        if not isinstance(raw_quotes, list):
            raise YFinanceProviderError("company_name_resolution_failed")

        expected_name = _canonical_company_name(company_name)
        matched_symbols: list[str] = []
        for raw_quote in raw_quotes[:_COMPANY_SEARCH_LIMIT]:
            if not isinstance(raw_quote, Mapping):
                continue

            quote_type = str(
                raw_quote.get("quoteType")
                or raw_quote.get("quote_type")
                or ""
            ).strip().upper()
            if quote_type and quote_type != "EQUITY":
                continue

            raw_symbol = raw_quote.get("symbol")
            if not isinstance(raw_symbol, str):
                continue
            symbol = raw_symbol.strip().upper()
            if not _SYMBOL_PATTERN.fullmatch(symbol):
                continue

            candidate_names = (
                raw_quote.get("shortname"),
                raw_quote.get("longname"),
                raw_quote.get("shortName"),
                raw_quote.get("longName"),
                raw_quote.get("displayName"),
            )
            if any(
                isinstance(name, str)
                and _canonical_company_name(name) == expected_name
                for name in candidate_names
            ) and symbol not in matched_symbols:
                # Yahoo returns quotes in provider relevance order. Selecting
                # the first item here is safe because every retained candidate
                # has already passed exact canonical-name and equity checks.
                matched_symbols.append(symbol)

        if not matched_symbols:
            raise ValueError("company_name_not_found")
        return matched_symbols[0]

    def fetch_snapshot(
        self,
        symbol: str,
        operation: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        """Fetch one bounded SDK result and convert it to a safe snapshot."""

        try:
            ticker = self._module().Ticker(symbol)
            if operation == "history":
                records, query_context = self._history(ticker, variables)
                data_kind = "history"
            elif operation == "financial_statement":
                records, query_context = self._financial_statement(ticker, variables)
                data_kind = "financial_statement"
            elif operation == "company_profile":
                records = [self._company_profile(ticker, symbol)]
                query_context = None
                data_kind = "company_profile"
            else:
                records = [self._attributes(ticker)]
                query_context = None
                data_kind = "attributes"
        except (ValueError, YFinanceProviderError):
            raise
        except Exception:
            raise YFinanceProviderError("market_data_fetch_failed") from None

        quote_currency = self._read_quote_currency(ticker, records)

        snapshot: dict[str, Any] = {
            "records": records,
            "provenance": {
                "source": "isolated_yfinance_sdk",
                "record_count": len(records),
                "data_kind": data_kind,
                "symbol": symbol,
                "quote_currency": quote_currency,
            },
        }
        if query_context is not None:
            snapshot["query_context"] = query_context
        return snapshot

    def _read_quote_currency(
            self,
            ticker: Any,
            records: list[dict[str, Any]],
    ) -> str | None:
        """Return the security's normalized quote currency when available."""

        # Snapshot and attribute operations already include the safe currency field.
        if records:
            record_currency = records[0].get("currency")
            if isinstance(record_currency, str) and record_currency.strip():
                return record_currency.strip().upper()

        # History and financial-statement records do not normally contain currency.
        # Read only the bounded fast_info currency field.
        try:
            fast_info = ticker.fast_info
            raw_currency = (
                fast_info.get("currency")
                if hasattr(fast_info, "get")
                else None
            )
        except Exception:
            # Currency is useful metadata, but its absence must not break the result.
            return None

        if not isinstance(raw_currency, str):
            return None

        normalized = raw_currency.strip().upper()
        return normalized or None

    def _module(self) -> Any:
        if self._yfinance_module is None:
            try:
                self._yfinance_module = importlib.import_module("yfinance")
            except ImportError:
                raise YFinanceProviderError("market_data_dependency_unavailable") from None
        return self._yfinance_module

    def _history(
        self,
        ticker: Any,
        variables: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        period = _read_choice(variables, "period", "1mo", _ALLOWED_PERIODS)
        interval = _read_choice(variables, "interval", "1d", _ALLOWED_INTERVALS)
        start = _read_optional_date(variables, "start")
        end = _read_optional_date(variables, "end")
        if start is not None and end is not None and start >= end:
            raise ValueError("variables.start must be earlier than variables.end.")
        auto_adjust = _read_bool(variables, "auto_adjust", True)
        prepost = _read_bool(variables, "prepost", False)
        include_actions = _read_bool(variables, "include_actions", False)
        max_rows = _read_bounded_int(variables, "max_rows", default=100, minimum=1, maximum=1000)
        request_timeout = _read_bounded_int(
            variables,
            "timeout_seconds",
            default=15,
            minimum=1,
            maximum=60,
        )
        kwargs: dict[str, Any] = {
            "interval": interval,
            "auto_adjust": auto_adjust,
            "prepost": prepost,
            "actions": include_actions,
            "timeout": request_timeout,
        }
        if start is not None or end is not None:
            kwargs["start"] = start
            kwargs["end"] = end
        else:
            kwargs["period"] = period
        frame = ticker.history(**kwargs)
        records = (
            []
            if frame is None or getattr(frame, "empty", True)
            else [
                _json_safe_value(record)
                for record in frame.tail(max_rows).copy().reset_index().to_dict(orient="records")
            ]
        )
        return records, {
            "period": None if start is not None or end is not None else period,
            "interval": interval,
            "start": start,
            "end": end,
            "auto_adjust": auto_adjust,
            "prepost": prepost,
            "include_actions": include_actions,
        }

    def _financial_statement(
        self,
        ticker: Any,
        variables: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        statement = _read_statement(variables)
        frequency = _read_frequency(variables)
        max_periods = _read_bounded_int(variables, "max_periods", default=4, minimum=1, maximum=8)
        max_line_items = _read_bounded_int(variables, "max_line_items", default=80, minimum=1, maximum=200)
        line_item_filter = _read_line_item_filter(variables)
        provider_frequency = _PROVIDER_FREQUENCIES[frequency]
        if statement == "income_statement":
            frame = ticker.get_income_stmt(freq=provider_frequency, pretty=True)
        elif statement == "balance_sheet":
            frame = ticker.get_balance_sheet(freq=provider_frequency, pretty=True)
        else:
            frame = ticker.get_cashflow(freq=provider_frequency, pretty=True)
        if frame is None or getattr(frame, "empty", True):
            records: list[dict[str, Any]] = []
        else:
            columns = list(frame.columns)[:max_periods]
            records = []
            for raw_line_item, row in frame.loc[:, columns].iterrows():
                if line_item_filter is not None and _snake_case(str(raw_line_item)) != line_item_filter:
                    continue
                records.append(
                    {
                        "line_item": str(raw_line_item),
                        "values": [
                            {
                                "period_end": _json_safe_value(period),
                                "value": _json_safe_value(row.get(period)),
                            }
                            for period in columns
                        ],
                    }
                )
                if len(records) >= max_line_items:
                    break
        return records, {
            "statement": statement,
            "frequency": frequency,
            "max_periods": max_periods,
            "max_line_items": max_line_items,
        }

    def _attributes(self, ticker: Any) -> dict[str, Any]:
        fast_info = ticker.fast_info
        info_cache: dict[str, Any] | None = None
        attributes: dict[str, Any] = {}
        for public_name, (source_name, source_key) in _ATTRIBUTE_SOURCES.items():
            if source_name == "fast_info":
                value = fast_info.get(source_key) if hasattr(fast_info, "get") else None
            else:
                if info_cache is None:
                    raw_info = ticker.info
                    info_cache = raw_info if isinstance(raw_info, dict) else {}
                value = info_cache.get(source_key)
            attributes[public_name] = _json_safe_value(value)
        return attributes

    def _company_profile(self, ticker: Any, symbol: str) -> dict[str, Any]:
        """Return one bounded, allowlisted company profile."""

        try:
            raw_info = ticker.get_info()
        except AttributeError:
            raw_info = ticker.info

        info = raw_info if isinstance(raw_info, dict) else {}
        profile: dict[str, Any] = {
            "symbol": symbol,
            "verified": bool(info),
        }
        for public_name, provider_key in _COMPANY_PROFILE_SOURCES.items():
            profile[public_name] = _json_safe_value(info.get(provider_key))
        return profile



class YFinanceMarketDataAdapter(Adapter):
    """Fetch and shape bounded market data in an admitted isolated runtime.

    The adapter owns no OBS, Core, storage, queue, publishing, or credential
    behavior. Provider access is delegated to an injectable client whose SDK
    dependency and outbound policy are admitted by the runtime.
    """

    key = "nusaibah.yfinance_market_data"
    version = "0.2.3"

    def __init__(self, client: YFinanceMarketDataClient | None = None) -> None:
        self._client = client or YFinanceMarketDataClient()

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Validate one snapshot and return a stable JSON-safe result."""

        variables = inputs.get("variables", {})
        if not isinstance(variables, dict):
            raise ValueError("variables must be an object when provided.")

        operation = _read_operation(variables)
        if operation == "company_mapping":
            return self._invoke_company_mapping(
                variables=variables,
                context=context,
            )

        try:
            symbol, identifier_kind = _resolve_identifier(self._client, variables)
            snapshot = self._client.fetch_snapshot(symbol, operation, variables)
        except YFinanceProviderError as exc:
            if str(exc) == "company_name_resolution_failed":
                raise ValueError("company_name_resolution_failed") from None
            raise ValueError("market_data_fetch_failed") from None
        _validate_snapshot_identity(snapshot, symbol, operation)
        quote_currency = _read_quote_currency(snapshot)

        row_count = 0
        line_item_count = 0
        profile_field_count = 0
        if operation == "history":
            data, row_count = _prepare_history(snapshot, variables)
        elif operation == "snapshot":
            data = {"attributes": _prepare_attributes(snapshot)}
        elif operation == "attribute":
            attribute = _read_attribute(variables)
            attributes = _prepare_attributes(snapshot)
            data = {"attribute": attribute, "value": attributes.get(attribute)}
        elif operation == "company_profile":
            profile = _prepare_company_profile(snapshot, symbol)
            data = {"record": profile}
            profile_field_count = sum(
                1 for value in profile.values() if value is not None
            )
        else:
            data, line_item_count = _prepare_financial_statement(snapshot, variables)

        output = {
            "symbol": symbol,
            "operation": operation,
            "data": data,
            "metadata": {
                "source_kind": "isolated_provider_sdk",
                "library_family": "yfinance",
                "identifier_kind": identifier_kind,
                "quote_currency": quote_currency,
                "row_count": row_count,
                "line_item_count": line_item_count,
                "profile_field_count": profile_field_count,
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
                "company_profile_field_count": profile_field_count,
            },
        }
    def _invoke_company_mapping(
        self,
        *,
        variables: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Return bounded company-mapping candidates without selecting one listing."""

        identifier_kind, identifier_value = (
            _read_company_mapping_identifier(variables)
        )

        if identifier_kind != "company_name":
            raise ValueError(
                "company_mapping_identifier_not_implemented: "
                f"{identifier_kind}"
            )

        max_candidates = _read_bounded_int(
            variables,
            "max_yahoo_candidates",
            default=10,
            minimum=1,
            maximum=25,
        )
        timeout_seconds = _read_bounded_int(
            variables,
            "timeout_seconds",
            default=15,
            minimum=1,
            maximum=60,
        )

        try:
            yahoo_candidates = self._client.search_company_candidates(
                identifier_value,
                max_results=max_candidates,
                timeout_seconds=timeout_seconds,
            )
        except YFinanceProviderError:
            raise ValueError("company_candidate_search_failed") from None

        candidate_count = len(yahoo_candidates)

        if candidate_count == 0:
            identity_status = "not_found"
        elif candidate_count == 1:
            identity_status = "candidate"
        else:
            identity_status = "ambiguous"

        market_data = {
            "operation": "company_mapping",
            "requested_identifier": {
                "kind": identifier_kind,
                "value": identifier_value,
            },
            "company": {
                "cik": None,
                "company_name": identifier_value,
                "identity_status": identity_status,
            },
            "sec_securities": [],
            "yahoo_candidates": yahoo_candidates,
            "metadata": {
                "source_kind": "isolated_provider_sdk",
                "library_family": "yfinance",
                "candidate_count": candidate_count,
                "results_truncated": candidate_count >= max_candidates,
            },
        }

        return {
            "response_version": "1",
            "status": "success",
            "outputs": {
                "market_data": market_data,
            },
            "logs": [
                {
                    "level": "info",
                    "message": (
                        "Prepared company_mapping candidates for "
                        f"{identifier_value}."
                    ),
                }
            ],
            "metrics": {
                "operation_count": 1,
                "company_mapping_candidate_count": candidate_count,
            },
        }

def _require_object(inputs: dict[str, Any], role: str) -> dict[str, Any]:
    value = inputs.get(role)
    if not isinstance(value, dict):
        raise ValueError(f"{role} input must be an object.")
    return value


def _resolve_identifier(
    client: YFinanceMarketDataClient,
    variables: dict[str, Any],
) -> tuple[str, str]:
    """Resolve exactly one supplied identifier to a validated ticker symbol."""

    raw_symbol = variables.get("symbol")
    raw_company_name = variables.get("company_name")

    symbol_supplied = raw_symbol not in (None, "")
    company_name_supplied = raw_company_name not in (None, "")

    if symbol_supplied and company_name_supplied:
        raise ValueError("Provide exactly one of variables.symbol or variables.company_name.")
    if not symbol_supplied and not company_name_supplied:
        raise ValueError("One of variables.symbol or variables.company_name is required.")

    if symbol_supplied:
        if not isinstance(raw_symbol, str) or not raw_symbol.strip():
            raise ValueError("variables.symbol must be a non-empty string.")
        return _validate_symbol(raw_symbol), "symbol"

    company_name = _read_company_name(raw_company_name)
    timeout_seconds = _read_bounded_int(
        variables,
        "timeout_seconds",
        default=15,
        minimum=1,
        maximum=60,
    )
    return (
        client.resolve_company_name(
            company_name,
            timeout_seconds=timeout_seconds,
        ),
        "company_name",
    )


def _validate_symbol(value: str) -> str:
    """Normalize and validate one explicit ticker symbol."""

    symbol = value.strip().upper()
    if not _SYMBOL_PATTERN.fullmatch(symbol):
        raise ValueError("variables.symbol contains unsupported characters.")
    return symbol


def _read_company_name(value: Any) -> str:
    """Validate one company-name search query without provider material."""

    if not isinstance(value, str):
        raise ValueError("variables.company_name must be a non-empty string.")
    if any(ord(character) < 32 for character in value):
        raise ValueError("variables.company_name contains unsupported control characters.")
    company_name = " ".join(value.split())
    if not company_name:
        raise ValueError("variables.company_name must be a non-empty string.")
    if len(company_name) > _COMPANY_NAME_MAX_LENGTH:
        raise ValueError(
            f"variables.company_name must be at most {_COMPANY_NAME_MAX_LENGTH} characters."
        )
    if not _canonical_company_name(company_name):
        raise ValueError("variables.company_name must contain letters or numbers.")
    return company_name


def _canonical_company_name(value: str) -> str:
    """Return a deterministic comparison form for provider company names."""

    tokens = re.findall(r"[a-z0-9]+", value.casefold())
    while tokens and tokens[-1] in _COMPANY_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def _read_operation(variables: dict[str, Any]) -> str:
    value = variables.get("operation", "history")
    if not isinstance(value, str) or value not in _ALLOWED_OPERATIONS:
        raise ValueError(
            "variables.operation must be history, snapshot, attribute, "
            "financial_statement, company_profile, or company_mapping."
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




def _read_choice(
    variables: dict[str, Any],
    key: str,
    default: str,
    allowed: set[str],
) -> str:
    value = variables.get(key, default)
    if not isinstance(value, str) or value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"variables.{key} must be one of: {choices}.")
    return value


def _read_optional_date(variables: dict[str, Any], key: str) -> str | None:
    value = variables.get(key)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError(f"variables.{key} must be a YYYY-MM-DD string.")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError(
            f"variables.{key} must be a valid YYYY-MM-DD date."
        ) from None


def _read_bool(variables: dict[str, Any], key: str, default: bool) -> bool:
    value = variables.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"variables.{key} must be true or false.")
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

def _read_quote_currency(snapshot: dict[str, Any]) -> str | None:
    """Read and validate optional quote-currency metadata."""

    provenance = snapshot.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("market_data_snapshot.provenance must be an object.")

    value = provenance.get("quote_currency")
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(
            "market_data_snapshot provenance quote_currency must be a string."
        )

    normalized = value.strip().upper()
    if not normalized:
        return None

    if not re.fullmatch(r"[A-Z]{3}", normalized):
        raise ValueError(
            "market_data_snapshot provenance quote_currency must be a "
            "three-letter currency code."
        )

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
        raise ValueError("market_data_snapshot provenance symbol must match the resolved symbol.")

    expected_kind = {
        "history": "history",
        "snapshot": "attributes",
        "attribute": "attributes",
        "financial_statement": "financial_statement",
        "company_profile": "company_profile",
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


def _prepare_company_profile(
    snapshot: dict[str, Any],
    expected_symbol: str,
) -> dict[str, Any]:
    """Project one provider profile through a strict field allowlist."""

    records = snapshot.get("records")
    if not isinstance(records, list) or len(records) != 1:
        raise ValueError(
            "market_data_snapshot.records must contain one company profile object."
        )
    raw_profile = records[0]
    if not isinstance(raw_profile, dict):
        raise ValueError(
            "market_data_snapshot.records must contain one company profile object."
        )

    profile = {
        field: _json_safe_value(raw_profile.get(field))
        for field in _COMPANY_PROFILE_FIELDS
    }
    if profile["symbol"] != expected_symbol:
        raise ValueError(
            "market_data_snapshot company profile symbol must match the resolved symbol."
        )
    if not isinstance(profile["verified"], bool):
        raise ValueError(
            "market_data_snapshot company profile verified must be true or false."
        )
    return profile


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