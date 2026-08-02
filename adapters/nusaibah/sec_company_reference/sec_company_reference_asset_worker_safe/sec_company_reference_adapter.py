from __future__ import annotations

import re
from typing import Any

from adapters.base import Adapter


_SEC_TICKER_PATTERN = re.compile(r"^[A-Z0-9.^=-]{1,32}$")
_RUNTIME_REQUEST_PATH = "runtime_request"
_RUNTIME_SOURCE_ROLE = "sec_company_reference_runtime"
_EDGARTOOLS_INVOKE_PATH = "edgartools_invoke"
_SUPPORTED_PROVIDER_PATHS = {
    _RUNTIME_REQUEST_PATH,
    _EDGARTOOLS_INVOKE_PATH,
}
EDGAR_IDENTITY = "Nedal Al Jaloudi n.aljaloudi@gmail.com"


class SecCompanyReferenceClient:
    """Resolve SEC company references through an approved data source.

    The base client performs no network access. A reviewed implementation or
    deterministic test fake must be injected before resolving a CIK.
    """

    def resolve_company_reference(
        self,
        identifier_kind: str,
        identifier_value: str,
    ) -> dict[str, Any]:
        """Return one bounded, normalised SEC company reference."""

        raise NotImplementedError(
            "sec_company_reference_provider_not_configured"
        )


class SecCompanyReferenceAdapter(Adapter):
    """Validate and shape bounded SEC company-reference results.

    Two opt-in provider pathways are supported:

    ``runtime_request``
        Consumes bounded, sanitized records resolved through the
        ``sec_company_reference_runtime`` Runtime Source role.

    ``edgartools_invoke``
        Invokes an approved EdgarTools client using the reviewed adapter-owned identity.

    The pathways are mutually exclusive and never fall back to one another.
    Existing injected clients remain supported for deterministic local runs.
    """

    key = "nusaibah.sec_company_reference"
    version = "0.1.1"

    def __init__(
        self,
        client: SecCompanyReferenceClient | None = None,
        edgartools_client: SecCompanyReferenceClient | None = None,
    ) -> None:
        """Create the adapter with optional explicit provider clients."""

        self._client = client
        self._edgartools_client = edgartools_client

    def invoke(
        self,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve one CIK through exactly one explicitly selected pathway."""

        if not isinstance(inputs, dict):
            raise ValueError("inputs must be an object.")

        variables = inputs.get("variables", {})
        if not isinstance(variables, dict):
            raise ValueError(
                "variables must be an object when provided."
            )

        identifier_kind, identifier_value = _read_identifier(variables)

        # SEC ticker resolution remains outside the current CIK-only slice.
        if identifier_kind == "sec_ticker":
            raise ValueError(
                "sec_company_reference_identifier_not_implemented: "
                "sec_ticker"
            )

        provider_path = _read_provider_path(inputs)
        client, source_kind = self._select_client(
            inputs=inputs,
            provider_path=provider_path,
        )

        reference = client.resolve_company_reference(
            identifier_kind,
            identifier_value,
        )

        return _prepare_company_reference(
            reference=reference,
            requested_kind=identifier_kind,
            requested_value=identifier_value,
            provider_path=provider_path,
            source_kind=source_kind,
        )

    def _select_client(
        self,
        *,
        inputs: dict[str, Any],
        provider_path: str | None,
    ) -> tuple[SecCompanyReferenceClient, str]:
        """Select one provider without automatic fallback or cross-calling."""

        if provider_path is None:
            if self._client is None:
                raise NotImplementedError(
                    "sec_company_reference_provider_not_configured"
                )

            return self._client, "governed_sec_reference"

        if provider_path == _RUNTIME_REQUEST_PATH:
            runtime_input = inputs.get(_RUNTIME_SOURCE_ROLE)

            if runtime_input is None:
                raise ValueError(
                    "sec_company_reference_runtime_role_required"
                )

            from runtime_sec_company_reference_client import (
                RuntimeSourceSecCompanyReferenceClient,
            )

            return (
                RuntimeSourceSecCompanyReferenceClient(runtime_input),
                "governed_sec_runtime_source",
            )

        if provider_path == _EDGARTOOLS_INVOKE_PATH:
            client = self._edgartools_client
            if client is None:
                from edgartools_sec_company_reference_client import (
                    EdgarToolsSecCompanyReferenceClient,
                )

                client = EdgarToolsSecCompanyReferenceClient(identity=EDGAR_IDENTITY)

            return client, "edgartools_company_lookup"

        # _read_provider_path validates all non-empty values.
        raise ValueError("unsupported_provider_path")


def _read_provider_path(inputs: dict[str, Any]) -> str | None:
    """Read an optional, explicit provider-path selector."""

    raw_execution = inputs.get("execution")
    if raw_execution is None:
        return None

    if not isinstance(raw_execution, dict):
        raise ValueError("inputs.execution must be an object.")

    raw_provider_path = raw_execution.get("provider_path")
    if raw_provider_path in (None, ""):
        return None

    if not isinstance(raw_provider_path, str):
        raise ValueError("execution.provider_path must be a string.")

    provider_path = raw_provider_path.strip()
    if provider_path not in _SUPPORTED_PROVIDER_PATHS:
        raise ValueError("unsupported_provider_path")

    return provider_path


def _read_identifier(
    variables: dict[str, Any],
) -> tuple[str, str]:
    """Return exactly one normalised SEC company identifier."""

    raw_cik = variables.get("cik")
    raw_ticker = variables.get("sec_ticker")

    cik_supplied = raw_cik not in (None, "")
    ticker_supplied = raw_ticker not in (None, "")

    if cik_supplied and ticker_supplied:
        raise ValueError(
            "Provide exactly one of variables.cik or "
            "variables.sec_ticker."
        )

    if not cik_supplied and not ticker_supplied:
        raise ValueError(
            "One of variables.cik or variables.sec_ticker is required."
        )

    if cik_supplied:
        if not isinstance(raw_cik, str) or not raw_cik.strip():
            raise ValueError(
                "variables.cik must be a non-empty string."
            )

        normalized = raw_cik.strip().lstrip("0") or "0"
        if not normalized.isdigit() or len(normalized) > 10:
            raise ValueError(
                "variables.cik must contain at most 10 digits."
            )

        return "cik", normalized.zfill(10)

    if not isinstance(raw_ticker, str) or not raw_ticker.strip():
        raise ValueError(
            "variables.sec_ticker must be a non-empty string."
        )

    ticker = raw_ticker.strip().upper()
    if not _SEC_TICKER_PATTERN.fullmatch(ticker):
        raise ValueError(
            "variables.sec_ticker contains unsupported characters."
        )

    return "sec_ticker", ticker


def _prepare_company_reference(
    *,
    reference: dict[str, Any],
    requested_kind: str,
    requested_value: str,
    provider_path: str | None = None,
    source_kind: str = "governed_sec_reference",
) -> dict[str, Any]:
    """Validate and project one deterministic SEC company reference."""

    if not isinstance(reference, dict):
        raise ValueError(
            "sec_company_reference must be an object."
        )

    raw_company = reference.get("company")
    raw_securities = reference.get("sec_securities")

    if not isinstance(raw_company, dict):
        raise ValueError(
            "sec_company_reference.company must be an object."
        )

    cik = raw_company.get("cik")
    company_name = raw_company.get("company_name")

    if cik != requested_value:
        raise ValueError(
            "sec_company_reference CIK must match the requested CIK."
        )

    if not isinstance(company_name, str):
        raise ValueError(
            "sec_company_reference company_name is required."
        )

    normalized_company_name = " ".join(company_name.split())
    if not normalized_company_name:
        raise ValueError(
            "sec_company_reference company_name is required."
        )

    if not isinstance(raw_securities, list):
        raise ValueError(
            "sec_company_reference.sec_securities must be a list."
        )

    securities: list[dict[str, str]] = []

    for raw_security in raw_securities:
        if not isinstance(raw_security, dict):
            raise ValueError(
                "Every SEC security must be an object."
            )

        raw_ticker = raw_security.get("ticker")
        raw_exchange = raw_security.get("exchange")

        if not isinstance(raw_ticker, str) or not raw_ticker.strip():
            raise ValueError(
                "Every SEC security must contain ticker."
            )

        ticker = raw_ticker.strip().upper()
        if not _SEC_TICKER_PATTERN.fullmatch(ticker):
            raise ValueError(
                "Every SEC security ticker contains "
                "unsupported characters."
            )

        if (
            not isinstance(raw_exchange, str)
            or not raw_exchange.strip()
        ):
            raise ValueError(
                "Every SEC security must contain exchange."
            )

        securities.append(
            {
                "ticker": ticker,
                "exchange": " ".join(raw_exchange.split()),
                "relationship": "direct_sec_symbol",
            }
        )

    metadata: dict[str, Any] = {
        "source_kind": source_kind,
        "security_count": len(securities),
    }
    if provider_path is not None:
        metadata["provider_path"] = provider_path

    company_reference = {
        "requested_identifier": {
            "kind": requested_kind,
            "value": requested_value,
        },
        "company": {
            "cik": cik,
            "company_name": normalized_company_name,
            "identity_status": "resolved",
        },
        "sec_securities": securities,
        "metadata": metadata,
    }

    return {
        "response_version": "1",
        "status": "success",
        "outputs": {
            "company_reference": company_reference,
        },
        "logs": [
            {
                "level": "info",
                "message": (
                    "Prepared SEC company reference for "
                    f"CIK {requested_value}."
                ),
            }
        ],
        "metrics": {
            "operation_count": 1,
            "sec_security_count": len(securities),
        },
    }

