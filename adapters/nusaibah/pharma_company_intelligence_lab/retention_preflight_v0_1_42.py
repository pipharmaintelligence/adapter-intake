"""Run the runtime's real output checks before the first Skill mutation."""
from hashlib import sha256
import json
from devtools.preview_output_validator import validate_preview_outputs, PreviewOutputValidationError


def diagnostic(error):
    detail={'stage':'output_validation','rule':error.rule,'path':error.safe_path}
    value=getattr(error,'classification',None)
    if value is not None:detail['classification']=value
    return detail


def preflight_publication(states):
    for state in states:
        if state.get('memory_candidate') is None:continue
        candidate=state['memory_candidate']
        try:
            validate_preview_outputs({'proposed_skills':{'memory_text':candidate.markdown,
                'methodology_text':state.get('methodology_learning_candidate')}})
        except PreviewOutputValidationError as error:
            # Never publish material that cannot cross the same retention
            # boundary. Other companies remain independent work items.
            state['incomplete_schema_preview']=True
            state['no_supported_enrichment']=False
            state['result']={'company_id':state['company_id'],'status':'completed',
                'research_incomplete':True,'accepted_claim_count':0,
                'retention_admission':{'status':'blocked','publication_withheld':True,
                    'validation_detail':diagnostic(error)}}
            continue
        row=state['result'];omitted=[]
        # Optional raw source snapshots or unused model presentation must not
        # defeat retention of an independently safe, exact publication candidate.
        # Validate each field with the SAME generic validator; do not rewrite a
        # rejected value or smuggle it into a different exemption/record shape.
        for key,value in list(row.items()):
            try:validate_preview_outputs({'intelligence_dossier':{key:value}})
            except PreviewOutputValidationError as error:
                encoded=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
                omitted.append({'field':key,'sha256':sha256(encoded).hexdigest(),
                    'size_bytes':len(encoded),'validation_detail':diagnostic(error)})
                row.pop(key)
        # These fields are necessary for publication. An unexpectedly rejected
        # control field must not silently bypass an enrichment/baseline check.
        required={'section_enrichment','methodology_learning_before_digest','profile_document'}
        if not required.issubset(row):
            state['incomplete_schema_preview']=True
        row['retention_admission']={'status':'ready_with_omissions' if omitted else 'ready',
            'publication_withheld':bool(state.get('incomplete_schema_preview')),
            'exact_candidate_validated':True,'omitted_fields':omitted}
        if omitted:row['research_incomplete']=True
        validate_preview_outputs({'intelligence_dossier':row})
