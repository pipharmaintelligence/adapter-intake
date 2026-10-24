"""Role-specific business JSON schemas, not provider settings or authority."""
if __package__:
    from .quality_v0_1_12 import OUTCOMES
    from .contracts_v0_1_12 import REASON_CODES
else:
    from quality_v0_1_12 import OUTCOMES
    from contracts_v0_1_12 import REASON_CODES


def item_contract(role,subject_id,obligations,*,candidates=None,reconciliation=None,dependency_ids=None,editor_snapshot=None,accepted_ids=None):
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
    if role=='product_memory_editor' and editor_snapshot is not None:
        choices=[]
        refs_allowed=list(accepted_ids or [])
        required=['edit_id','operation','target_paragraph_id','before_digest','section_path','new_text','supporting_item_ids','rationale']
        targets=editor_snapshot.get('paragraphs',[])
        ops=['append_paragraph'] if editor_snapshot.get('section_exists') else ['add_section']
        if editor_snapshot.get('section_exists') and targets:
            ops += ['keep','enrich_paragraph','replace_paragraph']
        for op in ops:
            for paragraph in (targets if op in {'keep','enrich_paragraph','replace_paragraph'} else [None]):
                properties={'edit_id':{'type':'string'}, 'operation':{'const':op},
                    'target_paragraph_id':{'const':paragraph['paragraph_id'] if paragraph else None},
                    'before_digest':{'const':paragraph['digest'] if paragraph else None},
                    'section_path':{'const':editor_snapshot['section_path']},
                    'new_text':{'type':'null'} if op=='keep' else {'type':'string','minLength':1,'maxLength':3000},
                    'supporting_item_ids':{'type':'array','uniqueItems':True,'minItems':0 if op=='keep' else 1,
                        'maxItems':len(refs_allowed),'items':{'enum':refs_allowed} if refs_allowed else {'type':'string'}},
                    'rationale':{'type':'string','minLength':1,'maxLength':1500}}
                choices.append({'type':'object','additionalProperties':False,'required':required,'properties':properties})
        return {'type':'array','maxItems':8,'items':{'oneOf':choices}}
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
                if row.get('unresolved_dependency_ids'):
                    props['verdict']={'enum':['needs_evidence','contradicted','invalid']}
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
    if dependency_ids is not None:
        allowed=list(dict.fromkeys(dependency_ids))
        base['depends_on']={'type':'array','uniqueItems':True,'maxItems':len(allowed),
            'items':{'enum':allowed} if allowed else {'type':'string'}}
    return {'type':'array','maxItems':32,'items':{'type':'object','additionalProperties':False,'required':list(base),'properties':base}}
