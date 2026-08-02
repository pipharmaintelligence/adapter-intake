from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest


ASSET_ROOT = Path(__file__).resolve().parents[1]
if str(ASSET_ROOT) not in sys.path:
    sys.path.insert(0, str(ASSET_ROOT))

import sec_company_reference_launch as launch_module  # noqa: E402
from sec_company_reference_launch import (  # noqa: E402
    DEFAULT_EDGAR_IDENTITY,
    configure_edgartools_identity,
    main,
)


def _run_launcher(
    capsys: pytest.CaptureFixture[str],
    *arguments: str,
) -> tuple[int, dict[str, Any], str]:
    """Run the launcher and parse its standard-output JSON."""

    exit_code = main(list(arguments))

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert isinstance(payload, dict)

    return exit_code, payload, captured.err


def test_launcher_runtime_check_is_network_free(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Report runtime readiness without reading fixtures or using a network."""

    exit_code, payload, stderr = _run_launcher(
        capsys,
        "--runtime-check-only",
    )

    assert exit_code == 0
    assert payload == {
        "category": "runtime_ready",
        "network_calls_made": False,
        "safe": True,
        "schema_version": "sec_company_reference.launch.v1",
        "status": "ready",
        "values_included": False,
    }
    assert stderr == ""


def test_launcher_diagnostics_are_network_free(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Expose only safe launcher capability facts."""

    exit_code, payload, stderr = _run_launcher(
        capsys,
        "--diagnostics-only",
    )

    assert exit_code == 0
    assert payload["status"] == "ready"
    assert payload["category"] == "launcher_diagnostics_ready"
    assert payload["asset_key"] == "nusaibah.sec_company_reference"
    assert payload["asset_version"] == "0.1.0"
    assert payload["direct_result_mode"] == "local_fixture_only"
    assert payload["queued_execution_enabled"] is False
    assert payload["network_calls_made"] is False
    assert payload["values_included"] is False
    assert stderr == ""


def test_launcher_input_dry_run_hides_identifier_value(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Validate launch inputs without exposing the supplied CIK."""

    exit_code, payload, stderr = _run_launcher(
        capsys,
        "--cik",
        "1114448",
        "--skip-publish",
    )

    assert exit_code == 0
    assert payload["status"] == "ready"
    assert payload["category"] == "governed_launch_inputs_ready"
    assert payload["execution_profile"] == "direct_result"
    assert payload["variable_keys"] == ["cik"]
    assert payload["values_included"] is False
    assert payload["network_calls_made"] is False

    serialized = json.dumps(payload)
    assert "1114448" not in serialized
    assert "0001114448" not in serialized
    assert stderr == ""


def test_launcher_direct_result_matches_expected_fixture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Return the locked response through fixture-backed direct execution."""

    expected_path = (
        ASSET_ROOT
        / "fixtures"
        / "sec_company_reference.cik.expected.json"
    )
    expected_payload = json.loads(
        expected_path.read_text(encoding="utf-8")
    )

    exit_code, payload, stderr = _run_launcher(
        capsys,
        "--asset-root",
        str(ASSET_ROOT),
        "--cik",
        "1114448",
        "--execution-profile",
        "direct_result",
    )

    assert exit_code == 0
    assert payload == expected_payload
    assert stderr == ""


def test_launcher_blocks_queued_execution(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Keep queued execution closed until an approved SEC client exists."""

    exit_code, payload, stderr = _run_launcher(
        capsys,
        "--cik",
        "1114448",
        "--execution-profile",
        "queued_summary",
    )

    assert exit_code == 2
    assert payload["status"] == "blocked"
    assert (
        payload["category"]
        == "queued_execution_requires_approved_sec_client"
    )
    assert payload["network_calls_made"] is False
    assert payload["values_included"] is False
    assert stderr == ""


def test_launcher_blocks_sec_ticker_resolution(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Keep ticker-to-CIK resolution outside the current launcher slice."""

    exit_code, payload, stderr = _run_launcher(
        capsys,
        "--sec-ticker",
        "nvs",
        "--execution-profile",
        "direct_result",
    )

    assert exit_code == 2
    assert payload["status"] == "blocked"
    assert (
        payload["category"]
        == "sec_ticker_resolution_not_implemented"
    )
    assert payload["network_calls_made"] is False
    assert stderr == ""


def test_launcher_rejects_fixture_outside_asset_root(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Prevent launcher fixture reads outside the selected asset root."""

    outside_fixture = tmp_path / "outside.json"
    outside_fixture.write_text("{}", encoding="utf-8")

    asset_root = tmp_path / "asset"
    asset_root.mkdir()

    exit_code, payload, stderr = _run_launcher(
        capsys,
        "--asset-root",
        str(asset_root),
        "--fixture-path",
        str(outside_fixture),
        "--cik",
        "1114448",
    )

    assert exit_code == 2
    assert payload["status"] == "blocked"
    assert payload["category"] == "fixture_path_outside_asset_root"
    assert payload["network_calls_made"] is False
    assert stderr == ""


@pytest.mark.parametrize(
    "cik",
    [
        "ABC123",
        "12345678901",
        "-1114448",
    ],
)
def test_launcher_rejects_invalid_cik(
    cik: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reject malformed CIK values before fixture access."""

    exit_code, payload, stderr = _run_launcher(
        capsys,
        "--cik",
        cik,
        "--skip-publish",
    )

    assert exit_code == 2
    assert payload["status"] == "blocked"
    assert payload["category"] == "cik_invalid"
    assert payload["network_calls_made"] is False
    assert stderr == ""


def test_launcher_uses_adapter_owned_identity_without_env_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EDGAR_IDENTITY", raising=False)

    source = configure_edgartools_identity()

    assert source == "adapter_owned"
    assert DEFAULT_EDGAR_IDENTITY
    assert "EDGAR_IDENTITY" not in os.environ

@pytest.mark.parametrize("execution_substrate", ["local_worker", "ecs"])
def test_launcher_keeps_identity_out_of_environment_for_edgartools(
    execution_substrate: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Keep identity adapter-owned on local-worker and ECS."""

    observed: dict[str, Any] = {}

    class FakeAdapter:
        def invoke(
            self,
            inputs: dict[str, Any],
            context: dict[str, Any],
        ) -> dict[str, Any]:
            observed["environment_identity"] = os.environ.get("EDGAR_IDENTITY")
            observed["inputs"] = inputs
            observed["context"] = context
            return {
                "response_version": "1",
                "status": "success",
                "outputs": {},
                "logs": [],
                "metrics": {},
            }

    monkeypatch.delenv("EDGAR_IDENTITY", raising=False)
    monkeypatch.setattr(
        launch_module,
        "build_edgartools_adapter",
        lambda: FakeAdapter(),
    )

    exit_code, payload, stderr = _run_launcher(
        capsys,
        "--cik",
        "1114448",
        "--provider-path",
        "edgartools_invoke",
        "--execution-substrate",
        execution_substrate,
    )

    assert exit_code == 0
    assert payload["status"] == "success"
    assert observed["environment_identity"] is None
    assert observed["inputs"]["execution"] == {
        "provider_path": "edgartools_invoke",
    }
    assert observed["context"]["execution_substrate"] == execution_substrate
    assert stderr == ""


def test_launcher_blocks_runtime_request_without_projection(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Keep runtime lease/projection work outside the standalone launcher."""

    exit_code, payload, stderr = _run_launcher(
        capsys,
        "--cik",
        "1114448",
        "--provider-path",
        "runtime_request",
        "--execution-substrate",
        "ecs",
    )

    assert exit_code == 2
    assert payload["status"] == "blocked"
    assert (
        payload["category"]
        == "runtime_request_requires_runtime_projection_injection"
    )
    assert payload["provider_path"] == "runtime_request"
    assert payload["network_calls_made"] is False
    assert stderr == ""
