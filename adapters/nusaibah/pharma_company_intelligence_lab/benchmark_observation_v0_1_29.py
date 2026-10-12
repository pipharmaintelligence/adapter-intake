"""Disabled benchmark projection; never dispatch a benchmark or its backup."""
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy

def observe_benchmark(inputs,**kwargs):
    """Keep result shape explicit without calling runtime capabilities."""
    return {'schema_version':legacy.BENCHMARK_SCHEMA_VERSION,'company_id':kwargs['company_id'],
        'role':legacy.BENCHMARK_ROLE,'status':'disabled','results':[],
        'enabled':False,'scores_known':False,'reason_code':'benchmark_disabled'}

def procedural_snapshot(company_id,chunks,before,after):
    lines=['### Procedural Enrichment Observation',
        'This records actual section planning. Benchmarks are disabled; no score or non-regression is claimed.',
        'Company ID: '+str(company_id)]
    for chunk in chunks:
        lines.extend(['','### '+chunk['section_id']])
        for field in ('questions','methodology_steps'):
            for text in chunk[field]:lines.append('- '+field+': '+' '.join(text.split()))
    return '\n'.join(lines)
