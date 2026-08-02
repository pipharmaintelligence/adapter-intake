from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .local_sec_company_reference_client import (
        LocalFixtureSecCompanyReferenceClient,
    )
    from .sec_company_reference_adapter import SecCompanyReferenceAdapter
except ImportError:  # Standalone adapter-project execution.
    from local_sec_company_reference_client import (
        LocalFixtureSecCompanyReferenceClient,
    )
    from sec_company_reference_adapter import SecCompanyReferenceAdapter


ASSET_ROOT = Path(__file__).resolve().parent

REQUEST_FIXTURE = (
    ASSET_ROOT
    / "fixtures"
    / "sec_company_reference.cik.request.json"
)

REFERENCE_FIXTURE = (
    ASSET_ROOT
    / "fixtures"
    / "sec_company_reference.cik.expected.json"
)


def load_json(path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON object from disk."""

    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path.name}.")

    return payload


def main() -> None:
    """Run the SEC company-reference adapter using local fixtures only."""

    request_payload = load_json(REQUEST_FIXTURE)

    client = LocalFixtureSecCompanyReferenceClient(
        REFERENCE_FIXTURE
    )
    adapter = SecCompanyReferenceAdapter(client=client)

    result = adapter.invoke(
        request_payload["inputs"],
        request_payload.get("context", {}),
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()