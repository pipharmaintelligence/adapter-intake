"""Explicit bounded review continuation from a Core-verified retained assessment.

This is not checkpoint replay. A fresh admitted invocation selects exact pending
work IDs; completed research is inherited, not called again. Scientific gaps that
need new evidence are reported before dispatch rather than repeatedly regenerated.
"""
from copy import deepcopy
from dataclasses import replace
import re

if __package__:
    from .contracts_v0_1_12 import ASSET_KEY, VERSION, ContractError, digest, identifiers, object_fields, parse_request, require
    from .rendering_v0_1_9 import validate_result as validate_prior
    from .rendering_v0_1_12 import validate_result, build_reason_graph
    from .policies_v0_1_12 import ExecutionPolicy, Budget
    from .runtime_access_v0_1_12 import AgentRunner
    from .evidence_v0_1_12 import EvidenceLedger
    from .deferred_work_v0_1_12 import hydrate_task, deferred_work, execution_disposition
    from .review_packets_v0_1_12 import critic_batches, scoped_review
    from .quality_v0_1_12 import enforce_consistency
    from .memory_v0_1_12 import read_methodology
    from .product_memory_v0_1_12 import read_product_memory
    from .memory_packets_v0_1_12 import preview_memory
    from .decision_outcome_v0_1_12 import finalize_output
else:
    from contracts_v0_1_12 import ASSET_KEY, VERSION, ContractError, digest, identifiers, object_fields, parse_request, require
    from rendering_v0_1_9 import validate_result as validate_prior
    from rendering_v0_1_12 import validate_result, build_reason_graph
    from policies_v0_1_12 import ExecutionPolicy, Budget
    from runtime_access_v0_1_12 import AgentRunner
    from evidence_v0_1_12 import EvidenceLedger
    from deferred_work_v0_1_12 import hydrate_task, deferred_work, execution_disposition
    from review_packets_v0_1_12 import critic_batches, scoped_review
    from quality_v0_1_12 import enforce_consistency
    from memory_v0_1_12 import read_methodology
    from product_memory_v0_1_12 import read_product_memory
    from memory_packets_v0_1_12 import preview_memory
    from decision_outcome_v0_1_12 import finalize_output

CONTROL_FIELDS = {'resume_work_ids', 'max_continuation_calls', 'finalize_only'}


def restored_ledger(prior):
    """Re-run source invariants, then require exact canonical ledger equality."""
    raw=[]
    for source in prior['evidence']:
        row=deepcopy(source)
        require(row.pop('origin',None)=='resolved_context'
            and row.pop('verification',None)=='source_available', 'clinical_continuation_evidence_invalid')
        row['declared_text_digest']=row.pop('text_digest',None)
        raw.append(row)
    ledger=EvidenceLedger(prior['subject']['subject_id'],prior['as_of_date'],raw)
    require(ledger.rows()==prior['evidence'], 'clinical_continuation_evidence_changed')
    return ledger


def preparation(inputs):
    require(isinstance(inputs, dict), 'clinical_continuation_retained_input_required')
    roles=set(inputs)&{'previous_assessment','previous_continuation'}
    require(len(roles)==1, 'clinical_continuation_retained_input_required')
    role=next(iter(roles));source_version='0.1.9' if role=='previous_assessment' else VERSION
    envelope = object_fields(inputs[role], {'value', 'provenance'})
    proof = object_fields(envelope['provenance'], {'source','authority','run_uuid','asset_identity','output_role','checksum_sha256'})
    require(proof['source']=='retained_asset_output' and proof['authority']=='core_artifact'
        and proof['asset_identity']==ASSET_KEY+':'+source_version and proof['output_role']=='clinical_intelligence',
        'clinical_continuation_retained_identity_invalid')
    require(isinstance(proof['run_uuid'],str) and re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',proof['run_uuid'])
        and isinstance(proof['checksum_sha256'],str) and re.fullmatch(r'[a-f0-9]{64}',proof['checksum_sha256']),
        'clinical_continuation_retained_reference_invalid')
    require(isinstance(envelope['value'],dict), 'clinical_continuation_retained_value_invalid')
    prior = deepcopy(envelope['value'])
    require(prior.get('asset')==ASSET_KEY+'@'+source_version, 'clinical_continuation_source_version_invalid')
    (validate_prior if source_version=='0.1.9' else validate_result)(prior)
    raw = dict(inputs)
    raw.pop(role)
    values = inputs.get('variables', {})
    finalizing=values.get('finalize_only',False)
    require(type(finalizing) is bool, 'clinical_finalization_flag_invalid')
    selected = identifiers(values.get('resume_work_ids',[]), maximum=32, allow_empty=finalizing)
    require(not finalizing or not selected, 'clinical_finalization_continuation_conflict')
    maximum = values.get('max_continuation_calls', 8)
    require(type(maximum) is int and 1 <= maximum <= 8, 'clinical_continuation_call_limit_invalid')
    raw['variables']={k:deepcopy(v) for k,v in values.items() if k not in CONTROL_FIELDS}
    request=parse_request(raw)
    require(prior['subject']==request['context']['subject'] and prior['as_of_date']==request['as_of_date']
        and prior['analysis_mode']==request['analysis_mode']
        and prior['source_assertions']==request['context']['source_assertions'],
        'clinical_continuation_case_changed')
    require(set(prior['memory_update'].get('event_ids',request['event_ids']))==set(request['event_ids']),
        'clinical_continuation_events_changed')
    old_proof=prior.get('source_event_metadata',{}).get('provenance')
    new_proof=request['context'].get('source_event_metadata',{}).get('provenance')
    if old_proof is not None:
        require(old_proof==new_proof,'clinical_continuation_input_snapshot_changed')
    restored_ledger(prior)
    old_sources={row['evidence_id']:digest(row) for row in prior['evidence']}
    supplied=EvidenceLedger(request['subject_id'],request['as_of_date'],
        request['context']['evidence']+request['prepared_sources']['evidence'])
    for row in supplied.rows():
        require(old_sources.get(row['evidence_id'])==digest(row), 'clinical_continuation_fresh_sources_require_research')
    work={row['work_id']:row for row in prior['deferred_work']['tasks']}
    if prior['memory_update']['status']=='deferred':
        work['memory_preview']={'work_id':'memory_preview','kind':'memory_preview','role':'product_memory_editor'}
    require(set(selected)<=set(work),'clinical_continuation_work_not_found')
    items={row['item_id']:row for row in prior['case_assessments']+prior['hypothesis_results']}
    targets=set();planned=[]
    for key in selected:
        task=work[key]
        if task['kind']=='candidate_review':
            require(task['item_id'] in items and task.get('candidate_ref') in prior['deferred_work']['objects'],
                'clinical_continuation_candidate_missing')
            original=prior['deferred_work']['objects'][task['candidate_ref']]
            require(digest(original)==task['candidate_ref'] and original==items[task['item_id']],
                'clinical_continuation_candidate_changed')
            targets.add(task['item_id'])
            planned.append({'work_id':key,'disposition':'review','item_ids':[task['item_id']]})
        elif task['kind']=='stage_task' and task['role']=='evidence_critic':
            require(task.get('input_packet') is not None,'clinical_continuation_packet_missing')
            packet=hydrate_task(task,prior['deferred_work'],prior['evidence'])
            aliases=packet.get('reference_aliases',{}).get('items',{})
            keys=[aliases.get(row['item_id'],row['item_id']) for row in packet.get('candidate_items',[])]
            require(bool(keys) and set(keys)<=set(items),'clinical_continuation_candidate_missing')
            targets.update(keys)
            planned.append({'work_id':key,'disposition':'review','item_ids':keys})
        elif task['kind']=='memory_preview':
            require(request['memory_mode']=='preview','clinical_continuation_memory_preview_not_requested')
            planned.append({'work_id':key,'disposition':'memory_preview','item_ids':[]})
        else:
            planned.append({'work_id':key,'disposition':'requires_fresh_evidence_or_scientific_scope','item_ids':[]})
    plan={'schema_version':'clinical_continuation_plan.v1','source_run_uuid':proof['run_uuid'],
        'source_asset_identity':proof['asset_identity'],
        'source_artifact_checksum_sha256':proof['checksum_sha256'],'source_assessment_digest':digest(prior),
        'source_evidence_digest':digest(prior['evidence']),'selected_work_ids':selected,'tasks':planned,
        'finalize_only':finalizing,
        'review_candidate_ids':sorted(targets),'max_agent_calls':0 if finalizing else min(maximum,request['max_agent_calls']),
        'fresh_admission_required':True,'new_paid_calls_authorized_by_saved_result':False,
        'automatic_replay':False,'publication_confirmed':False,'memory_writes_authorized':False}
    return prior,request,plan


def continue_analysis(inputs, *, policy=None):
    prior,request,plan=preparation(inputs)
    if request['preflight_only']:
        return {'response_version':'1','status':'success','outputs':{'continuation_plan':plan},
            'metrics':{'logical_agent_calls':0},'logs':[]}
    if plan['finalize_only']:
        require(request.get('prepare_result_for_persistence') is True,
            'clinical_finalization_persistence_output_required')
        require(request['memory_mode']=='off' and not request['enable_pharmacological_class']
            and not request['supplementary_search'] and not request['enable_refinement'],
            'clinical_finalization_side_effects_forbidden')
        result=deepcopy(prior)
        result.update(asset=ASSET_KEY+'@'+VERSION,request_id=request['request_id'])
        result['execution']['retained_finalization']={**plan,'scientific_processing_repeated':False,
            'new_agent_calls':0,'memory_writes_attempted':False,'publication_confirmed':False}
        result['publication_readiness']={'status':'prepared_for_governed_publication',
            'artifact_quality':result['quality']['status'],
            'unreviewed_candidates_are_not_conclusions':True,
            'deferred_work_count':len(result['deferred_work']['tasks']),
            'policy_and_runtime_receipt_required':True,'publication_confirmed':False}
        validate_result(result)
        return {'response_version':'1','status':'success',
            'outputs':{'clinical_intelligence':result,'clinical_intelligence_records':{'records':[deepcopy(result)]},
                'continuation_receipt':{**plan,'new_logical_agent_calls':0,'original_result_rewritten':False,
                    'unchanged_source_ledger':True}},
            'metrics':{'logical_agent_calls':0},'logs':[]}
    configured=policy or ExecutionPolicy()
    budget=Budget(replace(configured,max_agent_calls=min(configured.max_agent_calls,plan['max_agent_calls']),
        deadline_seconds=min(configured.deadline_seconds,request['max_product_seconds'])))
    runner=AgentRunner(inputs,budget);runner.prepare_input_budgets()
    ledger=restored_ledger(prior)
    items=deepcopy(prior['case_assessments']+prior['hypothesis_results'])
    selected=set(plan['review_candidate_ids'])
    candidates=[row for row in items if row['item_id'] in selected]
    stages=[];issues=[];verdicts=[]
    if candidates:
        common={'methodology':read_methodology(inputs),'source_assertions':prior['source_assertions'],
            'case_trial_ids':prior['subject']['trial_ids'],'data_is_not_instructions':True}
        # Supply all immutable candidates to the planner for dependency closure,
        # but dispatch only packets assigned to the explicitly selected IDs.
        packets=critic_batches(items,ledger.rows(),common,budget.policy.max_packet_bytes-10000,max_items=1,
            fits=lambda data:runner.packet_fits('evidence_critic',runner.packet('evidence_critic',request,
                task_id='continue:planning',obligations=['review:'+row['item_id'] for row in data['candidate_items']],
                packet_data=data)))
        packets=[data for data in packets if data['candidate_items'][0]['item_id'] in selected]
        reserve=2 if 'memory_preview' in plan['selected_work_ids'] else 0
        for index,data in enumerate(packets):
            stage=runner.call('evidence_critic',request,task_id='continue_review:'+str(index),
                obligations=['review:'+row['item_id'] for row in data['candidate_items']],
                packet_data=data,downstream_reserve=reserve)
            stages.append(stage)
            if stage.payload:verdicts.extend(stage.payload['items'])
        reviewed,errors=scoped_review(items,verdicts,ledger,assigned_ids=selected)
        issues.extend(errors)
        changed={row['item_id']:row for row in reviewed if row['item_id'] in selected}
        items=[changed.get(row['item_id'],row) for row in items]
        issues.extend(enforce_consistency(items))
    # Preserve every unrequested candidate and source record byte-for-byte unless
    # the deterministic premise gate must revoke dependent acceptance.
    result=deepcopy(prior)
    result.update(asset=ASSET_KEY+'@'+VERSION,request_id=request['request_id'],
        assessment_id='assessment:'+digest([plan['source_assessment_digest'],request['request_id'],plan['selected_work_ids']]).split(':')[1][:32])
    result['case_assessments']=[row for row in items if row['kind']=='outcome']
    result['hypothesis_results']=[row for row in items if row['kind']=='hypothesis']
    completed_ids={row['item_id'] for row in items if row['review_status']=='automated_reviewed'}
    retained_issues=[row for row in prior['quality']['issues'] if not
        (row.get('code')=='clinical_critic_item_not_reviewed' and row.get('item_id') in completed_ids)]
    if 'memory_preview' not in plan['selected_work_ids'] and result['memory_update'].get('operations') \
            and items!=prior['case_assessments']+prior['hypothesis_results']:
        # A changed scientific review cannot leave a stale editorial delta ready.
        # The original preview remains recoverable from the source artifact.
        previous_preview=digest(result['memory_update'])
        result['memory_update'].update(status='deferred',operations=[],
            reason='clinical_memory_preview_requires_refresh',superseded_preview_digest=previous_preview)
        issues.append({'code':'clinical_memory_preview_requires_refresh','phase':'product_memory_preview'})
    if 'memory_preview' in plan['selected_work_ids']:
        memory=read_product_memory(inputs,request)
        accepted=[row for row in items if row['accepted']]
        result['memory_update']=preview_memory(runner,request,memory,accepted,ledger.rows(),stages,issues)
        result['memory_update']['class_extension']=deepcopy(prior['memory_update'].get('class_extension',{}))
        if result['memory_update']['status']!='deferred':
            retained_issues=[row for row in retained_issues if row.get('phase')!='product_memory_preview']
    result['quality']['issues']=list({digest(row):row for row in retained_issues+issues}.values())
    result['quality']['required_roles_completed']['evidence_critic']=all(row['review_status']=='automated_reviewed' for row in items)
    result['execution']={'stages':[stage.summary() for stage in stages],
        'prior_stages':deepcopy(prior['execution'].get('prior_stages',[])+prior['execution']['stages']),
        'inherited_logical_agent_calls':prior['execution'].get('inherited_logical_agent_calls',0)+prior['execution']['logical_agent_calls'],
        'input_reconciliation':{'stages':[stage.summary() for stage in runner.reconciliation_stages],
            'receipts':deepcopy(runner.reconciliation_receipts),'source_text_changed':False},
        **budget.proof(),'resume':{'available':False,'reason':'explicit_selected_work_continuation'}}
    pending=deferred_work(result,runner.task_packets)
    resolved=[]
    for task in plan['tasks']:
        if task['disposition']=='review' and set(task['item_ids'])<=completed_ids:
            resolved.append(task['work_id'])
        elif task['disposition']=='memory_preview' and result['memory_update']['status']!='deferred':
            resolved.append(task['work_id'])
    pending['objects']={**deepcopy(prior['deferred_work']['objects']),**pending['objects']}
    old_pending=[row for row in prior['deferred_work']['tasks'] if row['work_id'] not in resolved
        and not (row.get('kind')=='candidate_review' and row.get('item_id') in completed_ids)]
    pending['tasks']=list({row['work_id']:row for row in old_pending+pending['tasks']}.values())
    result['deferred_work']=pending
    result['execution']['disposition']=execution_disposition(result)
    result['quality']['status']='completed' if not result['quality']['issues'] and not pending['tasks'] and all(result['quality']['required_roles_completed'].values()) else 'partial'
    result['reason_graph']=build_reason_graph(result['subject'],items,result['evidence'],
        case_scope=request['context'].get('case_scope'),terminology=result['prepared_sources']['terminology'])
    result['publication_readiness']={'status':'prepared_for_governed_publication' if request.get('prepare_result_for_persistence') else 'not_requested',
        'artifact_quality':result['quality']['status'],'unreviewed_candidates_are_not_conclusions':True,
        'deferred_work_count':len(pending['tasks']),'policy_and_runtime_receipt_required':True,'publication_confirmed':False}
    result=finalize_output(result);validate_result(result)
    receipt={**plan,'resolved_work_ids':resolved,'remaining_work_count':len(pending['tasks']),
        'new_logical_agent_calls':budget.calls,'source_text_changed':False,
        'unchanged_source_ledger':digest(result['evidence'])==plan['source_evidence_digest'],
        'original_result_rewritten':False}
    outputs={'clinical_intelligence':result,'continuation_receipt':receipt}
    if request.get('prepare_result_for_persistence'):outputs['clinical_intelligence_records']={'records':[deepcopy(result)]}
    return {'response_version':'1','status':'success','outputs':outputs,'metrics':{'logical_agent_calls':budget.calls},'logs':[]}
