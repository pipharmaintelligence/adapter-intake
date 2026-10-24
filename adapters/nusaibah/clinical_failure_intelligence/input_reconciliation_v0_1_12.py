"""One affected-input reconciliation pass; canonical evidence never becomes model-editable."""
from copy import deepcopy
if __package__:
    from .contracts_v0_1_12 import ContractError,digest,canonical_bytes,object_fields,require
else:
    from contracts_v0_1_12 import ContractError,digest,canonical_bytes,object_fields,require

ELIGIBLE_ERRORS=frozenset({'clinical_span_mismatch','clinical_span_offsets_invalid',
    'clinical_critic_evidence_mismatch','clinical_spans_invalid','clinical_fields_invalid',
    'clinical_text_invalid','clinical_outcome_value_invalid','clinical_hypothesis_plan_invalid',
    'clinical_memory_operation_invalid','clinical_memory_append_target_invalid',
    'clinical_memory_section_operation_invalid',
    'clinical_memory_single_paragraph_required'})
PLAN_FIELDS={'original_task_id','target_role','action','affected_item_ids','evidence_ids',
             'groups','prepared_items','rationale'}


def item_key(row):
    if not isinstance(row,dict):return None
    return next((row[key] for key in ('claim_id','item_id','edit_id') if isinstance(row.get(key),str)),None)


def references(row):
    return {ref for field in ('supporting_evidence_ids','contradicting_evidence_ids')
            for ref in (row.get(field,[]) if isinstance(row.get(field,[]),list) else []) if isinstance(ref,str)}


def focus_data(data,rejected):
    """Supply only affected complete items, dependency closure and source windows."""
    keys={item_key(row) for row in rejected}
    result={key:deepcopy(data[key]) for key in ('case_trial_ids','case_scope','edit_contract',
        'review_kind','memory_review_contract','reviewed_findings_provenance') if key in data}
    candidates=[row for row in data.get('candidate_items',[]) if row.get('item_id') in keys]
    if candidates:result['candidate_items']=deepcopy(candidates)
    seeds={row.get('source_assertion_id') for row in rejected if isinstance(row.get('source_assertion_id'),str)}
    if seeds:result['source_assertions']=deepcopy([row for row in data.get('source_assertions',[]) if row.get('assertion_id') in seeds])
    context={row['item_id']:row for row in data.get('dependency_context',[])}
    needed={ref for row in candidates for ref in row.get('depends_on',[])}
    previous=set()
    while previous!=needed:
        previous=set(needed)
        needed.update(ref for key in previous if key in context for ref in context[key].get('depends_on',[]))
    dependencies=[row for key,row in context.items() if key in needed]
    if dependencies:result['dependency_context']=deepcopy(dependencies)
    if 'accepted_items' in data:
        accepted_ids={key for row in rejected for key in (row.get('supporting_item_ids',[]) if isinstance(row.get('supporting_item_ids',[]),list) else []) if isinstance(key,str)}
        result['accepted_items']=deepcopy([row for row in data['accepted_items'] if row['item_id'] in accepted_ids])
        if 'reviewed_findings_provenance' in result:
            result['reviewed_findings_provenance'].update(accepted_item_ids=[row['item_id'] for row in result['accepted_items']],
                accepted_items_digest=digest(result['accepted_items']))
        # Full selected old paragraphs are required for any editorial retry.
        if 'memory_context' in data:result['memory_context']=deepcopy(data['memory_context'])
    refs={ref for row in [*rejected,*candidates,*dependencies] for ref in references(row)}
    refs.update(data.get('case_context_evidence_ids',[]) if candidates else [])
    result['evidence_packet']=deepcopy([row for row in data.get('evidence_packet',[]) if row['evidence_id'] in refs])
    if candidates:result['case_context_evidence_ids']=[ref for ref in data.get('case_context_evidence_ids',[]) if ref in refs]
    return result


def _validate_prepared(rows,originals,data,role):
    require(isinstance(rows,list) and len(rows)<=len(originals),'clinical_reconciliation_prepared_invalid')
    table={item_key(row):row for row in originals}
    candidates={row['item_id']:row for row in data.get('candidate_items',[])}
    evidence={row['evidence_id']:row for row in data.get('evidence_packet',[])}
    seen=set()
    for row in rows:
        key=item_key(row)
        require(key in table and key not in seen,'clinical_reconciliation_item_scope_invalid');seen.add(key)
        original=table[key]
        mutable=({'source_spans'} if role.endswith('researcher') else
                 {'supporting_evidence_ids','contradicting_evidence_ids'} if role=='evidence_critic' else set())
        require(set(row)==set(original) and all(row[field]==original[field] for field in original if field not in mutable),
                'clinical_reconciliation_scientific_change_forbidden')
        if role.endswith('researcher'):
            require(isinstance(row.get('source_spans'),list) and len(row['source_spans'])<=8,'clinical_reconciliation_span_invalid')
            require(len(row['source_spans'])==len(original.get('source_spans',[])),'clinical_reconciliation_span_identity_invalid')
            for span,original_span in zip(row['source_spans'],original.get('source_spans',[])):
                require(isinstance(span,dict) and isinstance(original_span,dict) and span.get('evidence_id')==original_span.get('evidence_id'),
                    'clinical_reconciliation_span_identity_invalid')
                object_fields(span,{'evidence_id','start','end','quote','text_digest'})
                ref=span['evidence_id'];source=evidence.get(ref)
                require(source is not None and ref in references(original),'clinical_reconciliation_source_invalid')
                start,end=span['start'],span['end'];quote=span['quote']
                require(type(start)is int and type(end)is int and isinstance(quote,str) and bool(quote)
                    and 0<=start<end<=len(source['text']) and source['text'][start:end]==quote
                    and span['text_digest']==source['text_digest'],'clinical_reconciliation_span_invalid')
        if role=='evidence_critic':
            candidate=candidates.get(key)
            require(candidate is not None,'clinical_reconciliation_item_scope_invalid')
            for field in ('supporting_evidence_ids','contradicting_evidence_ids'):
                require(isinstance(row.get(field),list) and all(isinstance(ref,str) and ref in candidate[field]
                    for ref in row[field]),'clinical_reconciliation_evidence_expansion')


def ask_reconciler(runner,request,stage,*,mode,data,errors,originals=None,inventory=None,downstream_reserve=0):
    """An admitted Agent proposes input only. No unknown error becomes retryable."""
    originals=originals or [];inventory=inventory or []
    if not request['enable_refinement'] or stage.role=='input_reconciler':return None
    if mode not in {'retry_items','partition_input'}:return None
    if mode=='partition_input' and stage.code!='clinical_packet_requires_partitioning':return None
    if mode=='retry_items' and (not errors or any(row.get('code') not in ELIGIBLE_ERRORS for row in errors)):
        return None
    keys=[item_key(row) for row in originals] if mode=='retry_items' else [row['unit_id'] for row in inventory]
    if not keys or any(key is None for key in keys) or len(keys)!=len(set(keys)):return None
    if runner._input_budgets.get('input_reconciler') is None:
        runner.note_reconciliation(stage,'unresolved','clinical_reconciliation_role_not_admitted')
        return None
    with runner.budget.lock:
        available = runner.budget.policy.max_agent_calls-runner.budget.calls-downstream_reserve
        correction_slots = runner.budget.policy.max_reconciliation_agent_calls-runner.budget.reconciliation_calls
    if available < 2 or correction_slots < 2:
        runner.note_reconciliation(stage,'unresolved','clinical_reconciliation_budget_deferred')
        return None
    key=digest([stage.role,stage.task_id,stage.input_digest])
    if not runner.budget.admit_business_repair(key):
        runner.note_reconciliation(stage,'unresolved','clinical_reconciliation_task_limit')
        return None
    descriptor={'mode':mode,'original_task_id':stage.task_id,'target_role':stage.role,
        'original_input_digest':stage.input_digest,'original_output_digest':digest(stage.payload),
        'affected_item_ids':keys,'validation_errors':deepcopy(errors),
        'affected_fragment':deepcopy(originals),'input_inventory':deepcopy(inventory),
        'limits':{'max_partitions':runner.budget.policy.max_reconciliation_partitions,
            'max_packet_bytes':runner.budget.policy.max_packet_bytes,
            'target_allowance':deepcopy(runner._input_budgets.get(stage.role)),
            'passes_per_original_task':1},
        'authority':'proposal_for_one_original_role_retry_only'}
    packet_data={**deepcopy(data),'input_reconciliation':descriptor,'reconciliation_work':True}
    try:
        result=runner.call('input_reconciler',request,task_id='reconcile:'+key.split(':')[1][:24],
            obligations=['prepare_affected_input'],packet_data=packet_data,downstream_reserve=downstream_reserve+1)
    except ContractError as error:
        if error.code!='clinical_agent_identity_mismatch':raise
        runner.note_reconciliation(stage,'unresolved','clinical_reconciliation_identity_invalid')
        return None
    runner.record_reconciliation_stage(result)
    try:
        require(result.status=='completed' and result.payload is not None,'clinical_reconciliation_incomplete')
        require(result.payload['followup_requests']==[] and len(result.payload['items'])==1,'clinical_reconciliation_plan_invalid')
        plan=object_fields(result.payload['items'][0],PLAN_FIELDS)
        require(plan['original_task_id']==stage.task_id and plan['target_role']==stage.role,'clinical_reconciliation_identity_invalid')
        require(plan['affected_item_ids']==keys,'clinical_reconciliation_item_scope_invalid')
        require(isinstance(plan['rationale'],str) and 0<len(plan['rationale'].strip())<=2000,'clinical_reconciliation_plan_invalid')
        supplied={row['evidence_id'] for row in data.get('evidence_packet',[])}
        require(isinstance(plan['evidence_ids'],list) and all(isinstance(ref,str) and ref in supplied
            for ref in plan['evidence_ids']),'clinical_reconciliation_source_invalid')
        require(plan['action'] in {'prepare_retry','partition_input','unresolved'},'clinical_reconciliation_plan_invalid')
        if plan['action']=='unresolved':
            require(plan['groups']==[] and plan['prepared_items']==[],'clinical_reconciliation_plan_invalid')
            runner.note_reconciliation(stage,'unresolved','clinical_reconciliation_source_gap',result)
            return None
        if mode=='retry_items':
            require(plan['action']=='prepare_retry' and plan['groups']==[],'clinical_reconciliation_plan_invalid')
            _validate_prepared(plan['prepared_items'],originals,data,stage.role)
        else:
            require(plan['action']=='partition_input' and plan['prepared_items']==[],'clinical_reconciliation_plan_invalid')
            groups=plan['groups']
            require(isinstance(groups,list) and 1<=len(groups)<=runner.budget.policy.max_reconciliation_partitions
                and all(isinstance(group,list) and bool(group) and all(isinstance(ref,str) for ref in group) for group in groups),
                'clinical_reconciliation_partition_invalid')
            flat=[ref for group in groups for ref in group]
            require(len(flat)==len(keys) and len(set(flat))==len(keys) and set(flat)==set(keys),
                    'clinical_reconciliation_partition_coverage_invalid')
        runner.note_reconciliation(stage,'prepared','clinical_reconciliation_plan_validated',result)
        return plan,result
    except ContractError as error:
        runner.note_reconciliation(stage,'unresolved',error.code,result)
        return None


def partition_data(data,field,group):
    """Rebuild a request from immutable original units; the model edits no source."""
    result=deepcopy(data);selected=set(group)
    if field=='evidence_packet':
        claims=[row for row in data.get('research_claims',[]) if references(row)&selected]
        required=selected|set(data.get('case_context_evidence_ids',[]))|{ref for row in claims for ref in references(row)}
        if 'research_claims' in data:result['research_claims']=deepcopy(claims)
        result['evidence_packet']=[deepcopy(row) for row in data['evidence_packet'] if row['evidence_id'] in required]
        require(required<={row['evidence_id'] for row in result['evidence_packet']},'clinical_reconciliation_source_closure_invalid')
        if 'evidence_scope' in result:
            result['evidence_scope'].update(assigned_evidence_ids=sorted(selected),assigned_count=len(selected),included_evidence_ids=sorted(required),
                complete_evidence_in_packet=len(required)==result['evidence_scope'].get('total_evidence_count'),
                independent_exhaustiveness_claim=False)
    else:
        result[field]=[deepcopy(row) for row in data[field] if row['item_id'] in selected]
        if field=='accepted_items' and 'reviewed_findings_provenance' in result:
            result['reviewed_findings_provenance'].update(accepted_item_ids=[row['item_id'] for row in result[field]],
                accepted_items_digest=digest(result[field]))
            if 'editorial_batch_scope' in result:result['editorial_batch_scope']['complete_case_findings']=False
        context={row['item_id']:row for row in [*data.get('candidate_items',[]),*data.get('dependency_context',[])]}
        needed={ref for row in result[field] for ref in row.get('depends_on',[])}
        previous=set()
        while previous!=needed:
            previous=set(needed)
            needed.update(ref for key in previous if key in context for ref in context[key].get('depends_on',[]))
        dependencies=[row for key,row in context.items() if key in needed-selected]
        if 'dependency_context' in result:result['dependency_context']=deepcopy(dependencies)
        required={ref for row in [*result[field],*dependencies] for ref in references(row)}|set(data.get('case_context_evidence_ids',[]))
        result['evidence_packet']=[deepcopy(row) for row in data.get('evidence_packet',[]) if row['evidence_id'] in required]
        if field=='candidate_items':
            require(required<={row['evidence_id'] for row in result['evidence_packet']},'clinical_reconciliation_source_closure_invalid')
            if 'review_packet_scope' in result:result['review_packet_scope'].update(assigned_item_ids=sorted(selected),full_evidence_read=False)
    return result


def recover_partition(runner,request,stage,*,packet_data,obligations,downstream_reserve):
    """Retry only an undispatched oversize input, once, with exact coverage."""
    from_role=stage.role
    if stage.code!='clinical_packet_requires_partitioning' or packet_data.get('input_reconciliation_retry'):
        return stage
    if from_role=='input_reconciler':return stage
    field=('candidate_items' if from_role=='evidence_critic' and 'candidate_items' in packet_data else
           'accepted_items' if from_role=='product_memory_editor' and 'accepted_items' in packet_data else 'evidence_packet')
    units=packet_data.get(field,[])
    if not isinstance(units,list) or not units:return stage
    key_field='evidence_id' if field=='evidence_packet' else 'item_id'
    assigned=packet_data.get('evidence_scope',{}).get('assigned_evidence_ids') if field=='evidence_packet' else None
    if assigned is not None:units=[row for row in units if row[key_field] in assigned]
    inventory=[{'unit_id':row[key_field],'canonical_digest':digest(row),'bytes':len(canonical_bytes(row)),
        'chars':len(canonical_bytes(row).decode('utf-8'))} for row in units]
    answer=ask_reconciler(runner,request,stage,mode='partition_input',data={},
        errors=[{'code':stage.code}],inventory=inventory,downstream_reserve=downstream_reserve)
    if answer is None:return stage
    plan,reconciler=answer;specs=[]
    try:
        for index,group in enumerate(plan['groups']):
            data=partition_data(packet_data,field,group)
            data['input_reconciliation_retry']={'original_task_id':stage.task_id,'original_input_digest':stage.input_digest,
                'reconciler_output_digest':digest(reconciler.payload),'group_index':index,'group_count':len(plan['groups']),
                'assigned_unit_ids':group,'source_text_changed':False}
            task_id='input_retry:'+digest([stage.task_id,stage.input_digest]).split(':')[1][:20]+':'+str(index)
            assigned_obligations=['review:'+row['item_id'] for row in data[field]] if field=='candidate_items' else obligations
            packet=runner.packet(from_role,request,task_id=task_id,obligations=assigned_obligations,packet_data=data)
            require(runner.packet_fits(from_role,packet),'clinical_reconciliation_retry_still_oversize')
            specs.append((task_id,assigned_obligations,data))
    except ContractError as error:
        runner.note_reconciliation(stage,'unresolved',error.code,reconciler);return stage
    retries=[]
    for index,(task_id,assigned_obligations,data) in enumerate(specs):
        retries.append(runner.call(from_role,request,task_id=task_id,obligations=assigned_obligations,
            packet_data=data,downstream_reserve=downstream_reserve+len(specs)-index-1))
    # The SDK retains each real child stage; this is an explicit adapter join.
    from copy import copy
    joined=copy(stage);items=[];followups=[]
    for index,row in enumerate(retries):
        if row.payload:
            values=deepcopy(row.payload['items'])
            if len(retries)>1 and from_role in {'outcome_adjudicator','hypothesis_analyst'}:
                mapping={item['item_id']:'partition:'+str(index)+':'+digest(item['item_id']).split(':')[1][:20] for item in values if isinstance(item,dict) and isinstance(item.get('item_id'),str)}
                for item in values:
                    if isinstance(item,dict) and item.get('item_id') in mapping:
                        item['item_id']=mapping[item['item_id']]
                        if isinstance(item.get('depends_on'),list):item['depends_on']=[mapping.get(ref,ref) for ref in item['depends_on']]
            if len(retries)>1 and from_role.endswith('researcher'):
                for item in values:
                    if isinstance(item,dict) and isinstance(item.get('claim_id'),str):
                        item['claim_id']='partition:'+str(index)+':'+digest(item['claim_id']).split(':')[1][:20]
            items.extend(values);followups.extend(row.payload['followup_requests'])
    if len(items)>runner.budget.policy.max_task_items or len(followups)>8:
        runner.note_reconciliation(stage,'unresolved','clinical_reconciliation_join_limit',reconciler);return stage
    complete=all(row.status=='completed' for row in retries)
    joined.status='completed' if complete else 'partial'
    joined.code=None if complete else 'clinical_reconciliation_retry_incomplete'
    joined.payload={'schema_version':'clinical_agent_response.v1','task_id':stage.task_id,'subject_id':request['subject_id'],
        'role':from_role,'items':items,'followup_requests':followups,'coverage':[
            {'obligation_id':key,'status':'completed' if complete else 'unresolved'} for key in obligations]}
    joined.evidence_ids=tuple(sorted({ref for row in retries for ref in row.evidence_ids or ()}))
    joined.attempts=tuple(row.summary() for row in [stage,reconciler,*retries])
    joined.semantic_metadata={'input_reconciliation':{'representation':'adapter_validated_partition_join',
        'original_input_digest':stage.input_digest,'groups':deepcopy(plan['groups']),
        'retry_statuses':[row.status for row in retries],'source_text_changed':False}}
    return joined
