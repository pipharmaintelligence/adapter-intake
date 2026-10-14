"""Faithful formatting recovery includes the new claim decisions and feedback."""
from typing import Any
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .agent_response_recovery_v0_1_40 import (normalize_json_envelope, AgentResponseDiagnosticError,
        safe_diagnostic, payload_diagnostic, formatting_normal_form, require_preserved_business, project_business_payload)
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy
    from agent_response_recovery_v0_1_40 import (normalize_json_envelope, AgentResponseDiagnosticError,
        safe_diagnostic, payload_diagnostic, formatting_normal_form, require_preserved_business, project_business_payload)
AgentContractValidationError=legacy.AgentContractValidationError
UnresolvedAgentResponse=legacy.UnresolvedAgentResponse
extract_agent_json=legacy.extract_agent_json

def _validated_agent_response(inputs: Any, envelope: Any, *, role: str,
                              company_id: int, contract: dict[str, Any],
                              validator: Any) -> Any:
    """One original call, deterministic diagnostics, at most one backup call."""
    try:
        envelope, wrappers = normalize_json_envelope(envelope, role=role)
        value, _ = extract_agent_json(envelope, expected_role=role, company_id=company_id,
                                      expected_schema_version=contract["schema_version"])
    except (AgentResponseDiagnosticError, AgentContractValidationError) as error:
        if error.code not in {"pharma_agent_business_schema_invalid", "pharma_agent_status_invalid"}:
            raise  # runtime completion and company/role authority remain strict
        diagnostic = safe_diagnostic(error, role=role)
        inputs.record_response_recovery(company_id=company_id, role=role,
                                         status="unresolved", diagnostic=diagnostic)
        # With no faithful typed business object, a backup cannot prove that it
        # preserved content. Retain the issue, never send arbitrary raw prose.
        raise UnresolvedAgentResponse(diagnostic) from None
    try:
        validated = validator(value)
    except (ValueError, TypeError, AgentContractValidationError) as initial_error:
        diagnostic = payload_diagnostic(initial_error, value, role=role, contract=contract)
    else:
        if wrappers:
            inputs.record_response_recovery(company_id=company_id, role=role,
                                             status="json_unwrapped", wrappers=wrappers)
        return validated
    cleaned = formatting_normal_form(value, contract)
    try:
        validated = validator(cleaned)
        require_preserved_business(value, cleaned, contract=contract, role=role)
    except (ValueError, TypeError, AgentContractValidationError):
        pass
    else:
        inputs.record_response_recovery(company_id=company_id, role=role,
                                         status="deterministic_cleanup", wrappers=wrappers,
                                         diagnostic=diagnostic)
        return validated
    repaired_envelope = inputs.invoke_response_resolver(original_role=role, input={
        "company_id": company_id, "research_role": role,
        "failed_contract": diagnostic,
        "invalid_response": project_business_payload(value, contract),
        "response_contract": contract,
        "repair_scope": "business_json_format_only",
    })
    try:
        repaired_envelope, repaired_wrappers = normalize_json_envelope(repaired_envelope, role=role)
        repaired, _ = extract_agent_json(repaired_envelope, expected_role=role,
                                         company_id=company_id,
                                         expected_schema_version=contract["schema_version"])
        repaired = formatting_normal_form(repaired, contract)
        validated = validator(repaired)
        require_preserved_business(value, repaired, contract=contract, role=role)
    except AgentContractValidationError as final_error:
        if final_error.code in {"pharma_agent_company_id_invalid", "pharma_agent_role_invalid",
                                "pharma_agent_runtime_envelope_invalid",
                                "pharma_agent_runtime_result_invalid"}:
            raise
        final_diagnostic = safe_diagnostic(final_error, role=role)
    except (ValueError, TypeError) as final_error:
        final_diagnostic = safe_diagnostic(final_error, role=role)
    else:
        inputs.record_response_recovery(company_id=company_id, role=role, status="agent_repaired",
                                         wrappers=wrappers + repaired_wrappers,
                                         diagnostic=diagnostic)
        return validated
    inputs.record_response_recovery(company_id=company_id, role=role, status="unresolved",
                                     wrappers=wrappers, diagnostic=final_diagnostic)
    raise UnresolvedAgentResponse(final_diagnostic)
