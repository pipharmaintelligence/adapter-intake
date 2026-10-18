"""Contain trusted output exhaustion without replaying paid work or parsing truncation."""
from devtools.runtime_agent_invocation import RuntimeAgentInvocationError
try:
    from .invocation_recovery_v0_1_48 import InvocationRecoveryInputs as Base, BoundedRecoveryInputs
    from .invocation_recovery_v0_1_30 import ACTIVE_ROLES
    from . import legacy_preparation_helpers_v0_1_23 as legacy
except ImportError:
    from invocation_recovery_v0_1_48 import InvocationRecoveryInputs as Base, BoundedRecoveryInputs
    from invocation_recovery_v0_1_30 import ACTIVE_ROLES
    import legacy_preparation_helpers_v0_1_23 as legacy


class InvocationRecoveryInputs(Base):
    def invoke_agent(self, role, *, input, on_error='raise'):
        try:
            return super().invoke_agent(role, input=input, on_error=on_error)
        except RuntimeAgentInvocationError as error:
            # Only SDK-sanitized provider classification is authoritative. Never
            # inspect exception prose, rejected JSON, thoughts or provider text.
            if (getattr(error, 'cause_code', None) != 'provider_execution_output_limit_reached'
                    or role not in ACTIVE_ROLES | {legacy.RESEARCH_RESOLVER_ROLE}):
                raise
            owner = role
            if role == legacy.RESEARCH_RESOLVER_ROLE:
                owner = input.get('original_role')
                if owner not in ACTIVE_ROLES:
                    raise
            detail = legacy.evidence_diagnostic(role=owner, stage='agent_output_budget',
                field='content', rule='provider_output_limit_reached')
            self._issue(input, role, detail, 'affected_chunk_withheld_no_provider_retry')
            if self._bounded is not None:
                self._bounded.record_response_recovery(company_id=input['company_id'], role=owner,
                    status='unresolved', diagnostic=detail)
            # Existing section/company continuation preserves validated siblings
            # and original publication checks. A resolver cannot finish missing
            # output safely; do not spend another paid call on truncated text.
            raise legacy.UnresolvedAgentResponse(detail) from None
