"""Contain typed business validation failures at the smallest scheduled work item.

The inherited coordinator still owns dispatch, budgets, ordering and diagnostics.
This boundary covers the actual validator classes used by research, review and
presentation, including historical helpers that do not share a base exception.
It never retries a provider call or changes a validator's decision.
"""
try:
    from .agent_chunks_v0_1_42 import ChunkCoordinator as Base, MeasuredDispatchInputs
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .agent_response_recovery_v0_1_40 import AgentResponseDiagnosticError
    from .research_diagnostics_v0_1_17 import ResearchContractValidationError
    from .research_response_contract_v0_1_26 import ResearchResponseContractError
    from .candidate_validation_v0_1_21 import CandidateContractError
except ImportError:
    from agent_chunks_v0_1_42 import ChunkCoordinator as Base, MeasuredDispatchInputs
    import legacy_preparation_helpers_v0_1_23 as legacy
    from agent_response_recovery_v0_1_40 import AgentResponseDiagnosticError
    from research_diagnostics_v0_1_17 import ResearchContractValidationError
    from research_response_contract_v0_1_26 import ResearchResponseContractError
    from candidate_validation_v0_1_21 import CandidateContractError


BUSINESS_VALIDATION_ERRORS = (
    ResearchContractValidationError,
    ResearchResponseContractError,
    AgentResponseDiagnosticError,
    legacy.AgentResponseDiagnosticError,
    CandidateContractError,
)


class ChunkCoordinator(Base):
    def parallel(self, items, fn):
        def contained(item):
            try:
                return fn(item)
            except BUSINESS_VALIDATION_ERRORS as error:
                # These concrete classes represent rejected model content. Keep
                # their original role/stage/field/rule, not exception prose. The
                # inherited scheduler retains the packet location and continues
                # independent siblings. Runtime/admission/storage exceptions and
                # unexpected programming errors are deliberately outside this set.
                raise legacy.UnresolvedAgentResponse(dict(error.proof_failure_detail)) from None
        return super().parallel(items, contained)
