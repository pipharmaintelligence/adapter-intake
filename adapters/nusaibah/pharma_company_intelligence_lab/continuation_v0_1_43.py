"""Keep incomplete work local and render one compact document-quality annex."""
from hashlib import sha256
import json,re
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .methodology_contract import MethodologyPlan, ResearchFocus
    from .agent_chunks_v0_1_33 import paragraph_units
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy
    from methodology_contract import MethodologyPlan, ResearchFocus
    from agent_chunks_v0_1_33 import paragraph_units


def partial_plan(company_id, chunks):
    """Assemble only individually validated chunks; invent no missing questions."""
    focuses=[]
    for role in legacy.RESEARCH_ROLES:
        rows=[c for c in chunks if c['research_role']==role]
        if not rows:continue
        def texts(field):return tuple(dict.fromkeys(t for c in rows for t in c[field]))
        priority=max((c['priority'] for c in rows),key=lambda p:legacy._PRIORITY_RANK[p])
        focuses.append(ResearchFocus(role,priority,tuple(c['section_id'] for c in rows),
                                     texts('questions'),texts('freshness_focus'),texts('evidence_focus')))
    return MethodologyPlan(company_id,tuple(focuses),(),(),())


def allow_incomplete_continuation(publication):
    """Recognize a proven pre-write skip, never a failed or ambiguous mutation."""
    if publication.get('publication_complete'):return publication
    receipts=[publication.get(name) for name in ('memory','methodology')]
    allowed={'enrichment_unresolved','enrichment_validation_incomplete'}
    if all(isinstance(r,dict) and r.get('status')=='withheld' and r.get('reason') in allowed
           and not r.get('change_id') and not r.get('upload_id') and not r.get('operation_id')
           for r in receipts):
        publication.update(continuation_allowed=True,required_mutation=False)
        for receipt in receipts:receipt.update(write_attempted=False)
    return publication


def review_annex(state, coordinator):
    """One table of short codes and source numbers; no quotes, prompts or stacks."""
    progress=state.get('progress',{});result=state['result'];rows=[];refs=[]
    snapshots=progress.get('retrieved_source_snapshot') or result.get('retrieved_source_snapshot') or {}
    units=snapshots.get('source_units',[])
    locations={}
    for unit in units:
        locator=unit.get('locator')
        if not isinstance(locator,str):continue
        if locator not in refs:refs.append(locator)
        for number,paragraph in enumerate(paragraph_units(unit.get('text','')),1):
            locations[(locator,paragraph['source_start'],paragraph['source_end'])]=(number,refs.index(locator)+1)
    def add(section,paragraph,issue,citation):
        labels={'needs_enrichment':'Evidence insufficient','unresolved':'Review unresolved',
                'planner_unresolved':'Plan unavailable','invalid_schema':'Invalid response schema',
                'phase_call_budget_reserved_for_downstream':'Call budget reached',
                'execution_budget_reserved_for_consolidation':'Time budget reached',
                'no_supported_enrichment_after_section_critic':'No supported enrichment'}
        issue=labels.get(issue,issue)
        row={'section':section or 'Not located','paragraph':paragraph,'issue':issue,'citation':citation}
        for previous in rows:
            if all(previous[k]==row[k] for k in ('section','paragraph','issue')):
                if citation!='—' and citation not in previous['citation'].split(', '):
                    previous['citation']=citation if previous['citation']=='—' else previous['citation']+', '+citation
                return
        if row not in rows and len(rows)<64:rows.append(row)
    def locate(section,diagnostic,claims=()):
        found=False
        for claim in claims:
            if section and claim.get('section_id')!=section:continue
            if claim.get('native_grounding'):
                for locator in claim.get('citation_locators',[]):
                    if locator in refs:
                        add(section or claim.get('section_id'),None,diagnostic,f'[{refs.index(locator)+1}]');found=True
            for span in claim.get('source_spans',[]):
                for (locator,start,end),(number,ref) in locations.items():
                    if span.get('locator')==locator and start<=span.get('start',-1)<end:
                        add(section or claim.get('section_id'),number,diagnostic,f'[{ref}]');found=True
        if not found:add(section,None,diagnostic,'—')
    joined=state.get('joined_research') or progress.get('joined_research',{})
    claims=joined.get('claims',[])+joined.get('withheld_claims',[])
    for claim in claims:
        if claim.get('native_grounding'):
            for locator in claim.get('citation_locators',[]):
                if locator not in refs:refs.append(locator)
    critic=state.get('critic') or progress.get('critic',{})
    for outcome in critic.get('section_outcomes',[]):
        if outcome.get('status')!='validated':
            issue=(outcome.get('diagnostic') or {}).get('rule') or outcome.get('reason') or outcome.get('status','needs_review')
            locate(outcome.get('section_id'),issue,claims)
    for item in (result.get('issues_annex') or {}).get('items',[]):
        if rows and item.get('rule')=='no_supported_enrichment_after_section_critic':continue
        sections=item.get('section_ids') or [None]
        for section in sections:
            if section is None and item.get('rule') not in {'no_supported_enrichment_after_section_critic','no_usable_research_evidence'}:
                add(None,None,item.get('rule','needs_review'),'—')
            else:locate(section,item.get('rule','needs_review'),claims)
    for item in progress.get('planner_diagnostics',[]):
        locate(item.get('section_id'),item['diagnostic'].get('rule','planner_unresolved'))
    for claim in joined.get('withheld_claims',[]):
        locate(claim.get('section_id'),claim.get('issue_code','Claim needs review'),[claim])
    for item in result.get('chunk_phase_issues',[]):
        locate(item.get('section_id'),item.get('rule','Presentation unavailable'))
    for item in result.get('source_retrieval',[]):
        if item.get('status') in {'unavailable','source_admission_incomplete'}:
            locate(None,item.get('reason','Optional source unavailable'))
    for item in result.get('section_enrichment',{}).get('omitted_facts',[]):
        claim=next((c for c in claims if c['claim_id']==item['claim_id']),{})
        locate(claim.get('section_id'),item['reason'],[claim])
    for entry in coordinator.proof().get('outcomes',[]):
        diagnostic=entry.get('diagnostic')
        if diagnostic and entry.get('company_id')==state['company_id']:
            sections=entry.get('section_ids') or [None]
            found=False
            for location in entry.get('source_locations',[]):
                for (locator,start,end),(number,ref) in locations.items():
                    if locator==location.get('locator') and start==location.get('source_start'):
                        for section in sections:add(section,number,diagnostic.get('rule','chunk_unresolved'),f'[{ref}]')
                        found=True
            # A hash is not a paragraph number; unknown location stays explicit.
            if not found:
                for section in sections:add(section,None,diagnostic.get('rule','chunk_unresolved'),'—')
    if not rows:return None
    # References are locators only. Existing source/citation inventories own text.
    return {'schema_version':'pharma_review_issues.v1','title':'Annex: Need Review',
            'columns':['Section / subsection','Paragraph','Issue','Ref.'],
            'items':rows,'issue_count':len(rows),'references':
            [{'citation':f'[{i+1}]','locator':locator} for i,locator in enumerate(refs)],
            'canonical_candidates_withheld':not (state.get('publication') or {}).get('publication_complete',False)}


def finalize_profiles(states,coordinator):
    """Use short references and one evidence register, including local fallbacks."""
    from dataclasses import replace
    try:
        from .profile_research_v0_1_43 import MAX_PROFILE_CHARS as MAX_MEMORY_CANDIDATE_CHARS
        from .section_enrichment_v0_1_28 import literal
        from .profile_rendering_v0_1_43 import reference_text
    except ImportError:
        from profile_research_v0_1_43 import MAX_PROFILE_CHARS as MAX_MEMORY_CANDIDATE_CHARS
        from section_enrichment_v0_1_28 import literal
        from profile_rendering_v0_1_43 import reference_text
    for state in states:
        candidate=state.get('memory_candidate')
        if candidate is None:continue
        enrichment=state['result'].get('section_enrichment',{})
        annex=review_annex(state,coordinator) or {'items':[],'references':[]}
        refs=list(enrichment.get('references',[])); by_locator={r['locator']:r['citation'] for r in refs}
        previous_refs={r['citation']:r['locator'] for r in annex['references']}
        rows=[]
        for row in annex['items']:
            labels=[]
            for old in re.findall(r'\[\d+\]',row['citation']):
                locator=previous_refs[old]
                if locator not in by_locator:
                    label='[R'+str(len(refs)+1)+']';by_locator[locator]=label
                    refs.append({'citation':label,'locator':locator})
                labels.append(by_locator[locator])
            rows.append({**row,'citation':', '.join(dict.fromkeys(labels)) or '—'})
        for issue in enrichment.get('narrative_issues',[]):
            row={'section':issue['section']+('/'+issue['subsection'] if issue.get('subsection') else ''),
                'paragraph':issue.get('paragraph'),'issue':issue['issue'],'citation':'—'}
            if row not in rows:rows.append(row)
        # Mark actual gaps explicitly even when no critic returned a verdict.
        for sid in ('company_profile','product_portfolio_intelligence','markets_commercial_signals','regulatory_clinical_risk_signals'):
            if sid not in enrichment.get('sections',[]) and not any(r['section']==sid for r in rows):
                rows.append({'section':sid,'paragraph':None,'issue':'No new supported evidence','citation':'—'})
        table='\n\n### Annex: Need Review\n\n| Section / subsection | Paragraph | Issue | Ref. |\n|---|---|---|---|\n'
        cell=lambda value:literal(str(value)).replace('|','\\|')
        added=[];extra_refs=refs[len(enrichment.get('references',[])):]
        extra='\n'.join(r['citation']+' '+reference_text(r['locator']) for r in extra_refs)
        for row in rows:
            line='| '+' | '.join(cell(row[k] if row[k] is not None else '—') for k in ('section','paragraph','issue','citation'))+' |\n'
            if len(candidate.markdown+table+line+extra)+160>MAX_MEMORY_CANDIDATE_CHARS:continue
            table+=line;added.append(row)
        if len(added)<len(rows):table+='\nAdditional review items: '+str(len(rows)-len(added))+'. See the retained dossier.\n'
        if candidate.fact_ids or enrichment.get('unverified_research'):
            # Insert before previous memory so the current profile and annexes read first.
            marker='\n\n### Annex: Previous Memory'
            front,separator,prior=candidate.markdown.partition(marker)
            text=front+('\n'+extra if extra else '')+(table if rows else '')+separator+prior
            if len(text)<=MAX_MEMORY_CANDIDATE_CHARS:
                candidate=replace(candidate,markdown=text)
                state['memory_candidate']=candidate
        state['result']['published_review_annex_item_count']=len(added) if candidate.fact_ids or enrichment.get('unverified_research') else 0
        state['result']['issues_annex']={'schema_version':'pharma_review_issues.v1','title':'Annex: Need Review',
            'columns':['Section / subsection','Paragraph','Issue','Ref.'],'items':rows,'references':refs,
            'issue_count':len(rows),'canonical_candidates_withheld':False}
        state['result']['profile_document']={'format':'markdown','text':candidate.markdown,
            'paragraph_support':enrichment.get('paragraphs',[])}
        state['result']['profile_section_coverage']=[
            {'section_id':sid,'status':'supported_content' if sid in enrichment.get('sections',[]) else 'evidence_gap'}
            for sid in ('company_profile','product_portfolio_intelligence','markets_commercial_signals','regulatory_clinical_risk_signals')]
        state['result']['required_section_coverage_count']=sum(
            row['status']=='supported_content' for row in state['result']['profile_section_coverage'])
        state['result']['profile_coverage_complete']=(state['result']['required_section_coverage_count']==4
            and not enrichment.get('omitted_facts'))
        state['result']['verification_complete']=not enrichment.get('unverified_research') and not state['result'].get('research_incomplete',True)
        state['result']['verified_section_coverage_count']=len(enrichment.get('verified_sections',[]))
        state['candidate_changed']=candidate.markdown.strip()!=(state.get('before_target_text') or '').strip()


def admit_retention(states, coordinator, forwarded, maximum=440*1024):
    """Compact only an oversize company's retained row before any write."""
    for state in states:
        state['result']['agent_input_preflight']=coordinator.proof()
        annex=review_annex(state,coordinator)
        if annex is not None and 'issues_annex' not in state['result']:state['result']['issues_annex']=annex
    extras={'research_response_observations':forwarded.observations,
            'agent_invocation_response_issues':forwarded.invocation_issues}
    def encode(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    def size():return len(encode({'company_results':[s['result'] for s in states],**extras}))
    for state in sorted(states,key=lambda s:len(encode(s['result'])),reverse=True):
        if size()<=maximum:break
        old=encode(state['result']);previous=state['result']
        state.update(incomplete_schema_preview=True,no_supported_enrichment=False)
        state['result']={'company_id':state['company_id'],'company_name':previous.get('company_name'),
            'status':'completed','review_outcome':'incomplete','research_incomplete':True,
            'agent_schema_incomplete':False,'accepted_claim_count':0,
            'retention_admission':{'status':'incomplete','publication_withheld':True,
                'original_size_bytes':len(old),'original_sha256':sha256(old).hexdigest(),
                'candidate_truncated':False,'business_body_retained':False},
            'issues_annex':{'items':[{'rule':'retention_budget_exceeded_publication_withheld',
                                     'section_ids':[]}]}}
        state['result']['issues_annex']=review_annex(state,coordinator)
    if size()>maximum:
        # Diagnostic metadata can be bounded without ever publishing a truncated candidate.
        for state in states:
            state['result'].pop('agent_input_preflight',None)
        forwarded.observations.clear();forwarded.invocation_issues.clear()
    if size()>maximum:raise ValueError('retention_metadata_budget_invalid')
