"""Client for runtime-owned SEC company-reference projections.

This module performs no network access. The runtime is responsible for leases,
bindings, capabilities, outbound requests, retries, and safe response reduction.
The client receives only the bounded projection passed to the adapter.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class RuntimeProjectionSecCompanyReferenceClient:
    """Return a bounded company reference supplied by the governed runtime."""

    def __init__(self, projection: dict[str, Any]) -> None:
        """Store one runtime-owned, already reduced SEC projection."""

        if not isinstance(projection, dict):
            raise ValueError("runtime_request_projection_invalid")

        self._projection = deepcopy(projection)

    def resolve_company_reference(
        self,
        identifier_kind: str,
        identifier_value: str,
    ) -> dict[str, Any]:
        """Return the projection without performing provider execution."""

        if identifier_kind != "cik":
            raise ValueError("runtime_request_identifier_not_supported")

        # The adapter validates the requested CIK, company shape, and security
        # records. Returning a copy prevents mutation of runtime-owned input.
        return deepcopy(self._projection)
