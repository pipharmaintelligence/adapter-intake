from __future__ import annotations

import json
from typing import Any, ClassVar

from adapters.base import Adapter
from system import CALLABLE_VARIABLES_INPUT_ROLE, CallableAssetVariables

try:
    from .company_name_upsert_outputs import build_company_name_upserts
except ImportError:  # pragma: no cover - local adapter-root execution path
    from company_name_upsert_outputs import build_company_name_upserts


class CompanyNameUpsertAdapter(Adapter):
    """Build governed company-name upsert candidates from delivered rows.

    The adapter receives sanitized ``@input.companies`` records from Assets/Core
    or from local fixture/profile mode. It does not query DLM Core, issue SQL,
    update a database, or call providers directly.
    """

    key: ClassVar[str] = "nusaibah.company_name_upsert"
    version: ClassVar[str] = "0.1.0"

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Return safe upsert candidates for the approved output policy."""

        variables = self._variables(inputs)
        companies = self._records(inputs, "companies")
        result = build_company_name_upserts(companies)

        return {
            "response_version": "1",
            "status": "success",
            "outputs": {
                "company_name_upsert_summary": {
                    "input_handle": "@input.companies",
                    "source_node": "@node companies",
                    "record_count": len(companies),
                    "candidate_count": result["candidate_count"],
                    "callable_variables_present": bool(variables),
                    "callable_variable_keys": sorted(variables.keys()),
                    "operation_intent": "upsert",
                    "authority": "core_output_policy_required",
                },
                "company_name_upserts": result,
            },
            "logs": [
                {
                    "level": "info",
                    "message": "Built company name upsert candidates from runtime-delivered @input.companies.",
                }
            ],
            "metrics": {
                "input_record_count": len(companies),
                "candidate_count": result["candidate_count"],
            },
        }

    @staticmethod
    def _variables(inputs: dict[str, Any]) -> CallableAssetVariables:
        value = inputs.get(CALLABLE_VARIABLES_INPUT_ROLE, {})
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("Callable variables must be an object when provided.")
        return value

    @classmethod
    def _records(cls, inputs: dict[str, Any], role: str) -> list[dict[str, Any]]:
        value = inputs.get(role)
        if not isinstance(value, dict):
            raise ValueError(f"{role} input must be an object.")
        records = value.get("records")
        if not isinstance(records, list):
            raise ValueError(f"{role}.records must be a list.")

        normalized: list[dict[str, Any]] = []
        for record in records:
            decoded = cls._safe_row(record)
            if isinstance(decoded, dict):
                normalized.append(decoded)
        return normalized

    @staticmethod
    def _safe_row(record: Any) -> Any:
        if isinstance(record, dict) and isinstance(record.get("text"), str):
            try:
                decoded = json.loads(record["text"])
            except json.JSONDecodeError:
                return record
            if isinstance(decoded, dict):
                return decoded
        return record
