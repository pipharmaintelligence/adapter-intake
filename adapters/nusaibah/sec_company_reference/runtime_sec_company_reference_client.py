"""Client for sanitized SEC company-reference Runtime Source records.

This module performs no network access. The governed runtime owns leases,
bindings, capabilities, provider requests, retries, and response sanitization.
Python receives only bounded records through the Runtime Source role.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class RuntimeSourceSecCompanyReferenceClient:
    """Convert one sanitized Runtime Source record into adapter input shape.

    This client performs no network access. It receives records that the
    trusted runtime has already fetched and sanitized.
    """

    def __init__(self, runtime_input: dict[str, Any]) -> None:
        """Validate and retain exactly one Runtime Source company record."""

        if not isinstance(runtime_input, dict):
            raise ValueError(
                "sec_company_reference_runtime_role_invalid"
            )

        records = runtime_input.get("records")

        if not isinstance(records, list):
            raise ValueError(
                "sec_company_reference_runtime_records_required"
            )

        if len(records) == 0:
            raise ValueError(
                "sec_company_reference_runtime_record_not_found"
            )

        if len(records) > 1:
            raise ValueError(
                "sec_company_reference_runtime_multiple_records"
            )

        record = records[0]

        if not isinstance(record, dict):
            raise ValueError(
                "sec_company_reference_runtime_record_invalid"
            )

        # Copy runtime-owned data so adapter processing cannot mutate it.
        self._record = deepcopy(record)

    def resolve_company_reference(
        self,
        identifier_kind: str,
        identifier_value: str,
    ) -> dict[str, Any]:
        """Map one normalized Runtime Source record to adapter shape."""

        if identifier_kind != "cik":
            raise ValueError(
                "runtime_request_identifier_not_supported"
            )

        raw_cik = self._record.get("cik")
        company_name = self._record.get("name")
        tickers = self._record.get("tickers")
        exchanges = self._record.get("exchanges")

        if not isinstance(raw_cik, str) or not raw_cik.strip():
            raise ValueError(
                "sec_company_reference_runtime_cik_invalid"
            )

        normalized_cik = raw_cik.strip().lstrip("0") or "0"
        if not normalized_cik.isdigit() or len(normalized_cik) > 10:
            raise ValueError(
                "sec_company_reference_runtime_cik_invalid"
            )

        if not isinstance(company_name, str) or not company_name.strip():
            raise ValueError(
                "sec_company_reference_runtime_name_invalid"
            )

        if not isinstance(tickers, list):
            raise ValueError(
                "sec_company_reference_runtime_tickers_invalid"
            )

        if not isinstance(exchanges, list):
            raise ValueError(
                "sec_company_reference_runtime_exchanges_invalid"
            )

        if len(tickers) != len(exchanges):
            raise ValueError(
                "sec_company_reference_runtime_security_count_mismatch"
            )

        securities: list[dict[str, Any]] = []

        for ticker, exchange in zip(tickers, exchanges, strict=True):
            securities.append(
                {
                    "ticker": ticker,
                    "exchange": exchange,
                }
            )

        return {
            "company": {
                "cik": normalized_cik.zfill(10),
                "company_name": company_name,
            },
            "sec_securities": securities,
        }