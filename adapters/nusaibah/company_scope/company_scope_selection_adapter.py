"""Resolve a bounded selector, preserving verified missing IDs without paid work."""
from typing import ClassVar
from adapters.base import Adapter
try:
    from . import scope_contract as contract
except ImportError:
    import scope_contract as contract

class CompanyScopeSelectionAdapter(Adapter):
    key: ClassVar[str]='nusaibah.company_scope'
    version: ClassVar[str]='0.1.2'
    def invoke(self,inputs,context):
        del context
        if not isinstance(inputs,dict) or set(inputs)!={'variables','companies'}:
            raise contract.CompanyScopeError('company_scope_input_invalid')
        request=contract.normalize_selector(inputs['variables'])
        rows,lake=contract._source_envelope(inputs['companies'])
        contexts=contract.assemble_record_contexts(rows,lake,requested_ids=set(request.company_ids))
        found={record.company_id:record for record in contexts}
        missing=[cid for cid in request.company_ids if cid not in found]
        result={'schema_version':contract.RESULT_SCHEMA,'selector_kind':request.selector_kind,
            'requested_company_ids':list(request.company_ids),'duplicate_id_count':request.duplicate_id_count,
            'company_count':len(found),'corporate_id':contract.CORPORATE_ID,'complete':True,
            'resolution':'not_found' if not found else 'partial' if missing else 'resolved',
            'missing_company_ids':missing,'validation_scope':'resolved_rows_only',
            'runtime_authority_verified':False,
            'records':[found[cid].to_dict() for cid in request.company_ids if cid in found]}
        result['digest']=contract.canonical_digest(result)
        return {'response_version':'1','status':'success','outputs':{'company_scope_result':result,
            'company_scope_summary':{'schema_version':'company_scope_summary.v1','company_count':len(found),
                'missing_company_count':len(missing),'complete':True,'max_company_ids':contract.MAX_COMPANY_IDS,
                'agent_call_count':0,'mutable_call_count':0}},
            'metrics':{'company_count':len(found),'agent_call_count':0,'mutable_call_count':0}}
