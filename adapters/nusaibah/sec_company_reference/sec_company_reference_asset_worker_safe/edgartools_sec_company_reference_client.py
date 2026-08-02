"""Optional EdgarTools provider for SEC company-reference lookups.

The library import is lazy so fixture and runtime-request pathways do not need
EdgarTools installed. SEC identity configuration remains external through the
``EDGAR_IDENTITY`` environment variable.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from typing import Any


CompanyFactory = Callable[[str], Any]


class EdgarToolsSecCompanyReferenceClient:
    """Resolve a bounded SEC company reference through EdgarTools."""

    def __init__(
        self,
        *,
        company_factory: CompanyFactory | None = None,
        identity: str | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        """Create the client with injectable dependencies for local tests."""

        self._company_factory = company_factory
        self._identity = str(identity or "").strip()
        self._environment = environment if environment is not None else os.environ

    def resolve_company_reference(
        self,
        identifier_kind: str,
        identifier_value: str,
    ) -> dict[str, Any]:
        """Resolve one CIK and project only company and security fields."""

        if identifier_kind != "cik":
            raise ValueError("edgartools_identifier_not_supported")

        identity = self._identity or str(
            self._environment.get("EDGAR_IDENTITY", "")
        ).strip()
        if not identity:
            raise RuntimeError("edgartools_identity_not_configured")

        company_factory = self._company_factory or _load_company_factory(identity)

        try:
            company = company_factory(identifier_value)
        except Exception as exc:  # EdgarTools exposes several provider errors.
            raise RuntimeError("edgartools_lookup_failed") from exc

        if bool(getattr(company, "not_found", False)):
            raise ValueError("edgartools_company_not_found")

        cik = _normalize_cik(getattr(company, "cik", identifier_value))
        company_name = _normalise_required_text(
            getattr(company, "name", None),
            "edgartools_company_name_missing",
        )

        tickers = _normalise_string_sequence(
            getattr(company, "tickers", None),
            "edgartools_tickers_missing",
        )
        exchanges = _read_exchanges(company)

        if len(tickers) != len(exchanges):
            raise ValueError("edgartools_ticker_exchange_mismatch")

        securities = [
            {
                "ticker": ticker.upper(),
                "exchange": exchange,
            }
            for ticker, exchange in zip(tickers, exchanges, strict=True)
        ]

        return {
            "company": {
                "cik": cik,
                "company_name": company_name,
            },
            "sec_securities": securities,
        }


def _load_company_factory(identity: str) -> CompanyFactory:
    """Import EdgarTools and configure the adapter-owned SEC identity."""

    try:
        from edgar import Company, set_identity
    except ImportError as exc:
        raise RuntimeError("edgartools_dependency_unavailable") from exc

    set_identity(identity)
    return Company


def _read_exchanges(company: Any) -> list[str]:
    """Read exchange values from supported EdgarTools company surfaces."""

    raw_exchanges = getattr(company, "exchanges", None)

    if raw_exchanges in (None, [], ()):
        get_exchanges = getattr(company, "get_exchanges", None)
        if callable(get_exchanges):
            raw_exchanges = get_exchanges()

    return _normalise_string_sequence(
        raw_exchanges,
        "edgartools_exchanges_missing",
    )


def _normalise_string_sequence(
    value: Any,
    error_code: str,
) -> list[str]:
    """Normalise a non-empty string sequence without accepting mappings."""

    if isinstance(value, str):
        values: Sequence[Any] = [value]
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        values = value
    else:
        raise ValueError(error_code)

    normalised: list[str] = []
    for item in values:
        normalised.append(_normalise_required_text(item, error_code))

    if not normalised:
        raise ValueError(error_code)

    return normalised


def _normalise_required_text(value: Any, error_code: str) -> str:
    """Return one whitespace-normalised text value."""

    if not isinstance(value, str):
        raise ValueError(error_code)

    normalised = " ".join(value.split())
    if not normalised:
        raise ValueError(error_code)

    return normalised


def _normalize_cik(value: Any) -> str:
    """Normalise an EdgarTools CIK to the adapter's ten-digit form."""

    raw = str(value).strip()
    if raw.endswith(".0"):
        raw = raw[:-2]

    unpadded = raw.lstrip("0") or "0"
    if not unpadded.isdigit() or len(unpadded) > 10:
        raise ValueError("edgartools_cik_invalid")

    return unpadded.zfill(10)

