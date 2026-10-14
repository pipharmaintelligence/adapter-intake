"""Readable section paragraphs and a single compact evidence register."""
from dataclasses import replace
import re
from urllib.parse import urlsplit
try:
    from .dossier_contract import SECTION_BY_ID
    from .memory_contract import MAX_MEMORY_CANDIDATE_CHARS
    from .section_enrichment_v0_1_28 import literal
except ImportError:
    from dossier_contract import SECTION_BY_ID
    from memory_contract import MAX_MEMORY_CANDIDATE_CHARS
    from section_enrichment_v0_1_28 import literal

PROFILE_MARKER = '<!-- readable-company-profile:v1 -->'
BUSINESS_SECTIONS = ('company_profile','product_portfolio_intelligence',
                     'markets_commercial_signals','regulatory_clinical_risk_signals')


def reference_text(locator):
    # URLs already passed source admission. Markdown escaping their underscores
    # changes the locator and can turn a public reference into an invalid URL.
    return '<'+locator+'>' if urlsplit(locator).scheme in {'https','http'} else literal(locator)


def normalized(text):
    return ' '.join(re.findall(r'\w+', text.casefold()))


def qualified_statement(claim):
    text = claim['statement'].strip()
    date = claim.get('as_of_date')
    if date and str(date) not in text:
        text = 'As of '+str(date)+', '+text
    qualifiers = claim.get('evidence_qualifiers', [])
    historical = any('historical' in q or 'snapshot' in q for q in qualifiers)
    if historical and not any(word in text.lower() for word in ('historical','snapshot','recorded','as of')):
        text = 'The historical source records: '+text
    if claim.get('inference'):
        text = 'Interpretation, rather than an independently verified fact: '+text
    # Qualifications are business meaning; provenance detail belongs in annex.
    other = [q.replace('_',' ') for q in qualifiers if 'historical' not in q and 'snapshot' not in q]
    if other: text += ' ('+'; '.join(other)+')'
    return text.rstrip('. ') + '.'


def build_profile_candidate(candidate, before, claims, *, paragraphs=(), company_name='', issues=()):
    allowed = set(candidate.fact_ids); known = {}; seen = set(); aliases = {}
    for claim in claims:
        if claim['claim_id'] not in allowed: continue
        key = (normalized(claim['statement']), claim.get('as_of_date'),
               tuple(claim.get('evidence_qualifiers', [])), bool(claim.get('inference')))
        if key in seen:
            aliases[claim['claim_id']] = next(cid for cid,c in known.items() if (
                normalized(c['statement']), c.get('as_of_date'), tuple(c.get('evidence_qualifiers', [])), bool(c.get('inference'))) == key)
            continue
        if not (claim.get('source_spans') or claim.get('native_grounding')): continue
        seen.add(key); known[claim['claim_id']] = claim
    existing = set(re.findall(r'<!-- enrichment_fact: ([^\n]+) -->', before))
    if PROFILE_MARKER in before and set(known).issubset(existing):
        return replace(candidate, markdown=before, fact_ids=()), {
            'schema_version':'pharma_section_enrichment.v1','sections':[], 'added_fact_ids':[],
            'omitted_facts':[], 'baseline_preserved':True, 'paragraphs':[], 'references':[],
            'narrative_issues':list(issues),'scope':'critic_reviewed_paragraphs','human_approval_required':False}
    accepted = []; used = set()
    for paragraph in paragraphs:
        ids = list(dict.fromkeys(aliases.get(c,c) for c in paragraph['claim_ids']))
        if not ids or any(c not in known for c in ids) or set(ids) & used: continue
        if any(known[c]['section_id'] != paragraph['section_id'] for c in ids): continue
        accepted.append({**paragraph, 'claim_ids':ids}); used.update(ids)
    # If presentation failed, preserve supported research in readable prose.
    # Group at most three sentences by section, with no invented transition.
    for sid in BUSINESS_SECTIONS:
        remaining = [c for c in known.values() if c['section_id']==sid and c['claim_id'] not in used]
        for offset in range(0,len(remaining),3):
            group = remaining[offset:offset+3]
            accepted.append({'section_id':sid,'subsection_id':None,
                'text':' '.join(qualified_statement(c) for c in group),
                'claim_ids':[c['claim_id'] for c in group], 'basis':'reviewed_claim_prose_fallback'})
    refs = []; included = []; rendered = []; omitted = []; sections = []
    # Prior material is preserved verbatim in the annex, not injected into each
    # Agent or mistaken for current evidence. It remains under Core history/CAS.
    previous = ('\n\n### Annex: Previous Memory\n\n'+before) if before.strip() else ''
    title = '### '+literal(company_name or 'Company '+str(candidate.company_id))+' — Company Profile\n\n'
    title += PROFILE_MARKER+'\n\n'
    for sid in BUSINESS_SECTIONS:
        block = '\n#### '+SECTION_BY_ID[sid].title+'\n\n'; section_rows = []
        for p in (p for p in accepted if p['section_id']==sid):
            locs = list(dict.fromkeys(loc for cid in p['claim_ids'] for loc in known[cid]['citation_locators']))
            next_refs = refs + [loc for loc in locs if loc not in refs]
            labels = ['[R'+str(next_refs.index(loc)+1)+']' for loc in locs]
            sub = p.get('subsection_id'); spec = next((s for s in SECTION_BY_ID[sid].subsections if s.subsection_id==sub),None)
            heading = ('##### '+spec.title+'\n\n') if spec else ''
            text = heading+literal(p['text'])+' '+' '.join(labels)+'\n\n'
            markers = ''.join('<!-- enrichment_fact: '+cid+' -->\n' for cid in p['claim_ids'])
            # Reserve a compact quality table; never truncate a paragraph or
            # overwrite prior memory to make an oversize document appear full.
            tentative_ids = included+p['claim_ids']
            register = evidence_register(next_refs, known, tentative_ids)
            proposed = title+''.join(sections)+block+text+markers+register+previous
            if len(proposed)>MAX_MEMORY_CANDIDATE_CHARS-2500:
                omitted.extend({'claim_id':cid,'reason':'profile_size_budget'} for cid in p['claim_ids']); continue
            refs=next_refs;block+=text+markers;included+=p['claim_ids']
            section_rows.append({**p,'paragraph':len(section_rows)+1,'citation':' '.join(labels)})
        if not section_rows:
            block += 'No supported new findings were established for this section in this pass.\n\n'
        rendered.extend(section_rows); sections.append(block)
    if not included:
        markdown = before
    else:
        markdown = title+''.join(sections)+evidence_register(refs,known,included)+previous
    return replace(candidate,markdown=markdown,fact_ids=tuple(dict.fromkeys(included))), {
        'schema_version':'pharma_section_enrichment.v1',
        'sections':list(dict.fromkeys(p['section_id'] for p in rendered)),
        'added_fact_ids':list(dict.fromkeys(included)), 'omitted_facts':omitted,
        'baseline_preserved':not before or before in markdown,
        'paragraphs':rendered, 'references':[{'citation':'[R'+str(i+1)+']','locator':loc} for i,loc in enumerate(refs)],
        'narrative_issues':list(issues), 'scope':'critic_reviewed_paragraphs', 'human_approval_required':False}


def evidence_register(refs, known, ids):
    if not ids: return ''
    out = '\n### Annex: Evidence\n\n| Ref. | Evidence date | Basis |\n|---|---|---|\n'
    for i,loc in enumerate(refs,1):
        claims = [known[c] for c in dict.fromkeys(ids) if loc in known[c]['citation_locators']]
        dates = ', '.join(dict.fromkeys(str(c.get('as_of_date') or 'Not stated') for c in claims))
        bases = ', '.join(dict.fromkeys('Provider grounding' if c.get('native_grounding') else 'Exact source span' for c in claims))
        out += f'| [R{i}] | {dates} | {bases} |\n'
    # Full URL/locator appears once in this register, never in every paragraph.
    return out+'\n'+ '\n'.join('[R'+str(i+1)+'] '+reference_text(loc) for i,loc in enumerate(refs))+'\n'
