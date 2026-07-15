"""Run the SFDA full crawl and publish flow using the installed PI OBS wheel.

This helper is intended for developer/operator orchestration only. It keeps the
adapter pure: the adapter still receives resolved `sfda_response.records` and
returns normalized `drugs` output. It is not an ECS entrypoint, not a source
authority, and not a DLM/Core write client.

Flow:
1. Check the local Python runtime/wheel.
2. Build a fresh resolved SFDA input file with devtools.crawler_input_builder.
3. Validate full crawl coverage.
4. Queue the governed run through Assets and poll bounded runtime-write evidence.

Safety:
- No sensitive material is stored in this file.
- No raw target URL is stored in this file.
- No local machine path is stored in this file.
- No generated records are stored in this file.
- Assets owns queueing and observability; the selected runtime owns exact-file
  self-inspection and the single provider-direct output write.
- The policy helper never dispatches a second prepared-output publish.
- `obs-asset-launch` may call this helper, but this helper remains below the
  adapter-intake launcher contract and above the approved wheel commands.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
from datetime import date
from pathlib import Path
from typing import Any


RUNTIME_PACKAGE_NAME = "pi-obs-python-runtime"

DEFAULT_CAPABILITIES: dict[str, Any] = {
    "capabilities": {
        "sfda_getdrugs_crawler": {
            "handle": "@crawler.sfda_getdrugs",
            "kind": "crawler",
            "mode": "crawler_free_mode",
            "auth": {
                "mode": "public",
            },
            "runtime_profile": "spa_browser_session_api",
            "operation": "api_post_records",
            "egress": {
                "network_authority": "public_web",
                "execution_substrate": "server_managed",
                "region_policy": "platform_selected",
            },
            "auth_refresh": {
                "mode": "not_required",
                "owner": "none",
                "material_visibility": "none",
                "retry_owner": "assets_runtime",
            },
            "expected_input_role": "sfda_response",
            "expected_output_role": "drugs",
            "required": True,
            "pagination": {
                "mode": "incrementing_page_number",
                "page_parameter": "page",
                "start_page": 1,
                "page_step": 1,
                "stop_conditions": [
                    "explicit_last_page_metadata",
                    "empty_records_page",
                    "duplicate_page_hash",
                    "max_pages_guard",
                ],
                "max_pages_guard": 1000,
                "on_guard": "return_partial_with_pagination_truncated_true",
            },
            "request_shape": {
                "method": "POST",
                "body_fields": [
                    "TradeName",
                    "scientificName",
                    "Agent",
                    "ManufacturerName",
                    "RegNo",
                    "page",
                ],
                "required_page_field": "page",
            },
        }
    }
}


DEFAULT_REQUEST_WITHOUT_TARGET: dict[str, Any] = {
    "response": {
        "metadata_path": "data.result",
        "record_path": "data.result.results",
    },
    "request": {
        "method": "POST",
        "fields": {
            "ManufacturerName": "",
            "Agent": "",
            "RegNo": "",
            "TradeName": "",
            "page": "1",
            "scientificName": "",
        },
    },
}


def parse_version_tuple(value: str) -> tuple[int, ...]:
    """Parse a simple dotted version into a comparable integer tuple.

    This intentionally avoids external dependencies such as `packaging`.
    Non-numeric suffixes are ignored after the numeric prefix of each part.
    """
    parts: list[int] = []

    for raw_part in value.split("."):
        digits = []
        for char in raw_part:
            if char.isdigit():
                digits.append(char)
            else:
                break

        if digits:
            parts.append(int("".join(digits)))
        else:
            parts.append(0)

    return tuple(parts)


def check_runtime(*, minimum_runtime_version: str, skip_runtime_check: bool) -> None:
    """Check that the installed PI OBS runtime is usable before doing work."""
    if skip_runtime_check:
        print("Runtime check skipped by --skip-runtime-check.", flush=True)
        return

    print("Checking local PI OBS Python runtime...", flush=True)
    print(f"  python={sys.executable}", flush=True)

    try:
        installed_version = importlib.metadata.version(RUNTIME_PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError(
            f"{RUNTIME_PACKAGE_NAME} is not installed in this Python environment.\n"
            f"Current Python: {sys.executable}\n"
            "Install the wheel into this interpreter, then rerun."
        ) from exc

    installed_tuple = parse_version_tuple(installed_version)
    minimum_tuple = parse_version_tuple(minimum_runtime_version)

    if installed_tuple < minimum_tuple:
        raise RuntimeError(
            f"{RUNTIME_PACKAGE_NAME} version is too old.\n"
            f"Installed: {installed_version}\n"
            f"Required minimum: {minimum_runtime_version}\n"
            "Upgrade the wheel in this virtual environment, then rerun."
        )

    required_modules = [
        "devtools.crawler_input_builder",
        "devtools.asset_policy_runner",
        "devtools.asset_preflight",
        "devtools.adapter_intake",
    ]

    missing_modules = [
        module_name
        for module_name in required_modules
        if importlib.util.find_spec(module_name) is None
    ]

    if missing_modules:
        raise RuntimeError(
            "The installed runtime is missing required devtools modules:\n"
            + "\n".join(f"  - {module_name}" for module_name in missing_modules)
        )

    print(f"Runtime check passed: {RUNTIME_PACKAGE_NAME} {installed_version}", flush=True)


def stream_reader(
    pipe: Any,
    *,
    sink: Any | None,
    capture: list[str] | None,
) -> None:
    """Read a subprocess pipe until EOF, optionally printing and capturing lines."""
    try:
        for line in pipe:
            if capture is not None:
                capture.append(line)
            if sink is not None:
                print(line, file=sink, end="", flush=True)
    finally:
        pipe.close()


def run_command(command: list[str], *, cwd: Path, stream_stdout: bool = False) -> str:
    """Run a child command, stream progress live, and return captured stdout.

    The crawler writes progress to stderr. We stream stderr line-by-line so
    DataSpell shows crawl progress while the process is running.

    Stdout is captured because the wheel commands return final JSON reports on
    stdout, and the caller needs to parse those reports.
    """
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
        env=env,
    )

    stdout_chunks: list[str] = []

    if process.stdout is None or process.stderr is None:
        raise RuntimeError("Subprocess pipes were not created correctly.")

    stdout_thread = threading.Thread(
        target=stream_reader,
        kwargs={
            "pipe": process.stdout,
            "sink": sys.stdout if stream_stdout else None,
            "capture": stdout_chunks,
        },
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=stream_reader,
        kwargs={
            "pipe": process.stderr,
            "sink": sys.stderr,
            "capture": None,
        },
        daemon=True,
    )

    stdout_thread.start()
    stderr_thread.start()

    return_code = process.wait()

    stdout_thread.join()
    stderr_thread.join()

    stdout = "".join(stdout_chunks)

    if return_code != 0:
        raise RuntimeError(
            f"Command failed with exit code {return_code}.\n\n"
            f"STDOUT:\n{stdout}"
        )

    return stdout


def load_json_report(text: str, *, label: str) -> dict[str, Any]:
    """Parse a JSON report emitted by a wheel CLI."""
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} did not return valid JSON.") from exc

    if not isinstance(value, dict):
        raise RuntimeError(f"{label} returned JSON, but not a JSON object.")

    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON object to disk using UTF-8."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def normalize_execution_substrate(value: str) -> str:
    """Normalize a substrate label accepted by Assets."""
    normalized = value.replace("-", "_").lower().strip()
    allowed = {"local_worker", "ecs"}
    if normalized not in allowed:
        raise ValueError("execution_substrate must be local_worker or ecs.")
    return normalized


def run_local_diagnostics(
    *,
    asset_root: Path,
    env_file: Path | None,
    intake_yaml: Path | None,
    execution_substrate: str,
) -> dict[str, Any]:
    """Run lightweight readiness checks before any full crawl starts."""
    print("Running SFDA helper diagnostics...", flush=True)

    diagnostics: dict[str, Any] = {
        "schema_version": "sfda_getdrugs.helper_diagnostics.v1",
        "status": "ready",
        "execution_substrate": execution_substrate,
        "checks": {},
    }

    fixture_inputs = asset_root / "fixtures" / "sfda_getdrugs.inputs.json"
    if fixture_inputs.is_file():
        command = [
            sys.executable,
            "-m",
            "devtools.asset_preflight",
            "--adapter-root",
            str(asset_root),
            "--asset-key",
            "sfda.getdrugs",
            "--asset-version",
            "0.1.0",
            "--inputs-file",
            str(fixture_inputs),
            "--mode",
            "balanced",
            "--pretty",
        ]
        if env_file is not None and env_file.is_file():
            command.extend(["--env-file", str(env_file)])

        output = run_command(command, cwd=asset_root)
        preflight = load_json_report(output, label="asset preflight")
        local_package = preflight.get("local_package") if isinstance(preflight.get("local_package"), dict) else {}
        diagnostics["checks"]["asset_preflight"] = {
            "status": local_package.get("status") or preflight.get("status"),
            "category": local_package.get("category"),
            "safe": preflight.get("safe"),
        }
        if diagnostics["checks"]["asset_preflight"]["status"] != "ready":
            diagnostics["status"] = "blocked"
    else:
        diagnostics["checks"]["asset_preflight"] = {
            "status": "skipped",
            "reason": "fixture inputs file not found",
        }

    if intake_yaml is not None:
        if intake_yaml.is_file():
            output = run_command(
                [
                    sys.executable,
                    "-m",
                    "devtools.adapter_intake",
                    "--adapter-yaml",
                    str(intake_yaml),
                    "--pretty",
                ],
                cwd=asset_root,
            )
            intake = load_json_report(output, label="adapter intake")
            diagnostics["checks"]["adapter_intake"] = {
                "status": intake.get("status"),
                "category": intake.get("category"),
                "checked_count": intake.get("checked_count"),
                "blocked_count": intake.get("blocked_count"),
            }
            if intake.get("status") != "ready":
                diagnostics["status"] = "blocked"
        else:
            diagnostics["checks"]["adapter_intake"] = {
                "status": "skipped",
                "reason": "adapter.yaml not found",
            }

    print(json.dumps(diagnostics, indent=2, ensure_ascii=False), flush=True)

    if diagnostics["status"] != "ready":
        raise RuntimeError("SFDA helper diagnostics did not pass.")

    return diagnostics

def resolve_target_url(*, target_url: str | None, target_url_env: str | None) -> str | None:
    """Resolve a local target URL without storing it in the helper file."""
    if target_url:
        return target_url.strip()

    if target_url_env:
        value = os.environ.get(target_url_env, "").strip()
        if value:
            return value

    return None


def make_request_file_if_needed(
    *,
    temp_root: Path,
    request_file: Path | None,
    target_url: str | None,
) -> Path:
    """Return an existing request file or create a temporary one from safe defaults."""
    if request_file is not None:
        resolved = request_file.expanduser().resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"Request file was not found: {resolved}")
        return resolved

    if not target_url:
        raise RuntimeError(
            "No crawler request source was provided. Pass --request-file, "
            "or set --target-url-env to an environment variable containing the target URL, "
            "or pass --target-url locally."
        )

    request_payload = json.loads(json.dumps(DEFAULT_REQUEST_WITHOUT_TARGET))
    request_payload["request"]["target_url"] = target_url

    generated_request = temp_root / "sfda_getdrugs.request.generated.json"
    write_json(generated_request, request_payload)
    return generated_request


def make_capabilities_file_if_needed(
    *,
    temp_root: Path,
    capabilities_file: Path | None,
) -> Path:
    """Return an existing capabilities file or create one from safe built-in defaults."""
    if capabilities_file is not None:
        resolved = capabilities_file.expanduser().resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"Capabilities file was not found: {resolved}")
        return resolved

    generated_capabilities = temp_root / "sfda_getdrugs.capabilities.generated.json"
    write_json(generated_capabilities, DEFAULT_CAPABILITIES)
    return generated_capabilities


def make_runtime_source_inputs_file(
    *,
    temp_root: Path,
    runtime_source_inputs_file: Path,
    max_pages: int,
    cooldown_seconds: float,
    timeout_seconds: float,
    retry_attempts: int,
    retry_backoff_seconds: float,
) -> Path:
    """Copy a Runtime Source control profile and apply safe crawl controls."""
    resolved = runtime_source_inputs_file.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Runtime Source inputs file was not found: {resolved}")

    payload = json.loads(resolved.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise RuntimeError("Runtime Source inputs file must be a JSON object.")

    role = payload.get("sfda_response")
    if not isinstance(role, dict):
        raise RuntimeError("Runtime Source inputs file must contain sfda_response.")

    input_config = role.setdefault("input", {})
    if not isinstance(input_config, dict):
        raise RuntimeError("Runtime Source sfda_response.input must be an object.")

    pagination = input_config.setdefault("pagination", {})
    if not isinstance(pagination, dict):
        raise RuntimeError("Runtime Source sfda_response.input.pagination must be an object when present.")

    pagination["max_pages"] = max_pages
    pagination["cooldown_seconds"] = cooldown_seconds
    pagination["timeout_seconds"] = timeout_seconds
    pagination["retry_attempts"] = retry_attempts
    pagination["retry_backoff_seconds"] = retry_backoff_seconds

    generated = temp_root / "sfda_getdrugs.runtime_source.launch.inputs.json"
    write_json(generated, payload)
    print("Prepared Runtime Source crawl controls:", flush=True)
    print(f"  max_pages={max_pages}", flush=True)
    print(f"  cooldown_seconds={cooldown_seconds}", flush=True)
    print(f"  retry_attempts={retry_attempts}", flush=True)
    print(f"  retry_backoff_seconds={retry_backoff_seconds}", flush=True)
    return generated


def build_crawl_inputs(
    *,
    asset_root: Path,
    request_file: Path,
    capabilities_file: Path,
    output_path: Path,
    max_pages: int,
    minimum_pages: int,
    minimum_records: int,
    cooldown_seconds: float,
    timeout_seconds: float,
    retry_attempts: int,
    retry_backoff_seconds: float,
) -> dict[str, Any]:
    """Crawl SFDA pages and write an adapter-ready inputs JSON file."""
    print("Starting SFDA crawl...", flush=True)

    output = run_command(
        [
            sys.executable,
            "-m",
            "devtools.crawler_input_builder",
            "--request-file",
            str(request_file),
            "--capabilities",
            str(capabilities_file),
            "--capability-name",
            "sfda_getdrugs_crawler",
            "--input-role",
            "sfda_response",
            "--page-field",
            "page",
            "--start-page",
            "1",
            "--page-step",
            "1",
            "--max-pages",
            str(max_pages),
            "--record-limit",
            "1000000",
            "--cooldown-seconds",
            str(cooldown_seconds),
            "--timeout-seconds",
            str(timeout_seconds),
            "--retry-attempts",
            str(retry_attempts),
            "--retry-backoff-seconds",
            str(retry_backoff_seconds),
            "--progress",
            "--output",
            str(output_path),
            "--pretty",
        ],
        cwd=asset_root,
    )

    report = load_json_report(output, label="crawler")

    pages_crawled = int(report.get("pages_crawled") or 0)
    record_count = int(report.get("record_count") or 0)
    stop_reason = str(report.get("stop_reason") or "")

    if report.get("status") != "completed":
        raise RuntimeError(f"Crawler did not complete. Status: {report.get('status')}")

    if pages_crawled < minimum_pages:
        raise RuntimeError(
            f"Crawler did not reach full coverage: pages_crawled={pages_crawled}, "
            f"minimum_pages={minimum_pages}"
        )

    if record_count < minimum_records:
        raise RuntimeError(
            f"Crawler returned too few records: record_count={record_count}, "
            f"minimum_records={minimum_records}"
        )

    print("Crawler completed:", flush=True)
    print(f"  pages_crawled={pages_crawled}", flush=True)
    print(f"  record_count={record_count}", flush=True)
    print(f"  stop_reason={stop_reason}", flush=True)

    return report


def publish_to_node(
    *,
    asset_root: Path,
    env_file: Path,
    inputs_file: Path,
    extraction_date: str,
    prepared_output_wait_seconds: int,
    prepared_output_poll_seconds: int,
    minimum_records: int,
    execution_substrate: str,
    stage_native_payload: bool,
) -> dict[str, Any]:
    """Queue one Assets-observed runtime publisher and poll its safe evidence."""
    print("Submitting governed runtime-owned publish through Assets queue...", flush=True)

    command = [
        sys.executable,
        "-m",
        "devtools.asset_policy_runner",
        "--env-file",
        str(env_file),
        "--pretty",
        "run",
        "--policy-id",
        "app_sfda_getdrugs_daily_snapshot",
        "--execution-substrate",
        execution_substrate,
        "--inputs-file",
        str(inputs_file),
        "--entity-key",
        "sfda.getdrugs",
        "--output-role",
        "drugs",
        "--output-name",
        "sfda_getdrugs_daily_snapshot",
        "--artifact-type",
        "json",
        "--content-type",
        "application/json",
        "--schema-version",
        "sfda_getdrugs.records.v1",
        "--partition-value",
        f"extraction_date={extraction_date}",
        "--min-record-count",
        str(minimum_records),
    ]

    if stage_native_payload:
        command.extend(
            [
                "--native-payload-role",
                "sfda_response",
                "--native-payload-format",
                "jsonl",
                "--native-payload-chunk-bytes",
                "8388608",
            ]
        )

    command.extend(
        [
            "--prepared-output-wait-seconds",
            str(prepared_output_wait_seconds),
            "--prepared-output-poll-seconds",
            str(prepared_output_poll_seconds),
            "--runtime-owned-output-write",
        ]
    )

    output = run_command(command, cwd=asset_root)

    report = load_json_report(output, label="policy runner")
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)

    return report

def validate_positive_int(value: int, *, name: str) -> int:
    """Validate a positive integer CLI option."""
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")
    return value


def main() -> int:
    """CLI entry point for local full SFDA crawl and publish."""
    default_asset_root = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description="Run full SFDA crawl and publish to the governed JSON node."
    )
    parser.add_argument(
        "--asset-root",
        type=Path,
        default=default_asset_root,
        help="Local asset folder. Defaults to the folder containing this script.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Local dotenv file used by the installed PI OBS wheel. Do not commit it.",
    )
    parser.add_argument(
        "--request-file",
        type=Path,
        help="Optional local crawler request file. Do not push files containing raw URLs through intake.",
    )
    parser.add_argument(
        "--runtime-source-inputs-file",
        type=Path,
        help="Small Runtime Source referenced inputs file. Use this for ECS; it must not contain resolved records or raw source material.",
    )
    parser.add_argument(
        "--target-url-env",
        default="SFDA_GETDRUGS_TARGET_URL",
        help="Environment variable containing the crawler target URL when --request-file is omitted.",
    )
    parser.add_argument(
        "--target-url",
        help="Optional local target URL. Prefer --target-url-env for repeatable local runs.",
    )
    parser.add_argument(
        "--capabilities-file",
        type=Path,
        help="Optional local capabilities file. If omitted, safe built-in SFDA defaults are used.",
    )
    parser.add_argument(
        "--extraction-date",
        default=date.today().isoformat(),
        help="Partition value for extraction_date, for example 2026-07-11.",
    )
    parser.add_argument(
        "--execution-substrate",
        default="local_worker",
        choices=["local_worker", "local-worker", "ecs"],
        help="Runtime substrate requested from Assets for the publish-policy prepare run.",
    )
    parser.add_argument(
        "--idempotency-key",
        help="Deprecated compatibility option; runtime publication derives replay protection from the inspected payload and partition.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maximum pages to crawl. Required by the launcher for production Runtime Source runs.",
    )
    parser.add_argument(
        "--minimum-pages",
        type=int,
        default=449,
        help="Minimum accepted page coverage before publish.",
    )
    parser.add_argument(
        "--minimum-records",
        type=int,
        default=8000,
        help="Minimum accepted record count before publish.",
    )
    parser.add_argument(
        "--cooldown-seconds",
        type=float,
        default=0.0,
        help="Delay between page requests.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="HTTP timeout per crawler page.",
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=2,
        help="Maximum HTTP attempts per page.",
    )
    parser.add_argument(
        "--retry-backoff-seconds",
        type=float,
        default=1.0,
        help="Base delay between retry attempts.",
    )
    parser.add_argument(
        "--prepared-output-wait-seconds",
        type=int,
        default=1800,
        help="How long the policy runner waits for the prepared output.",
    )
    parser.add_argument(
        "--prepared-output-poll-seconds",
        type=int,
        default=5,
        help="Prepared-output polling interval.",
    )
    parser.add_argument(
        "--minimum-runtime-version",
        default="0.1.60",
        help="Minimum accepted pi-obs-python-runtime version.",
    )
    parser.add_argument(
        "--skip-runtime-check",
        action="store_true",
        help="Skip local runtime/wheel checks.",
    )
    parser.add_argument(
        "--runtime-check-only",
        action="store_true",
        help="Check the installed runtime and exit without crawling or publishing.",
    )
    parser.add_argument(
        "--diagnostics-only",
        action="store_true",
        help="Run runtime/package/intake diagnostics and exit without crawling or publishing.",
    )
    parser.add_argument(
        "--skip-diagnostics",
        action="store_true",
        help="Skip lightweight package/intake diagnostics before crawl.",
    )
    parser.add_argument(
        "--intake-yaml",
        type=Path,
        help="Optional adapter-intake adapter.yaml for reviewed-helper readiness checks.",
    )
    parser.add_argument(
        "--keep-inputs-file",
        type=Path,
        help="Optional local path where the generated resolved inputs file should be copied.",
    )
    parser.add_argument(
        "--skip-publish",
        action="store_true",
        help="Build and validate the crawl input, but do not publish.",
    )

    args = parser.parse_args()

    check_runtime(
        minimum_runtime_version=args.minimum_runtime_version,
        skip_runtime_check=args.skip_runtime_check,
    )

    if args.runtime_check_only:
        print("Runtime check only completed.", flush=True)
        return 0

    asset_root = args.asset_root.expanduser().resolve()
    env_file = args.env_file.expanduser().resolve() if args.env_file else None
    intake_yaml = args.intake_yaml.expanduser().resolve() if args.intake_yaml else None
    execution_substrate = normalize_execution_substrate(args.execution_substrate)
    runtime_source_inputs_file = args.runtime_source_inputs_file.expanduser().resolve() if args.runtime_source_inputs_file else None
    request_file_arg = args.request_file.expanduser().resolve() if args.request_file else None
    capabilities_file_arg = (
        args.capabilities_file.expanduser().resolve() if args.capabilities_file else None
    )

    if not asset_root.is_dir():
        raise FileNotFoundError(f"Asset root was not found: {asset_root}")

    if not args.skip_diagnostics:
        run_local_diagnostics(
            asset_root=asset_root,
            env_file=env_file,
            intake_yaml=intake_yaml,
            execution_substrate=execution_substrate,
        )

    if args.diagnostics_only:
        print("Diagnostics-only completed.", flush=True)
        return 0

    if not args.skip_publish:
        if env_file is None:
            raise RuntimeError("--env-file is required unless --skip-publish is used.")
        if not env_file.is_file():
            raise FileNotFoundError(f"Env file was not found: {env_file}")

    if args.max_pages is None and runtime_source_inputs_file is not None:
        raise RuntimeError("--max-pages is required for Runtime Source production runs.")
    max_pages = validate_positive_int(args.max_pages if args.max_pages is not None else 450, name="max_pages")
    minimum_pages = validate_positive_int(args.minimum_pages, name="minimum_pages")
    minimum_records = validate_positive_int(args.minimum_records, name="minimum_records")
    retry_attempts = validate_positive_int(args.retry_attempts, name="retry_attempts")
    wait_seconds = validate_positive_int(
        args.prepared_output_wait_seconds,
        name="prepared_output_wait_seconds",
    )
    poll_seconds = validate_positive_int(
        args.prepared_output_poll_seconds,
        name="prepared_output_poll_seconds",
    )

    target_url = resolve_target_url(
        target_url=args.target_url,
        target_url_env=args.target_url_env,
    )


    if runtime_source_inputs_file is not None:
        if not runtime_source_inputs_file.is_file():
            raise FileNotFoundError(
                f"Runtime Source inputs file was not found: {runtime_source_inputs_file}"
            )

        if args.skip_publish:
            print("Skipped publish because --skip-publish was set.", flush=True)
            return 0

        assert env_file is not None
        with tempfile.TemporaryDirectory(prefix="sfda_getdrugs_runtime_source_") as temp_dir:
            prepared_runtime_source_inputs = make_runtime_source_inputs_file(
                temp_root=Path(temp_dir),
                runtime_source_inputs_file=runtime_source_inputs_file,
                max_pages=max_pages,
                cooldown_seconds=args.cooldown_seconds,
                timeout_seconds=args.timeout_seconds,
                retry_attempts=retry_attempts,
                retry_backoff_seconds=args.retry_backoff_seconds,
            )
            publish_to_node(
                asset_root=asset_root,
                env_file=env_file,
                inputs_file=prepared_runtime_source_inputs,
                extraction_date=args.extraction_date,
                prepared_output_wait_seconds=wait_seconds,
                prepared_output_poll_seconds=poll_seconds,
                minimum_records=minimum_records,
                execution_substrate=execution_substrate,
                stage_native_payload=False,
            )
        return 0

    if execution_substrate == "ecs":
        raise RuntimeError(
            "ECS publish requires --runtime-source-inputs-file so Assets/Core resolves "
            "the source for the remote worker. Local crawler native-payload staging is "
            "local_worker-only until remote runtime object delivery is configured."
        )

    with tempfile.TemporaryDirectory(prefix="sfda_getdrugs_") as temp_dir:
        temp_root = Path(temp_dir)
        inputs_file = temp_root / f"sfda_getdrugs_{args.extraction_date}.inputs.json"

        request_file = make_request_file_if_needed(
            temp_root=temp_root,
            request_file=request_file_arg,
            target_url=target_url,
        )
        capabilities_file = make_capabilities_file_if_needed(
            temp_root=temp_root,
            capabilities_file=capabilities_file_arg,
        )

        build_crawl_inputs(
            asset_root=asset_root,
            request_file=request_file,
            capabilities_file=capabilities_file,
            output_path=inputs_file,
            max_pages=max_pages,
            minimum_pages=minimum_pages,
            minimum_records=minimum_records,
            cooldown_seconds=args.cooldown_seconds,
            timeout_seconds=args.timeout_seconds,
            retry_attempts=retry_attempts,
            retry_backoff_seconds=args.retry_backoff_seconds,
        )

        if args.keep_inputs_file is not None:
            keep_path = args.keep_inputs_file.expanduser().resolve()
            keep_path.parent.mkdir(parents=True, exist_ok=True)
            keep_path.write_text(inputs_file.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"Kept generated inputs file at: {keep_path}", flush=True)

        if args.skip_publish:
            print("Skipped publish because --skip-publish was set.", flush=True)
            return 0

        assert env_file is not None

        publish_to_node(
            asset_root=asset_root,
            env_file=env_file,
            inputs_file=inputs_file,
            extraction_date=args.extraction_date,
            prepared_output_wait_seconds=wait_seconds,
            prepared_output_poll_seconds=poll_seconds,
            minimum_records=minimum_records,
            execution_substrate=execution_substrate,
            stage_native_payload=True,
        )

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
