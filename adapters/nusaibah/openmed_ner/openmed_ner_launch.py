"""Run OpenMed NER through the reviewed direct-result/no-publish profile.

The helper accepts a bounded local JSON request, invokes the existing adapter
once, validates and size-bounds the response through the runtime direct-result
invoker, and returns the result to caller memory. It performs no Assets API,
queue, staging, Core, storage, or publication operation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence


ASSET_KEY = "nusaibah.openmed_ner"
ASSET_VERSION = "0.1.0"
LAUNCHER_MANIFEST = "openmed_ner.launcher.json"
DEFAULT_CONTEXT: dict[str, Any] = {
    "max_records": 8,
    "max_characters": 4000,
    "max_length": 128,
    "score_threshold": 0.5,
}
_ALLOWED_ROLE_FIELDS = {"records", "metadata", "provenance"}
_ALLOWED_RECORD_FIELDS = {"record_id", "text"}


class OpenMedNerLaunchError(RuntimeError):
    """Value-safe launcher failure."""


def invoke_direct_adapter(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Load the governed in-memory invoker only during direct execution."""
    from devtools.direct_asset import invoke_direct_adapter as implementation

    return implementation(*args, **kwargs)


def build_direct_adapter() -> Any:
    """Instantiate only the reviewed OpenMed NER adapter."""
    from openmed_ner_adapter import OpenMedNerAdapter

    return OpenMedNerAdapter()


def build_parser() -> argparse.ArgumentParser:
    """Build the narrow operator CLI used by ``obs-asset-launch``."""
    parser = argparse.ArgumentParser(
        description="Run bounded OpenMed NER as an in-memory direct result."
    )
    parser.add_argument(
        "--asset-root",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    parser.add_argument("--request-file", type=Path)
    parser.add_argument(
        "--execution-substrate",
        default="local_worker",
        choices=("local_worker", "local-worker"),
    )
    parser.add_argument(
        "--execution-profile",
        default="direct_result",
        choices=("direct_result",),
    )
    parser.add_argument("--runtime-check-only", action="store_true")
    parser.add_argument("--diagnostics-only", action="store_true")
    parser.add_argument("--skip-publish", action="store_true")
    parser.add_argument("--skip-diagnostics", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the reviewed direct-result path and print one safe JSON response."""
    args = build_parser().parse_args(argv)

    if args.runtime_check_only:
        _print_safe_report("runtime_ready")
        return 0
    if args.diagnostics_only:
        _print_safe_report("launcher_diagnostics_ready")
        return 0

    phase = "input_validation"
    try:
        if args.request_file is None:
            raise OpenMedNerLaunchError("request_file_required")

        inputs, record_count = load_request_inputs(args.request_file)
        if args.skip_publish:
            _print(
                {
                    "schema_version": "openmed_ner.launch.v1",
                    "status": "ready",
                    "category": "direct_result_input_ready",
                    "safe": True,
                    "values_included": False,
                    "network_calls_made": False,
                    "mutation_executed": False,
                    "record_count": record_count,
                }
            )
            return 0

        phase = "direct_execution"
        dependency_required, max_result_bytes = direct_result_settings(args.asset_root)
        context = {
            "mode": "direct_result",
            "execution_substrate": args.execution_substrate.replace("-", "_"),
            "asset_key": ASSET_KEY,
            "asset_version": ASSET_VERSION,
            **DEFAULT_CONTEXT,
        }
        try:
            result = invoke_direct_adapter(
                build_direct_adapter(),
                inputs,
                context,
                require_dependency_environment=dependency_required,
                max_result_bytes=max_result_bytes,
            )
        except Exception:
            # The public launcher result must not expose local paths, framework
            # details, model internals, or dependency-environment diagnostics.
            raise OpenMedNerLaunchError("direct_result_execution_failed") from None

        _print(result)
        return 0 if result.get("status") == "success" else 2
    except (OSError, ValueError, json.JSONDecodeError, OpenMedNerLaunchError) as exc:
        category = (
            str(exc)
            if isinstance(exc, OpenMedNerLaunchError)
            else f"{phase}_failed"
        )
        _print(
            {
                "schema_version": "openmed_ner.launch.v1",
                "status": "blocked",
                "category": category,
                "safe": True,
                "values_included": False,
                "network_calls_made": False,
                "mutation_executed": False,
            }
        )
        return 2


def load_request_inputs(path: Path) -> tuple[dict[str, Any], int]:
    """Load a bounded JSON request without exposing its values in reports.

    The file may contain either the adapter envelope
    ``{"text_records": {"records": [...]}}`` or the existing local fixture
    shape ``{"records": [...]}``. The latter is wrapped under the declared
    ``text_records`` role before invocation.
    """
    request_path = path.expanduser().resolve()
    if not request_path.is_file() or request_path.suffix.lower() != ".json":
        raise OpenMedNerLaunchError("request_file_invalid")

    value = json.loads(request_path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or isinstance(value, list):
        raise OpenMedNerLaunchError("request_payload_invalid")

    if "text_records" in value:
        if set(value) != {"text_records"}:
            raise OpenMedNerLaunchError("request_payload_invalid")
        role_value = value.get("text_records")
        inputs = value
    else:
        role_value = value
        inputs = {"text_records": value}

    if not isinstance(role_value, dict) or isinstance(role_value, list):
        raise OpenMedNerLaunchError("text_records_invalid")
    if set(role_value) - _ALLOWED_ROLE_FIELDS:
        raise OpenMedNerLaunchError("text_records_fields_invalid")
    records = role_value.get("records")
    if not isinstance(records, list):
        raise OpenMedNerLaunchError("records_invalid")
    if len(records) < 1 or len(records) > int(DEFAULT_CONTEXT["max_records"]):
        raise OpenMedNerLaunchError("record_limit_exceeded")

    seen_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or isinstance(record, list):
            raise OpenMedNerLaunchError("record_invalid")
        if set(record) - _ALLOWED_RECORD_FIELDS:
            raise OpenMedNerLaunchError("record_fields_invalid")
        record_id = record.get("record_id")
        text = record.get("text")
        if not isinstance(record_id, str) or not record_id.strip():
            raise OpenMedNerLaunchError("record_id_invalid")
        normalized_record_id = record_id.strip()
        if len(normalized_record_id) > 128:
            raise OpenMedNerLaunchError("record_id_invalid")
        if normalized_record_id in seen_ids:
            raise OpenMedNerLaunchError("record_id_duplicate")
        if not isinstance(text, str) or not text.strip():
            raise OpenMedNerLaunchError("record_text_invalid")
        if len(text) > int(DEFAULT_CONTEXT["max_characters"]):
            raise OpenMedNerLaunchError("record_text_too_long")
        seen_ids.add(normalized_record_id)

    return inputs, len(records)


def direct_result_settings(asset_root: Path) -> tuple[bool, int]:
    """Read and validate the direct-result limits from the reviewed manifest."""
    manifest_path = asset_root.expanduser().resolve() / LAUNCHER_MANIFEST
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        raise OpenMedNerLaunchError("direct_result_contract_invalid") from None

    execution = manifest.get("execution") if isinstance(manifest, dict) else None
    direct = execution.get("direct_result") if isinstance(execution, dict) else None
    if not isinstance(direct, dict):
        raise OpenMedNerLaunchError("direct_result_contract_invalid")

    dependency_mode = direct.get("dependency_environment")
    max_result_bytes = direct.get("max_result_bytes")
    if dependency_mode not in {"required", "optional"}:
        raise OpenMedNerLaunchError("direct_result_contract_invalid")
    if (
        isinstance(max_result_bytes, bool)
        or not isinstance(max_result_bytes, int)
        or max_result_bytes < 1
        or max_result_bytes > 10 * 1024 * 1024
    ):
        raise OpenMedNerLaunchError("direct_result_contract_invalid")

    return dependency_mode == "required", max_result_bytes


def _print_safe_report(category: str) -> None:
    _print(
        {
            "schema_version": "openmed_ner.launch.v1",
            "status": "ready",
            "category": category,
            "safe": True,
            "values_included": False,
            "network_calls_made": False,
            "mutation_executed": False,
            "asset_key": ASSET_KEY,
            "asset_version": ASSET_VERSION,
        }
    )


def _print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True))


if __name__ == "__main__":
    raise SystemExit(main())
