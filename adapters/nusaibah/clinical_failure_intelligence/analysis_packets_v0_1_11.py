"""Complete, traceable Agent evidence batches; canonical source stays unchanged."""
from copy import deepcopy
if __package__:
    from .contracts_v0_1_11 import canonical_bytes, digest, require
    from .case_context_v0_1_11 import case_context_ids
else:
    from contracts_v0_1_11 import canonical_bytes, digest, require
    from case_context_v0_1_11 import case_context_ids


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
    # An unfit shared base cannot be repaired by splitting assigned windows.
    # Keep one explicit deferred unit with all assignments, never N futile calls.
    if len(canonical_bytes(packet([]))) > max_bytes or (fits is not None and not fits(packet([]))):
        return [ordered]
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
    anchors=case_context_ids(all_evidence,common.get('case_trial_ids'))
    assigned = {row['evidence_id'] for row in batch}
    visible=assigned | anchors
    # Case-critical *source windows* are global. Repeating every claim mentioning
    # an anchor drags unrelated evidence closures into all packets and can turn
    # a 45-call assessment into 101 calls. Claims stay with their assigned windows.
    selected_claims = [row for row in claims if refs(row) & assigned]
    # Generated outcome references are not globally repeated source authority.
    # Keep their complete records once in the canonical result. Supply a compact,
    # explicitly provisional decision index for dependencies; only supplied source
    # windows can substantiate a new scientific claim in this packet.
    required = visible | {ref for row in selected_claims for ref in refs(row)}
    evidence = [deepcopy(row) for row in all_evidence if row['evidence_id'] in required]
    result = {**deepcopy(common), 'evidence_packet':agent_evidence_view(evidence), 'research_claims':deepcopy(selected_claims),
              'case_context_evidence_ids':sorted(anchors),
              'evidence_scope':{'assigned_evidence_ids':sorted(assigned),
                                'included_evidence_ids':sorted(required),
                                'total_evidence_count':len(all_evidence),
                                'complete_evidence_in_packet':len(required)==len(all_evidence),
                                'other_evidence_digest':digest([row['evidence_id'] for row in all_evidence
                                                              if row['evidence_id'] not in required]),
                                'independent_exhaustiveness_claim':False}}
    if outcomes is not None:
        result['case_assessments'] = [{key:deepcopy(row[key]) for key in
            ('item_id','dimension','value','trial_ids','accepted','review_status') if key in row}
            | {'canonical_record_digest':digest(row)} for row in outcomes]
        result['case_assessment_scope'] = {
            'representation':'provisional_decision_index', 'total_records':len(outcomes),
            'canonical_records_digest':digest(outcomes), 'source_evidence':False,
            'independent_review_complete':False,
            'instruction':'Outcome entries are provisional dependency identities, not evidence. Cite only complete supplied evidence_packet windows. Unknown or conflicting outcomes remain unresolved. Full outcome statements and references are retained in the canonical result.'}
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
