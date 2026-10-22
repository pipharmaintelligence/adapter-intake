"""Bounded editorial preview over reviewed derived findings, with full provenance.

Scientific acceptance happens in the evidence critic before this module. Memory
editing may summarize those exact reviewed findings; it cannot invent new clinical
claims or re-certify unseen raw windows. Full sources remain in the result ledger.
"""
from copy import deepcopy
if __package__:
    from .contracts_v0_1_8 import ContractError,digest,require
    from .business_recovery_v0_1_8 import correct_business
    from .input_reconciliation_v0_1_8 import ELIGIBLE_ERRORS
    from .product_memory_v0_1_8 import memory_projection,editor_contract,validate_edit_candidates,review_edit_plan
else:
    from contracts_v0_1_8 import ContractError,digest,require
    from business_recovery_v0_1_8 import correct_business
    from input_reconciliation_v0_1_8 import ELIGIBLE_ERRORS
    from product_memory_v0_1_8 import memory_projection,editor_contract,validate_edit_candidates,review_edit_plan


def memory_data(items,memory,evidence,case_scope):
    require(all(row.get('accepted') is True and row.get('review_status')=='automated_reviewed'
                for row in items),'clinical_memory_unreviewed_findings')
    return {'memory_context':memory_projection(memory),'accepted_items':deepcopy(items),
        'evidence_packet':[], 'case_scope':deepcopy(case_scope),'edit_contract':editor_contract(),
        'reviewed_findings_provenance':{'representation':'reviewed_derived_findings',
            'accepted_item_ids':[row['item_id'] for row in items],
            'accepted_items_digest':digest(items),'canonical_evidence_digest':digest(evidence),
            'canonical_evidence_count':len(evidence),'raw_sources_supplied':False,
            'instruction':'Summarize only these complete independently reviewed findings, preserving their exact scope, uncertainty and references. No new causal inference. Source text is retained in the canonical evidence ledger, not supplied here. Editorial review checks entailment from reviewed findings and preservation of the entire supplied old paragraph; it does not certify unseen raw sources.'}}


def memory_batches(items,packet,fits):
    batches,current=[],[]
    for item in items:
        if current and (len(current)>=32 or not fits(packet(current+[item]))):
            batches.append(current);current=[]
        current.append(item)
    if current:batches.append(current)
    return batches


def preview_memory(runner,request,memory,items,evidence,stages,issues):
    base=review_edit_plan([],None,memory,request)
    scope=request['context']['case_scope']
    def editor_packet(batch):
        return runner.packet('product_memory_editor',request,task_id='memory_edit:planning',
            obligations=['product_memory_delta'],packet_data=memory_data(batch,memory,evidence,scope))
    batches=memory_batches(items,editor_packet,lambda packet:runner.packet_fits('product_memory_editor',packet))
    candidates,verdicts=[],[]
    complete=True
    try:
        for index,batch in enumerate(batches):
            data=memory_data(batch,memory,evidence,scope)
            data['editorial_batch_scope']={'index':index,'total_batches':len(batches),
                'total_accepted_findings':len(items),'complete_case_findings':len(batch)==len(items)}
            editor=runner.call('product_memory_editor',request,task_id='memory_edit:'+str(index),
                obligations=['product_memory_delta'],downstream_reserve=1+2*(len(batches)-index-1),packet_data=data)
            stages.append(editor)
            complete=complete and editor.status=='completed'
            raw=deepcopy(editor.payload['items']) if editor.payload else []
            try:
                validate_edit_candidates(raw,memory,batch)
            except ContractError as original_error:
                if original_error.code not in ELIGIBLE_ERRORS:raise
                rejected,errors,good=[],[],[]
                for row in raw:
                    try:validate_edit_candidates([row],memory,batch)
                    except ContractError as error:
                        if error.code not in ELIGIBLE_ERRORS or not isinstance(row,dict) or not isinstance(row.get('edit_id'),str):raise
                        rejected.append(row);errors.append({'code':error.code,'edit_id':row['edit_id']})
                    else:good.append(row)
                fixed=correct_business(runner,request,editor,packet_data=data,
                    obligations=['correct_edit:'+row['edit_id'] for row in rejected],
                    rejected_items=rejected,errors=errors,downstream_reserve=1+2*(len(batches)-index-1))
                if fixed is None:raise original_error
                stages.append(fixed);complete=complete and fixed.status=='completed'
                revised=fixed.payload['items'] if fixed.payload else []
                allowed={row['edit_id'] for row in rejected}
                require(all(isinstance(row,dict) and row.get('edit_id') in allowed for row in revised),
                    'clinical_business_correction_scope_invalid')
                require({row['edit_id'] for row in revised}==allowed,'clinical_memory_correction_incomplete')
                raw=good+deepcopy(revised)
                validate_edit_candidates(raw,memory,batch)
            for row in raw:
                row['edit_id']='edit:'+str(index)+':'+digest(row['edit_id']).split(':')[1][:24]
            selected=validate_edit_candidates(raw,memory,batch)
            candidates.extend(selected)
            # Enforce the aggregate contract; no silently dropped excess edits.
            if len(candidates)>8:raise ContractError('clinical_memory_aggregate_edit_limit')
            for edit in selected:
                needed=[row for row in batch if row['item_id'] in edit['supporting_item_ids']]
                review_data=memory_data(needed,memory,evidence,scope)
                review_data.update(review_kind='product_memory_edits',candidate_edits=[edit],
                    memory_review_contract={'required_fields':['edit_id','accepted','scope_preserved',
                        'evidence_supported','prior_content_preserved','rationale']})
                critic=runner.call('evidence_critic',request,task_id='memory_review:'+edit['edit_id'],
                    obligations=['memory_review:'+edit['edit_id']],
                    downstream_reserve=2*(len(batches)-index-1),packet_data=review_data)
                stages.append(critic)
                complete=complete and critic.status=='completed'
                if critic.payload:verdicts.extend(critic.payload['items'])
        # Validate the joined edits again: different batches cannot overwrite the
        # same original paragraph. Every aggregate conflict fails closed.
        fields=set(editor_contract()['required_fields'])
        joined=validate_edit_candidates([{k:v for k,v in row.items() if k in fields}
                                        for row in candidates],memory,items)
        plan=review_edit_plan(joined,verdicts,memory,request)
        plan['editorial_batches']={'planned':len(batches),'accepted_findings':len(items),
            'review_source':'reviewed_derived_findings','all_stages_completed':complete}
        if not complete:plan.update(status='deferred',reason='clinical_memory_editorial_review_incomplete')
        return plan
    except ContractError as error:
        issues.append({'code':error.code,'phase':'product_memory_preview'})
        return {**base,'status':'deferred','reason':error.code}
