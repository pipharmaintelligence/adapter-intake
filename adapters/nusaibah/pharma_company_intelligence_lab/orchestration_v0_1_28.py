"""One bounded targeted enrichment pass and automatic validated Core Skill publication."""
from dataclasses import replace
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .orchestration_v0_1_26 import FinalBoundedAgentInputs,invoke_v0_1_26
    from .invocation_recovery_v0_1_26 import InvocationRecoveryInputs
    from .company_preparation_v0_1_28 import prepare_company_v0_1_28
    from .company_result_v0_1_21 import augment_incomplete_company_state_v0_1_21
    from .candidate_validation_v0_1_21 import CandidateContractError
    from .automatic_publication_v0_1_27 import publish_company
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy
    from orchestration_v0_1_26 import FinalBoundedAgentInputs,invoke_v0_1_26
    from invocation_recovery_v0_1_26 import InvocationRecoveryInputs
    from company_preparation_v0_1_28 import prepare_company_v0_1_28
    from company_result_v0_1_21 import augment_incomplete_company_state_v0_1_21
    from candidate_validation_v0_1_21 import CandidateContractError
    from automatic_publication_v0_1_27 import publish_company

def invoke_v0_1_28(inputs,*,asset_identity):
    request=legacy.validate_batch_request(inputs)
    if legacy.portfolio_review_passes(inputs)!=1:
        raise ValueError('0.1.28 performs one targeted enrichment pass; portfolio_review_passes must equal 1')
    if len(request.company_ids)>2:
        raise ValueError('Use bounded company work items; 0.1.28 permits at most two companies per execution')
    if inputs['variables'].get('review_decision') is not None or inputs.get('reviewed_result') is not None:
        raise ValueError('0.1.28 enriches the supplied CompanyContext directly; no caller review packet is used')
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
    forwarded=InvocationRecoveryInputs(inputs)
    bounded=FinalBoundedAgentInputs(forwarded,request,review_passes=1)
    # Four section critics replace one aggregate critic; all calls remain finite.
    bounded._role_limits[legacy.CRITIC_ROLE]=4
    bounded._ordinary_company_limit=15
    bounded._per_company_limit=30
    bounded._role_limits[legacy.RESEARCH_RESOLVER_ROLE]=15
    bounded.agent_call_limit=len(records)*30
    states=[]
    # Readonly preparation is an internal phase of the same execution, not another workflow.
    preparation_request=replace(request,memory_mode='preview')
    for record in records:
        progress={}
        try:
            state=prepare_company_v0_1_28(bounded,request=preparation_request,record=record,
                methodology=methodology,review_passes=1,progress=progress)
        except (legacy.UnresolvedAgentResponse,CandidateContractError,legacy.AgentContractValidationError) as error:
            if isinstance(error,legacy.AgentContractValidationError) and not legacy.recoverable_quality(error):raise
            detail=error.diagnostic if isinstance(error,legacy.UnresolvedAgentResponse) else error.proof_failure_detail
            state=legacy._incomplete_company_state(bounded,record=record,diagnostic=detail,progress=progress)
            state=augment_incomplete_company_state_v0_1_21(state)
        states.append(state)
    rows=[]
    for state in states:
        result=state['result']
        # Qualification-era human-review fields do not describe production enrichment.
        for key in list(result):
            if 'independent_review' in key or 'pre_review' in key or key in {'automated_quality_gate_passed','memory_mutation_eligible','methodology_learning_apply_authority'}:
                result.pop(key)
        result['human_approval_required']=False
        result['search_enabled_agent_call_count']=0
        result['enrichment_stage']='one_targeted_pass'
        result['agent_response_recovery_trace']=bounded.company_recovery_trace(state['company_id'])
        if request.memory_mode=='apply':
            publication=publish_company(inputs,state)
        else:
            publication={'company_id':state['company_id'],'publication_complete':False,'status':'not_requested'}
        result['skill_publication']=publication
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
        'agent_call_count':bounded.agent_call_count,'portfolio_review_pass_count':sum(r.get('portfolio_review_pass_count',0) for r in rows),
        'memory_mutations_made':sum((r['skill_publication'].get('memory') or {}).get('status')=='applied' for r in rows),
        'methodology_learning_mutations_made':sum((r['skill_publication'].get('methodology') or {}).get('status')=='applied' for r in rows)}}
