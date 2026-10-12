"""Benchmark feedback is optional and never repaired into an invented score."""
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy

def observe_benchmark(inputs,**kwargs):
    try:return legacy._run_benchmark(inputs,**kwargs)
    except (legacy.UnresolvedAgentResponse,legacy.AgentContractValidationError) as error:
        if isinstance(error,legacy.AgentContractValidationError) and not legacy.recoverable_quality(error):raise
        diagnostic=error.diagnostic if isinstance(error,legacy.UnresolvedAgentResponse) else error.proof_failure_detail
        return {'schema_version':legacy.BENCHMARK_SCHEMA_VERSION,'company_id':kwargs['company_id'],
            'role':legacy.BENCHMARK_ROLE,'status':'unscored','results':[],
            'diagnostic':diagnostic,'scores_known':False}

def procedural_snapshot(company_id,chunks,before,after):
    lines=['### Procedural Enrichment Observation',
        'This records actual planning and benchmark availability, not company facts or a passed score.',
        'Company ID: '+str(company_id),'Baseline benchmark: '+before['status'],
        'Proposed benchmark: '+after['status']]
    for chunk in chunks:
        lines.extend(['','### '+chunk['section_id']])
        for field in ('questions','methodology_steps'):
            for text in chunk[field]:lines.append('- '+field+': '+' '.join(text.split()))
    return '\n'.join(lines)
