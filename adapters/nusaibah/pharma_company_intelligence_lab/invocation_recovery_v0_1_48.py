"""Repair a research schema echo once, without replacing research or citations."""
from copy import deepcopy
import json
import time
from devtools.trusted_runtime_callable_child_bridge import RuntimeCallableBridgeError

try:
    from .invocation_recovery_v0_1_41 import InvocationRecoveryInputs as Base, BoundedRecoveryInputs as BoundedBase
    from .research_envelope_v0_1_26 import complete_research_contract, RESEARCH_ROLES
    from .research_response_contract_v0_1_26 import RESEARCH_SCHEMA_VERSION
    from . import legacy_preparation_helpers_v0_1_23 as legacy
except ImportError:
    from invocation_recovery_v0_1_41 import InvocationRecoveryInputs as Base, BoundedRecoveryInputs as BoundedBase
    from research_envelope_v0_1_26 import complete_research_contract, RESEARCH_ROLES
    from research_response_contract_v0_1_26 import RESEARCH_SCHEMA_VERSION
    import legacy_preparation_helpers_v0_1_23 as legacy


def business_bytes(value):
    return json.dumps({k: v for k, v in value.items() if k != 'schema_version'},
                     ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


class BoundedRecoveryInputs(BoundedBase):
    def invoke_asset(self, role, *, variables=None, on_error='raise'):
        # Only this immutable, pure computation operation may be replayed. No
        # Agent, Skill mutation or unknown callable failure is retried here.
        pure_span = (role == 'review_toolkit' and isinstance(variables, dict)
                     and variables.get('operation') == 'resolve_exact_spans')
        for attempt in range(1, 4):
            try:
                return super().invoke_asset(role, variables=variables, on_error=on_error)
            except RuntimeCallableBridgeError as error:
                delay = 5 * attempt
                reserve = self.coordinator.publication_reserve_seconds
                if (not pure_span or str(error) != 'direct_runtime_callable_execution_timed_out'
                        or attempt == 3 or self._source_toolkit_calls >= 32
                        or self.coordinator.clock() + delay + 30 + reserve >= self.coordinator.deadline):
                    raise
                time.sleep(delay)
        raise AssertionError('unreachable')


class InvocationRecoveryInputs(Base):
    def invoke_agent(self, role, *, input, on_error='raise'):
        envelope = super().invoke_agent(role, input=input, on_error=on_error)
        if role not in RESEARCH_ROLES or self._bounded is None or not isinstance(envelope, dict):
            return envelope
        result = envelope.get('result', {}) if isinstance(envelope, dict) else {}
        content = result.get('content')
        if (envelope.get('status') != 'completed' or result.get('schema_version') != 'agent_result.v1'
                or result.get('kind') != 'json' or not isinstance(content, list) or len(content) != 1
                or not isinstance(content[0], dict) or content[0].get('type') != 'json'):
            return envelope
        value = content[0].get('value')
        if (not isinstance(value, dict) or value.get('schema_version') == RESEARCH_SCHEMA_VERSION
                or type(value.get('company_id')) is not int or value['company_id'] != input['company_id']
                or value.get('role') != role or value.get('status') != 'completed'):
            return envelope
        diagnostic = legacy.evidence_diagnostic(role=role, stage='agent_business_schema',
                                               field='schema_version', rule='schema_version')
        repaired_envelope = self._bounded.invoke_response_resolver(original_role=role, input={
            'company_id': input['company_id'], 'research_role': role,
            'failed_contract': diagnostic, 'invalid_response': deepcopy(value),
            'response_contract': complete_research_contract(input.get('response_contract', {})),
            'repair_scope': 'research_business_json',
            'repair_instruction': 'Correct schema_version only to the required literal. Copy every other '
                'field and value exactly, including all claims, citations, dates, confidence and uncertainties. '
                'Do not search, add facts, delete fields, change identity or strengthen a verdict.',
        })
        # The existing resolver reservation and global dispatcher own the budget.
        # Its response still passes the original schema and identity validators.
        repaired, _ = legacy.extract_agent_json(repaired_envelope, expected_role=role,
            company_id=input['company_id'], expected_schema_version=RESEARCH_SCHEMA_VERSION)
        if business_bytes(value) != business_bytes(repaired):
            detail = legacy.evidence_diagnostic(role=role, stage='research_repair',
                field='business_payload', rule='repair_changed_business_content')
            self._bounded.record_response_recovery(company_id=input['company_id'], role=role,
                status='unresolved', diagnostic=detail)
            raise legacy.UnresolvedAgentResponse(detail)
        self._bounded.record_response_recovery(company_id=input['company_id'], role=role,
            status='schema_echo_repaired', diagnostic=diagnostic)
        # Keep the original admitted citations and provider support metadata.
        return {**envelope, 'result': {**result, 'content': [{**content[0], 'value': repaired}]}}
