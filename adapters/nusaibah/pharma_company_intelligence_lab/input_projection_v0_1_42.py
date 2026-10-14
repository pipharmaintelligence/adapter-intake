"""Project complete focused packets before measurement and before dispatch."""
from copy import deepcopy
import re
try:
    from .agent_chunks_v0_1_33 import paragraph_units, unique
    from .dossier_contract import SECTION_BY_ID
except ImportError:
    from agent_chunks_v0_1_33 import paragraph_units, unique
    from dossier_contract import SECTION_BY_ID


def focus_input(payload):
    value = deepcopy(payload)
    evidence = value.get('research_evidence')
    if isinstance(evidence, dict):
        claims = evidence.get('claims', [])
        sections = {c['section_id'] for c in claims}
        locators = {r for c in claims for r in c.get('citation_locators', [])}
        spans = {r for c in claims for r in c.get('exact_span_refs', [])}
        for key in ('citation_sources', 'citations'):
            if isinstance(evidence.get(key), list):
                evidence[key] = unique([r for r in evidence[key] if isinstance(r, dict) and r.get('locator') in locators])
        if isinstance(evidence.get('exact_span_catalog'), dict):
            evidence['exact_span_catalog'] = {k: v for k, v in evidence['exact_span_catalog'].items() if k in spans}
        evidence.pop('withheld_claims', None)
        value['packing_scope'] = {**value.get('packing_scope', {}), 'section_ids': sorted(sections)}
        memory = value.get('existing_company_memory')
        if isinstance(memory, str):
            # Do not send the full growing profile and repeated provenance to
            # every downstream call. Whole paragraphs only; no fact truncation.
            titles = {SECTION_BY_ID[s].title.casefold() for s in sections if s in SECTION_BY_ID}
            selected = []; size = 0; relevant = False; annex = False
            for unit in paragraph_units(memory):
                text = unit['text']
                heading = re.match(r'\s*#{1,6}\s+([^\n]+)', text)
                if heading:
                    name = heading.group(1).strip().casefold()
                    annex = name.startswith('annex:')
                    if name in {s.title.casefold() for s in SECTION_BY_ID.values()}:
                        relevant = name in titles
                if relevant and not annex and size + len(text) <= 2400:
                    selected.append(text); size += len(text)
            value['existing_company_memory'] = ''.join(selected)
            original_size=value.get('prior_memory_scope',{}).get('source_char_count',len(memory))
            value['prior_memory_scope'] = {'complete': False, 'basis': 'applicable_whole_paragraphs',
                                           'source_char_count': original_size, 'supplied_char_count': size}
    return value
