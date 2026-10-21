"""Complete, traceable Agent evidence batches; canonical source stays unchanged."""
from copy import deepcopy
if __package__:
    from .contracts_v0_1_6 import canonical_bytes, digest, require
else:
    from contracts_v0_1_6 import canonical_bytes, digest, require


def agent_evidence_view(rows):
    """Factor transport provenance out of model packets, never scientific data.

    Canonical ledger rows keep every field. IDs, complete source text/digests,
    clinical metadata, exact locators and scope remain in each Agent packet.
    """
    result = deepcopy(rows)
    for row in result:
        context = row.get("source_context")
        if isinstance(context, dict):
            for key in ("acquisition", "source_asset", "source_result_id", "source_result_digest"):
                context.pop(key, None)
    return result


def evidence_batches(rows, packet, *, max_bytes, max_items=64, fits=None):
    """Size the complete signed-business packet, splitting only between windows."""
    require(type(max_bytes) is int and max_bytes > 0 and type(max_items) is int and max_items > 0,
            'clinical_packet_budget_invalid')
    def priority(row):
        context = row.get('source_context', {})
        pointer = context.get('source_pointer', '')
        use = context.get('evidence_use', '')
        return (0 if use in {'posted_results','safety_results'} or '/resultsSection/' in pointer else
                2 if any(value in pointer.casefold() for value in ('contact','location')) else 1)
    ordered = sorted(rows, key=priority)
    batches, current = [], []
    for row in ordered:
        if current and (len(current) >= max_items or len(canonical_bytes(packet(current+[row]))) > max_bytes or
                        (fits is not None and not fits(packet(current+[row])))):
            batches.append(current)
            current = []
        # An atomic oversize window is kept whole; AgentRunner defers it explicitly.
        current.append(row)
    if current:
        batches.append(current)
    return batches or [[]]


def refs(row):
    return set(row.get('supporting_evidence_ids', [])) | set(row.get('contradicting_evidence_ids', []))


def closed_packet(batch, all_evidence, claims, common, *, outcomes=None):
    """Include relevant complete claims and their evidence closure, never sliced text."""
    assigned = {row['evidence_id'] for row in batch}
    selected_claims = [row for row in claims if refs(row) & assigned]
    selected_outcomes = [row for row in (outcomes or []) if refs(row) & assigned]
    required = assigned | {ref for row in selected_claims+selected_outcomes for ref in refs(row)}
    evidence = [deepcopy(row) for row in all_evidence if row['evidence_id'] in required]
    result = {**deepcopy(common), 'evidence_packet':agent_evidence_view(evidence), 'research_claims':deepcopy(selected_claims),
              'evidence_scope':{'assigned_evidence_ids':sorted(assigned),
                                'included_evidence_ids':sorted(required),
                                'total_evidence_count':len(all_evidence),
                                'complete_evidence_in_packet':len(required)==len(all_evidence),
                                'other_evidence_digest':digest([row['evidence_id'] for row in all_evidence
                                                              if row['evidence_id'] not in required]),
                                'independent_exhaustiveness_claim':False}}
    if outcomes is not None:
        result['case_assessments'] = deepcopy(selected_outcomes)
    return result


def namespace_candidates(stage, kind, index, *, multiple):
    """Keep batch-local candidate IDs distinct without merging contradictory facts."""
    if not multiple or not stage.payload:
        return
    rows = stage.payload.get('items')
    if not isinstance(rows, list):
        return
    mapping = {row['item_id']:kind+':'+str(index)+':'+digest(row['item_id']).split(':')[1][:24]
               for row in rows if isinstance(row, dict) and isinstance(row.get('item_id'), str)}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get('item_id'),str) and row['item_id'] in mapping:
            row['item_id'] = mapping[row['item_id']]
            if isinstance(row.get('depends_on'), list):
                row['depends_on'] = [mapping.get(value,value) for value in row['depends_on']]


def item_evidence(items, evidence):
    """Memory editing receives only the complete evidence supporting its candidates."""
    required = {ref for item in items for ref in refs(item)}
    return agent_evidence_view([row for row in evidence if row['evidence_id'] in required])
