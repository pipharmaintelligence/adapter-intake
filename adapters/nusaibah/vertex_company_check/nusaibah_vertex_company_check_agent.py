from __future__ import annotations

from typing import Any

from system.runtime import agent, input, output


@agent(
    "company_online_check",
    instructions=(
        "Prepare the canonical local company_note shape for server-authorized "
        "Vertex grounding and at most one governed PubMed search call."
    ),
)
@input("companies")
@output("company_note")
def company_online_check(inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Return local intent metadata without executing providers or MCP tools."""
    companies = inputs.get("companies", {})
    records = companies.get("records", []) if isinstance(companies, dict) else []
    variables = inputs.get("variables", {}) if isinstance(inputs.get("variables", {}), dict) else {}
    company = records[0] if isinstance(records, list) and records and isinstance(records[0], dict) else {}
    company_id = variables.get("company_id") or company.get("id")
    company_name = _company_name(company)

    generated_note = (
        f"Best current-evidence review for {company_name} is prepared for "
        "server-authorized Vertex grounding and one governed PubMed search call."
        if company_name
        else "Best current-evidence review is blocked until the company input row is resolved."
    )

    return {
        "outputs": {
            "company_note": {
                "company_id": company_id,
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
                "message": "Prepared safe local @agent output without provider or MCP execution.",
            },
        ],
        "metrics": {
            "record_count": len(records) if isinstance(records, list) else 0,
            "search_grounding_requested": 1,
            "mcp_tool_call_requested": 1,
            "mcp_tool_call_limit": 1,
        },
    }


def _company_name(record: dict[str, Any]) -> str:
    """Resolve a stable display name from the governed company record."""
    for key in ("company", "company_name", "name", "label"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
