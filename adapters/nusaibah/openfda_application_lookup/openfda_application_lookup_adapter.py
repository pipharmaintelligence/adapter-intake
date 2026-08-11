"""API-blind openFDA Drugs@FDA application lookup adapter.

The trusted OBS runtime resolves the governed Runtime Source before this adapter
runs. This module never performs provider HTTP, applies authentication, reads
credentials, or calls OBS/DLM Core directly.
"""

from __future__ import annotations

import re
from typing import Any

from adapters.base import Adapter


_APPLICATION_NUMBER_RE = re.compile(r"^[A-Z]{2,8}[0-9]{4,10}$")
_DATE_RE = re.compile(r"^[0-9]{8}$")
_MAX_RUNTIME_RECORDS = 10
_CAPABILITY = "openfda.application.lookup"
_RUNTIME_ROLE = "openfda_application_runtime"


class OpenFdaApplicationLookupAdapter(Adapter):
    """Return a small deterministic summary for one Drugs@FDA application.

    Expected resolved inputs::

        {
            "variables": {"application_number": "NDA020164"},
            "openfda_application_runtime": {"records": [...]}
        }

    The Runtime Source role must already contain normalized records. Provider
    transport, authentication, retries, pagination, and response materialization
    are intentionally outside this adapter.
    """

    key = "nusaibah.openfda_application_lookup"
    version = "0.1.0"

    def invoke(
        self,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Look up one application number in resolved openFDA records.

        Args:
            inputs: Safe resolved adapter inputs. ``variables.application_number``
                is the developer input and ``openfda_application_runtime.records``
                is populated by trusted runtime resolution.
            context: Safe runtime context. No credential or provider material is
                read from this object.

        Returns:
            Standard adapter output containing one lookup capability result with
            the requested application number, one brand name when available, and
            the latest submission status date when available.

        Raises:
            ValueError: If the input contract is malformed, unbounded, ambiguous,
                or does not contain a record matching the requested application.
        """

        if not isinstance(inputs, dict):
            raise ValueError("openfda_inputs_invalid")
        if not isinstance(context, dict):
            raise ValueError("openfda_context_invalid")

        application_number = _application_number(inputs)
        records = _runtime_records(inputs)
        match = _single_matching_record(records, application_number)

        brand_names = _brand_names(match)
        submission_dates = _submission_status_dates(match)

        brand_name = brand_names[0] if brand_names else None
        latest_submission_status_date = max(submission_dates) if submission_dates else None

        if brand_name is None and latest_submission_status_date is None:
            raise ValueError("openfda_application_lookup_result_fields_missing")

        return {
            "outputs": {
                "application_lookup": {
                    "capability": _CAPABILITY,
                    "application_number": application_number,
                    "brand_name": brand_name,
                    "submission_status_date": latest_submission_status_date,
                }
            },
            "logs": [
                {
                    "level": "info",
                    "message": (
                        "openFDA application lookup completed from resolved "
                        "Runtime Source records."
                    ),
                }
            ],
            "metrics": {
                "runtime_record_count": len(records),
                "matched_record_count": 1,
                "brand_name_count": len(brand_names),
                "submission_count": len(submission_dates),
            },
        }


def _application_number(inputs: dict[str, Any]) -> str:
    """Read and normalize the single developer-facing application number."""

    variables = inputs.get("variables")
    if not isinstance(variables, dict):
        raise ValueError("openfda_variables_required")

    raw = variables.get("application_number")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("openfda_application_number_required")

    normalized = re.sub(r"[\s-]+", "", raw).upper()
    if _APPLICATION_NUMBER_RE.fullmatch(normalized) is None:
        raise ValueError("openfda_application_number_invalid")

    return normalized


def _runtime_records(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a bounded list of already-resolved Runtime Source records."""

    role = inputs.get(_RUNTIME_ROLE)
    if not isinstance(role, dict):
        raise ValueError("openfda_runtime_role_required")

    records = role.get("records")
    if not isinstance(records, list):
        raise ValueError("openfda_runtime_records_required")
    if len(records) > _MAX_RUNTIME_RECORDS:
        raise ValueError("openfda_runtime_records_unbounded")

    normalized: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("openfda_runtime_record_invalid")
        normalized.append(record)

    return normalized


def _single_matching_record(
    records: list[dict[str, Any]],
    application_number: str,
) -> dict[str, Any]:
    """Select exactly one record for the requested application number."""

    matches = [
        record
        for record in records
        if application_number in _record_application_numbers(record)
    ]

    if not matches:
        raise ValueError("openfda_application_not_found")
    if len(matches) > 1:
        raise ValueError("openfda_application_multiple_matches")

    return matches[0]


def _record_application_numbers(record: dict[str, Any]) -> set[str]:
    """Collect safe application-number identifiers from one normalized record."""

    values: list[Any] = [record.get("application_number")]
    openfda = record.get("openfda")
    if isinstance(openfda, dict):
        candidate = openfda.get("application_number")
        if isinstance(candidate, list):
            values.extend(candidate)
        else:
            values.append(candidate)

    normalized: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        candidate = re.sub(r"[\s-]+", "", value).upper()
        if _APPLICATION_NUMBER_RE.fullmatch(candidate):
            normalized.add(candidate)

    return normalized


def _brand_names(record: dict[str, Any]) -> list[str]:
    """Collect unique brand names without returning the full provider record."""

    candidates: list[Any] = []

    openfda = record.get("openfda")
    if isinstance(openfda, dict):
        value = openfda.get("brand_name")
        if isinstance(value, list):
            candidates.extend(value)
        else:
            candidates.append(value)

    products = record.get("products")
    if isinstance(products, list):
        for product in products:
            if not isinstance(product, dict):
                continue
            value = product.get("brand_name")
            if isinstance(value, list):
                candidates.extend(value)
            else:
                candidates.append(value)

    names: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        name = candidate.strip()
        if not name or len(name) > 300:
            continue
        folded = name.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        names.append(name)

    return names


def _submission_status_dates(record: dict[str, Any]) -> list[str]:
    """Return valid YYYYMMDD submission status dates from one application."""

    submissions = record.get("submissions")
    if not isinstance(submissions, list):
        return []

    dates: list[str] = []
    for submission in submissions:
        if not isinstance(submission, dict):
            continue
        value = submission.get("submission_status_date")
        if isinstance(value, str):
            normalized = value.strip()
            if _DATE_RE.fullmatch(normalized):
                dates.append(normalized)

    return dates


__all__ = ["OpenFdaApplicationLookupAdapter"]
