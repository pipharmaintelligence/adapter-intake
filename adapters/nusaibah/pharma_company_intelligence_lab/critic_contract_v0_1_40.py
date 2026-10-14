"""Claim-local enrichment decisions and actionable feedback from the same critic."""
from copy import deepcopy
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .dossier_contract import SECTION_BY_ID
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy
    from dossier_contract import SECTION_BY_ID


def extend_contract(contract, section_id, claim_ids, prior_guidance=()):
    result=deepcopy(contract)
    result['required_fields']=list(dict.fromkeys(result.get('required_fields',[])+['claim_reviews','future_guidance']))
    result['claim_reviews']={'shape':{'claim_id':'one supplied claim ID','decision':'supported | unsupported | needs_review'},
        'required_claim_ids':list(claim_ids),'exactly_one_per_claim':True}
    result['future_guidance']={'maximum_items':4,'shape':{'subsection_id':'a declared subsection ID or null',
        'observation':'specific short deficiency or useful outcome from THIS review',
        'next_action':'concrete research or verification action for a future Agent',
        'success_check':'observable evidence needed to close the gap'},'maximum_text_chars_per_field':400}
    result['enrichment_semantics']=(
        'Evaluate every supplied claim individually. A section can need more research while its supported '
        'claims remain useful. Use needs_review for unresolved attribution, contradiction, or unsupported '
        'entailment; do not reject a whole section because coverage is incomplete. Native grounding is '
        'provider evidence, not a fetched webpage quote; assess the exact company, date, source relevance '
        'and claim semantics. A supplied historical baseline can support only historical statements. '
        'Identify affected claim IDs in the dispositions for every contradiction. Produce actionable '
        'future_guidance from actual findings, including failed/incomplete sections; return [] when '
        'nothing useful was learned. Do not write a methodology essay, repeat rules, or invent facts.')
    result['allowed_subsection_ids']=[s.subsection_id for s in SECTION_BY_ID[section_id].subsections]
    result['resolved_guidance_ids']={'type':'array','optional':True,
        'allowed_values':[g['guidance_id'] for g in prior_guidance],
        'instruction':'List a prior guidance ID only when current supported evidence meets its success_check. Otherwise keep it open.'}
    return result


def validate_critic(value, *, section_id, prior_guidance=(), **kwargs):
    result=legacy.validate_critic_payload(value,**kwargs)
    known=kwargs['known_claim_ids']
    reviews=value.get('claim_reviews')
    if not isinstance(reviews,list) or len(reviews)!=len(known):
        raise ValueError('claim_reviews must dispose every supplied claim')
    decisions={}
    for row in reviews:
        if not isinstance(row,dict) or set(row)!={'claim_id','decision'}:
            raise ValueError('claim_review_shape_invalid')
        if row['claim_id'] not in known or row['claim_id'] in decisions or row['decision'] not in {'supported','unsupported','needs_review'}:
            raise ValueError('claim_review_disposition_invalid')
        decisions[row['claim_id']]=row['decision']
    rejected={c for c,d in decisions.items() if d!='supported'}|set(result['unsupported_claim_ids'])|set(result['stale_claim_ids'])
    if result['contradiction_items'] and not rejected:
        raise ValueError('contradiction_requires_affected_claim_disposition')
    feedback=value.get('future_guidance')
    if not isinstance(feedback,list) or len(feedback)>4:
        raise ValueError('future_guidance_must_be_bounded_list')
    allowed={s.subsection_id for s in SECTION_BY_ID[section_id].subsections}
    guidance=[]
    for row in feedback:
        if not isinstance(row,dict) or set(row)!={'subsection_id','observation','next_action','success_check'}:
            raise ValueError('future_guidance_shape_invalid')
        if row['subsection_id'] is not None and row['subsection_id'] not in allowed:
            raise ValueError('future_guidance_subsection_invalid')
        if any(not isinstance(row[k],str) or not row[k].strip() or len(row[k])>400 for k in ('observation','next_action','success_check')):
            raise ValueError('future_guidance_text_invalid')
        guidance.append({'section_id':section_id,**row,'origin':'section_critic'})
    resolved=value.get('resolved_guidance_ids',[])
    allowed_guidance={g['guidance_id'] for g in prior_guidance}
    if not isinstance(resolved,list) or len(resolved)>16 or any(not isinstance(g,str) or g not in allowed_guidance for g in resolved):
        raise ValueError('resolved_guidance_ids_invalid')
    if resolved and not any(d=='supported' and c not in rejected for c,d in decisions.items()):
        raise ValueError('resolved_guidance_requires_current_supported_evidence')
    return {**result,'rejected_claim_ids':sorted(rejected),'future_guidance':guidance,'resolved_guidance_ids':list(dict.fromkeys(resolved))}


def select_validated_sections(joined,critic):
    reviewed=set(critic.get('reviewed_claim_ids',[]))
    rejected=set(critic.get('rejected_claim_ids',[]))
    retained=[]; withheld=list(joined.get('withheld_claims',[]))
    for claim in joined['claims']:
        if claim['claim_id'] in reviewed-rejected:
            retained.append(claim)
        else:
            withheld.append({**claim,'issue_code':'claim_critic_unresolved','accepted':False})
    return {**joined,'claims':retained,'withheld_claims':withheld,
        'withheld_section_ids':list(dict.fromkeys(list(joined.get('withheld_section_ids',[]))+
            [c['section_id'] for c in withheld]))}
