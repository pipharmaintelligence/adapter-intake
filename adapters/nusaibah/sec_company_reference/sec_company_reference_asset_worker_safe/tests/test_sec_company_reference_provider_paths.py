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


def test_runtime_request_accepts_runtime_source_records_role() -> None:
    """Consume exactly one sanitized record supplied by Runtime Source."""

    edgartools_client = FailIfCalledClient()
    adapter = SecCompanyReferenceAdapter(
        edgartools_client=edgartools_client,
    )

    result = adapter.invoke(
        {
            "variables": {
                "cik": "1114448",
            },
            "execution": {
                "provider_path": "runtime_request",
            },
            "sec_company_reference_runtime": {
                "records": [
                    {
                        "cik": "0001114448",
                        "name": "Novartis AG",
                        "tickers": ["NVS"],
                        "exchanges": ["NYSE"],
                    }
                ]
            },
        },
        {},
    )

    reference = result["outputs"]["company_reference"]

    assert reference["company"] == {
        "cik": "0001114448",
        "company_name": "Novartis AG",
        "identity_status": "resolved",
    }
    assert reference["sec_securities"] == [
        {
            "ticker": "NVS",
            "exchange": "NYSE",
            "relationship": "direct_sec_symbol",
        }
    ]
    assert reference["metadata"] == {
        "source_kind": "governed_sec_runtime_source",
        "security_count": 1,
        "provider_path": "runtime_request",
    }

    # Selecting Runtime Source must never invoke the local EdgarTools path.
    assert edgartools_client.calls == 0

def test_runtime_request_requires_runtime_source_role() -> None:
    """Require the canonical Runtime Source role for runtime execution."""

    edgartools_client = FailIfCalledClient()
    adapter = SecCompanyReferenceAdapter(
        edgartools_client=edgartools_client,
    )

    with pytest.raises(
        ValueError,
        match="^sec_company_reference_runtime_role_required$",
    ):
        adapter.invoke(
            {
                "variables": {
                    "cik": "1114448",
                },
                "execution": {
                    "provider_path": "runtime_request",
                },
            },
            {},
        )

    assert edgartools_client.calls == 0

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
            "sec_company_reference_runtime": {
                "records": [
                    {
                        "cik": "0000000001",
                        "name": "Wrong Runtime Company",
                        "tickers": [],
                        "exchanges": [],
                    }
                ],
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


def test_edgartools_failure_does_not_fallback_to_runtime_source() -> None:
    """Fail the EdgarTools path without switching to Runtime Source."""

    adapter = SecCompanyReferenceAdapter(
        edgartools_client=FailingEdgarToolsClient(),
    )

    with pytest.raises(RuntimeError, match="edgartools_lookup_failed"):
        adapter.invoke(
            {
                "variables": {"cik": "1114448"},
                "execution": {"provider_path": "edgartools_invoke"},
                "sec_company_reference_runtime": {
                    "records": [
                        {
                            "cik": "0001114448",
                            "name": "Novartis AG",
                            "tickers": ["NVS"],
                            "exchanges": ["NYSE"],
                        }
                    ],
                },
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

def test_runtime_request_rejects_empty_runtime_source_records() -> None:
    """Fail when Runtime Source resolves no SEC company record."""

    edgartools_client = FailIfCalledClient()
    adapter = SecCompanyReferenceAdapter(
        edgartools_client=edgartools_client,
    )

    with pytest.raises(
        ValueError,
        match="^sec_company_reference_runtime_record_not_found$",
    ):
        adapter.invoke(
            {
                "variables": {
                    "cik": "1114448",
                },
                "execution": {
                    "provider_path": "runtime_request",
                },
                "sec_company_reference_runtime": {
                    "records": [],
                },
            },
            {},
        )

    assert edgartools_client.calls == 0


def test_runtime_request_rejects_multiple_runtime_source_records() -> None:
    """Fail rather than choosing an arbitrary Runtime Source record."""

    edgartools_client = FailIfCalledClient()
    adapter = SecCompanyReferenceAdapter(
        edgartools_client=edgartools_client,
    )

    with pytest.raises(
        ValueError,
        match="^sec_company_reference_runtime_multiple_records$",
    ):
        adapter.invoke(
            {
                "variables": {
                    "cik": "1114448",
                },
                "execution": {
                    "provider_path": "runtime_request",
                },
                "sec_company_reference_runtime": {
                    "records": [
                        {
                            "cik": "0001114448",
                            "name": "Novartis AG",
                            "tickers": ["NVS"],
                            "exchanges": ["NYSE"],
                        },
                        {
                            "cik": "0000320193",
                            "name": "Apple Inc.",
                            "tickers": ["AAPL"],
                            "exchanges": ["Nasdaq"],
                        },
                    ],
                },
            },
            {},
        )

    assert edgartools_client.calls == 0

def test_runtime_request_rejects_non_object_runtime_source_role() -> None:
    """Require the Runtime Source role to be an object."""

    edgartools_client = FailIfCalledClient()
    adapter = SecCompanyReferenceAdapter(
        edgartools_client=edgartools_client,
    )

    with pytest.raises(
        ValueError,
        match="^sec_company_reference_runtime_role_invalid$",
    ):
        adapter.invoke(
            {
                "variables": {
                    "cik": "1114448",
                },
                "execution": {
                    "provider_path": "runtime_request",
                },
                "sec_company_reference_runtime": "invalid",
            },
            {},
        )

    assert edgartools_client.calls == 0


def test_runtime_request_rejects_missing_records_list() -> None:
    """Require the Runtime Source role to contain a records list."""

    edgartools_client = FailIfCalledClient()
    adapter = SecCompanyReferenceAdapter(
        edgartools_client=edgartools_client,
    )

    with pytest.raises(
        ValueError,
        match="^sec_company_reference_runtime_records_required$",
    ):
        adapter.invoke(
            {
                "variables": {
                    "cik": "1114448",
                },
                "execution": {
                    "provider_path": "runtime_request",
                },
                "sec_company_reference_runtime": {},
            },
            {},
        )

    assert edgartools_client.calls == 0


def test_runtime_request_rejects_non_object_runtime_source_record() -> None:
    """Require the resolved Runtime Source record to be an object."""

    edgartools_client = FailIfCalledClient()
    adapter = SecCompanyReferenceAdapter(
        edgartools_client=edgartools_client,
    )

    with pytest.raises(
        ValueError,
        match="^sec_company_reference_runtime_record_invalid$",
    ):
        adapter.invoke(
            {
                "variables": {
                    "cik": "1114448",
                },
                "execution": {
                    "provider_path": "runtime_request",
                },
                "sec_company_reference_runtime": {
                    "records": ["invalid"],
                },
            },
            {},
        )

    assert edgartools_client.calls == 0

def test_runtime_request_rejects_mismatched_runtime_source_cik() -> None:
    """Reject a Runtime Source record for a different requested company."""

    edgartools_client = FailIfCalledClient()
    adapter = SecCompanyReferenceAdapter(
        edgartools_client=edgartools_client,
    )

    with pytest.raises(
        ValueError,
        match=(
            "^sec_company_reference CIK must match "
            "the requested CIK\\.$"
        ),
    ):
        adapter.invoke(
            {
                "variables": {
                    "cik": "1114448",
                },
                "execution": {
                    "provider_path": "runtime_request",
                },
                "sec_company_reference_runtime": {
                    "records": [
                        {
                            # Apple instead of the requested Novartis CIK.
                            "cik": "0000320193",
                            "name": "Apple Inc.",
                            "tickers": ["AAPL"],
                            "exchanges": ["Nasdaq"],
                        }
                    ],
                },
            },
            {},
        )

    # A bad Runtime Source result must not trigger another provider.
    assert edgartools_client.calls == 0

def test_runtime_request_rejects_missing_runtime_source_name() -> None:
    """Require a non-empty company name from Runtime Source."""

    edgartools_client = FailIfCalledClient()
    adapter = SecCompanyReferenceAdapter(
        edgartools_client=edgartools_client,
    )

    with pytest.raises(
        ValueError,
        match="^sec_company_reference_runtime_name_invalid$",
    ):
        adapter.invoke(
            {
                "variables": {
                    "cik": "1114448",
                },
                "execution": {
                    "provider_path": "runtime_request",
                },
                "sec_company_reference_runtime": {
                    "records": [
                        {
                            "cik": "0001114448",
                            "name": "",
                            "tickers": ["NVS"],
                            "exchanges": ["NYSE"],
                        }
                    ],
                },
            },
            {},
        )

    assert edgartools_client.calls == 0

def test_runtime_request_rejects_mismatched_security_counts() -> None:
    """Require one exchange value for every ticker value."""

    edgartools_client = FailIfCalledClient()
    adapter = SecCompanyReferenceAdapter(
        edgartools_client=edgartools_client,
    )

    with pytest.raises(
        ValueError,
        match=(
            "^sec_company_reference_runtime_"
            "security_count_mismatch$"
        ),
    ):
        adapter.invoke(
            {
                "variables": {
                    "cik": "1114448",
                },
                "execution": {
                    "provider_path": "runtime_request",
                },
                "sec_company_reference_runtime": {
                    "records": [
                        {
                            "cik": "0001114448",
                            "name": "Novartis AG",
                            "tickers": ["NVS", "NOVN"],
                            "exchanges": ["NYSE"],
                        }
                    ],
                },
            },
            {},
        )

    assert edgartools_client.calls == 0
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
