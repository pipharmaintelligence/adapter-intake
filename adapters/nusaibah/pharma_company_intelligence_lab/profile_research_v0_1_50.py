"""Keep safe research in the profile; verification controls fact status only."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from datetime import date
import calendar
import json, re
from devtools.preview_output_validator import validate_preview_outputs, PreviewOutputValidationError
try:
    from .profile_rendering_v0_1_42 import BUSINESS_SECTIONS, reference_text, normalized
    from .dossier_contract import SECTION_BY_ID
    from .section_enrichment_v0_1_28 import literal
except ImportError:
    from profile_rendering_v0_1_42 import BUSINESS_SECTIONS, reference_text, normalized
    from dossier_contract import SECTION_BY_ID
    from section_enrichment_v0_1_28 import literal

PROFILE_MARKER='<!-- readable-company-profile:v2 -->'
MAX_PROFILE_CHARS=384000
# The portable Skill contract is still 1 MiB per UTF-8 file. Leave room for
# its title, frontmatter and sibling sections; never slice a paragraph to fit.
MAX_PROFILE_BYTES=960*1024
PARAGRAPH_MARKER=re.compile(r'<!-- profile_paragraph: (\d+):(\d+); verification: (verified|unverified) -->')


def _date_pattern(value):
    """Recognize equivalent explicit dates, without guessing ambiguous numerals."""
    try:
        parsed = date.fromisoformat(str(value))
    except ValueError:
        return re.escape(str(value))
    month = '(?:'+calendar.month_name[parsed.month]+'|'+calendar.month_abbr[parsed.month]+r'\.?)'
    day = '0?'+str(parsed.day)+r'(?:st|nd|rd|th)?' if parsed.day < 10 else str(parsed.day)+r'(?:st|nd|rd|th)?'
    year = str(parsed.year)
    return '(?:'+re.escape(str(value))+'|'+month+r'\s+'+day+r',?\s+'+year+'|'+day+r'\s+'+month+r',?\s+'+year+')'


def clean_repeated_date(text, as_of_date):
    """Remove only adjacent equivalent as-of prefixes; retain different dates."""
    if not as_of_date:
        return text
    prefix = r'as\s+of\s+'+_date_pattern(as_of_date)+r'\s*,\s*'
    return re.sub(r'^('+prefix+r')(?:'+prefix+r')+', lambda match: match.group(1), text, flags=re.I)


def qualified_statement(claim):
    text = clean_repeated_date(claim['statement'].strip(), claim.get('as_of_date'))
    as_of = claim.get('as_of_date')
    if as_of and not re.search(r'(?<!\w)'+_date_pattern(as_of)+r'(?!\w)', text, re.I):
        text = 'As of '+str(as_of)+', '+text
    qualifiers = claim.get('evidence_qualifiers', [])
    historical = any('historical' in q or 'snapshot' in q for q in qualifiers)
    if historical and not any(word in text.lower() for word in ('historical','snapshot','recorded','as of')):
        text = 'The historical source records: '+text
    if claim.get('inference'):
        text = 'Interpretation, rather than an independently verified fact: '+text
    other = [q.replace('_',' ') for q in qualifiers if 'historical' not in q and 'snapshot' not in q]
    if other:
        text += ' ('+'; '.join(other)+')'
    return text.rstrip('. ') + '.'


def current_profile_context(text, maximum=None):
    """Existing prose once, without old evidence/history ledgers in new research."""
    current=re.split(r'(?m)^#{1,6}\s+Annex:', text or '', maxsplit=1)[0].strip()
    if maximum is None:return current
    selected=[];size=0
    for paragraph in re.split(r'\n\s*\n', current):
        if size+len(paragraph)+2>maximum:break
        selected.append(paragraph);size+=len(paragraph)+2
    return '\n\n'.join(selected)


def section_profile_context(text, sections, maximum=2400):
    titles={SECTION_BY_ID[s].title.casefold():s for s in BUSINESS_SECTIONS}
    selected=[];size=0;current=None
    for paragraph in re.split(r'\n\s*\n',current_profile_context(text)):
        heading=re.match(r'\s*#{1,6}\s+(.+)',paragraph)
        if heading:
            title=re.sub(r'^\d+\.\s*','',heading.group(1).strip()).casefold()
            if title in titles:current=titles[title]
        if current not in sections:continue
        if size+len(paragraph)+2>maximum:continue
        selected.append(paragraph);size+=len(paragraph)+2
    return '\n\n'.join(selected)


def safe_business(value):
    try:
        validate_preview_outputs({'company_profile': value})
        return True
    except PreviewOutputValidationError:
        return False


def semantic_key(claim):
    try:
        from .profile_memory_v0_1_45 import prose_key
    except ImportError:
        from profile_memory_v0_1_45 import prose_key
    context=claim.get('semantic_context') or {}
    return (prose_key(claim['statement']),claim.get('as_of_date'),tuple(claim.get('evidence_qualifiers',[])),
            bool(claim.get('inference')),claim.get('actor') or context.get('actor'),
            claim.get('counterparty') or context.get('counterparty'))


def research_records(joined, critic=None):
    """Copy original model statements before accepted-only downstream filtering."""
    critic=critic or {}; reviewed=set(critic.get('reviewed_claim_ids',[])); rejected=set(critic.get('rejected_claim_ids',[]))
    accepted={c['claim_id'] for c in joined.get('claims',[])}; records=[]; seen={}; issues=[]
    for original in list(joined.get('claims',[]))+list(joined.get('withheld_claims',[])):
        if original.get('section_id') not in BUSINESS_SECTIONS or not isinstance(original.get('statement'),str) or not original['statement'].strip():
            continue
        claim={k:deepcopy(v) for k,v in original.items() if not k.startswith('_')}
        if not safe_business(claim):
            issues.append({'claim_id':original.get('claim_id'),'reason':'unsafe_business_content'})
            continue
        verified=(claim['claim_id'] in accepted and claim['claim_id'] in reviewed-rejected
                  and bool(claim.get('source_spans') or claim.get('native_grounding')))
        claim['verification_status']='verified' if verified else 'unverified'
        claim['verification_reason']=None if verified else original.get('issue_code') or original.get('_source_issue') or 'verification_pending'
        key=semantic_key(claim)
        if key in seen:
            position=seen[key]
            if verified and records[position]['verification_status']!='verified':records[position]=claim
            continue
        seen[key]=len(records);records.append(claim)
    return records,issues


def narrative_joined(joined, records):
    return {**joined,'claims':records}


def build_profile_candidate(candidate, before, claims, *, paragraphs=(), company_name='', issues=(), research=()):
    """Render every distinct safe statement once; annex holds coordinates only."""
    try:
        from .profile_memory_v0_1_45 import current_memory_records
    except ImportError:
        from profile_memory_v0_1_45 import current_memory_records
    known={};keys={};aliases={}
    supplied=list(research)+[{**deepcopy(c),'verification_status':'verified','verification_reason':None} for c in claims]
    input_digest = sha256(json.dumps({'research': supplied, 'paragraphs': list(paragraphs)},
        sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    input_marker = '<!-- profile_input_digest: '+input_digest+' -->'
    carried = [c for c in current_memory_records(before, supplied, paragraphs) if safe_business(c)] if supplied else []
    supplied += carried
    for claim in supplied:
        key=semantic_key(claim);previous=keys.get(key)
        if previous is not None:
            aliases[claim['claim_id']]=previous
            if claim.get('verification_status')=='verified' and known[previous].get('verification_status')!='verified':
                aliases[previous]=claim['claim_id'];keys[key]=claim['claim_id']
                known.pop(previous);known[claim['claim_id']]=deepcopy(claim)
            continue
        keys[key]=claim['claim_id'];known[claim['claim_id']]=deepcopy(claim)
    allowed=set(candidate.fact_ids)
    for claim in known.values():
        if claim['claim_id'] not in allowed:claim['verification_status']='unverified'
    rows=[];used=set();omitted=[]
    for p in paragraphs:
        ids=list(dict.fromkeys(aliases.get(cid,cid) for cid in p['claim_ids']))
        if not ids or any(cid not in known or known[cid]['section_id']!=p['section_id'] for cid in ids) or set(ids)&used:
            continue
        if not safe_business(p['text']):continue
        verified=(p.get('verification_status')=='verified' and all(known[c]['verification_status']=='verified' for c in ids))
        rows.append({**p,'claim_ids':ids,'verification_status':'verified' if verified else 'unverified'})
        used.update(ids)
    for sid in BUSINESS_SECTIONS:
        for status in ('verified','unverified'):
            own=[c for c in known.values() if c['section_id']==sid and c['verification_status']==status and c['claim_id'] not in used]
            # A complete original statement is a paragraph. Arbitrarily joining
            # three unrelated claims creates a ledger disguised as prose.
            for claim in own:
                rows.append({'section_id':sid,'subsection_id':claim.get('subsection_id'),
                    'text':qualified_statement(claim), 'claim_ids':[claim['claim_id']],
                    'verification_status':status,'basis':'original_research_prose_fallback'})
    refs=[];rendered=[];fact_ids=[];sections=[];review=[]
    previous=''
    digest=sha256(json.dumps({'research':list(known.values()),'paragraphs':rows},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    digest_marker='<!-- profile_research_digest: '+digest+' -->'
    title='### '+literal(company_name or 'Company '+str(candidate.company_id))+' — Company Profile\n\n'+PROFILE_MARKER+'\n'+digest_marker+'\n'+input_marker+'\n\n'
    for number,sid in enumerate(BUSINESS_SECTIONS,1):
        block='\n#### '+str(number)+'. '+SECTION_BY_ID[sid].title+'\n\n'; own=[]
        for p in (p for p in rows if p['section_id']==sid):
            ordinal=len(own)+1; verified=p['verification_status']=='verified'
            locators=list(dict.fromkeys(loc for cid in p['claim_ids'] for loc in known[cid].get('citation_locators',[])))
            locators=[loc for loc in locators if isinstance(loc,str) and safe_business(loc)]
            next_refs=refs+[loc for loc in locators if loc not in refs]
            labels=['[R'+str(next_refs.index(loc)+1)+']' for loc in locators]
            marker=f'<!-- profile_paragraph: {number}:{ordinal}; verification: '+p['verification_status']+' -->\n'
            text=marker+('**Unverified research.** ' if not verified else '')+literal(p['text'])+(' '+' '.join(labels) if labels else '')+'\n\n'
            markers=''.join('<!-- enrichment_fact: '+cid+' -->\n' for cid in p['claim_ids'] if verified and cid in allowed)
            tentative=title+''.join(sections)+block+text+markers+previous
            reference_budget='\n'.join(reference_text(loc) for loc in next_refs)
            annex_reserve=max(12000,len(reference_budget)+len(next_refs)*100+(len(review)+1)*32+4096)
            byte_reserve=max(12000,len(reference_budget.encode('utf-8'))+len(next_refs)*100+(len(review)+1)*32+4096)
            if (len(tentative)>MAX_PROFILE_CHARS-annex_reserve
                    or len(tentative.encode('utf-8'))>MAX_PROFILE_BYTES-byte_reserve):
                omitted.extend({'claim_id':cid,'reason':'profile_size_budget'} for cid in p['claim_ids']);continue
            refs=next_refs;block+=text+markers;own.append({**p,'section_number':number,'paragraph':ordinal,'citation':' '.join(labels)})
            if verified:fact_ids.extend(cid for cid in p['claim_ids'] if cid in allowed)
            else:review.append({'section_number':number,'paragraph_number':ordinal})
        if not own:block+='Research did not establish a useful finding for this section in this bounded pass.\n\n'
        rendered.extend(own);sections.append(block)
    evidence='\n### Annex: Evidence\n\n| Ref. | Verification |\n|---|---|\n'
    for i,loc in enumerate(refs,1):
        verified=any(p['verification_status']=='verified' and any(loc in known[c].get('citation_locators',[]) for c in p['claim_ids']) for p in rendered)
        evidence+=f'| [R{i}] | '+('Verified source for marked facts' if verified else 'Proposed source; support not confirmed')+' |\n'
    evidence+='\n'+'\n'.join('[R'+str(i+1)+'] '+reference_text(loc) for i,loc in enumerate(refs))+'\n'
    annex='\n### Annex: Unverified Research\n\n| Section | Paragraph |\n|---|---|\n'
    annex+=''.join('| '+str(r['section_number'])+' | '+str(r['paragraph_number'])+' |\n' for r in review)
    markdown=title+''.join(sections)+evidence+(annex if review else '')+previous if rendered else before
    # Exact identical inputs are a true no-change; never nest previous history
    # repeatedly just because another reflection pass rendered the same content.
    if input_marker in current_profile_context(before) and '### Annex: Previous Memory' not in before:
        markdown=before
    return replace(candidate,markdown=markdown,fact_ids=tuple(dict.fromkeys(fact_ids))),{
        'schema_version':'pharma_section_enrichment.v1','sections':list(dict.fromkeys(p['section_id'] for p in rendered)),
        'verified_sections':list(dict.fromkeys(p['section_id'] for p in rendered if p['verification_status']=='verified')),
        'added_fact_ids':list(dict.fromkeys(fact_ids)),'omitted_facts':omitted,
        'baseline_preserved':not before or before == markdown,
        'prior_memory_carried_paragraph_count':len(carried), 'history_authority':'core_dynamic_skill',
        'paragraphs':rendered,'references':[{'citation':'[R'+str(i+1)+']','locator':loc} for i,loc in enumerate(refs)],
        'unverified_research':review,'narrative_issues':list(issues),'scope':'company_profile_with_explicit_verification',
        'human_approval_required':False}
