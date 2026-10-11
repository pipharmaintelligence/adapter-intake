"""Opt-in, content-only recovery over trusted static invocation diagnostics.

No raw rejected provider output, authority or transport implementation is read.
Policy/auth/identity/forbidden-material/unknown failures continue to propagate.
"""
from typing import Any
from devtools.runtime_agent_invocation import RuntimeAgentInvocationError
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .orchestration_v0_1_24 import _ResearchContractInputs, RESEARCH_ROLES, MAX_RESPONSE_OBSERVATIONS
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy
    from orchestration_v0_1_24 import _ResearchContractInputs, RESEARCH_ROLES, MAX_RESPONSE_OBSERVATIONS

_CONTENT_RULES = frozenset({
    "agent_result_json_object_invalid", "agent_result_json_value_invalid",
})
_ORIGINAL_ROLES = RESEARCH_ROLES | frozenset({
    legacy.PLANNER_ROLE, legacy.BENCHMARK_ROLE, legacy.STRATEGIC_ROLE,
    legacy.CRITIC_ROLE, legacy.SYNTHESIS_ROLE,
})

def invocation_diagnostic(error: Exception, *, role: str) -> dict[str, str] | None:
    if not isinstance(error, RuntimeAgentInvocationError):
        return None
    proof = getattr(error, "proof_failure_detail", None)
    if (getattr(error, "cause_code", None) != "provider_execution_vertex_response_invalid"
            or not isinstance(proof, dict)
            or set(proof) != {"schema_version", "proof_kind", "role", "stage", "rule", "field"}
            or proof.get("schema_version") != "proof_failure_detail.v1"
            or proof.get("proof_kind") != "agent_contract"
            or proof.get("role") != "provider" or proof.get("stage") != "terminal_content"
            or proof.get("field") != "content" or proof.get("rule") not in _CONTENT_RULES):
        return None
    return {**proof, "role": role, "stage": "agent_invocation_response"}

class InvocationRecoveryInputs(_ResearchContractInputs):
    """Keep research section recovery local; skip dependent stages on other roles."""
    def __init__(self, inputs: Any):
        super().__init__(inputs)
        self.invocation_issues: list[dict[str, Any]] = []

    def invoke_agent(self, role: str, *, input: dict[str, Any], on_error: str = "raise") -> Any:
        forwarded = {**input, "json_serialization_requirements": (
            "Return exactly one complete JSON object for the declared response contract. "
            "Use JSON double quotes and escape embedded quotes, newlines and control characters. "
            "No prose, Markdown fences, stringified JSON or extra response fields. "
            "Keep section prose concise and spend the supplied output budget on supported claims "
            "and exact evidence references; never truncate JSON or invent evidence."
        )}
        try:
            return super().invoke_agent(role, input=forwarded, on_error=on_error)
        except RuntimeAgentInvocationError as error:
            diagnostic = invocation_diagnostic(error, role=role)
            if diagnostic is None:
                raise
            with self._lock:
                if len(self.invocation_issues) < MAX_RESPONSE_OBSERVATIONS:
                    self.invocation_issues.append({
                        "company_id": input["company_id"], "role": role,
                        "original_role": input.get("original_role") if role == legacy.RESEARCH_RESOLVER_ROLE and isinstance(input.get("original_role"), str) and input["original_role"] in _ORIGINAL_ROLES else None,
                        "pass_number": (input.get("portfolio_review") or {}).get("pass_number"),
                        "diagnostic": diagnostic, "rejected_text_available": False,
                        "action": "affected_result_withheld", "backup_attempted": role == legacy.RESEARCH_RESOLVER_ROLE,
                    })
            if role in RESEARCH_ROLES:
                raise  # The version-owned research loop preserves prior passes.
            if role == legacy.RESEARCH_RESOLVER_ROLE:
                original = input.get("original_role")
                # Source-owned resolver helpers provide this association; never
                # infer it from rejected provider text.
                if isinstance(original, str) and original in _ORIGINAL_ROLES:
                    diagnostic = {**diagnostic, "role": original, "stage": "agent_response_resolver"}
            raise legacy.UnresolvedAgentResponse(diagnostic) from None
