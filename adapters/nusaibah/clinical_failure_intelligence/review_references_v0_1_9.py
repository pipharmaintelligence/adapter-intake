"""Lossless per-review aliases; source text and reference polarity stay unchanged."""
from copy import deepcopy
if __package__:
    from .contracts_v0_1_9 import require
else:
    from contracts_v0_1_9 import require


def compact_review(data, obligations):
    """Factor repeated logical IDs once, without dropping a passage or evidence edge."""
    value = deepcopy(data)
    item_keys = sorted({row['item_id'] for field in ('candidate_items','dependency_context') for row in value.get(field,[])})
    evidence_keys = sorted({row['evidence_id'] for row in value.get('evidence_packet',[])} |
        {ref for row in value.get('other_evidence_index',[]) for ref in row.get('evidence_ids',[])})
    items = {key:'I'+str(i+1) for i,key in enumerate(item_keys)}
    evidence = {key:'E'+str(i+1) for i,key in enumerate(evidence_keys)}
    for field in ('candidate_items','dependency_context'):
        for row in value.get(field,[]):
            row['item_id'] = items[row['item_id']]
            row['depends_on'] = [items[key] for key in row.get('depends_on',[])]
            for name in ('supporting_evidence_ids','contradicting_evidence_ids'):
                row[name] = [evidence[key] for key in row[name]]
    for row in value.get('evidence_packet',[]):
        row['evidence_id'] = evidence[row['evidence_id']]
    for row in value.get('other_evidence_index',[]):
        if 'evidence_ids' in row:
            row['evidence_ids'] = [evidence[key] for key in row['evidence_ids']]
    if 'case_context_evidence_ids' in value:
        value['case_context_evidence_ids'] = [evidence[key] for key in value['case_context_evidence_ids']]
    if 'review_packet_scope' in value:
        value['review_packet_scope']['assigned_item_ids'] = [items[key] for key in value['review_packet_scope']['assigned_item_ids']]
    value['reference_aliases'] = {'schema_version':'clinical_review_aliases.v1',
        'items':{alias:key for key,alias in items.items()},
        'evidence':{alias:key for key,alias in evidence.items()},
        'instruction':'Use only local I/E aliases in reference fields and review obligations. Aliases are exact identities, not source summaries. Copy scientific text unchanged. Never move a source between support and contradiction.'}
    return value, ['review:'+items[x[len('review:'):]] for x in obligations]


def expand_review(payload, packet):
    """Decode only explicit identity fields; unknown aliases fail closed."""
    mapping = packet.get('reference_aliases')
    if mapping is None:
        return payload
    value = deepcopy(payload)
    def one(key, domain):
        require(isinstance(key,str) and key in mapping[domain], 'clinical_review_alias_unknown')
        return mapping[domain][key]
    for row in value['items']:
        require(isinstance(row,dict), 'clinical_critic_items_invalid')
        row['item_id'] = one(row.get('item_id'),'items')
        for field in ('supporting_evidence_ids','contradicting_evidence_ids'):
            require(isinstance(row.get(field),list),'clinical_critic_evidence_mismatch')
            row[field] = [one(key,'evidence') for key in row[field]]
    for row in value['coverage']:
        key = row.get('obligation_id') if isinstance(row,dict) else None
        require(isinstance(key,str) and key.startswith('review:'),'clinical_agent_coverage_invalid')
        row['obligation_id'] = 'review:'+one(key[len('review:'):],'items')
    for row in value['followup_requests']:
        require(isinstance(row,dict) and isinstance(row.get('affected_item_ids'),list),'clinical_followup_contract_invalid')
        row['affected_item_ids'] = [one(key,'items') for key in row['affected_item_ids']]
    return value
