"""Paragraph/subsection analysis and synthesis with typed consolidation."""
from copy import deepcopy
from collections import deque
from dataclasses import replace
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .agent_chunks_v0_1_33 import unique,paragraph_units
    from .memory_contract import MemoryCandidate,MEMORY_TARGET_SECTION
    from .candidate_validation_v0_1_21 import require_candidate_fact_ids,CandidateContractError
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy
    from agent_chunks_v0_1_33 import unique,paragraph_units
    from memory_contract import MemoryCandidate,MEMORY_TARGET_SECTION
    from candidate_validation_v0_1_21 import require_candidate_fact_ids,CandidateContractError

def evidence_units(inputs,claims):
    sources={u['locator']:u['text'] for u in inputs.units};result=[]
    for claim in claims:
        scope=claim['section_id']+'|'+str(claim.get('subsection_id') or 'profile')
        for span in claim.get('source_spans',[]):
            text=sources.get(span['locator'],'')
            paragraph=next((p for p in paragraph_units(text)
                if p['source_start']<=span['start'] and span['end']<=p['source_end']),None)
            if paragraph is not None:
                scope=span['locator']+'|'+(paragraph['subsection'] or paragraph['unit_id']);break
        result.append({'section_id':claim['section_id'],'subsection':scope,
                       'unit_id':claim['claim_id'],'claim':claim})
    return result

def scope_research(joined,claims):
    sections={c['section_id'] for c in claims}
    return {**joined,'claims':claims,'sections':[s for s in joined['sections'] if s['section_id'] in sections]}

class ScopedPlan:
    def __init__(self,plan,sections):self.plan=plan;self.sections=sections
    def __getattr__(self,name):return getattr(self.plan,name)
    def to_agent_input(self):
        value=deepcopy(self.plan.to_agent_input())
        # Keep only the current piece's role focus, not all companies/roles.
        owners={r for r,ids in legacy.RESEARCH_ROLE_SECTIONS.items() if set(ids)&set(self.sections)}
        focus=value.get('research_focus')
        if isinstance(focus,dict):value['research_focus']={r:p for r,p in focus.items() if r in owners}
        if isinstance(focus,list):value['research_focus']=[p for p in focus if p.get('role') in owners]
        return value

def packets_for_evidence(inputs,role,joined,base):
    units=evidence_units(inputs,joined['claims'])
    def attach(payload,rows):
        claims=[r['claim'] for r in rows]
        payload['_piece_claims']=claims
        payload['_piece_section_ids']=unique([c['section_id'] for c in claims])
        # Measurement must cover the same input that the role function builds.
        payload['research_evidence']=legacy._research_for_downstream(scope_research(joined,claims))
        owners={r for r,ids in legacy.RESEARCH_ROLE_SECTIONS.items() if set(ids)&set(payload['_piece_section_ids'])}
        payload['methodology_plan']['research_focus']=[r for r in payload['methodology_plan'].get('research_focus',[]) if r['role'] in owners]
        if role==legacy.SYNTHESIS_ROLE:
            payload['strategic_analysis']=scope_analysis(payload['strategic_analysis'],payload['_piece_section_ids'])
            payload['critic_findings']=scope_critic(payload['critic_findings'],payload['_piece_section_ids'],{c['claim_id'] for c in claims})
            payload['allowed_memory_fact_ids']=[c['claim_id'] for c in claims if c.get('verification_status')=='verified']
            payload['allowed_narrative_claim_ids']=[c['claim_id'] for c in claims]
            payload['claim_verification']={c['claim_id']:c.get('verification_status','unverified') for c in claims}
        result=inputs.prepare_input(role,payload)
        result['_piece_claims']=claims;result['_piece_section_ids']=payload['_piece_section_ids']
        return result
    return inputs.coordinator.partition(role,base,units,attach)

def run_strategy(inputs,*,company_id,company_name_value,baseline,memory_text,joined_research,methodology_plan):
    role=legacy.STRATEGIC_ROLE
    base={'company_id':company_id,'company_name':company_name_value,'governed_company_baseline':baseline,
        'existing_company_memory':memory_text,'methodology_plan':methodology_plan.to_agent_input(),
        'response_contract':legacy.response_contract_for_role(role,company_id=company_id)}
    packets,omitted=packets_for_evidence(inputs,role,joined_research,base)
    def work(packet):
        claims=packet['_piece_claims'];sections=packet['_piece_section_ids']
        scoped=scope_research(joined_research,claims)
        result=legacy._run_strategic(ChunkInputOverlay(inputs,packet),company_id=company_id,
            company_name_value=company_name_value,baseline=baseline,memory_text=memory_text,
            joined_research=scoped,methodology_plan=ScopedPlan(methodology_plan,sections))
        return {'result':result,'section_ids':sections}
    outcomes=inputs.coordinator.parallel(packets,work)
    chunks=[r['value'] for r in outcomes if r['status']=='completed']
    values=[r['result'] for r in chunks]
    for r in outcomes:
        if r['status']=='unresolved':inputs.phase_issues.append(r['diagnostic'])
    if omitted:inputs.phase_issues.append(legacy.evidence_diagnostic(role=role,stage='input_preflight',
        field='paragraphs',rule='indivisible_paragraph_or_subsection_exceeds_budget'))
    return {'schema_version':legacy.STRATEGIC_SCHEMA_VERSION,'company_id':company_id,'role':role,'status':'completed',
        **{k:unique([v for row in values for v in row[k]]) for k in
            ('implications','opportunities','risks','internal_public_deltas','uncertainties')},
        'aggregation_kind':'validated_chunk_results','chunk_results':chunks,'chunk_count':len(packets),
        'unresolved_chunk_count':len(outcomes)-len(values)+len(omitted)}

class ChunkInputOverlay:
    """Preserve runtime helpers while attaching the measured execution piece."""
    def __init__(self,inputs,packet):self._inputs=inputs;self.packet=packet
    def __getattr__(self,name):return getattr(self._inputs,name)
    def invoke_agent(self,role,*,input,on_error='raise'):
        # Use the exact focused, measured packet. Rebuilding the legacy full
        # company input here used to reintroduce excluded memory and evidence.
        forwarded={k:v for k,v in self.packet.items() if not k.startswith('_piece_')}
        return self._inputs.invoke_agent(role,input=forwarded,on_error=on_error)

def scope_analysis(strategic,sections):
    chunks=strategic.get('chunk_results')
    if not isinstance(chunks,list):return strategic
    selected=[r['result'] for r in chunks if set(r['section_ids'])&set(sections)]
    return {k:unique([v for row in selected for v in row[k]]) for k in
        ('implications','opportunities','risks','internal_public_deltas','uncertainties')}

def scope_critic(critic,sections,claim_ids):
    value=deepcopy(critic)
    value['section_outcomes']=[o for o in value.get('section_outcomes',[]) if o['section_id'] in sections]
    for field in ('unsupported_claim_ids','stale_claim_ids'):
        value[field]=[c for c in value[field] if c in claim_ids]
    value['missing_section_ids']=[s for s in value['missing_section_ids'] if s in sections]
    return value


def packets_for_synthesis(inputs, joined, base):
    """Measure whole claim statements for one editorial section at a time.

    The full critic dossier, source inventory, global plan and prior memory
    remain in the result. They are not fresh material for the prose writer.
    Full claim meanings/qualifiers and applicable learned guidance are kept.
    """
    try:
        from .profile_research_v0_1_45 import BUSINESS_SECTIONS
    except ImportError:
        from profile_research_v0_1_45 import BUSINESS_SECTIONS
    units = []
    for sid in BUSINESS_SECTIONS:
        own = [c for c in joined['claims'] if c['section_id'] == sid]
        # Keep explicit subsections together. Unclassified claims form a
        # section-focused unit; the writer assigns canonical subsections.
        groups = {}
        for claim in own:
            groups.setdefault(claim.get('subsection_id'), []).append(claim)
        for subsection, claims in groups.items():
            size = 0; part = 1
            for claim in claims:
                if size and size + len(claim['statement']) > 5000:
                    part += 1; size = 0
                units.append({'section_id':sid, 'subsection':str(subsection)+':'+str(part),
                              'unit_id':claim['claim_id'], 'claim':claim})
                size += len(claim['statement'])

    def attach(payload, rows):
        claims = [r['claim'] for r in rows]
        sections = unique([c['section_id'] for c in claims])
        # Copy claims intact: dates, legal entity/rights, negative findings,
        # uncertainty and source references must survive editorial packing.
        payload['research_evidence'] = {'claims':deepcopy(claims)}
        payload['packing_scope'] = {'section_ids':sections, 'editorial_only':True}
        payload['allowed_narrative_claim_ids'] = [c['claim_id'] for c in claims]
        payload['allowed_memory_fact_ids'] = [c['claim_id'] for c in claims if c.get('verification_status') == 'verified']
        payload['claim_verification'] = {c['claim_id']:c.get('verification_status','unverified') for c in claims}
        payload['editorial_scope'] = legacy._section_requests(tuple(sections))
        value = inputs.prepare_input(legacy.SYNTHESIS_ROLE, payload)
        value['_piece_claims'] = claims
        value['_piece_section_ids'] = sections
        return value

    focused = {k:deepcopy(base[k]) for k in ('company_id','company_name','methodology_packet',
        'canonical_sections','narrative_instruction','response_contract')}
    packets, omitted = inputs.coordinator.partition(legacy.SYNTHESIS_ROLE, focused, units, attach)
    # Each section gets its first packet before any section gets overflow.
    # Do not raise the six-call role allowance or the global execution limits.
    queues = {sid:deque(p for p in packets if p['_piece_section_ids'] == [sid]) for sid in BUSINESS_SECTIONS}
    ordered = []
    while any(queues.values()):
        for queue in queues.values():
            if queue:
                ordered.append(queue.popleft())
    return ordered, omitted

def run_synthesis(inputs,*,company_id,company_name_value,baseline,memory_text,joined_research,
                  strategic,critic,methodology,methodology_plan,profile_research=()):
    verified_joined=joined_research
    joined_research={**joined_research,'claims':list(profile_research) or joined_research['claims']}
    role=legacy.SYNTHESIS_ROLE
    base={'company_id':company_id,'company_name':company_name_value,'governed_company_baseline':baseline,
        'existing_company_memory':memory_text,'methodology_plan':methodology_plan.to_agent_input(),
        'methodology_packet':{'memory_rules':list(methodology.planner_packet.memory_rules)},
        'strategic_analysis':strategic,'critic_findings':critic,
        'canonical_sections':legacy._section_requests(tuple(s.section_id for s in legacy.CANONICAL_SECTIONS)),
        'allowed_memory_fact_ids':[c['claim_id'] for c in joined_research['claims']],
        'narrative_instruction':narrative_instruction(),
        'response_contract':{**legacy.response_contract_for_role(role,company_id=company_id),
            'dossier_schema_version':legacy.DOSSIER_SCHEMA_VERSION}}
    packets,omitted=packets_for_synthesis(inputs,joined_research,base)
    def work(packet):
        claims=packet['_piece_claims'];sections=packet['_piece_section_ids']
        scoped=scope_research(joined_research,claims)
        try:
            from .profile_narrative_v0_1_46 import synthesize_packet
        except ImportError:
            from profile_narrative_v0_1_46 import synthesize_packet
        result,candidate=synthesize_packet(inputs,packet,company_id=company_id)
        try:require_candidate_fact_ids(fact_ids=candidate.fact_ids,accepted_claim_ids={c['claim_id'] for c in claims if c.get('verification_status')=='verified'})
        except CandidateContractError as error:raise legacy.UnresolvedAgentResponse(error.proof_failure_detail) from None
        return {'result':result,'candidate':candidate,'section_ids':sections}
    outcomes=inputs.coordinator.parallel(packets,work)
    values=[r['value'] for r in outcomes if r['status']=='completed']
    for r in outcomes:
        if r['status']=='unresolved':inputs.phase_issues.append(r['diagnostic'])
    if omitted:inputs.phase_issues.append(legacy.evidence_diagnostic(role=role,stage='input_preflight',
        field='paragraphs',rule='indivisible_paragraph_or_subsection_exceeds_budget'))
    # Synthesis is presentation assistance; already reviewed facts survive its failure.
    sections=[]
    for spec in legacy.CANONICAL_SECTIONS:
        pieces=[s for row in values if spec.section_id in row['section_ids']
                for s in row['result']['sections'] if s['section_id']==spec.section_id]
        def text(field,subsection=None):
            strings=[s[field] for s in pieces] if subsection is None else [p['content'] for s in pieces
                for p in s['subsections'] if p['subsection_id']==subsection]
            return '\n\n'.join(unique([s for s in strings if s.strip()])) or ''
        sections.append({'section_id':spec.section_id,'content':text('content') if not spec.subsections else '',
            'subsections':[{'subsection_id':s.subsection_id,'content':text('content',s.subsection_id)} for s in spec.subsections]})
    try:
        from .profile_narrative_v0_1_46 import review_paragraphs
    except ImportError:
        from profile_narrative_v0_1_46 import review_paragraphs
    paragraphs, narrative_issues = review_paragraphs(inputs, company_id=company_id,
        company_name=company_name_value, sections=sections, claims=joined_research['claims'])
    fact_ids=tuple(c['claim_id'] for c in verified_joined['claims'])
    # This is explicit adapter consolidation, not a fabricated Agent result.
    # The readable-profile renderer replaces this compatibility staging text with
    # qualified admitted facts and the preserved baseline before publication.
    candidate=MemoryCandidate(company_id,MEMORY_TARGET_SECTION,
        'Validated source-backed chunk findings are assembled below.',fact_ids)
    return {'schema_version':legacy.SYNTHESIS_SCHEMA_VERSION,'company_id':company_id,'role':role,'status':'completed',
        'sections':sections,'residual_uncertainties':unique([v for row in values for v in row['result']['residual_uncertainties']]),
        'memory_candidate':{'company_id':company_id,'target_section':MEMORY_TARGET_SECTION,
                            'markdown':candidate.markdown,'fact_ids':list(fact_ids)},
        'publication_paragraphs':paragraphs,'narrative_issues':narrative_issues,
        'aggregation_kind':'critic_reviewed_paragraphs_with_claim_fallback','chunk_count':len(packets),
        'unresolved_chunk_count':len(outcomes)-len(values)+len(omitted)},candidate


def narrative_instruction():
    try:
        from .profile_narrative_v0_1_46 import INSTRUCTION
    except ImportError:
        from profile_narrative_v0_1_46 import INSTRUCTION
    return INSTRUCTION
