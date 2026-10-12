"""Declare the complete research envelope around the immutable 0.1.23 kernel.

This composition changes provider input only. It never repairs a returned status,
changes runtime authority, performs a retry, or grants publication authority.
"""
from __future__ import annotations

from copy import deepcopy
from threading import Lock
from typing import Any

try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .orchestration_v0_1_23 import invoke_v0_1_23
    from .research_response_contract_v0_1_26 import RESEARCH_SCHEMA_VERSION
except ImportError:  # pragma: no cover - flat intake execution
    import legacy_preparation_helpers_v0_1_23 as legacy
    from orchestration_v0_1_23 import invoke_v0_1_23
    from research_response_contract_v0_1_26 import RESEARCH_SCHEMA_VERSION


RESEARCH_ROLES = frozenset({
    "portfolio_researcher", "market_researcher", "regulatory_risk_researcher",
})
BUSINESS_FIELDS = (
    "schema_version", "company_id", "role", "status", "sections", "claims", "uncertainties",
)
MAX_RESPONSE_OBSERVATIONS = legacy.MAX_COMPANY_ITERATIONS * (legacy.MAX_AGENT_CALLS_PER_COMPANY_PREVIEW + 2) * 2


def complete_research_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Add required envelope literals without changing evidence or field bounds."""
    result = deepcopy(contract)
    result["schema_version"] = {"type": "string", "required_value": RESEARCH_SCHEMA_VERSION}
    result["status"] = {"type": "string", "required_value": "completed"}
    result["required_fields"] = list(BUSINESS_FIELDS)
    result["additional_response_fields_allowed"] = False
    result["completion_semantics"] = (
        "completed means this bounded research response is finished, not that evidence is complete "
        "or approved. Represent evidence gaps with empty claims and explicit uncertainties; "
        "never invent facts or change a negative quality verdict to satisfy this field."
    )
    return result


class _ResearchContractInputs(dict):
    """Execution-local input proxy preserving every existing runtime capability."""

    def __init__(self, inputs: Any) -> None:
        super().__init__(inputs)
        self._inputs = inputs
        self._lock = Lock()
        self.observations: list[dict[str, Any]] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inputs, name)

    def invoke_agent(self, role: str, *, input: dict[str, Any], on_error: str = "raise") -> Any:
        research = role in RESEARCH_ROLES
        research_backup = (
            role == "research_response_resolver"
            and input.get("original_role") in RESEARCH_ROLES
            and input.get("repair_scope") == "research_business_json"
        )
        forwarded = input
        if (research or research_backup) and isinstance(input.get("response_contract"), dict):
            forwarded = {**input, "response_contract": complete_research_contract(input["response_contract"])}
        envelope = self._inputs.invoke_agent(role, input=forwarded, on_error=on_error)
        if research or research_backup:
            self._record_observation(role, forwarded, envelope)
        return envelope

    def _record_observation(self, role: str, input: dict[str, Any], envelope: Any) -> None:
        # Static classifications only: never retain raw model status/prose, prompts,
        # URLs, provider bodies or credentials. Existing kernel validates authority.
        value = None
        result = envelope.get("result") if isinstance(envelope, dict) else None
        content = result.get("content") if isinstance(result, dict) else None
        if isinstance(content, list) and len(content) == 1 and isinstance(content[0], dict):
            candidate = content[0].get("value")
            if isinstance(candidate, dict):
                value = candidate
        classification = "unavailable"
        if isinstance(value, dict):
            status = value.get("status")
            if "status" not in value:
                classification = "missing"
            elif not isinstance(status, str):
                classification = "invalid_type"
            elif status in {"completed", "incomplete", "failed", "no_evidence", "success"}:
                classification = status
            else:
                classification = "other_string"
        observation = {
            "role": role,
            "company_id": input["company_id"],
            "pass_number": (input.get("portfolio_review") or {}).get("pass_number"),
            "business_status_class": classification,
            "business_schema_matches": isinstance(value, dict) and value.get("schema_version") == RESEARCH_SCHEMA_VERSION,
        }
        with self._lock:
            # Kernel has finite company/role/backup budgets. Bound this projection too.
            if len(self.observations) < MAX_RESPONSE_OBSERVATIONS:
                self.observations.append(observation)


def invoke_v0_1_24(inputs: Any, *, asset_identity: str) -> dict[str, Any]:
    """Run the same preview kernel with a complete provider-visible contract."""
    # Preserve the kernel's input rejection before copying into the proxy.
    legacy.validate_batch_request(inputs)
    forwarded = _ResearchContractInputs(inputs)
    response = invoke_v0_1_23(forwarded, asset_identity=asset_identity)
    response["outputs"]["intelligence_dossier"]["research_response_observations"] = sorted(
        forwarded.observations,
        key=lambda row: (row["company_id"], row["role"], row["pass_number"] or 0),
    )
    return response
