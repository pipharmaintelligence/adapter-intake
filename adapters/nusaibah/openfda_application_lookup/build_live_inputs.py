"""Build the value-safe OBS input envelope for the openFDA proof asset.

This helper performs no network I/O. The developer supplies one application
number; the helper adds the already-governed Runtime Source selector that the
trusted worker resolves before adapter invocation.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_RUNTIME_SOURCE_ID = "rt_src_79fadcd06a7f45ceb98ae05c41bb907a"
_RUNTIME_SOURCE_RE = re.compile(r"^rt_src_[a-f0-9]{32}$")
_APPLICATION_NUMBER_RE = re.compile(r"^[A-Z]{2,8}[0-9]{4,10}$")


def normalize_application_number(value: str) -> str:
    """Normalize and validate a Drugs@FDA application number."""

    if not isinstance(value, str):
        raise ValueError("application_number must be a string")
    normalized = re.sub(r"[\s-]+", "", value).upper()
    if _APPLICATION_NUMBER_RE.fullmatch(normalized) is None:
        raise ValueError("application_number has an unsupported format")
    return normalized


def build_live_inputs(
    application_number: str,
    runtime_source_id: str = DEFAULT_RUNTIME_SOURCE_ID,
) -> dict[str, Any]:
    """Build safe direct Runtime Source inputs with no binding or secret data."""

    application = normalize_application_number(application_number)
    source_id = str(runtime_source_id or "").strip()
    if _RUNTIME_SOURCE_RE.fullmatch(source_id) is None:
        raise ValueError("runtime_source_id has an unsupported format")

    return {
        "variables": {
            "application_number": application,
        },
        "openfda_application_runtime": {
            "runtime_source_id": source_id,
            "input": {
                "search": f"application_number:{application}",
            },
        },
    }


def main() -> int:
    """Write one live-input JSON document for obs-adapter-runner."""

    parser = argparse.ArgumentParser(
        description="Build safe openFDA Runtime Source inputs from one application number."
    )
    parser.add_argument("application_number")
    parser.add_argument(
        "--runtime-source-id",
        default=DEFAULT_RUNTIME_SOURCE_ID,
        help="Safe governed Runtime Source identifier. Defaults to the PI-1773 openFDA source.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = build_live_inputs(args.application_number, args.runtime_source_id)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    if args.output is None:
        print(encoded, end="")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded, encoding="utf-8")
    print(json.dumps({"status": "ready", "output": str(args.output), "safe": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
