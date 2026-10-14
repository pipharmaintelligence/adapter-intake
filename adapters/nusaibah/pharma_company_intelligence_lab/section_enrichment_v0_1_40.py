"""Compact readable company knowledge; facts only, existing text preserved."""
from dataclasses import replace
import re
try:
    from .dossier_contract import SECTION_BY_ID
    from .section_enrichment_v0_1_28 import line,literal
    from .memory_contract import MAX_MEMORY_CANDIDATE_CHARS
except ImportError:
    from dossier_contract import SECTION_BY_ID
    from section_enrichment_v0_1_28 import line,literal
    from memory_contract import MAX_MEMORY_CANDIDATE_CHARS

ANNEX_RESERVE=4000

def build_enrichment_candidate(candidate,before,claims):
    existing=set(re.findall(r'<!-- enrichment_fact: ([^\n]+) -->',before))
    normalized=line(before).casefold();seen=set();refs=[];included=[];omitted=[];sections=[]
    body='';allowed=set(candidate.fact_ids)
    for section_id,spec in SECTION_BY_ID.items():
        block=''
        for claim in claims:
            cid=claim['claim_id'];statement=claim['statement'];key=line(statement).casefold()
            if cid not in allowed or claim['section_id']!=section_id or cid in existing or key in normalized or key in seen:continue
            if not (claim.get('source_spans') or claim.get('native_grounding')):
                omitted.append({'claim_id':cid,'reason':'source_evidence_missing'});continue
            locators=claim['citation_locators'];next_refs=refs+[r for r in locators if r not in refs]
            citations=' '.join('[R'+str(next_refs.index(r)+1)+']' for r in locators)
            text='- '+literal(statement)+' '+citations+'\n'
            qualifiers=claim.get('evidence_qualifiers',[])
            if qualifiers:text+='  Qualifications: '+literal('; '.join(qualifiers))+'\n'
            if claim.get('inference'):text+='  Interpretation; not an independently verified fact.\n'
            if claim.get('as_of_date'):text+='  Evidence date: '+literal(claim['as_of_date'])+'.\n'
            if claim.get('native_grounding'):text+='  Basis: provider-grounded source, reviewed for this claim; webpage text not independently quoted.\n'
            text+='<!-- enrichment_fact: '+cid+' -->\n'
            heading='\n#### '+spec.title+'\n\n' if not block else ''
            ref_text='\n'.join('[R'+str(i+1)+'] '+literal(uri) for i,uri in enumerate(next_refs))
            proposed=before.rstrip()+'\n\n### Company Intelligence Update\n'+body+block+heading+text+'\n##### Sources for this update\n'+ref_text
            if len(proposed)>MAX_MEMORY_CANDIDATE_CHARS-ANNEX_RESERVE:
                omitted.append({'claim_id':cid,'reason':'profile_size_budget'});continue
            refs=next_refs;block+=heading+text;included.append(cid);seen.add(key)
        if block:sections.append(section_id);body+=block
    markdown=before.rstrip()
    if body:
        markdown+='\n\n### Company Intelligence Update\n'+body+'\n##### Sources for this update\n\n'
        markdown+='\n'.join('[R'+str(i+1)+'] '+literal(uri) for i,uri in enumerate(refs))
    return replace(candidate,markdown=markdown,fact_ids=tuple(included)),{
        'schema_version':'pharma_section_enrichment.v1','sections':sections,'added_fact_ids':included,
        'omitted_facts':omitted,'baseline_preserved':markdown.startswith(before.rstrip()),
        'scope':'critic_reviewed_claims','human_approval_required':False}
