"""Explicit bounded correction of rejected business items, never a transport replay."""
from copy import deepcopy
if __package__:
    from .contracts_v0_1_8 import digest
else:
    from contracts_v0_1_8 import digest


def correct_business(runner, request, stage, *, packet_data, obligations,
                     rejected_items, errors, downstream_reserve=0):
    """Correct only completed, identity-validated business output, with the same evidence.

    The original stage/digest is retained in execution. This is neither permission
    to retry unknown provider outcomes nor to accept a model's corrected assertions.
    The caller must re-run the same evidence/identity validators on the result.
    """
    if not request['enable_refinement'] or not stage.payload or not rejected_items:
        return None
    key=digest([stage.task_id,rejected_items,errors])
    if not runner.budget.admit_business_repair(key):
        return None
    data={**deepcopy(packet_data),'business_correction':{
        'attempt':1,'original_task_id':stage.task_id,'original_output_digest':digest(stage.payload),
        'rejected_items':deepcopy(rejected_items),'validation_errors':deepcopy(errors),
        'instruction':'Return only the assigned rejected item identities, corrected against the SAME supplied evidence. For source spans copy exact literal source text and its provided digest; never paraphrase a quote. Critic references must remain subsets of each candidate original support/contra sets with unchanged polarity. If support is insufficient, return an unresolved/needs_evidence verdict, not an invented correction. Do not repeat valid siblings or broaden source authority.'}}
    return runner.call(stage.role,request,task_id='business_fix:'+key.split(':')[1][:24],
        obligations=obligations,packet_data=data,downstream_reserve=downstream_reserve)
