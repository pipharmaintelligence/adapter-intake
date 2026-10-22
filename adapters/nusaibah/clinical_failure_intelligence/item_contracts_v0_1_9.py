"""Role-specific business JSON schemas, not provider settings or authority."""
if __package__:
    from .quality_v0_1_9 import OUTCOMES
    from .contracts_v0_1_9 import REASON_CODES
else:
    from quality_v0_1_9 import OUTCOMES
    from contracts_v0_1_9 import REASON_CODES


def item_contract(role,subject_id,obligations,*,candidates=None,reconciliation=None):
    """Describe ordinary analysis/review items; other admitted task kinds stay unchanged."""
    string={'type':'string'};refs={'type':'array','items':string}
    if role=='input_reconciler':
        context=reconciliation or {}
        properties={'original_task_id':{'const':context.get('original_task_id')},
            'target_role':{'const':context.get('target_role')},
            'action':{'enum':['prepare_retry','partition_input','unresolved']},
            'affected_item_ids':{'const':context.get('affected_item_ids',[])},
            'evidence_ids':refs,'groups':{'type':'array','maxItems':2,'items':refs},
            'prepared_items':{'type':'array','maxItems':32,'items':{'type':'object'}},
            'rationale':{'type':'string','minLength':1,'maxLength':2000}}
        return {'type':'array','minItems':1,'maxItems':1,'items':{'type':'object',
            'additionalProperties':False,'required':list(properties),'properties':properties}}
    base={'item_id':string,'subject_id':{'const':subject_id},'statement':string,
        'supporting_evidence_ids':refs,'contradicting_evidence_ids':refs,'depends_on':refs}
    if role=='outcome_adjudicator' and all(x.startswith(('outcome:','correct_item:')) for x in obligations):
        base.update(dimension={'enum':list(OUTCOMES)},
            value=string,trial_ids=refs)
    elif role=='hypothesis_analyst' and all(x.startswith(('seed:','correct_item:')) or x=='hypothesis_assessment' for x in obligations):
        base.update(source_assertion_id={'type':['string','null']},reason_code={'enum':sorted(REASON_CODES)},
            scope={'type':'string','maxLength':2000},proposed_verdict={'enum':['untested','supported','refuted','inconclusive']},
            alternative_explanations={'type':'array','minItems':1,'maxItems':8,'items':{'type':'string','maxLength':2000}},
            validation_indicators={'type':'array','minItems':1,'maxItems':8,'items':{'type':'string','maxLength':2000}},
            falsification_condition={'type':'string','maxLength':2000},lesson={'type':['string','null'],'maxLength':2000})
    elif role=='evidence_critic' and all(x.startswith('review:') for x in obligations):
        ids=[x[len('review:'):] for x in obligations]
        base={'item_id':{'enum':ids},'verdict':{'enum':['accepted','needs_evidence','contradicted','invalid']},
            'rationale':{'type':'string','maxLength':4000},'supporting_evidence_ids':refs,'contradicting_evidence_ids':refs,'scope_preserved':{'type':'boolean'}}
        schema={'type':'object','additionalProperties':False,'required':list(base),'properties':base}
        if candidates is not None:
            by_id={row['item_id']:row for row in candidates}
            # oneOf is supported by the runtime's JSON schema contract. Each item
            # has its own closed reference sets; no cross-item union can authorize it.
            choices=[]
            for key in ids:
                row=by_id[key]
                props={**base,'item_id':{'const':key}}
                for field in ('supporting_evidence_ids','contradicting_evidence_ids'):
                    allowed=row[field]
                    props[field]={'type':'array','uniqueItems':True,
                        'items':{'enum':allowed} if allowed else {'type':'string'},
                        'maxItems':len(allowed)}
                choices.append({'type':'object','additionalProperties':False,
                    'required':list(base),'properties':props})
            schema={'oneOf':choices}
        return {'type':'array','minItems':len(ids),'maxItems':len(ids),'items':schema}
    else:return None
    return {'type':'array','maxItems':32,'items':{'type':'object','additionalProperties':False,'required':list(base),'properties':base}}
