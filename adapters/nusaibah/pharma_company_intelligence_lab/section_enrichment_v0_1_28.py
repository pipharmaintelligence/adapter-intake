"""Deterministic, append-only section enrichment from selected admitted claims."""
from dataclasses import replace
import re
try:
    from .dossier_contract import SECTION_BY_ID
    from .memory_contract import MAX_MEMORY_CANDIDATE_CHARS
    from .candidate_validation_v0_1_21 import require_candidate_fact_ids
except ImportError:
    from dossier_contract import SECTION_BY_ID
    from memory_contract import MAX_MEMORY_CANDIDATE_CHARS
    from candidate_validation_v0_1_21 import require_candidate_fact_ids

def line(text):
    return ' '.join(text.split())

def literal(text):
    return re.sub(r'([\\`*_\[\]<>])',r'\\\1',line(text))

def build_enrichment_candidate(candidate, before, claims):
    by_id={c['claim_id']:c for c in claims}
    require_candidate_fact_ids(fact_ids=candidate.fact_ids,accepted_claim_ids=by_id)
    normalized=line(before).casefold()
    existing_ids=set(re.findall(r'<!-- enrichment_fact: ([^\n]+) -->',before))
    additions=[]; included=[]; sections=[]; omitted=[]
    for section_id,spec in SECTION_BY_ID.items():
        body=[]
        for claim_id in candidate.fact_ids:
            claim=by_id[claim_id]
            if claim['section_id']!=section_id:
                continue
            statement=claim['statement']
            if claim_id in existing_ids or line(statement).casefold() in normalized:
                continue
            if not claim.get('source_spans'):
                omitted.append({'claim_id':claim_id,'reason':'exact_source_span_missing'});continue
            text='- '+literal(statement)+'\n'
            if claim.get('inference') is True:
                text+='  Evidence type: explicitly labelled model inference, not an independently verified fact.\n'
            qualifications=claim.get('evidence_qualifiers',[])
            if qualifications:
                text+='  Qualifications: '+literal('; '.join(qualifications))+'\n'
            context=claim.get('semantic_context',{})
            temporal={key:claim.get(key) for key in ('as_of_date',)}
            temporal.update({key:context.get(key) for key in (
                'event_date','publication_date','status_as_of_date','event_state',
                'observation_kind','governed_snapshot_relation','entity_label_kind','relationship_kind',
                'actor','counterparty','territory','manufacturing_responsibility',
                'reported_total','component_total','remainder_label')})
            for key,value in temporal.items():
                if value is not None and value!='not_applicable':
                    text+='  '+key+': '+literal(str(value))+'\n'
            for span in claim['source_spans']:
                # Plain locators are provenance, never executable Markdown URLs.
                text+='  Source locator: '+literal(span['locator'])+'\n'
                text+='  Source snapshot: '+literal(span['source_snapshot_id'])+'\n'
            text+='<!-- enrichment_fact: '+claim_id+' -->\n'
            heading='\n#### '+spec.title+'\n\n' if not body else ''
            proposed=before.rstrip()+''.join(additions)+'\n### Automated Section Enrichment\n'+''.join(body)+heading+text
            if len(proposed)>MAX_MEMORY_CANDIDATE_CHARS:
                omitted.append({'claim_id':claim_id,'reason':'section_enrichment_size_budget'});continue
            body.append(heading+text);included.append(claim_id)
        if body:
            sections.append(section_id);additions.extend(body)
    markdown=before.rstrip()
    if additions:
        markdown+='\n\n### Automated Section Enrichment\n'+''.join(additions)
    if not markdown.strip():
        markdown='No source-verified enrichment was available.'
    return replace(candidate,markdown=markdown,fact_ids=tuple(included)),{
        'schema_version':'pharma_section_enrichment.v1','sections':sections,'added_fact_ids':included,
        'omitted_facts':omitted,'baseline_preserved':bool(before) and markdown.startswith(before.rstrip()),
        'scope':'selected_admitted_claims','human_approval_required':False}
