from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest


ASSET_ROOT = Path(__file__).resolve().parents[1]
if str(ASSET_ROOT) not in sys.path:
    sys.path.insert(0, str(ASSET_ROOT))

from edgartools_sec_company_reference_client import (  # noqa: E402
    EdgarToolsSecCompanyReferenceClient,
)
from runtime_sec_company_reference_client import (  # noqa: E402
    RuntimeProjectionSecCompanyReferenceClient,
)
from sec_company_reference_adapter import (  # noqa: E402
    SecCompanyReferenceAdapter,
    _read_provider_path,
)


RUNTIME_PROJECTION = {
    "company": {
        "cik": "0001114448",
        "company_name": "Novartis AG",
    },
    "sec_securities": [
        {
            "ticker": "NVS",
            "exchange": "NYSE",
        }
    ],
}


def test_runtime_request_path_uses_only_runtime_projection() -> None:
    """Use the runtime-owned projection without invoking EdgarTools."""

    edgartools_client = FailIfCalledClient()
    adapter = SecCompanyReferenceAdapter(
        edgartools_client=edgartools_client,
    )

    result = adapter.invoke(
        {
            "variables": {"cik": "1114448"},
            "execution": {"provider_path": "runtime_request"},
            "sec_runtime_response": RUNTIME_PROJECTION,
        },
        {},
    )

    reference = result["outputs"]["company_reference"]
    assert reference["company"]["cik"] == "0001114448"
    assert reference["metadata"] == {
        "source_kind": "governed_sec_runtime_projection",
        "security_count": 1,
        "provider_path": "runtime_request",
    }
    assert edgartools_client.calls == 0


def test_runtime_request_requires_safe_projection() -> None:
    """Do not let Python create or acquire a runtime lease itself."""

    adapter = SecCompanyReferenceAdapter()

    with pytest.raises(
        ValueError,
        match="runtime_request_projection_required",
    ):
        adapter.invoke(
            {
                "variables": {"cik": "1114448"},
                "execution": {"provider_path": "runtime_request"},
            },
            {},
        )


def test_runtime_projection_client_returns_copy() -> None:
    """Do not mutate runtime-owned input projections."""

    projection = {
        "company": {
            "cik": "0001114448",
            "company_name": "Novartis AG",
        },
        "sec_securities": [],
    }
    client = RuntimeProjectionSecCompanyReferenceClient(projection)

    result = client.resolve_company_reference("cik", "0001114448")
    result["company"]["company_name"] = "Changed"

    assert projection["company"]["company_name"] == "Novartis AG"


def test_edgartools_path_uses_only_edgartools_client() -> None:
    """Ignore any runtime projection when EdgarTools is explicitly selected."""

    edgartools_client = FakeEdgarToolsClient()
    adapter = SecCompanyReferenceAdapter(
        edgartools_client=edgartools_client,
    )

    result = adapter.invoke(
        {
            "variables": {"cik": "1114448"},
            "execution": {"provider_path": "edgartools_invoke"},
            "sec_runtime_response": {
                "company": {
                    "cik": "0000000001",
                    "company_name": "Wrong Runtime Company",
                },
                "sec_securities": [],
            },
        },
        {},
    )

    reference = result["outputs"]["company_reference"]
    assert reference["company"]["company_name"] == "Novartis AG"
    assert reference["metadata"] == {
        "source_kind": "edgartools_company_lookup",
        "security_count": 1,
        "provider_path": "edgartools_invoke",
    }
    assert edgartools_client.calls == 1


def test_edgartools_failure_does_not_fallback_to_runtime_projection() -> None:
    """Fail the selected path rather than silently changing providers."""

    adapter = SecCompanyReferenceAdapter(
        edgartools_client=FailingEdgarToolsClient(),
    )

    with pytest.raises(RuntimeError, match="edgartools_lookup_failed"):
        adapter.invoke(
            {
                "variables": {"cik": "1114448"},
                "execution": {"provider_path": "edgartools_invoke"},
                "sec_runtime_response": RUNTIME_PROJECTION,
            },
            {},
        )


def test_read_provider_path_rejects_unsupported_path() -> None:
    """Require a known, explicit provider pathway."""

    with pytest.raises(ValueError, match="unsupported_provider_path"):
        _read_provider_path(
            {
                "execution": {
                    "provider_path": "automatic_fallback",
                }
            }
        )


def test_read_provider_path_rejects_non_object_execution() -> None:
    """Keep execution selection structurally separate from variables."""

    with pytest.raises(
        ValueError,
        match="inputs.execution must be an object",
    ):
        _read_provider_path({"execution": "runtime_request"})


def test_edgartools_client_projects_company_and_exchanges() -> None:
    """Project only bounded identity fields from an EdgarTools company."""

    requested: list[str] = []

    def company_factory(identifier: str) -> FakeCompany:
        requested.append(identifier)
        return FakeCompany()

    client = EdgarToolsSecCompanyReferenceClient(
        company_factory=company_factory,
        environment={"EDGAR_IDENTITY": "PI Adapter owner@example.com"},
    )

    result = client.resolve_company_reference("cik", "0001114448")

    assert requested == ["0001114448"]
    assert result == RUNTIME_PROJECTION


def test_edgartools_client_requires_external_identity() -> None:
    """Keep SEC identity outside source code and provider arguments."""

    client = EdgarToolsSecCompanyReferenceClient(
        company_factory=lambda identifier: FakeCompany(),
        environment={},
    )

    with pytest.raises(
        RuntimeError,
        match="edgartools_identity_not_configured",
    ):
        client.resolve_company_reference("cik", "0001114448")


def test_edgartools_client_rejects_ticker_exchange_mismatch() -> None:
    """Do not guess exchange placement when EdgarTools arrays disagree."""

    client = EdgarToolsSecCompanyReferenceClient(
        company_factory=lambda identifier: FakeCompany(
            tickers=["NVS", "NOVN"],
            exchanges=["NYSE"],
        ),
        environment={"EDGAR_IDENTITY": "PI Adapter owner@example.com"},
    )

    with pytest.raises(
        ValueError,
        match="edgartools_ticker_exchange_mismatch",
    ):
        client.resolve_company_reference("cik", "0001114448")


def test_edgartools_client_rejects_not_found_company() -> None:
    """Return a stable error for an unresolved EdgarTools company."""

    client = EdgarToolsSecCompanyReferenceClient(
        company_factory=lambda identifier: FakeCompany(not_found=True),
        environment={"EDGAR_IDENTITY": "PI Adapter owner@example.com"},
    )

    with pytest.raises(
        ValueError,
        match="edgartools_company_not_found",
    ):
        client.resolve_company_reference("cik", "0001114448")


class FakeEdgarToolsClient:
    """Return the deterministic provider-boundary projection."""

    def __init__(self) -> None:
        self.calls = 0

    def resolve_company_reference(
        self,
        identifier_kind: str,
        identifier_value: str,
    ) -> dict[str, Any]:
        self.calls += 1
        assert identifier_kind == "cik"
        assert identifier_value == "0001114448"
        return RUNTIME_PROJECTION


class FailingEdgarToolsClient:
    """Fail without permitting a provider fallback."""

    def resolve_company_reference(
        self,
        identifier_kind: str,
        identifier_value: str,
    ) -> dict[str, Any]:
        raise RuntimeError("edgartools_lookup_failed")


class FailIfCalledClient:
    """Record and reject any unexpected EdgarTools invocation."""

    def __init__(self) -> None:
        self.calls = 0

    def resolve_company_reference(
        self,
        identifier_kind: str,
        identifier_value: str,
    ) -> dict[str, Any]:
        self.calls += 1
        raise AssertionError("EdgarTools must not run for runtime_request")


class FakeCompany:
    """Provide the EdgarTools properties used by the client wrapper."""

    def __init__(
        self,
        *,
        tickers: list[str] | None = None,
        exchanges: list[str] | None = None,
        not_found: bool = False,
    ) -> None:
        self.cik = 1114448
        self.name = "Novartis AG"
        self.tickers = tickers if tickers is not None else ["NVS"]
        self.exchanges = exchanges if exchanges is not None else ["NYSE"]
        self.not_found = not_found
