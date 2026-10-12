"""Critique each research section independently; failed sections do not erase siblings."""
from copy import deepcopy
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy

def run_section_critics(inputs,*,company_id,company_name_value,joined_research,strategic,methodology,methodology_plan):
    section_ids=[s for role in legacy.RESEARCH_ROLES for s in legacy.RESEARCH_ROLE_SECTIONS[role]]
    results=[];outcomes=[]
    for section_id in section_ids:
        evidence=deepcopy(legacy._research_for_downstream(joined_research))
        evidence['claims']=[c for c in evidence['claims'] if c['section_id']==section_id]
        evidence['sections']=[s for s in evidence['sections'] if s['section_id']==section_id]
        owner=next(role for role in legacy.RESEARCH_ROLES if section_id in legacy.RESEARCH_ROLE_SECTIONS[role])
        evidence['no_evidence_research_roles']=[] if evidence['claims'] else [owner]
        evidence['unresolved_research_responses']=[r for r in evidence['unresolved_research_responses'] if r.get('role')==owner]
        evidence['citation_count_by_role']={owner:evidence['citation_count_by_role'].get(owner,0)}
        locators={span['locator'] for c in evidence['claims'] for span in c.get('source_spans',[])}
        evidence['citation_sources']=[c for c in evidence['citation_sources'] if c.get('locator') in locators]
        # The immutable planner catalogs role-scoped and cross-cutting requirements;
        # it does not invent a section_id for a broad role question.
        requirements=[{**r,'reviewed_section_id':section_id} for r in methodology_plan.requirement_catalog()
                      if r['role'] in (owner,None)]
        ids=tuple(r['requirement_id'] for r in requirements)
        contract=legacy.response_contract_for_role(legacy.CRITIC_ROLE,company_id=company_id,planner_requirement_ids=ids)
        try:
            envelope=inputs.invoke_agent(legacy.CRITIC_ROLE,input={
                'company_id':company_id,'company_name':company_name_value,
                'methodology_packet':{'evidence_rules':list(methodology.planner_packet.evidence_rules)},
                'planner_requirements':requirements,'reviewed_section_ids':[section_id],
                'research_evidence':evidence,
                'enrichment_instruction':'Critique only this section and its declared subsections. These checks improve enrichment; they are not human approval. Preserve exact source qualifications. Report unsupported/stale claim IDs explicitly; do not invent evidence to fill a gap.',
                'response_contract':contract},on_error='raise')
            result=legacy._validated_agent_response(inputs,envelope,role=legacy.CRITIC_ROLE,company_id=company_id,
                contract=contract,validator=lambda v:legacy.validate_critic_payload(v,company_id=company_id,
                    known_claim_ids={c['claim_id'] for c in evidence['claims']},known_section_ids={section_id},
                    known_plan_requirement_ids=set(ids)))
        except (legacy.UnresolvedAgentResponse,legacy.AgentContractValidationError) as error:
            if isinstance(error,legacy.AgentContractValidationError) and not legacy.recoverable_quality(error):raise
            detail=error.diagnostic if isinstance(error,legacy.UnresolvedAgentResponse) else error.proof_failure_detail
            outcomes.append({'section_id':section_id,'status':'unresolved','diagnostic':detail});continue
        passed=(result['recommendation']=='pass' and result['citation_coverage']['status']=='sufficient'
                and not result['unsupported_claim_ids'] and not result['stale_claim_ids']
                and not result['missing_section_ids'] and not result['contradiction_items']
                and not any(r['disposition']=='unsatisfied' for r in result['unmet_plan_requirements']))
        outcomes.append({'section_id':section_id,'status':'validated' if passed else 'needs_enrichment',
                         'recommendation':result['recommendation']})
        results.append(result)
    def merged(field):
        values=[]
        for result in results:
            for value in result[field]:
                if value not in values:values.append(value)
        return values
    complete=all(o['status']=='validated' for o in outcomes)
    critic={'schema_version':legacy.CRITIC_SCHEMA_VERSION,'company_id':company_id,'role':legacy.CRITIC_ROLE,'status':'completed',
        'unsupported_claim_ids':merged('unsupported_claim_ids'),'contradiction_items':merged('contradiction_items'),
        'stale_claim_ids':merged('stale_claim_ids'),'missing_section_ids':merged('missing_section_ids'),
        'unmet_plan_requirements':merged('unmet_plan_requirements'),
        'citation_coverage':{'status':'sufficient' if complete else 'insufficient','notes':'See individual section enrichment checks.'},
        'residual_uncertainties':merged('residual_uncertainties'),'recommendation':'pass' if complete else 'fail',
        'section_outcomes':outcomes}
    return critic

def select_validated_sections(joined,critic):
    valid={o['section_id'] for o in critic['section_outcomes'] if o['status']=='validated'}
    rejected={c for key in ('unsupported_claim_ids','stale_claim_ids') for c in critic[key]}
    retained=[];withheld=list(joined.get('withheld_claims',[]))
    for claim in joined['claims']:
        if claim['section_id'] in valid and claim['claim_id'] not in rejected:retained.append(claim)
        else:withheld.append({**claim,'issue_code':'section_critic_enrichment_unresolved','accepted':False})
    if not retained:
        raise legacy.UnresolvedAgentResponse(legacy.evidence_diagnostic(role=legacy.CRITIC_ROLE,
            stage='pre_synthesis_quality',rule='no_supported_enrichment_after_section_critic',field='claims'))
    return {**joined,'claims':retained,'withheld_claims':withheld,
            'withheld_section_ids':list(dict.fromkeys(list(joined.get('withheld_section_ids',[]))+[
                o['section_id'] for o in critic['section_outcomes'] if o['status']!='validated']))}
