from __future__ import annotations

import json
from collections import Counter
from typing import Any, ClassVar

from adapters.base import Adapter
from system import CALLABLE_VARIABLES_INPUT_ROLE, CallableAssetVariables

try:
    from .dump_agents_outputs import REFERENCE_DATA_FIELDS, build_dump_agents_by_agent_id
except ImportError:  # pragma: no cover - local adapter-root execution path
    from dump_agents_outputs import REFERENCE_DATA_FIELDS, build_dump_agents_by_agent_id


class DumpAgentsAdapter(Adapter):
    """Inspect and shape runtime-delivered ``@input.agents`` records.

    The adapter consumes records that Assets/Core have already resolved and
    sanitized. It does not call DLM Core, OBS, storage, or databases directly.
    """

    key: ClassVar[str] = "nusaibah.dump_agents"
    version: ClassVar[str] = "0.1.0"

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Return schema metadata and a logical per-agent output preview."""

        variables = self._variables(inputs)
        agents = self._records(inputs, "agents")

        schema = self._infer_observed_schema(agents)
        stats = self._basic_stats(agents)

        schema_summary = {
            "input_handle": "@input.agents",
            "source_node": "@node agents",
            "record_count": len(agents),
            "field_count": schema["field_count"],
            "field_names": schema["field_names"],
            "field_types": schema["field_types"],
            "missing_counts": schema["missing_counts"],
            "stats": stats,
            "reference_data_fields_observed": self._reference_data_fields(agents),
            "callable_variables_present": bool(variables),
            "callable_variable_keys": sorted(variables.keys()),
        }

        dump_agents_by_agent_id = build_dump_agents_by_agent_id(
            records=agents,
            limit=10,
        )

        return {
            "response_version": "1",
            "status": "success",
            "outputs": {
                "schema_summary": schema_summary,
                "dump_agents_by_agent_id": dump_agents_by_agent_id,
            },
            "logs": [
                {
                    "level": "info",
                    "message": "Built logical dump_agents_by_agent_id output from runtime-delivered @input.agents.",
                }
            ],
            "metrics": {
                "record_count": len(agents),
                "field_count": schema["field_count"],
                "dump_agents_by_agent_id_count": dump_agents_by_agent_id["record_count"],
            },
        }

    @staticmethod
    def _variables(inputs: dict[str, Any]) -> CallableAssetVariables:
        """Return optional callable variables without exposing their values."""

        value = inputs.get(CALLABLE_VARIABLES_INPUT_ROLE, {})

        if value is None:
            return {}

        if not isinstance(value, dict):
            raise ValueError("Callable variables must be an object when provided.")

        return value

    @classmethod
    def _records(cls, inputs: dict[str, Any], role: str) -> list[dict[str, Any]]:
        """Extract records from one runtime-delivered input role."""

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
        """Decode rows when runtime delivers records as ``{"text": "..."}``."""

        if isinstance(record, dict) and isinstance(record.get("text"), str):
            try:
                decoded = json.loads(record["text"])
            except json.JSONDecodeError:
                return record

            if isinstance(decoded, dict):
                return decoded

        return record

    @staticmethod
    def _infer_observed_schema(records: list[dict[str, Any]]) -> dict[str, Any]:
        """Infer observed field names, Python value types, and missing counts."""

        field_names = sorted({key for record in records for key in record.keys()})
        field_types: dict[str, list[str]] = {}
        missing_counts: dict[str, int] = {}

        for field_name in field_names:
            observed_types: set[str] = set()
            missing = 0

            for record in records:
                value = record.get(field_name)

                if value is None or value == "":
                    missing += 1
                    continue

                observed_types.add(type(value).__name__)

            field_types[field_name] = sorted(observed_types)
            missing_counts[field_name] = missing

        return {
            "field_count": len(field_names),
            "field_names": field_names,
            "field_types": field_types,
            "missing_counts": missing_counts,
        }

    @classmethod
    def _basic_stats(cls, records: list[dict[str, Any]]) -> dict[str, Any]:
        """Return small safe stats for known agents fields."""

        return {
            "by_headquarter": cls._count_by_field(records, "headquarter"),
        }

    @staticmethod
    def _reference_data_fields(records: list[dict[str, Any]]) -> list[str]:
        """Return reference-looking fields observed as ordinary row data."""

        observed = {key for record in records for key in record}

        return [field for field in REFERENCE_DATA_FIELDS if field in observed]

    @staticmethod
    def _count_by_field(records: list[dict[str, Any]], field_name: str) -> dict[str, int]:
        """Count non-empty values for one field."""

        counter: Counter[str] = Counter()

        for record in records:
            value = str(record.get(field_name, "")).strip()
            if value:
                counter[value] += 1

        return dict(counter)
