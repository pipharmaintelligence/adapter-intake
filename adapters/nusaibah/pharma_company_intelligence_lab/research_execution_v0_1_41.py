"""Fair role/section rounds; reuse the attested grounded claim validation path."""
from collections import deque
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .research_execution_v0_1_40 import consolidate_role, _research_piece, join_research_v0_1_26
    from .research_claim_pipeline_v0_1_26 import research_response_contract_for_role_v0_1_26
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy
    from research_execution_v0_1_40 import consolidate_role, _research_piece, join_research_v0_1_26
    from research_claim_pipeline_v0_1_26 import research_response_contract_for_role_v0_1_26


def run_research_fanout_v0_1_33(inputs, **kwargs):
    company_id = kwargs['company_id']; queues = {}; diagnostics = {}; results = {}
    planned = {focus.role for focus in kwargs['methodology_plan'].research_focus}
    for role in legacy.RESEARCH_ROLES:
        diagnostics[role] = []
        if role not in planned:
            queues[role] = deque()
            diagnostics[role].append(legacy.evidence_diagnostic(role=role, stage='section_planning',
                field='sections', rule='research_role_unplanned'))
            continue
        base = {'company_id': company_id, 'company_name': kwargs['company_name_value'],
            'objective': kwargs['request'].objective, 'research_depth': kwargs['request'].research_depth,
            'governed_company_baseline': kwargs['baseline'],
            'required_sections': legacy._section_requests(legacy.RESEARCH_ROLE_SECTIONS[role]),
            'planned_section_ids': kwargs['methodology_plan'].role_focus(role)['section_ids'],
            'methodology_plan': kwargs['methodology_plan'].role_focus(role),
            'response_contract': research_response_contract_for_role_v0_1_26(role=role, company_id=company_id)}
        packets, omitted = inputs.research_packets(role, base)
        queues[role] = deque(packets)
        if omitted:
            diagnostics[role].append(legacy.evidence_diagnostic(role=role, stage='input_preflight',
                field='paragraphs', rule='indivisible_paragraph_or_subsection_exceeds_budget'))
    work = []
    while any(queues.values()):
        for role in legacy.RESEARCH_ROLES:
            if queues[role]: work.append({**queues[role].popleft(), '_dispatch_role': role})
    def execute(packet):
        value = dict(packet); role = value.pop('_dispatch_role')
        return _research_piece(inputs, role, value, **kwargs)
    outcomes = inputs.coordinator.parallel(work, execute)
    for role in legacy.RESEARCH_ROLES:
        own = [result for packet,result in zip(work,outcomes) if packet['_dispatch_role']==role]
        parts = [result['value'] for result in own if result['status']=='completed']
        diagnostics[role].extend(result['diagnostic'] for result in own if result['status']=='unresolved')
        results[role] = consolidate_role(parts, role, company_id, diagnostics[role])
    return results
