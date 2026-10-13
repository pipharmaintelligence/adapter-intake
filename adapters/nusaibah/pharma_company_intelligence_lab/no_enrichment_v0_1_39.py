"""A resolved review with no supported delta is a completed, write-free outcome."""
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy

NO_ENRICHMENT_RULES = frozenset({
    'no_supported_enrichment_after_section_critic', 'no_usable_research_evidence',
})


def complete_no_enrichment(state, diagnostic):
    """Normalize only known empty-evidence outcomes; keep execution errors visible."""
    progress = state.get('progress', {})
    research = progress.get('research', {})
    critic = progress.get('critic', {})
    result = state['result']
    if (diagnostic.get('rule') not in NO_ENRICHMENT_RULES
        or diagnostic.get('stage') != 'pre_synthesis_quality'
        or result.get('agent_schema_incomplete')
        or result.get('unresolved_agent_responses')
        or not research
        or set(research) != set(legacy.RESEARCH_ROLES)
        or (diagnostic.get('rule') == 'no_supported_enrichment_after_section_critic'
            and not critic.get('section_outcomes'))
        or any(payload.get('_unresolved_response') for payload in research.values())
        or any(outcome.get('status') == 'unresolved' or outcome.get('chunk_diagnostics')
               for outcome in critic.get('section_outcomes', []))
        or any(observation.get('status') == 'source_admission_incomplete'
               for observation in progress.get('source_retrieval', []))):
        return False
    claims = progress.get('joined_research', {}).get('claims', [])
    state.update(no_supported_enrichment=True, incomplete_schema_preview=False,
                 memory_mutation_eligible=False, methodology_learning_candidate=None)
    result.update(business_result_state='no_change', review_outcome='no_change',
                  source_admitted_claim_count=len(claims), accepted_claim_count=0,
                  withheld_claim_count=len(claims), research_evidence_state='no_supported_enrichment',
                  section_enrichment={'sections': [], 'added_fact_ids': [], 'omitted_facts': [],
                                      'baseline_preserved': True})
    # Keep critic limitations and rejected research visible without treating an
    # empty set of supported facts as a broken response or a pending mutation.
    annex = result.get('issues_annex', {})
    for item in annex.get('items', []):
        if item.get('rule') in NO_ENRICHMENT_RULES:
            item['action'] = 'no_change'
    annex['canonical_candidates_withheld'] = False
    return True


def no_enrichment_publication(inputs, state):
    """Resolve the no-write phase without inventing a ZIP or upload readback."""
    if (not state.get('no_supported_enrichment') or state.get('incomplete_schema_preview')
        or state['result'].get('accepted_claim_count') != 0
        or state.get('memory_mutation_eligible') is not False):
        raise ValueError('No-enrichment publication requires a validated write-free state.')
    memory = legacy._read_company_memory(inputs, company_id=state['company_id'], allow_absent=True)
    methodology, _ = legacy._load_methodology_learning(inputs, company_id=state['company_id'])
    digests = {'memory': memory['digest'],
               'methodology': None if methodology is None else methodology.content_digest()}
    state['result'].update(memory_before_digest=digests['memory'],
                           methodology_learning_before_digest=digests['methodology'],
                           memory_initialized=memory['handle'] is not None,
                           memory_initialization_required=False)
    # publication_complete means all required work in this phase is resolved;
    # the existing no_change status explicitly records that nothing was uploaded.
    return {'company_id': state['company_id'], 'publication_complete': True,
            'human_approval_required': False, 'storage_authority': 'core_dynamic_skill',
            'cross_skill_atomic': False,
            **{name: {'status': 'no_change', 'reason': 'no_supported_enrichment',
                      'no_change_verified': True, 'write_attempted': False,
                      'before_digest': digest, 'after_digest': digest,
                      'upload_id': None, 'operation_id': None, 'upload_verified': False,
                      'change_id': None, 'readback_verified': False, 'history_verified': False}
               for name, digest in digests.items()}}
