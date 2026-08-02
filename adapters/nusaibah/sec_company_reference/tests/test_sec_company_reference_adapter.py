from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
import json

import pytest


ASSET_ROOT = Path(__file__).resolve().parents[1]
if str(ASSET_ROOT) not in sys.path:
    sys.path.insert(0, str(ASSET_ROOT))

from sec_company_reference_adapter import (  # noqa: E402
    SecCompanyReferenceAdapter,
    _read_identifier,
)

from local_sec_company_reference_client import (
    LocalFixtureSecCompanyReferenceClient,
)

from run_sec_company_reference_local import main

@pytest.mark.parametrize(
    ("variables", "expected"),
    [
        (
            {"cik": "1114448"},
            ("cik", "0001114448"),
        ),
        (
            {"cik": "0001114448"},
            ("cik", "0001114448"),
        ),
        (
            {"sec_ticker": "nvs"},
            ("sec_ticker", "NVS"),
        ),
    ],
)

def test_read_identifier_normalises_supported_identifiers(
    variables: dict[str, Any],
    expected: tuple[str, str],
) -> None:
    """Normalise valid CIK and SEC ticker identifiers."""

    assert _read_identifier(variables) == expected


def test_read_identifier_rejects_missing_identifier() -> None:
    """Require one SEC company identifier."""

    with pytest.raises(
        ValueError,
        match="One of variables.cik or variables.sec_ticker is required",
    ):
        _read_identifier({})


def test_read_identifier_rejects_multiple_identifiers() -> None:
    """Reject requests containing both supported identifiers."""

    with pytest.raises(
        ValueError,
        match="Provide exactly one",
    ):
        _read_identifier(
            {
                "cik": "0001114448",
                "sec_ticker": "NVS",
            }
        )


@pytest.mark.parametrize(
    ("variables", "message"),
    [
        ({"cik": "ABC123"}, "at most 10 digits"),
        ({"cik": "12345678901"}, "at most 10 digits"),
        (
            {"sec_ticker": "NVS;DROP"},
            "unsupported characters",
        ),
    ],
)
def test_read_identifier_rejects_invalid_values(
    variables: dict[str, Any],
    message: str,
) -> None:
    """Reject malformed identifiers before provider execution."""

    with pytest.raises(ValueError, match=message):
        _read_identifier(variables)


def test_adapter_returns_cik_company_reference() -> None:
    """Return the locked SEC-only contract for a CIK request."""

    adapter = SecCompanyReferenceAdapter(
        client=FakeSecCompanyReferenceClient()
    )

    result = adapter.invoke(
        {
            "variables": {
                "cik": "1114448",
            }
        },
        {},
    )

    reference = result["outputs"]["company_reference"]

    assert reference["requested_identifier"] == {
        "kind": "cik",
        "value": "0001114448",
    }
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
    assert reference["metadata"]["security_count"] == 1

def test_adapter_requires_configured_client_for_cik() -> None:
    """Fail safely when no approved SEC reference client is configured."""

    adapter = SecCompanyReferenceAdapter()

    with pytest.raises(
        NotImplementedError,
        match="sec_company_reference_provider_not_configured",
    ):
        adapter.invoke(
            {
                "variables": {
                    "cik": "1114448",
                }
            },
            {},
        )

def test_cik_fixture_matches_expected_response() -> None:
    """Run the CIK fixture through the fake client and match the contract."""

    request_path = (
        ASSET_ROOT
        / "fixtures"
        / "sec_company_reference.cik.request.json"
    )
    expected_path = (
        ASSET_ROOT
        / "fixtures"
        / "sec_company_reference.cik.expected.json"
    )

    request_payload = json.loads(
        request_path.read_text(encoding="utf-8")
    )
    expected_payload = json.loads(
        expected_path.read_text(encoding="utf-8")
    )

    adapter = SecCompanyReferenceAdapter(
        client=FakeSecCompanyReferenceClient()
    )

    result = adapter.invoke(
        request_payload["inputs"],
        request_payload.get("context", {}),
    )

    assert result == expected_payload

def test_adapter_keeps_sec_ticker_unimplemented() -> None:
    """Keep ticker resolution outside the current CIK slice."""

    adapter = SecCompanyReferenceAdapter(
        client=FakeSecCompanyReferenceClient()
    )

    with pytest.raises(
        ValueError,
        match=(
            "sec_company_reference_identifier_not_implemented: "
            "sec_ticker"
        ),
    ):
        adapter.invoke(
            {
                "variables": {
                    "sec_ticker": "NVS",
                }
            },
            {},
        )

def test_adapter_rejects_mismatched_provider_cik() -> None:
    """Reject provider output that does not match the requested identity."""

    adapter = SecCompanyReferenceAdapter(
        client=MismatchedCikClient()
    )

    with pytest.raises(
        ValueError,
        match="CIK must match the requested CIK",
    ):
        adapter.invoke(
            {
                "variables": {
                    "cik": "1114448",
                }
            },
            {},
        )

@pytest.mark.parametrize(
    ("security", "message"),
    [
        (
            {"exchange": "NYSE"},
            "must contain ticker",
        ),
        (
            {
                "ticker": "NVS;DROP",
                "exchange": "NYSE",
            },
            "ticker contains unsupported characters",
        ),
        (
            {"ticker": "NVS"},
            "must contain exchange",
        ),
    ],
)
def test_adapter_rejects_invalid_provider_security(
    security: dict[str, Any],
    message: str,
) -> None:
    """Reject malformed SEC security records from the provider boundary."""

    adapter = SecCompanyReferenceAdapter(
        client=InvalidSecurityClient(security)
    )

    with pytest.raises(ValueError, match=message):
        adapter.invoke(
            {
                "variables": {
                    "cik": "1114448",
                }
            },
            {},
        )

@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {
                "sec_securities": [],
            },
            "company must be an object",
        ),
        (
            {
                "company": {
                    "cik": "0001114448",
                    "company_name": "   ",
                },
                "sec_securities": [],
            },
            "company_name is required",
        ),
        (
            {
                "company": {
                    "cik": "0001114448",
                    "company_name": "Novartis AG",
                },
                "sec_securities": {},
            },
            "sec_securities must be a list",
        ),
    ],
)

def test_adapter_rejects_invalid_company_reference(
    payload: dict[str, Any],
    message: str,
) -> None:
    """Reject malformed company-reference data from the client boundary."""

    adapter = SecCompanyReferenceAdapter(
        client=InvalidCompanyReferenceClient(payload)
    )

    with pytest.raises(ValueError, match=message):
        adapter.invoke(
            {
                "variables": {
                    "cik": "1114448",
                }
            },
            {},
        )

def test_local_fixture_client_returns_provider_boundary_data() -> None:
    """Load the local fixture without leaking the response envelope."""

    fixture_path = (
        ASSET_ROOT
        / "fixtures"
        / "sec_company_reference.cik.expected.json"
    )

    client = LocalFixtureSecCompanyReferenceClient(fixture_path)

    result = client.resolve_company_reference(
        "cik",
        "0001114448",
    )

    assert result == {
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

def test_local_runner_prints_expected_response(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Run the local entry point and compare its JSON output with the fixture."""

    expected_path = (
        ASSET_ROOT
        / "fixtures"
        / "sec_company_reference.cik.expected.json"
    )
    expected_payload = json.loads(
        expected_path.read_text(encoding="utf-8")
    )

    main()

    captured = capsys.readouterr()
    actual_payload = json.loads(captured.out)

    assert actual_payload == expected_payload
    assert captured.err == ""

class FakeSecCompanyReferenceClient:
    """Return one deterministic SEC company reference."""

    def resolve_company_reference(
        self,
        identifier_kind: str,
        identifier_value: str,
    ) -> dict[str, Any]:
        assert identifier_kind == "cik"
        assert identifier_value == "0001114448"

        return {
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


class MismatchedCikClient:
    """Return a company reference for the wrong CIK."""

    def resolve_company_reference(
        self,
        identifier_kind: str,
        identifier_value: str,
    ) -> dict[str, Any]:
        return {
            "company": {
                "cik": "0000000001",
                "company_name": "Wrong Company",
            },
            "sec_securities": [],
        }

class InvalidSecurityClient:
    """Return one malformed SEC security for validation tests."""

    def __init__(self, security: dict[str, Any]) -> None:
        self._security = security

    def resolve_company_reference(
        self,
        identifier_kind: str,
        identifier_value: str,
    ) -> dict[str, Any]:
        return {
            "company": {
                "cik": "0001114448",
                "company_name": "Novartis AG",
            },
            "sec_securities": [self._security],
        }

class InvalidCompanyReferenceClient:
    """Return one malformed company-reference payload."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def resolve_company_reference(
        self,
        identifier_kind: str,
        identifier_value: str,
    ) -> dict[str, Any]:
        return self._payload
