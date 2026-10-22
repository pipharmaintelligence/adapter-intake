"""Role-specific business JSON schemas, not provider settings or authority."""
if __package__:
    from .quality_v0_1_7 import OUTCOMES
    from .contracts_v0_1_7 import REASON_CODES
else:
    from quality_v0_1_7 import OUTCOMES
    from contracts_v0_1_7 import REASON_CODES


def item_contract(role,subject_id,obligations):
    """Describe ordinary analysis/review items; other admitted task kinds stay unchanged."""
    string={'type':'string'};refs={'type':'array','items':string}
    base={'item_id':string,'subject_id':{'const':subject_id},'statement':string,
        'supporting_evidence_ids':refs,'contradicting_evidence_ids':refs,'depends_on':refs}
    if role=='outcome_adjudicator' and all(x.startswith('outcome:') for x in obligations):
        base.update(dimension={'enum':list(OUTCOMES)},
            value=string,trial_ids=refs)
    elif role=='hypothesis_analyst' and all(x.startswith('seed:') or x=='hypothesis_assessment' for x in obligations):
        base.update(source_assertion_id={'type':['string','null']},reason_code={'enum':sorted(REASON_CODES)},
            scope={'type':'string','maxLength':2000},proposed_verdict={'enum':['untested','supported','refuted','inconclusive']},
            alternative_explanations={'type':'array','minItems':1,'maxItems':8,'items':{'type':'string','maxLength':2000}},
            validation_indicators={'type':'array','minItems':1,'maxItems':8,'items':{'type':'string','maxLength':2000}},
            falsification_condition={'type':'string','maxLength':2000},lesson={'type':['string','null'],'maxLength':2000})
    elif role=='evidence_critic' and all(x.startswith('review:') for x in obligations):
        ids=[x[len('review:'):] for x in obligations]
        base={'item_id':{'enum':ids},'verdict':{'enum':['accepted','needs_evidence','contradicted','invalid']},
            'rationale':{'type':'string','maxLength':4000},'supporting_evidence_ids':refs,'contradicting_evidence_ids':refs,'scope_preserved':{'type':'boolean'}}
        return {'type':'array','minItems':len(ids),'maxItems':len(ids),
            'items':{'type':'object','additionalProperties':False,'required':list(base),'properties':base}}
    else:return None
    return {'type':'array','maxItems':32,'items':{'type':'object','additionalProperties':False,'required':list(base),'properties':base}}
