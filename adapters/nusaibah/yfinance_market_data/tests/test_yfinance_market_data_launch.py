from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "yfinance_market_data_launch.py"
SPEC = importlib.util.spec_from_file_location("yfinance_market_data_launch", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_build_history_variables_is_bounded() -> None:
    args = MODULE.build_parser().parse_args(
        ["--symbol", "novn.sw", "--max-rows", "5", "--period", "5d", "--interval", "1d"]
    )

    variables = MODULE.build_variables(args)

    assert variables["symbol"] == "NOVN.SW"
    assert variables["operation"] == "history"
    assert variables["max_rows"] == 5
    assert variables["auto_adjust"] is True


def test_invalid_symbol_is_rejected() -> None:
    args = MODULE.build_parser().parse_args(["--symbol", "NVS; whoami"])

    with pytest.raises(MODULE.YFinanceLaunchError, match="symbol_invalid"):
        MODULE.build_variables(args)


def test_skip_publish_makes_no_network_call(capsys: pytest.CaptureFixture[str]) -> None:
    assert MODULE.main(["--symbol", "NVS", "--skip-publish"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "ready"
    assert report["network_calls_made"] is False
    assert report["values_included"] is False


def test_direct_result_returns_values_without_assets_queue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OBS_ASSET_OUTBOUND_POLICY_ENFORCED=true\n", encoding="utf-8")
    (tmp_path / MODULE.LAUNCHER_MANIFEST).write_text(
        json.dumps(
            {
                "execution": {
                    "direct_result": {
                        "dependency_environment": "required",
                        "max_result_bytes": 1048576,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    adapter = object()
    calls: list[str] = []

    monkeypatch.setattr(
        MODULE,
        "load_env_file",
        lambda path: {"OBS_ASSET_OUTBOUND_POLICY_ENFORCED": "true"},
    )
    monkeypatch.setattr(MODULE, "build_direct_adapter", lambda: adapter)

    def fake_direct(current, inputs, context, **kwargs):
        calls.append("direct")
        assert current is adapter
        assert inputs["variables"]["symbol"] == "NVS"
        assert context["mode"] == "direct_result"
        assert kwargs["require_dependency_environment"] is True
        assert kwargs["max_result_bytes"] == 1048576
        assert os.environ["OBS_ASSET_OUTBOUND_POLICY_ENFORCED"] == "true"
        return {
            "response_version": "1",
            "status": "success",
            "outputs": {
                "market_data": {
                    "symbol": "NVS",
                    "data": {"records": [{"date": "2026-07-16", "close": 117.5}]} ,
                }
            },
        }

    def queue_call_forbidden(*args, **kwargs):
        raise AssertionError("Assets queue helper must not be called")

    monkeypatch.setattr(MODULE, "invoke_direct_adapter", fake_direct)
    monkeypatch.setattr(MODULE, "build_registration_payload", queue_call_forbidden)
    monkeypatch.setattr(MODULE, "register_assets", queue_call_forbidden)
    monkeypatch.setattr(MODULE, "run_runtime_smoke", queue_call_forbidden)

    assert MODULE.main(
        [
            "--asset-root",
            str(tmp_path),
            "--env-file",
            str(env_file),
            "--execution-profile",
            "direct_result",
            "--symbol",
            "NVS",
        ]
    ) == 0

    report = json.loads(capsys.readouterr().out)
    assert calls == ["direct"]
    assert report["status"] == "success"
    assert report["outputs"]["market_data"]["data"]["records"][0]["close"] == 117.5
    assert "run" not in report
    assert "registration" not in report


def test_live_path_registers_then_launches_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OBS_BASE_URL=http://example.invalid\n", encoding="utf-8")
    calls: list[str] = []

    monkeypatch.setattr(MODULE, "load_env_file", lambda path: {"OBS_BASE_URL": "http://example.invalid"})
    monkeypatch.setattr(MODULE, "build_registration_payload", lambda **kwargs: {"assets": [{}]})

    def fake_register_assets(**kwargs: object) -> dict[str, object]:
        calls.append("register")
        return {
            "status": "accepted",
            "execution_enabled": True,
            "registered_count": 1,
            "values_included": False,
        }

    def fake_run_runtime_smoke(args: object) -> dict[str, object]:
        calls.append("launch")
        assert getattr(args, "entity_key") == MODULE.ASSET_KEY
        assert getattr(args, "asset_key") == MODULE.ASSET_KEY
        assert getattr(args, "asset_version") == MODULE.ASSET_VERSION
        assert getattr(args, "include_safe_result") is True
        return {
            "status": "completed",
            "safe": True,
            "values_included": True,
            "result": {"data": {"outputs": {"market_data": {"symbol": "NVS"}}}},
        }

    monkeypatch.setattr(MODULE, "register_assets", fake_register_assets)
    monkeypatch.setattr(MODULE, "run_runtime_smoke", fake_run_runtime_smoke)

    assert MODULE.main(["--asset-root", str(tmp_path), "--env-file", str(env_file), "--symbol", "NVS"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert calls == ["register", "launch"]
    assert report["status"] == "completed"
    assert report["values_included"] is True
    assert report["run"]["result"]["data"]["outputs"]["market_data"]["symbol"] == "NVS"
