"""Launch the packaged yfinance adapter through a reviewed execution profile.

The queued_summary profile records a lightweight Assets run. direct_result
invokes the adapter once in its admitted dependency environment and returns
the full normalized response directly without using the Assets queue.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any, Iterator, Sequence

from devtools.connection_check import load_env_file
from devtools.obs_api_client import ObsApiError


def build_registration_payload(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Load registration orchestration only when a launch is requested."""
    from devtools.asset_register import build_registration_payload as implementation

    return implementation(*args, **kwargs)


def register_assets(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Load the governed registration client lazily."""
    from devtools.asset_register import register_assets as implementation

    return implementation(*args, **kwargs)


def run_runtime_smoke(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Load queue submission only after adapter discovery has completed."""
    from devtools.asset_runtime_smoke import run_runtime_smoke as implementation

    return implementation(*args, **kwargs)


def invoke_direct_adapter(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Load the governed in-memory invoker only for direct execution."""
    from devtools.direct_asset import invoke_direct_adapter as implementation

    return implementation(*args, **kwargs)


def build_direct_adapter() -> Any:
    """Instantiate only the reviewed yfinance adapter selected by this helper."""
    from yfinance_market_data_adapter import YFinanceMarketDataAdapter

    return YFinanceMarketDataAdapter()


ASSET_KEY = "nusaibah.yfinance_market_data"
ASSET_VERSION = "0.2.2"
LAUNCHER_MANIFEST = "yfinance_market_data.launcher.json"
_DIRECT_ENV_NAMES = {
    "CURL_CA_BUNDLE",
    "OBS_ASSET_DEPENDENCY_CACHE_ROOT",
    "OBS_ASSET_OUTBOUND_POLICY_ENFORCED",
    "REQUESTS_CA_BUNDLE",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
}
_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.^=-]{1,32}$")
_LINE_ITEM_PATTERN = re.compile(r"^[a-z0-9_]{1,128}$")
_PERIODS = ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max")
_INTERVALS = ("1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo")
_ATTRIBUTES = (
    "currency", "exchange", "quote_type", "last_price", "previous_close",
    "open", "day_high", "day_low", "year_high", "year_low", "market_cap",
    "shares", "last_volume", "short_name", "long_name", "sector", "industry", "country",
)


class YFinanceLaunchError(RuntimeError):
    """Value-safe launcher failure."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run yfinance through a reviewed queued or direct execution profile.")
    parser.add_argument("--asset-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--symbol")
    parser.add_argument(
        "--operation",
        choices=("history", "snapshot", "attribute", "financial_statement"),
        default="history",
    )
    parser.add_argument("--period", choices=_PERIODS, default="5d")
    parser.add_argument("--interval", choices=_INTERVALS, default="1d")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--max-rows", type=int, default=5)
    parser.add_argument("--round-digits", type=int, default=4)
    parser.add_argument("--attribute", choices=_ATTRIBUTES)
    parser.add_argument(
        "--statement",
        choices=("income_statement", "balance_sheet", "cash_flow"),
        default="income_statement",
    )
    parser.add_argument("--frequency", choices=("annual", "quarterly"), default="annual")
    parser.add_argument("--max-periods", type=int, default=4)
    parser.add_argument("--max-line-items", type=int, default=80)
    parser.add_argument("--line-item")
    parser.add_argument("--timeout-seconds", type=int, default=15)
    parser.add_argument("--no-auto-adjust", action="store_true")
    parser.add_argument("--prepost", action="store_true")
    parser.add_argument("--include-actions", action="store_true")
    parser.add_argument(
        "--execution-substrate",
        default="local_worker",
        choices=("local_worker", "local-worker", "ecs"),
    )
    parser.add_argument(
        "--execution-profile",
        default="queued_summary",
        choices=("queued_summary", "direct_result"),
    )
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--poll-timeout", type=float, default=300.0)
    parser.add_argument("--skip-publish", action="store_true")
    parser.add_argument("--diagnostics-only", action="store_true")
    parser.add_argument("--runtime-check-only", action="store_true")
    parser.add_argument("--skip-diagnostics", action="store_true")
    return parser


def build_variables(args: argparse.Namespace) -> dict[str, Any]:
    symbol = str(args.symbol or "").strip().upper()
    if not _SYMBOL_PATTERN.fullmatch(symbol):
        raise YFinanceLaunchError("symbol_invalid")
    _bounded(args.round_digits, 0, 10, "round_digits_invalid")
    _bounded(args.timeout_seconds, 1, 60, "timeout_invalid")

    variables: dict[str, Any] = {
        "symbol": symbol,
        "operation": args.operation,
        "round_digits": args.round_digits,
        "timeout_seconds": args.timeout_seconds,
    }

    if args.operation == "history":
        _bounded(args.max_rows, 1, 1000, "max_rows_invalid")
        start = _optional_date(args.start, "start_invalid")
        end = _optional_date(args.end, "end_invalid")
        if start is not None and end is not None and start >= end:
            raise YFinanceLaunchError("history_date_range_invalid")
        variables.update(
            {
                "period": args.period,
                "interval": args.interval,
                "max_rows": args.max_rows,
                "auto_adjust": not args.no_auto_adjust,
                "prepost": args.prepost,
                "include_actions": args.include_actions,
            }
        )
        if start is not None:
            variables["start"] = start
        if end is not None:
            variables["end"] = end
    elif args.operation == "attribute":
        if args.attribute is None:
            raise YFinanceLaunchError("attribute_required")
        variables["attribute"] = args.attribute
    elif args.operation == "financial_statement":
        _bounded(args.max_periods, 1, 8, "max_periods_invalid")
        _bounded(args.max_line_items, 1, 200, "max_line_items_invalid")
        variables.update(
            {
                "statement": args.statement,
                "frequency": args.frequency,
                "max_periods": args.max_periods,
                "max_line_items": args.max_line_items,
            }
        )
        if args.line_item:
            line_item = re.sub(r"[^A-Za-z0-9]+", "_", args.line_item).strip("_").lower()
            if not _LINE_ITEM_PATTERN.fullmatch(line_item):
                raise YFinanceLaunchError("line_item_invalid")
            variables["line_item"] = line_item

    return variables


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.runtime_check_only:
        _print({"schema_version": "yfinance_market_data.launch.v1", "status": "ready", "category": "runtime_ready", "safe": True, "values_included": False})
        return 0
    if args.diagnostics_only:
        _print(
            {
                "schema_version": "yfinance_market_data.launch.v1",
                "status": "ready",
                "category": "launcher_diagnostics_ready",
                "safe": True,
                "values_included": False,
                "network_calls_made": False,
                "asset_key": ASSET_KEY,
                "asset_version": ASSET_VERSION,
            }
        )
        return 0

    phase = "input_validation"
    try:
        variables = build_variables(args)
        if args.skip_publish:
            _print(
                {
                    "schema_version": "yfinance_market_data.launch.v1",
                    "status": "ready",
                    "category": "governed_launch_inputs_ready",
                    "safe": True,
                    "values_included": False,
                    "network_calls_made": False,
                    "variable_keys": sorted(variables),
                }
            )
            return 0
        if args.env_file is None:
            raise YFinanceLaunchError("env_file_required")

        env_values = load_env_file(str(args.env_file.expanduser().resolve()))
        if args.execution_profile == "direct_result":
            phase = "direct_execution"
            dependency_required, max_result_bytes = _direct_result_settings(args.asset_root)
            with _temporary_direct_environment(env_values):
                try:
                    result = invoke_direct_adapter(
                        build_direct_adapter(),
                        {"variables": variables},
                        {
                            "mode": "direct_result",
                            "execution_substrate": args.execution_substrate.replace("-", "_"),
                            "asset_key": ASSET_KEY,
                            "asset_version": ASSET_VERSION,
                        },
                        require_dependency_environment=dependency_required,
                        max_result_bytes=max_result_bytes,
                    )
                except Exception:
                    raise YFinanceLaunchError("direct_result_execution_failed") from None
            _print(result)
            return 0 if result.get("status") == "success" else 2

        env = dict(os.environ)
        env.update(env_values)
        phase = "registration_payload"
        registration_payload = build_registration_payload(adapter_root=str(args.asset_root.resolve()))
        phase = "registration"
        registration = register_assets(env=env, payload=registration_payload, timeout=30.0)
        if registration.get("status") != "accepted":
            raise YFinanceLaunchError("asset_registration_failed")
        if registration.get("execution_enabled") is not True:
            _print(
                {
                    "schema_version": "yfinance_market_data.launch.v1",
                    "status": "blocked",
                    "category": "registration_execution_not_ready",
                    "safe": True,
                    "values_included": False,
                    "registration": registration,
                }
            )
            return 2

        smoke_args = argparse.Namespace(
            env_file=str(args.env_file.expanduser().resolve()),
            client_id=None,
            source_app="obs-asset-launch-yfinance",
            entity_key=ASSET_KEY,
            asset_key=ASSET_KEY,
            asset_version=ASSET_VERSION,
            route="agent",
            mode="balanced",
            execution_substrate=args.execution_substrate.replace("-", "_"),
            inputs_json=json.dumps({"variables": variables}, separators=(",", ":")),
            inputs_file=None,
            tool_request_role="tool_request",
            mcp_record_json=[],
            no_poll=False,
            poll_interval=args.poll_interval,
            poll_timeout=args.poll_timeout,
            no_result=False,
            include_safe_result=True,
            pretty=True,
            **{
                "obs_" + "base_" + "url": None,
                "api_" + "key_" + "header": None,
                "api_" + "key": None,
            },
        )
        phase = "queue_execution"
        run = run_runtime_smoke(smoke_args)
        result = {
            "schema_version": "yfinance_market_data.launch.v1",
            "status": run.get("status"),
            "safe": True,
            "values_included": bool(run.get("values_included")),
            "registration": registration,
            "run": run,
        }
        _print(result)
        return 0 if run.get("status") == "completed" else 2
    except (ObsApiError, OSError, ValueError, YFinanceLaunchError) as exc:
        category = str(exc) if isinstance(exc, YFinanceLaunchError) else f"governed_{phase}_failed"
        _print(
            {
                "schema_version": "yfinance_market_data.launch.v1",
                "status": "blocked",
                "category": category,
                "safe": True,
                "values_included": False,
            }
        )
        return 2


def _direct_result_settings(asset_root: Path) -> tuple[bool, int]:
    manifest_path = asset_root.expanduser().resolve() / LAUNCHER_MANIFEST
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        raise YFinanceLaunchError("direct_result_contract_invalid") from None
    execution = manifest.get("execution") if isinstance(manifest, dict) else None
    direct = execution.get("direct_result") if isinstance(execution, dict) else None
    if not isinstance(direct, dict):
        raise YFinanceLaunchError("direct_result_contract_invalid")
    dependency_mode = direct.get("dependency_environment")
    max_result_bytes = direct.get("max_result_bytes")
    if dependency_mode not in {"required", "optional"}:
        raise YFinanceLaunchError("direct_result_contract_invalid")
    if (
        isinstance(max_result_bytes, bool)
        or not isinstance(max_result_bytes, int)
        or max_result_bytes < 1
        or max_result_bytes > 10 * 1024 * 1024
    ):
        raise YFinanceLaunchError("direct_result_contract_invalid")
    return dependency_mode == "required", max_result_bytes


@contextmanager
def _temporary_direct_environment(values: dict[str, str]) -> Iterator[None]:
    previous: dict[str, str | None] = {}
    for name in _DIRECT_ENV_NAMES:
        if name not in values:
            continue
        previous[name] = os.environ.get(name)
        os.environ[name] = str(values[name])
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _optional_date(value: str | None, code: str) -> str | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise YFinanceLaunchError(code) from exc


def _bounded(value: int, minimum: int, maximum: int, code: str) -> None:
    if isinstance(value, bool) or value < minimum or value > maximum:
        raise YFinanceLaunchError(code)


def _print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True))


if __name__ == "__main__":
    raise SystemExit(main())
