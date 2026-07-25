from __future__ import annotations

import json
from typing import Any, ClassVar

from adapters.base import Adapter
from system import CALLABLE_VARIABLES_INPUT_ROLE, CallableAssetVariables


AGENT_FIELDS = (
    "id",
    "agent",
    "headquarter",
    "address_line1",
    "address_line2",
    "telephone",
    "website",
    "description",
    "created_at",
    "updated_at",
)
MAX_AGENT_IDS = 3


class FullDumpAgentLoopAdapter(Adapter):
    """Build one bounded JSON projection from runtime-delivered agent records."""

    key: ClassVar[str] = "nusaibah.full_dump_agent_loop"
    version: ClassVar[str] = "0.1.0"

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Select requested records without resolving inputs or publishing outputs."""

        records = self._records(inputs)
        selected_ids = self._selected_agent_ids(inputs)
        records_by_id = self._records_by_id(records)

        selected_records: list[dict[str, Any]] = []
        missing_ids: list[str] = []

        for agent_id in selected_ids:
            record = records_by_id.get(agent_id)
            if record is None:
                missing_ids.append(agent_id)
                continue
            selected_records.append(self._project_record(record))

        full_dump_agent = {
            "format": "json",
            "layout": "single_file",
            "selection_mode": "selected_agent_ids",
            "selected_agent_ids": selected_ids,
            "missing_agent_ids": missing_ids,
            "record_count": len(selected_records),
            "fields": list(AGENT_FIELDS),
            "records": selected_records,
        }

        return {
            "response_version": "1",
            "status": "success",
            "outputs": {
                "full_dump_agent": full_dump_agent,
            },
            "logs": [
                {
                    "level": "info",
                    "message": "Built a bounded agent projection from runtime-delivered records.",
                }
            ],
            "metrics": {
                "input_record_count": len(records),
                "requested_agent_count": len(selected_ids),
                "selected_agent_count": len(selected_records),
                "missing_agent_count": len(missing_ids),
            },
        }

    @staticmethod
    def _variables(inputs: dict[str, Any]) -> CallableAssetVariables:
        variables = inputs.get(CALLABLE_VARIABLES_INPUT_ROLE)
        if not isinstance(variables, dict):
            raise ValueError("Callable variables must be an object.")
        return variables

    @classmethod
    def _selected_agent_ids(cls, inputs: dict[str, Any]) -> list[str]:
        candidate = cls._variables(inputs).get("agent_ids")

        if not isinstance(candidate, list):
            raise ValueError("Callable variable agent_ids must be a list.")

        if not 1 <= len(candidate) <= MAX_AGENT_IDS:
            raise ValueError(f"Callable variable agent_ids must contain between 1 and {MAX_AGENT_IDS} items.")

        selected_ids: list[str] = []

        for item in candidate:
            if isinstance(item, bool):
                raise ValueError("Callable variable agent_ids items must be non-empty strings or integers.")

            if isinstance(item, int):
                normalized = str(item)
            elif isinstance(item, str) and item.strip():
                normalized = item.strip()
            else:
                raise ValueError("Callable variable agent_ids items must be non-empty strings or integers.")

            if normalized in selected_ids:
                raise ValueError("Callable variable agent_ids must not contain duplicates.")

            selected_ids.append(normalized)

        return selected_ids

    @classmethod
    def _records(cls, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        agents = inputs.get("agents")
        if not isinstance(agents, dict):
            raise ValueError("agents input must be an object.")

        records = agents.get("records")
        if not isinstance(records, list):
            raise ValueError("agents.records must be a list.")

        normalized: list[dict[str, Any]] = []
        for record in records:
            decoded = cls._decode_record(record)
            if not isinstance(decoded, dict):
                raise ValueError("Every agents.records item must resolve to an object.")
            normalized.append(decoded)

        return normalized

    @staticmethod
    def _decode_record(record: Any) -> Any:
        if not isinstance(record, dict) or not isinstance(record.get("text"), str):
            return record

        try:
            decoded = json.loads(record["text"])
        except json.JSONDecodeError as exc:
            raise ValueError("agents.records text values must contain valid JSON objects.") from exc

        return decoded

    @classmethod
    def _records_by_id(cls, records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        indexed: dict[str, dict[str, Any]] = {}

        for record in records:
            identifier = record.get("id", record.get("agent_id"))
            if isinstance(identifier, bool) or not isinstance(identifier, (str, int)):
                raise ValueError("Every agent record must contain a string or integer id.")

            normalized = str(identifier).strip()
            if not normalized:
                raise ValueError("Every agent record id must be non-empty.")
            if normalized in indexed:
                raise ValueError("Agent record ids must be unique.")

            indexed[normalized] = record

        return indexed

    @staticmethod
    def _project_record(record: dict[str, Any]) -> dict[str, Any]:
        return {field: record.get(field) for field in AGENT_FIELDS}
