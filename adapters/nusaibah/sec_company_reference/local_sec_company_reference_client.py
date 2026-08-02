from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .sec_company_reference_adapter import SecCompanyReferenceClient
except ImportError:  # Standalone adapter-project execution.
    from sec_company_reference_adapter import SecCompanyReferenceClient


class LocalFixtureSecCompanyReferenceClient(
    SecCompanyReferenceClient
):
    """Resolve SEC company references from local deterministic fixtures."""

    def __init__(self, fixture_path: Path) -> None:
        """Create the client using one local expected-response fixture."""

        self._fixture_path = fixture_path

    def resolve_company_reference(
        self,
        identifier_kind: str,
        identifier_value: str,
    ) -> dict[str, Any]:
        """Return the matching company reference from the local fixture."""

        if identifier_kind != "cik":
            raise ValueError(
                "local_sec_company_reference_identifier_not_supported: "
                f"{identifier_kind}"
            )

        payload = json.loads(
            self._fixture_path.read_text(encoding="utf-8")
        )

        try:
            reference = payload["outputs"]["company_reference"]
        except (KeyError, TypeError) as exc:
            raise ValueError(
                "local_sec_company_reference_fixture_invalid"
            ) from exc

        company = reference.get("company")
        securities = reference.get("sec_securities")

        if not isinstance(company, dict):
            raise ValueError(
                "local_sec_company_reference_fixture_company_invalid"
            )

        if company.get("cik") != identifier_value:
            raise ValueError(
                "local_sec_company_reference_fixture_cik_not_found: "
                f"{identifier_value}"
            )

        if not isinstance(securities, list):
            raise ValueError(
                "local_sec_company_reference_fixture_securities_invalid"
            )

        # Return only provider-boundary data. The adapter owns the final
        # response envelope, logs, metrics, and identity projection.
        return {
            "company": {
                "cik": company.get("cik"),
                "company_name": company.get("company_name"),
            },
            "sec_securities": [
                {
                    "ticker": security.get("ticker"),
                    "exchange": security.get("exchange"),
                }
                for security in securities
                if isinstance(security, dict)
            ],
        }