from __future__ import annotations

from typing import Any

from adapters.base import Adapter


class NusaibahVertexCompanyCheckAdapter(Adapter):
    """Prepare a deterministic local placeholder for governed Vertex execution.

    The adapter remains provider- and MCP-blind. Assets and DLM Core own live
    Vertex grounding, governed MCP policy admission, tool execution, and the final
    sanitized generated result.
    """

    key = "nusaibah.vertex_company_check"
    version = "0.1.0"

    def invoke(self, inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Return the canonical ``company_note`` shape for local validation."""
        companies = inputs.get("companies", {})
        records = companies.get("records", []) if isinstance(companies, dict) else []
        variables = inputs.get("variables", {}) if isinstance(inputs.get("variables", {}), dict) else {}
        company = _first_record(records)

        requested_company_id = variables.get("company_id") or company.get("id")
        company_name = _company_name(company)

        generated_note = (
            f"Best current-evidence review for {company_name} is prepared for "
            "server-authorized Vertex grounding and one governed PubMed search call."
            if company_name
            else "Best current-evidence review is blocked until the company input row is resolved."
        )

        return {
            "response_version": "1",
            "status": "success",
            "outputs": {
                "company_note": {
                    "company_id": requested_company_id,
                    "company_name": company_name,
                    "generated_note": generated_note,
                    "evidence_summary": (
                        "Local deterministic placeholder only; live evidence must be returned by "
                        "the server-owned Vertex and governed MCP execution path."
                    ),
                    "confidence": "low" if not company_name else "medium",
                },
            },
            "logs": [
                {
                    "level": "info",
                    "message": (
                        "Prepared the canonical company_note shape without calling Vertex, "
                        "Google Search, PubMed MCP, OBS, or DLM Core."
                    ),
                },
            ],
            "metrics": {
                "record_count": len(records),
                "company_row_present": 1 if company else 0,
                "llm_generate_requested": 1,
                "search_grounding_requested": 1,
                "mcp_tool_call_requested": 1,
                "mcp_tool_call_limit": 1,
            },
        }


def _first_record(records: Any) -> dict[str, Any]:
    """Return the first resolved company record or an empty mapping."""
    if isinstance(records, list) and records and isinstance(records[0], dict):
        return records[0]
    return {}


def _company_name(record: dict[str, Any]) -> str:
    """Resolve a stable display name from the governed company record."""
    for key in ("company", "company_name", "name", "label"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
