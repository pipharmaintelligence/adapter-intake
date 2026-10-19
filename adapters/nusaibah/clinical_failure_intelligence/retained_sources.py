"""Consume exact Assets-hydrated retained source outputs without transport code.

Assets admits only run_uuid references and hydrates the exact client/producer/
role/checksum. Local construction of this shape is not signed-execution proof.
"""
from copy import deepcopy
import re
if __package__:
    from .contracts import digest, object_fields, require
else:
    from contracts import digest, object_fields, require

UUID = re.compile(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\Z')
SHA = re.compile(r'[a-f0-9]{64}\Z')
SOURCE_ROLES = {
    'trial_study_result': ('nusaibah.clinical_trials_lookup','0.1.1','trial_result',('study_get',),'case'),
    'trial_results_result': ('nusaibah.clinical_trials_lookup','0.1.1','trial_result',('results_get',),'case'),
    'literature_search_result': ('nusaibah.pubmed_evidence','0.1.0','literature_result',('trial_publications','article_search'),'case'),
    'literature_metadata_result': ('nusaibah.pubmed_evidence','0.1.0','literature_result',('article_get','article_batch'),'case'),
    'terminology_source_result': ('umls_terminology','0.1.1','terminology_result',('search',),'terminology'),
}
for index in range(1,4):
    SOURCE_ROLES['literature_abstract_'+str(index)+'_result'] = (
        'nusaibah.pubmed_evidence','0.1.0','literature_result',('abstract_get',),'case')
    SOURCE_ROLES['literature_integrity_'+str(index)+'_result'] = (
        'nusaibah.pubmed_evidence','0.1.0','literature_result',('integrity_get',),'case')


def prepare_retained_bundle(inputs, request):
    """Construct the normal clinical bundle from independently admitted source runs."""
    selected = [role for role in SOURCE_ROLES if role in inputs]
    if not selected:
        return None
    require(inputs.get('clinical_evidence') is None,'clinical_source_handoff_ambiguous')
    sources, identities = [], set()
    for role in selected:
        asset, version, output, operations, purpose = SOURCE_ROLES[role]
        envelope = object_fields(inputs[role], {'value','provenance'})
        provenance = object_fields(envelope['provenance'],
            {'source','authority','run_uuid','asset_identity','output_role','checksum_sha256'})
        require(provenance['source']=='retained_asset_output' and provenance['authority']=='core_artifact',
                'clinical_retained_source_authority_invalid')
        require(provenance['asset_identity']==asset+':'+version and provenance['output_role']==output,
                'clinical_retained_source_identity_mismatch')
        require(isinstance(provenance['run_uuid'],str) and UUID.fullmatch(provenance['run_uuid']) is not None
                and isinstance(provenance['checksum_sha256'],str) and SHA.fullmatch(provenance['checksum_sha256']) is not None,
                'clinical_retained_source_reference_invalid')
        value = envelope['value']
        require(isinstance(value,dict) and value.get('operation') in operations,
                'clinical_retained_source_operation_mismatch')
        identity = (provenance['run_uuid'], output)
        require(identity not in identities,'clinical_retained_source_duplicate')
        identities.add(identity)
        sources.append({'source_result_id':role+':'+provenance['run_uuid'], 'asset_key':asset,
            'asset_version':version,'output_role':output,'purpose':purpose,'result':deepcopy(value),
            'result_digest':digest(value),'execution_ref':provenance['run_uuid']})
    return {'schema_version':'clinical_evidence_bundle.v1',
            'bundle_id':'retained:'+digest([row['source_result_id'] for row in sources]).split(':')[1][:32],
            'subject_id':request['subject_id'],'product_id':request['context']['subject']['product_id'],
            'event_ids':deepcopy(request['event_ids']),'sources':sources}
