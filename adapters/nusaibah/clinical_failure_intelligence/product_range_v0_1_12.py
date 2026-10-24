"""Deterministic product selection from a complete, runtime-governed snapshot.

Indexes select distinct products in source order. This module owns neither
transport nor execution authority; each selected case still needs fresh admission.
"""
from copy import copy, deepcopy
import re

if __package__:
    from .contracts_v0_1_12 import ContractError, REQUEST_SCHEMA, canonical_bytes, digest, identifier, iso_date, require, safe_json
    from .source_events_v0_1_12 import MAX_SOURCE_BYTES, MAX_SOURCE_RECORDS, _record_object, _provenance, _identity_pair, _trial_selection, normalize_event_records
else:
    from contracts_v0_1_12 import ContractError, REQUEST_SCHEMA, canonical_bytes, digest, identifier, iso_date, require, safe_json
    from source_events_v0_1_12 import MAX_SOURCE_BYTES, MAX_SOURCE_RECORDS, _record_object, _provenance, _identity_pair, _trial_selection, normalize_event_records

RANGE = re.compile(r'(0|[1-9][0-9]*):(0|[1-9][0-9]*)\Z')
RANGE_FIELDS = {'product_index_range', 'product_index_digest', 'selected_product_index'}
CASE_FIELDS = {'subject_id', 'product_id', 'event_ids', 'indication_id', 'trial_id'}
BINDING_FIELDS = {'source_object_id'}
BASE_FIELDS = {'schema_version', 'request_id', 'as_of_date', 'analysis_mode', 'preflight_only',
    'memory_mode', 'enable_refinement', 'enable_pharmacological_class', 'supplementary_search',
    'prepare_result_for_persistence', 'agent_parallelism', 'max_agent_calls', 'max_product_seconds'}


def bounds(value):
    require(isinstance(value, str) and len(value) <= 24 and RANGE.fullmatch(value) is not None,
            'clinical_product_index_range_invalid')
    start, end = map(int, value.split(':'))
    require(start <= end, 'clinical_product_index_range_reversed')
    return start, end


def plan_products(inputs):
    """Return exact semantic selectors, never source bodies or fabricated pairs."""
    require(isinstance(inputs, dict) and {'variables', 'clinical_context'} <= set(inputs), 'clinical_inputs_invalid')
    values, envelope = inputs['variables'], inputs['clinical_context']
    require(isinstance(values, dict) and set(values) <= BASE_FIELDS | CASE_FIELDS | RANGE_FIELDS | BINDING_FIELDS,
            'clinical_product_range_fields_invalid')
    safe_json(values)
    if 'source_object_id' in values:
        require(type(values['source_object_id']) is int and values['source_object_id'] > 0,
                'clinical_source_object_id_invalid')
    require(values.get('schema_version') == REQUEST_SCHEMA, 'clinical_request_schema_invalid')
    identifier(values.get('request_id'))
    cutoff = iso_date(values.get('as_of_date'))
    require(values.get('analysis_mode', 'mechanistic_case') == 'mechanistic_case', 'clinical_source_case_mode_required')
    start, end = bounds(values.get('product_index_range'))
    require(isinstance(envelope, dict) and set(envelope) == {'records', 'provenance'}, 'clinical_source_envelope_invalid')
    rows = envelope['records']
    require(isinstance(rows, list) and len(rows) <= MAX_SOURCE_RECORDS, 'clinical_source_count_exceeds_limit')
    require(len(canonical_bytes(envelope)) <= MAX_SOURCE_BYTES, 'clinical_source_size_exceeds_limit')
    proof = _provenance(envelope, rows)
    products, events, seen_events, unassigned = {}, {}, set(), []
    for position, row in enumerate(rows):
        _record_object(row)
        require(row['event_id'] not in seen_events, 'clinical_source_event_duplicate')
        seen_events.add(row['event_id'])
        row_products = set()
        for product in row['products']:
            pid = identifier(product.get('product_id'))
            require(pid not in row_products, 'clinical_source_association_duplicate')
            row_products.add(pid)
            products.setdefault(pid, len(products))
            events.setdefault(pid, []).append(row)
        if not row_products:
            unassigned.append(row['event_id'])
    ordered = list(products)
    require(end < len(ordered), 'clinical_product_index_range_out_of_bounds')
    index_digest = digest({'source_snapshot': proof['file_sha256'], 'ordered_product_ids': ordered})
    if values.get('product_index_digest') is not None:
        require(values['product_index_digest'] == index_digest, 'clinical_product_index_snapshot_changed')
    selected = ordered[start:end + 1]
    groups, blocked, cases = {}, [], []
    for pid in selected:
        for row in events[pid]:
            try:
                require(row['event_date'] <= cutoff, 'clinical_source_event_future')
                indication_id, label = _identity_pair(row['indications'], 'designation_id', 'designation_label', None)
                require(indication_id is not None and isinstance(label, str) and label.strip(), 'clinical_source_indication_unresolved')
                trial_id, _ = _trial_selection(row['trials'], None)
                key = (pid, indication_id, trial_id, row['event_id'] if trial_id is None else None)
                groups.setdefault(key, []).append(row['event_id'])
            except ContractError as error:
                blocked.append({'product_index': products[pid], 'product_id': pid,
                    'event_id': row['event_id'], 'reason_code': error.code,
                    'resolution_required': {'deferred_case_id':'deferred_'+digest({
                        'snapshot':proof['file_sha256'],'product_id':pid,'event_id':row['event_id'],
                        'reason_code':error.code}).split(':')[1][:32],
                        'source_snapshot_sha256':proof['file_sha256'],'source_record_digest':digest(row),
                        'association_scope':'event_level_not_pairwise_attributed',
                        'indication_candidates':deepcopy(row['indications']),
                        'trial_candidates':deepcopy(row['trials']),
                        'next_action':'verify_source_association_before_selecting_case',
                        'automatic_assignment_permitted':False}})
    for (pid, indication_id, trial_id, event_scope), event_ids in groups.items():
        for offset in range(0, len(event_ids), 32):
            selected_events = event_ids[offset:offset + 32]
            scope = {'product_id': pid, 'indication_id': indication_id, 'trial_id': trial_id, 'event_ids': selected_events}
            case_id = 'case_' + digest(scope).split(':')[1][:32]
            variables = {k:deepcopy(v) for k,v in values.items() if k in BASE_FIELDS | BINDING_FIELDS}
            variables.update(schema_version=REQUEST_SCHEMA, analysis_mode='mechanistic_case',
                request_id='rq_' + digest([values['request_id'], case_id]).split(':')[1][:32],
                subject_id='subject_' + digest(scope).split(':')[1][:32], **scope,
                product_index_range=values['product_index_range'], product_index_digest=index_digest,
                selected_product_index=products[pid])
            if trial_id is None:
                variables.pop('trial_id')
            # Reuse the existing exact source scope validator. No Cartesian join.
            context = normalize_event_records(variables, envelope)
            cases.append({'case_id': case_id, 'product_index': products[pid], 'product_id': pid,
                'event_ids': selected_events, 'indication_id': indication_id, 'trial_id': trial_id,
                'subject': context['subject'], 'variables': variables})
    receipt = {'schema_version': 'clinical_product_selection.v1', 'index_base': 0, 'end_inclusive': True,
        'requested_range': values['product_index_range'], 'order': 'first_appearance_in_governed_snapshot',
        'source_snapshot_sha256': proof['file_sha256'], 'product_index_digest': index_digest,
        'source_record_count': len(rows), 'total_distinct_products': len(ordered),
        'selected_product_count': len(selected), 'selected_indexes': list(range(start, end + 1)),
        'selected_product_ids': selected, 'selected_case_count': len(cases),
        'blocked_case_count': len(blocked), 'unassigned_event_ids': unassigned}
    return {'schema_version': 'clinical_product_range_plan.v1',
        'status': 'needs_attention' if blocked or not cases else 'ready',
        'selection_receipt': receipt, 'cases': cases, 'blocked_cases': blocked,
        'workflow_concurrency': 2, 'execution_required': 'independently_admitted_case_workflows',
        'agent_calls': 0, 'publication_confirmed': False}


def scoped_inputs(inputs):
    """Verify the selected case again after fresh governed input hydration."""
    values = inputs['variables']
    require('selected_product_index' in values, 'clinical_product_range_case_required')
    index = values['selected_product_index']
    require(type(index) is int, 'clinical_product_index_invalid')
    plan = plan_products(inputs)
    require(index in plan['selection_receipt']['selected_indexes'], 'clinical_product_index_not_selected')
    matching = [row for row in plan['cases'] if row['product_index'] == index
        and row['product_id'] == values.get('product_id') and row['indication_id'] == values.get('indication_id')
        and row['trial_id'] == values.get('trial_id') and row['event_ids'] == values.get('event_ids')
        and row['subject']['subject_id'] == values.get('subject_id')]
    require(len(matching) == 1, 'clinical_product_range_case_mismatch')
    require(values.get('product_index_digest') == plan['selection_receipt']['product_index_digest'],
            'clinical_product_index_snapshot_changed')
    # Keep the runtime's admitted Agent/Skill accessors and private invocation
    # state. Converting to dict would discard them after a successful preflight.
    selected = copy(inputs)
    selected['variables'] = {k:deepcopy(v) for k,v in values.items() if k not in RANGE_FIELDS}
    return selected, {**plan['selection_receipt'], 'case_id': matching[0]['case_id'],
        'executed_product_index': index, 'executed_product_id': matching[0]['product_id']}


def range_selection(inputs):
    """Model-free top-level planner; single-case selectors cannot be hidden here."""
    values = inputs['variables']
    require(set(inputs) == {'variables', 'clinical_context'}, 'clinical_product_range_source_scope_conflict')
    require(not set(values) & CASE_FIELDS, 'clinical_product_range_selector_conflict')
    require(values.get('preflight_only') is True, 'clinical_product_range_requires_preflight_plan')
    plan = plan_products(inputs)
    return {'response_version': '1', 'status': 'success', 'outputs': {'product_selection': plan},
        'metrics': {'logical_agent_calls': 0}, 'logs': []}
