"""Launch the SEC company-reference adapter through reviewed provider paths.

The launcher supports three explicit paths:

``local_fixture``
    Deterministic fixture-backed direct execution for local verification.

``edgartools_invoke``
    Direct EdgarTools execution on either ``local_worker`` or ``ecs``. The
    launcher injects the reviewed organisation-wide identity when
    ``EDGAR_IDENTITY`` is absent. An existing environment value overrides the
    launcher default. The launcher never accepts or prints the identity.

``runtime_request``
    Declared by the asset but not executed by this standalone launcher. The
    governed runtime must acquire the lease/capability and inject the bounded
    SEC projection directly into the adapter invocation.

Provider paths are mutually exclusive and never fall back to one another.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Sequence

try:
    from .local_sec_company_reference_client import (
        LocalFixtureSecCompanyReferenceClient,
    )
    from .sec_company_reference_adapter import (
        EDGAR_IDENTITY,
        SecCompanyReferenceAdapter,
    )
except ImportError:  # Standalone adapter-project execution.
    from local_sec_company_reference_client import (
        LocalFixtureSecCompanyReferenceClient,
    )
    from sec_company_reference_adapter import (
        EDGAR_IDENTITY,
        SecCompanyReferenceAdapter,
    )


ASSET_KEY = "nusaibah.sec_company_reference"
ASSET_VERSION = "0.1.1"
LAUNCH_SCHEMA_VERSION = "sec_company_reference.launch.v1"

LOCAL_FIXTURE_PATH = "local_fixture"
RUNTIME_REQUEST_PATH = "runtime_request"
EDGARTOOLS_INVOKE_PATH = "edgartools_invoke"

DEFAULT_FIXTURE_PATH = Path(
    "fixtures/sec_company_reference.cik.expected.json"
)

DIRECT_RESULT_MAX_BYTES = 1_048_576

_CIK_PATTERN = re.compile(r"^\d{1,10}$")
_SEC_TICKER_PATTERN = re.compile(r"^[A-Z0-9.^=-]{1,32}$")
_SAFE_ERROR_CODE_PATTERN = re.compile(r"^[a-z0-9_]{1,120}$")

DEFAULT_EDGAR_IDENTITY = EDGAR_IDENTITY


class SecCompanyReferenceLaunchError(RuntimeError):
    """Represent a value-safe launcher failure."""


def configure_edgartools_identity() -> str:
    """Report the adapter-owned Edgar identity source without mutating env."""

    if not DEFAULT_EDGAR_IDENTITY.strip():
        raise SecCompanyReferenceLaunchError(
            "edgartools_identity_not_configured"
        )
    return "adapter_owned"


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for reviewed execution."""

    parser = argparse.ArgumentParser(
        description=(
            "Run the SEC company-reference adapter through diagnostics, "
            "input dry-run, local fixtures, or EdgarTools."
        )
    )

    parser.add_argument(
        "--asset-root",
        type=Path,
        default=Path(__file__).resolve().parent,
    )

    identifier_group = parser.add_mutually_exclusive_group()

    identifier_group.add_argument(
        "--cik",
        help="SEC Central Index Key, with or without leading zeroes.",
    )

    identifier_group.add_argument(
        "--sec-ticker",
        help=(
            "SEC ticker identifier. Validation exists, but resolution "
            "is not implemented."
        ),
    )

    parser.add_argument(
        "--provider-path",
        default=LOCAL_FIXTURE_PATH,
        choices=(
            LOCAL_FIXTURE_PATH,
            RUNTIME_REQUEST_PATH,
            EDGARTOOLS_INVOKE_PATH,
        ),
        help=(
            "Select exactly one provider path. runtime_request is runtime-"
            "owned and therefore blocked in this standalone launcher."
        ),
    )

    parser.add_argument(
        "--fixture-path",
        type=Path,
        default=DEFAULT_FIXTURE_PATH,
        help=(
            "Local expected-response fixture used only by local_fixture. "
            "Relative paths are resolved under --asset-root."
        ),
    )

    parser.add_argument(
        "--execution-substrate",
        default="local_worker",
        choices=(
            "local_worker",
            "local-worker",
            "ecs",
        ),
    )

    parser.add_argument(
        "--execution-profile",
        default="direct_result",
        choices=(
            "direct_result",
            "queued_summary",
        ),
    )

    parser.add_argument(
        "--skip-publish",
        action="store_true",
    )

    parser.add_argument(
        "--diagnostics-only",
        action="store_true",
    )

    parser.add_argument(
        "--runtime-check-only",
        action="store_true",
    )

    parser.add_argument(
        "--skip-diagnostics",
        action="store_true",
    )

    return parser


def build_variables(
    args: argparse.Namespace,
) -> dict[str, str]:
    """Validate and normalise exactly one launcher identifier."""

    raw_cik = str(args.cik or "").strip()
    raw_ticker = str(args.sec_ticker or "").strip().upper()

    if not raw_cik and not raw_ticker:
        raise SecCompanyReferenceLaunchError(
            "identifier_required"
        )

    if raw_cik:
        if not _CIK_PATTERN.fullmatch(raw_cik):
            raise SecCompanyReferenceLaunchError(
                "cik_invalid"
            )

        normalized_cik = raw_cik.lstrip("0") or "0"

        return {
            "cik": normalized_cik.zfill(10),
        }

    if not _SEC_TICKER_PATTERN.fullmatch(raw_ticker):
        raise SecCompanyReferenceLaunchError(
            "sec_ticker_invalid"
        )

    return {
        "sec_ticker": raw_ticker,
    }


def build_fixture_adapter(
    fixture_path: Path,
) -> SecCompanyReferenceAdapter:
    """Build the deterministic fixture-backed adapter."""

    client = LocalFixtureSecCompanyReferenceClient(
        fixture_path
    )

    return SecCompanyReferenceAdapter(
        client=client
    )


def build_edgartools_adapter() -> SecCompanyReferenceAdapter:
    """Build the adapter that lazily selects the EdgarTools client."""

    return SecCompanyReferenceAdapter()


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Execute one reviewed launcher command."""

    args = build_parser().parse_args(argv)
    edgar_identity_source = configure_edgartools_identity()

    execution_substrate = args.execution_substrate.replace("-", "_")

    if args.runtime_check_only:
        _print(
            {
                "schema_version": LAUNCH_SCHEMA_VERSION,
                "status": "ready",
                "category": "runtime_ready",
                "safe": True,
                "values_included": False,
                "network_calls_made": False,
            }
        )
        return 0

    if args.diagnostics_only:
        _print(
            {
                "schema_version": LAUNCH_SCHEMA_VERSION,
                "status": "ready",
                "edgartools_identity_source": edgar_identity_source,
                "category": "launcher_diagnostics_ready",
                "safe": True,
                "values_included": False,
                "network_calls_made": False,
                "asset_key": ASSET_KEY,
                "asset_version": ASSET_VERSION,
                # Retained for backward compatibility with the original
                # fixture-only launcher diagnostics contract.
                "direct_result_mode": "local_fixture_only",
                "launcher_provider_paths": [
                    LOCAL_FIXTURE_PATH,
                    EDGARTOOLS_INVOKE_PATH,
                ],
                "runtime_owned_provider_paths": [
                    RUNTIME_REQUEST_PATH,
                ],
                "default_provider_path": LOCAL_FIXTURE_PATH,
                "edgartools_identity_configured": (
                    _edgartools_identity_configured()
                ),
                "automatic_provider_fallback_enabled": False,
                "queued_execution_enabled": False,
            }
        )
        return 0

    phase = "input_validation"
    provider_invocation_started = False

    try:
        variables = build_variables(args)

        # --skip-publish is an input dry-run. It validates and normalises
        # arguments without reading fixtures or invoking a provider.
        if args.skip_publish:
            _print(
                {
                    "schema_version": LAUNCH_SCHEMA_VERSION,
                    "status": "ready",
                    "category": (
                        "governed_launch_inputs_ready"
                    ),
                    "safe": True,
                    "values_included": False,
                    "network_calls_made": False,
                    "variable_keys": sorted(variables),
                    "provider_path": args.provider_path,
                    "execution_profile": (
                        args.execution_profile
                    ),
                    "execution_substrate": execution_substrate,
                }
            )
            return 0

        # Queue registration and submission remain deliberately disabled.
        if args.execution_profile == "queued_summary":
            raise SecCompanyReferenceLaunchError(
                "queued_execution_requires_approved_sec_client"
            )

        # Ticker-to-CIK resolution is outside the current CIK-only slice.
        if "sec_ticker" in variables:
            raise SecCompanyReferenceLaunchError(
                "sec_ticker_resolution_not_implemented"
            )

        if args.provider_path == RUNTIME_REQUEST_PATH:
            raise SecCompanyReferenceLaunchError(
                "runtime_request_requires_runtime_source_injection"
            )

        if args.provider_path == LOCAL_FIXTURE_PATH:
            phase = "fixture_resolution"

            asset_root = (
                args.asset_root
                .expanduser()
                .resolve()
            )

            fixture_path = _resolve_fixture_path(
                asset_root=asset_root,
                fixture_path=args.fixture_path,
            )

            adapter = build_fixture_adapter(fixture_path)
            adapter_inputs: dict[str, Any] = {
                "variables": variables,
            }
            provider_mode = "local_fixture_only"

        elif args.provider_path == EDGARTOOLS_INVOKE_PATH:
            phase = "edgartools_configuration"

            if not _edgartools_identity_configured():
                raise SecCompanyReferenceLaunchError(
                    "edgartools_identity_not_configured"
                )

            adapter = build_edgartools_adapter()
            adapter_inputs = {
                "variables": variables,
                "execution": {
                    "provider_path": EDGARTOOLS_INVOKE_PATH,
                },
            }
            provider_mode = EDGARTOOLS_INVOKE_PATH

        else:  # argparse constrains this, retained as a fail-closed guard.
            raise SecCompanyReferenceLaunchError(
                "unsupported_provider_path"
            )

        phase = "direct_execution"
        provider_invocation_started = (
            args.provider_path == EDGARTOOLS_INVOKE_PATH
        )

        result = adapter.invoke(
            adapter_inputs,
            {
                "mode": "direct_result",
                "execution_substrate": execution_substrate,
                "asset_key": ASSET_KEY,
                "asset_version": ASSET_VERSION,
                "provider_mode": provider_mode,
            },
        )

        _ensure_result_size(result)
        _print(result)

        if result.get("status") == "success":
            return 0

        return 2

    except SecCompanyReferenceLaunchError as exc:
        category = str(exc)
        network_calls_made: bool | None = False

    except FileNotFoundError:
        category = "local_fixture_not_found"
        network_calls_made = False

    except json.JSONDecodeError:
        category = "local_fixture_invalid_json"
        network_calls_made = False

    except (RuntimeError, ValueError) as exc:
        category = _safe_error_category(
            exc,
            fallback=f"governed_{phase}_failed",
        )
        network_calls_made = (
            None if provider_invocation_started else False
        )

    except (OSError, TypeError):
        category = f"governed_{phase}_failed"
        network_calls_made = (
            None if provider_invocation_started else False
        )

    _print(
        {
            "schema_version": LAUNCH_SCHEMA_VERSION,
            "status": "blocked",
            "category": category,
            "safe": True,
            "values_included": False,
            "network_calls_made": network_calls_made,
            "provider_path": args.provider_path,
        }
    )

    return 2


def _edgartools_identity_configured() -> bool:
    """Return whether the reviewed adapter-owned identity is present."""

    return bool(DEFAULT_EDGAR_IDENTITY.strip())


def _safe_error_category(
    exc: BaseException,
    *,
    fallback: str,
) -> str:
    """Return a stable error code without exposing provider details."""

    message = str(exc).strip()
    if _SAFE_ERROR_CODE_PATTERN.fullmatch(message):
        return message

    return fallback


def _resolve_fixture_path(
    *,
    asset_root: Path,
    fixture_path: Path,
) -> Path:
    """Resolve a fixture while keeping reads inside the asset root."""

    candidate = fixture_path.expanduser()

    if not candidate.is_absolute():
        candidate = asset_root / candidate

    resolved = candidate.resolve()

    if (
        resolved != asset_root
        and asset_root not in resolved.parents
    ):
        raise SecCompanyReferenceLaunchError(
            "fixture_path_outside_asset_root"
        )

    if not resolved.is_file():
        raise FileNotFoundError(resolved)

    return resolved


def _ensure_result_size(
    result: dict[str, Any],
) -> None:
    """Reject direct results larger than the reviewed local limit."""

    encoded = json.dumps(
        result,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")

    if len(encoded) > DIRECT_RESULT_MAX_BYTES:
        raise SecCompanyReferenceLaunchError(
            "direct_result_size_limit_exceeded"
        )


def _print(
    payload: dict[str, Any],
) -> None:
    """Print one stable JSON payload to standard output."""

    print(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
