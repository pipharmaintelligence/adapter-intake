"""No-Agent preflight using the same pinned source verifier as enrichment."""
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .source_verification_v0_1_45 import TargetedSourceInputs
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy
    from source_verification_v0_1_45 import TargetedSourceInputs


def preflight_sources(inputs, request):
    rows = []
    for record in legacy.order_records_for_request(
            legacy.resolve_company_context(inputs, company_ids=request.company_ids), request):
        company_id = record['company_id']
        memory = legacy._read_company_memory(inputs, company_id=company_id, allow_absent=True)
        _, learning = legacy._load_methodology_learning(inputs, company_id=company_id)
        source = TargetedSourceInputs(inputs, record=record, memory_text=memory['text'], memory_digest=memory['digest'])
        locator = source.units[0]['locator']
        claim = {'claim_id': 'source_preflight', 'citation_locators': [locator],
                 'evidence_quotes': [{'locator': locator, 'quote': '"company_id":' + str(company_id)}]}
        verified, _ = source.verify_source_claims({'role': 'portfolio_researcher', 'claims': [claim]})
        rows.append({'company_id': company_id, 'source_count': len(source.units),
                     'methodology_available': bool(learning.strip()),
                     'toolkit_spans_verified': bool(verified['claims'][0].get('source_spans')),
                     'memory_digest': memory['digest'], 'agent_call_count': 0, 'mutable_call_count': 0})
    return {'response_version': '1', 'status': 'success', 'outputs': {'intelligence_dossier': {
        'schema_version': 'pharma_source_preflight.v1', 'status': 'completed',
        'business_result_state': 'source_preflight', 'requested_company_count': len(rows),
        'completed_company_count': len(rows), 'failed_company_count': 0,
        'company_results': rows, 'apply_authority': False}},
        'metrics': {'agent_call_count': 0, 'mutable_call_count': 0}}
