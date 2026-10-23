"""Lossless critic packet batching; every original verdict is validated separately.

No evidence, qualifications, scope or output rule is removed. Large packets use
the original single-review path. Provider concurrency remains coordinator-owned.
"""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
import math
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .agent_chunks_v0_1_39 import prepared_payload
    from .critic_response_v0_1_40 import _validated_agent_response
    from .critic_contract_v0_1_40 import validate_critic
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy
    from agent_chunks_v0_1_39 import prepared_payload
    from critic_response_v0_1_40 import _validated_agent_response
    from critic_contract_v0_1_40 import validate_critic

SCHEMA = 'pharma_critic_batch.v1'
MAX_PIECES = 3


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def factor(values):
    """Factor identical fields recursively; expansion reproduces exact packets."""
    copies = deepcopy(values)
    shared = {}
    for key in sorted(set.intersection(*(set(value) for value in copies))):
        entries = [value[key] for value in copies]
        if all(entry == entries[0] for entry in entries):
            shared[key] = entries[0]
            for value in copies:
                del value[key]
        elif all(isinstance(entry, dict) for entry in entries):
            common, pieces = factor(entries)
            if common:
                shared[key] = common
                for value, piece in zip(copies, pieces):
                    value[key] = piece
    return shared, copies


def expand(shared, piece):
    result = deepcopy(shared)
    for key, value in piece.items():
        result[key] = expand(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else deepcopy(value)
    return result


def payload_for(inputs, group):
    if len(group) == 1:
        return group[0]['packet']
    packets = [prepared_payload(legacy.CRITIC_ROLE, item['packet']) for item in group]
    shared, pieces = factor(packets)
    payload = {'company_id': packets[0]['company_id'], 'review_batch': {
        'schema_version': SCHEMA, 'independent_reviews': True,
        'shared_review_fields': shared,
        'review_packets': [{'packet_id': item['id'], 'fields': piece} for item, piece in zip(group, pieces)],
        'expansion_rule': 'Recursively merge shared_review_fields with each packet.fields. Lists are complete replacements. Each expanded packet is one independent original review; do not join claims, verdicts or section authority across packets.'},
        'response_contract': {'schema_version': SCHEMA, 'company_id': packets[0]['company_id'],
            'role': legacy.CRITIC_ROLE, 'status': 'completed',
            'reviews': [{'packet_id': item['id'], 'review': 'Exact original response_contract object for this expanded packet.'} for item in group],
            'instruction': 'Return exactly one review per packet_id, in supplied order. Apply every original field, bound, enum, company/section/claim/requirement ID and negative-verdict rule independently. Do not summarize away any required review, qualification or guidance. One bad/missing review grants no authority to its siblings.'}}
    return inputs.prepare_input(legacy.CRITIC_ROLE, payload)


def plan_batches(inputs, packets):
    rows = []
    for ordinal, item in enumerate(packets):
        packet = item['packet']
        identity = 'p'+sha256(encoded([ordinal, prepared_payload(legacy.CRITIC_ROLE, packet)]).encode()).hexdigest()
        rows.append({**item, 'id': identity})
    groups = [[] for _ in range(math.ceil(len(rows)/MAX_PIECES))]
    # Put larger packets into the currently lightest fitting group, avoiding a
    # final oversized review that holds the synthesis barrier open.
    for row in sorted(rows, key=lambda row: -len(encoded(row['packet']))):
        candidates = []
        for index, group in enumerate(groups):
            if len(group) >= MAX_PIECES:
                continue
            candidate = payload_for(inputs, [*group, row])
            measured = inputs.coordinator.measure(legacy.CRITIC_ROLE, candidate)
            if measured['within_input_budget']:
                candidates.append((len(encoded(payload_for(inputs, group))) if group else 0, index))
        if candidates:
            groups[min(candidates)[1]].append(row)
        else:
            # A valid original packet always keeps its unchanged legacy lane.
            inputs.coordinator.require_fit(legacy.CRITIC_ROLE, row['packet'])
            groups.append([row])
    groups = [group for group in groups if group]
    before = sum(inputs.coordinator.measure(legacy.CRITIC_ROLE, row['packet'])['provider_prompt_bound_chars'] for row in rows)
    after = sum(inputs.coordinator.measure(legacy.CRITIC_ROLE, payload_for(inputs, group))['provider_prompt_bound_chars'] for group in groups)
    return rows, groups, {'original_packet_count': len(rows), 'planned_group_count': len(groups),
                         'original_prompt_bound_chars': before, 'batched_prompt_bound_chars': after,
                         'max_reviews_per_call': MAX_PIECES, 'lossless_factoring': True}


def _diagnostic(rule):
    return legacy.evidence_diagnostic(role=legacy.CRITIC_ROLE, stage='critic_batch', field='reviews', rule=rule)


def dispatch_reviews(inputs, packets, company_id):
    rows, groups, proof = plan_batches(inputs, packets)
    def validate_piece(item, envelope):
        packet = item['packet']; section = item['section_id']; contract = packet['response_contract']
        known = {claim['claim_id'] for claim in packet['_piece_claims']}
        return _validated_agent_response(inputs, envelope, role=legacy.CRITIC_ROLE,
            company_id=company_id, contract=contract, validator=lambda value: validate_critic(value,
                section_id=section, prior_guidance=item['prior_guidance'], company_id=company_id,
                known_claim_ids=known, known_section_ids={section}, known_plan_requirement_ids=set(item['ids'])))
    def invoke_group(group):
        payload = payload_for(inputs, group)
        envelope = inputs.invoke_agent(legacy.CRITIC_ROLE, input=payload, on_error='raise')
        if len(group) == 1:
            return {group[0]['id']: {'status': 'completed', 'value': validate_piece(group[0], envelope)}}
        normalized, _ = legacy.normalize_json_envelope(envelope, role=legacy.CRITIC_ROLE)
        batch, _ = legacy.extract_agent_json(normalized, expected_role=legacy.CRITIC_ROLE,
                                             company_id=company_id, expected_schema_version=SCHEMA)
        reviews = batch.get('reviews')
        if not isinstance(reviews, list) or len(reviews) > len(group)+4:
            raise legacy.UnresolvedAgentResponse(_diagnostic('critic_batch_reviews_invalid'))
        counts = Counter(review.get('packet_id') for review in reviews if isinstance(review, dict) and isinstance(review.get('packet_id'), str))
        expected = {item['id'] for item in group}
        if any(identity not in expected for identity in counts):
            inputs.phase_issues.append(_diagnostic('critic_batch_unknown_review_id'))
        results = {}
        for item in group:
            identity = item['id']
            if counts[identity] != 1:
                results[identity] = {'status': 'unresolved', 'diagnostic': _diagnostic('critic_batch_review_missing_or_duplicate')}
                continue
            review = next(review.get('review') for review in reviews if isinstance(review, dict) and review.get('packet_id') == identity)
            piece_envelope = deepcopy(normalized)
            # Typed local projection of one unchanged business subobject, not
            # a fabricated runtime/provider receipt or new invocation.
            piece_envelope['result']['content'] = [{'type': 'json', 'value': review}]
            try:
                results[identity] = {'status': 'completed', 'value': validate_piece(item, piece_envelope)}
            except legacy.UnresolvedAgentResponse as error:
                results[identity] = {'status': 'unresolved', 'diagnostic': error.diagnostic}
            except legacy.AgentContractValidationError as error:
                if error.code not in {'pharma_agent_business_schema_invalid','pharma_agent_status_invalid',
                                      'pharma_agent_company_id_invalid','pharma_agent_role_invalid'}:
                    raise
                results[identity] = {'status': 'unresolved', 'diagnostic': legacy.safe_diagnostic(error, role=legacy.CRITIC_ROLE)}
        return results
    jobs = [{'company_id': company_id, 'group': group,
             'chunk_execution': {'chunk_id': 'critic_batch:'+sha256(encoded([row['id'] for row in group]).encode()).hexdigest()},
             'planned_section_ids': sorted({row['section_id'] for row in group})} for group in groups]
    outcomes = inputs.coordinator.parallel(jobs, lambda job: invoke_group(job['group']))
    results = {}
    for group, outcome in zip(groups, outcomes):
        if outcome['status'] == 'completed':
            results.update(outcome['value'])
        else:
            for item in group:
                results[item['id']] = {'status': 'unresolved', 'diagnostic': outcome['diagnostic']}
    by_section = {}
    for row in rows:
        by_section.setdefault(row['section_id'], []).append(results[row['id']])
    return by_section, proof
