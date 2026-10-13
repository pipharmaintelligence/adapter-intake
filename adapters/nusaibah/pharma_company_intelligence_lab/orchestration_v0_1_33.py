"""One bounded targeted enrichment pass and automatic validated Core Skill publication."""
from dataclasses import replace
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .orchestration_v0_1_26 import invoke_v0_1_26
    from .invocation_recovery_v0_1_33 import InvocationRecoveryInputs,BoundedRecoveryInputs
    from .company_preparation_v0_1_33 import prepare_company_v0_1_33
    from .company_result_v0_1_21 import augment_incomplete_company_state_v0_1_21
    from .candidate_validation_v0_1_21 import CandidateContractError
    from .automatic_publication_v0_1_29 import publish_company
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy
    from orchestration_v0_1_26 import invoke_v0_1_26
    from invocation_recovery_v0_1_33 import InvocationRecoveryInputs,BoundedRecoveryInputs
    from company_preparation_v0_1_33 import prepare_company_v0_1_33
    from company_result_v0_1_21 import augment_incomplete_company_state_v0_1_21
    from candidate_validation_v0_1_21 import CandidateContractError
    from automatic_publication_v0_1_29 import publish_company

def invoke_v0_1_33(inputs,*,asset_identity):
    request=legacy.validate_batch_request(inputs)
    if legacy.portfolio_review_passes(inputs)!=1:
        raise ValueError('0.1.33 performs one targeted enrichment pass; portfolio_review_passes must equal 1')
    if len(request.company_ids)>2:
        raise ValueError('Use bounded company work items; 0.1.33 permits at most two companies per execution')
    if inputs['variables'].get('review_decision') is not None or inputs.get('reviewed_result') is not None:
        raise ValueError('0.1.33 enriches the supplied CompanyContext directly; no caller review packet is used')
    preflight=inputs['variables'].get('preflight_only',False)
    if type(preflight) is not bool:raise ValueError('preflight_only must be boolean')
    if preflight:
        if request.memory_mode!='preview':raise ValueError('preflight_only is readonly')
        return invoke_v0_1_26(inputs,asset_identity=asset_identity)
    if request.publish_dossier:
        raise ValueError('This execution publishes Dynamic Skills; dossier node publication requires its own declared output policy')
    records=legacy.order_records_for_request(legacy.resolve_company_context(inputs,company_ids=request.company_ids),request)
    methodology=legacy.load_methodology(inputs)
    legacy._require_runtime_helpers(inputs)
    try:
        from .agent_chunks_v0_1_33 import ChunkCoordinator,MeasuredDispatchInputs
    except ImportError:
        from agent_chunks_v0_1_33 import ChunkCoordinator,MeasuredDispatchInputs
    import json
    from pathlib import Path
    manifest=json.loads(Path(__file__).with_name('nusaibah_pharma_company_intelligence_lab.asset.json').read_text(encoding='utf-8'))
    agents=manifest['versions']['0.1.33']['agents']
    prompt_chars={role:len(contract['definition']['chain']['steps'][0]['input']['text'])
        for role,contract in agents.items() if isinstance(contract.get('definition'),dict)}
    variables=inputs['variables']
    coordinator=ChunkCoordinator(parallelism=variables.get('agent_chunk_parallelism',2),
        input_chars=variables.get('agent_chunk_input_chars',42000),
        max_calls=variables.get('agent_chunk_max_calls',48),prompt_chars=prompt_chars)
    forwarded=InvocationRecoveryInputs(MeasuredDispatchInputs(inputs,coordinator))
    bounded=BoundedRecoveryInputs(forwarded,request,review_passes=1,coordinator=coordinator)
    forwarded.bind_recovery(bounded)
    states=[]
    # Readonly preparation is an internal phase of the same execution, not another workflow.
    preparation_request=replace(request,memory_mode='preview')
    for record in records:
        progress={}
        try:
            state=prepare_company_v0_1_33(bounded,request=preparation_request,record=record,
                methodology=methodology,review_passes=1,progress=progress)
        except (legacy.UnresolvedAgentResponse,CandidateContractError,legacy.AgentContractValidationError) as error:
            if isinstance(error,legacy.AgentContractValidationError) and not legacy.recoverable_quality(error):
                # These codes describe untrusted model business echoes, not Core admission or runtime authentication.
                if error.code not in {'pharma_agent_company_id_invalid','pharma_agent_role_invalid'}:raise
            detail=error.diagnostic if isinstance(error,legacy.UnresolvedAgentResponse) else error.proof_failure_detail
            if not isinstance(detail,dict):
                detail=legacy.evidence_diagnostic(role='orchestration',stage='agent_response_payload',
                    field='business_identity',rule='business_identity_invalid')
            state=legacy._incomplete_company_state(bounded,record=record,diagnostic=detail,progress=progress)
            state=augment_incomplete_company_state_v0_1_21(state)
        states.append(state)
    # Admit the complete retained business result before any Core mutation.
    # Publication receipts get a separate 64 KiB allowance; never truncate a
    # candidate and then publish it, or discover an output cap after a write.
    from hashlib import sha256
    probe={'company_results':[s['result'] for s in states],
        'agent_input_preflight':coordinator.proof(),
        'research_response_observations':forwarded.observations,
        'agent_invocation_response_issues':forwarded.invocation_issues}
    encoded=json.dumps(probe,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
    if len(encoded)>448*1024:
        detail=legacy.evidence_diagnostic(role='orchestration',stage='retention_admission',
            field='dossier',rule='retention_budget_exceeded_publication_withheld')
        for state in states:
            previous=state['result']
            state['incomplete_schema_preview']=True
            state['result']={'company_id':state['company_id'],'company_name':previous.get('company_name'),
                'review_outcome':'incomplete','research_incomplete':True,
                'issues_annex':{'unresolved':[detail],'canonical_candidates_withheld':True},
                'retention_admission':{'status':'incomplete','publication_withheld':True,
                    'original_size_bytes':len(encoded),'original_sha256':sha256(encoded).hexdigest(),
                    'candidate_truncated':False,'business_body_retained':False}}
    rows=[]
    for state in states:
        result=state['result']
        # Qualification-era human-review fields do not describe production enrichment.
        for key in list(result):
            if 'independent_review' in key or 'pre_review' in key or key in {'automated_quality_gate_passed','memory_mutation_eligible','methodology_learning_apply_authority'}:
                result.pop(key)
        result['human_approval_required']=False
        result['agent_input_preflight']=coordinator.proof()
        result['benchmark_enabled']=False
        result['benchmark_observation']={'status':'disabled','enabled':False,'scores_known':False,'is_publication_authority':False}
        result['benchmark_non_regression']=None
        result['benchmark_improvement_count']=None
        for phase in ('before','after'):
            for field in ('covered_count','partially_covered_count'):result['benchmark_'+phase+'_'+field]=None
        result['benchmark_agent_call_count']=bounded.company_agent_counts(state['company_id']).get(legacy.BENCHMARK_ROLE,0)
        result['search_enabled_agent_call_count']=0
        result['enrichment_stage']='one_targeted_pass'
        result['agent_response_recovery_trace']=bounded.company_recovery_trace(state['company_id'])
        if request.memory_mode=='apply':
            publication=publish_company(inputs,state)
        else:
            publication={'company_id':state['company_id'],'publication_complete':False,'status':'not_requested'}
        result['skill_publication']=publication
        # Keep role-level exhaustion visible even when surviving sections publish.
        unresolved=state.get('joined_research',{}).get('unresolved_research_responses')
        if unresolved is not None:result['unresolved_agent_responses']=unresolved
        annex=result.get('issues_annex')
        if isinstance(annex,dict):
            annex['canonical_candidates_withheld']=not publication['publication_complete']
        result['memory_update_status']=(publication.get('memory') or {}).get('status','not_requested')
        result['methodology_learning_update_status']=(publication.get('methodology') or {}).get('status','not_requested')
        result['section_enrichment_checks']=(state.get('critic') or state.get('progress',{}).get('critic',{})).get('section_outcomes',[])
        result['source_admitted_claim_count']=result.get('accepted_claim_count',0)
        for name,prefix in (('memory','memory'),('methodology','methodology_learning')):
            receipt=publication.get(name) or {}
            result[prefix+'_change_id']=receipt.get('change_id')
            result[prefix+'_after_digest']=receipt.get('after_digest')
            result[prefix+'_readback_verified']=receipt.get('readback_verified',False)
            result[prefix+'_history_verified']=receipt.get('history_verified',False)
        result['business_result_state']='enriched_and_published' if publication['publication_complete'] else 'enrichment_ready_or_partial'
        rows.append(result)
    complete=request.memory_mode=='apply' and all(r['skill_publication']['publication_complete'] for r in rows)
    dossier={'schema_version':'pharma_company_intelligence_dossier.v1','status':'completed',
        'requested_company_count':len(records),'completed_company_count':len(rows),'failed_company_count':0,
        'business_result_state':'enriched_and_published' if complete else 'enrichment_ready_or_partial',
        'human_approval_required':False,'publication_complete':complete,'portfolio_review_passes':1,
        'company_results':rows,'research_response_observations':forwarded.observations,
        'agent_invocation_response_issues':forwarded.invocation_issues}
    legacy.require_output_bound(dossier)
    return {'response_version':'1','status':'success','outputs':{'intelligence_dossier':dossier},'metrics':{
        'agent_call_count':coordinator.calls,'portfolio_review_pass_count':sum(r.get('portfolio_review_pass_count',0) for r in rows),
        'memory_mutations_made':sum((r['skill_publication'].get('memory') or {}).get('status')=='applied' for r in rows),
        'methodology_learning_mutations_made':sum((r['skill_publication'].get('methodology') or {}).get('status')=='applied' for r in rows)}}
