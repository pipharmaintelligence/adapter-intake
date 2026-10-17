"""Losslessly batch scoped reviews and retain every original section validator."""
from copy import deepcopy
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .agent_chunks_v0_1_33 import unique
    from .downstream_chunks_v0_1_43 import evidence_units
    from .critic_contract_v0_1_40 import validate_critic, extend_contract, select_validated_sections
    from .methodology_learning_v0_1_42 import read_guidance
    from .critic_response_v0_1_40 import _validated_agent_response
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy
    from agent_chunks_v0_1_33 import unique
    from downstream_chunks_v0_1_43 import evidence_units
    from critic_contract_v0_1_40 import validate_critic, extend_contract, select_validated_sections
    from methodology_learning_v0_1_42 import read_guidance
    from critic_response_v0_1_40 import _validated_agent_response

def merge_requirement_dispositions(values,requirement_ids):
    """Reduce only validated dispositions, preserving stronger negatives and notes."""
    dispositions=[]
    rank={'unresolved_evidence':0,'unsatisfied':1}
    for requirement_id in requirement_ids:
        rows=[d for row in values for d in row['unmet_plan_requirements'] if d['requirement_id']==requirement_id]
        if rows:
            strongest=max(rows,key=lambda d:rank[d['disposition']])
            dispositions.append({**strongest,'notes':'\n\n'.join(unique([d['notes'] for d in rows]))})
    return dispositions

def run_section_critics(inputs,*,company_id,company_name_value,joined_research,strategic,
                       methodology,methodology_plan,planner_chunks):
    section_ids=[s for role in legacy.RESEARCH_ROLES for s in legacy.RESEARCH_ROLE_SECTIONS[role]]
    ready={claim["section_id"] for claim in joined_research["claims"]}
    section_ids.sort(key=lambda section: section not in ready)  # stable: review actual findings before empty sections
    def section_work(section_id):
        prior_guidance=read_guidance(getattr(inputs,'guidance_text',''),[section_id])
        if not any(c['section_id']==section_id for c in planner_chunks):
            return {'static': ({'unsupported_claim_ids':[],'stale_claim_ids':[],'missing_section_ids':[],'contradiction_items':[],'unmet_plan_requirements':[],'residual_uncertainties':[]},{'section_id':section_id,'status':'not_reviewed','reason':'planner_unresolved'})}
        evidence=deepcopy(legacy._research_for_downstream(joined_research))
        evidence['claims']=[c for c in evidence['claims'] if c['section_id']==section_id]
        evidence['sections']=[s for s in evidence['sections'] if s['section_id']==section_id]
        owner=next(r for r in legacy.RESEARCH_ROLES if section_id in legacy.RESEARCH_ROLE_SECTIONS[r])
        evidence['no_evidence_research_roles']=[] if evidence['claims'] else [owner]
        evidence['unresolved_research_responses']=[d for d in evidence['unresolved_research_responses'] if d.get('role')==owner]
        chunk=next(c for c in planner_chunks if c['section_id']==section_id and c['research_role']==owner)
        fields={'question':'questions','freshness_focus':'freshness_focus','evidence_focus':'evidence_focus'}
        requirements=[{**r,'section_id':section_id,'reviewed_section_id':section_id}
            for r in methodology_plan.requirement_catalog() if r['role']==owner and r['kind'] in fields
            and r['text'] in chunk[fields[r['kind']]]]
        ids=tuple(r['requirement_id'] for r in requirements)
        base={'company_id':company_id,'company_name':company_name_value,
            'methodology_packet':{'evidence_rules':list(methodology.planner_packet.evidence_rules)},
            'planner_requirements':requirements,'reviewed_section_ids':[section_id],
            'reviewed_sections':legacy._section_requests((section_id,)),
            'enrichment_instruction':'Critique only this supplied paragraph/subsection piece. Preserve negative verdicts, exact source qualifications and uncertainty. Missing context here is not proof of a global negative. Other pieces are independently checked; do not invent citations, coverage or non-applicability.'}
        def attach(payload,rows):
            claims=[r['claim'] for r in rows];claim_ids=[c['claim_id'] for c in claims]
            contract=legacy.response_contract_for_role(legacy.CRITIC_ROLE,company_id=company_id,planner_requirement_ids=ids)
            payload['response_contract']={**contract,'allowed_section_ids':[section_id],'allowed_claim_ids':claim_ids,
                'allowed_requirement_ids':list(ids),'validation_contract':{**contract['validation_contract'],
                    'missing_section_ids_allowed_values':[section_id],'unsupported_claim_ids_allowed_values':claim_ids,
                    'stale_claim_ids_allowed_values':claim_ids,'unmet_plan_requirement_ids_allowed_values':list(ids)}}
            payload['response_contract']=extend_contract(payload['response_contract'], section_id, claim_ids,prior_guidance)
            payload['research_evidence']={**evidence,'claims':claims}
            result=inputs.prepare_input(legacy.CRITIC_ROLE,payload)
            result['_piece_claims']=claims
            return result
        units=evidence_units(inputs,evidence['claims']) or [{'section_id':section_id,'subsection':'no_evidence',
            'unit_id':section_id,'claim':None}]
        if not evidence['claims']:
            def empty_attach(payload,rows):return attach(payload,[])
            packets,omitted=inputs.coordinator.partition(legacy.CRITIC_ROLE,base,units,empty_attach)
        else:packets,omitted=inputs.coordinator.partition(legacy.CRITIC_ROLE,base,units,attach)
        return {'section_id':section_id,'evidence':evidence,'packets':packets,
                'omitted':omitted,'ids':ids,'prior_guidance':prior_guidance}
    prepared=[section_work(section_id) for section_id in section_ids]
    try:
        from .critic_batches_v0_1_51 import dispatch_reviews
    except ImportError:
        from critic_batches_v0_1_51 import dispatch_reviews
    packets=[{'section_id':item['section_id'],'packet':packet,'ids':item['ids'],
              'prior_guidance':item['prior_guidance']}
             for item in prepared if 'static' not in item for packet in item['packets']]
    answers,batching_proof=dispatch_reviews(inputs,packets,company_id)
    section_values=[];section_outcomes=[]
    for item in prepared:
        if 'static' in item:
            row,outcome=item['static'];section_values.append(row);section_outcomes.append(outcome)
            continue
        section_id=item['section_id'];evidence=item['evidence'];packets=item['packets']
        omitted=item['omitted'];ids=item['ids'];outcomes=answers.get(section_id,[])
        values=[o['value'] for o in outcomes if o['status']=='completed']
        diagnostics=[o['diagnostic'] for o in outcomes if o['status']=='unresolved']
        if omitted:diagnostics.append(legacy.evidence_diagnostic(role=legacy.CRITIC_ROLE,stage='input_preflight',
            field='paragraphs',rule='indivisible_paragraph_or_subsection_exceeds_budget'))
        def merged(field):return unique([v for row in values for v in row[field]])
        # Every negative is retained; this reduction cannot manufacture a pass.
        passed=bool(evidence['claims']) and bool(values) and len(values)==len(packets) and not diagnostics and all(
            row['recommendation']=='pass' and row['citation_coverage']['status']=='sufficient'
            and not row['unsupported_claim_ids'] and not row['stale_claim_ids'] and not row['missing_section_ids']
            and not row['contradiction_items'] and not any(d['disposition']=='unsatisfied' for d in row['unmet_plan_requirements']) for row in values)
        dispositions=merge_requirement_dispositions(values,ids)
        reviewed=unique([c['claim_id'] for packet,outcome in zip(packets,outcomes) if outcome['status']=='completed' for c in packet['_piece_claims']])
        result={'unsupported_claim_ids':merged('unsupported_claim_ids'),'stale_claim_ids':merged('stale_claim_ids'),
            'missing_section_ids':merged('missing_section_ids'),'contradiction_items':merged('contradiction_items'),
            'unmet_plan_requirements':dispositions,'residual_uncertainties':merged('residual_uncertainties'),
            'reviewed_claim_ids':reviewed,'rejected_claim_ids':merged('rejected_claim_ids'),
            'future_guidance':merged('future_guidance'),'resolved_guidance_ids':merged('resolved_guidance_ids')}
        outcome={'section_id':section_id,'status':'validated' if passed else 'unresolved' if diagnostics else 'needs_enrichment',
            'recommendation':'pass' if passed else 'fail','citation_coverage_status':'sufficient' if passed else 'insufficient',
            'unsupported_claim_ids':result['unsupported_claim_ids'],'stale_claim_ids':result['stale_claim_ids'],
            'missing_section_ids':result['missing_section_ids'],'contradiction_count':len(result['contradiction_items']),
            'requirement_dispositions':[{k:d[k] for k in ('requirement_id','disposition')} for d in dispositions],
            'reviewed_claim_ids':reviewed,'rejected_claim_ids':result['rejected_claim_ids'],
            'chunk_count':len(packets),'chunk_diagnostics':diagnostics}
        section_values.append(result);section_outcomes.append(outcome)
    values=section_values;outcomes=section_outcomes
    complete=all(o['status']=='validated' for o in outcomes)
    return {'schema_version':legacy.CRITIC_SCHEMA_VERSION,'company_id':company_id,'role':legacy.CRITIC_ROLE,'status':'completed',
        **{k:unique([v for row in values for v in row[k]]) for k in ('unsupported_claim_ids','stale_claim_ids',
            'missing_section_ids','contradiction_items','unmet_plan_requirements','residual_uncertainties',
            'reviewed_claim_ids','rejected_claim_ids','future_guidance','resolved_guidance_ids')},
        'citation_coverage':{'status':'sufficient' if complete else 'insufficient','notes':'See actual scoped chunk verdicts.'},
        'recommendation':'pass' if complete else 'fail','section_outcomes':outcomes,'review_batching':batching_proof}
