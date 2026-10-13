"""Complete no-enrichment reviews; preserve the existing validated write path."""
try:
    from .automatic_publication_v0_1_38 import publish_company as _publish_supported
    from .no_enrichment_v0_1_39 import no_enrichment_publication
    from .continuation_v0_1_39 import allow_incomplete_continuation
except ImportError:
    from automatic_publication_v0_1_38 import publish_company as _publish_supported
    from no_enrichment_v0_1_39 import no_enrichment_publication
    from continuation_v0_1_39 import allow_incomplete_continuation


def publish_company(inputs, state):
    if state.get('no_supported_enrichment'):
        return no_enrichment_publication(inputs, state)
    candidate = state.get('memory_candidate')
    # An empty deterministic delta is not a request to create a placeholder
    # package. Optional eligible methodology remains independent of this delta.
    if (not state.get('incomplete_schema_preview') and candidate is not None
        and not candidate.fact_ids
        and state.get('result', {}).get('section_enrichment', {}).get('added_fact_ids') == []):
        state = {**state, 'candidate_changed': False}
    return allow_incomplete_continuation(_publish_supported(inputs, state))
