"""One fragment diagnosis by input_reconciler, then one validated original-role retry."""
from copy import deepcopy
if __package__:
    from .contracts_v0_1_13 import digest
    from .input_reconciliation_v0_1_13 import ask_reconciler,focus_data
else:
    from contracts_v0_1_13 import digest
    from input_reconciliation_v0_1_13 import ask_reconciler,focus_data


def correct_business(runner, request, stage, *, packet_data, obligations,
                     rejected_items, errors, downstream_reserve=0):
    """A proposed input cannot approve its own evidence or replay a whole workflow."""
    if not request['enable_refinement'] or not stage.payload or not rejected_items:return None
    data=focus_data(packet_data,rejected_items)
    answer=ask_reconciler(runner,request,stage,mode='retry_items',data=data,errors=errors,
        originals=rejected_items,downstream_reserve=downstream_reserve)
    if answer is None:return None
    plan,reconciler=answer
    key=digest([stage.role,stage.task_id,stage.input_digest])
    retry_data={**deepcopy(data),'business_correction':{
        'attempt':1,'failed_task_id':stage.task_id,'failed_output_digest':digest(stage.payload),
        'rejected_items':deepcopy(rejected_items),'validation_errors':deepcopy(errors),
        'instruction':'Return only the assigned rejected identities, using this affected input and complete source windows. The reconciler proposal is unapproved input, not scientific authority. Independently apply the original role contract. If literal support is missing or a reference cannot be used within its original polarity, report unresolved. Do not repeat valid siblings.'},
        'input_reconciliation_retry':{'original_task_id':stage.task_id,'original_input_digest':stage.input_digest,
            'reconciler_output_digest':digest(reconciler.payload),'guidance':plan['rationale'],
            'prepared_fragment':deepcopy(plan['prepared_items']),'source_text_changed':False}}
    retry=runner.call(stage.role,request,task_id='business_fix:'+key.split(':')[1][:24],
        obligations=obligations,packet_data=retry_data,downstream_reserve=downstream_reserve)
    retry.attempts=tuple(row.summary() for row in (stage,reconciler,retry))
    return retry
