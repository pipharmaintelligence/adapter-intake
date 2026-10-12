"""Exact reviewed-packet consumption through the existing Dynamic Skill lane.

No Agents, source re-query, storage client, or invented approval. Core owns
authenticated retained-input hydration, mutable admission, upload, CAS/history.
"""
from hashlib import sha256
import json,re
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy

def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()

class ReviewedApplyError(ValueError):
    def __init__(self,rule):
        self.code='pharma_reviewed_apply_rejected'
        self.proof_failure_detail={'schema_version':'proof_failure_detail.v1','proof_kind':'review_authority',
            'role':'reviewed_result','stage':'pre_mutation','rule':rule}
        super().__init__(self.code)

def require(condition,rule):
    if not condition:
        raise ReviewedApplyError(rule)

def failure_detail(error):
    code=getattr(error,'code',None)
    safe=code if isinstance(code,str) and re.fullmatch(r'[a-z][a-z0-9_.]{0,100}',code) else 'skill_apply_or_readback_unconfirmed'
    detail={'failure_code':safe,'error_type':type(error).__name__}
    if isinstance(error,ReviewedApplyError):
        detail['proof_failure_detail']=error.proof_failure_detail
    return detail

def _apply_section(inputs,company_id,role,update_role,section,text,baseline_digest,baseline_package_digest,citations):
    update=inputs.dynamic_skill(update_role,variables={'company_id':str(company_id)})
    require(update.provenance().mutable is True,'mutable_role_required')
    require(update.content_digest()==baseline_digest,'baseline_stale')
    require(update.provenance().package_digest==baseline_package_digest,'package_baseline_stale')
    targets=update.find_sections(section)
    require(len(targets)==1,'section_ambiguous')
    changes=update.new_changeset().replace_section(targets[0].path,text.rstrip()+'\n')
    for citation in citations:
        changes=changes.add_citation(targets[0].path,citation)
    preview=update.preview(changes)
    require(preview.diff.old_digest==baseline_digest,'baseline_stale')
    if preview.diff.new_digest==baseline_digest:
        return {'status':'no_change','before_digest':baseline_digest,'after_digest':baseline_digest,
            'change_id':None,'readback_verified':True,'history_verified':False}
    receipt=update.apply(changes,expected_digest=baseline_digest)
    committed={'status':'applied','before_digest':receipt.before_content_digest,
        'after_digest':receipt.after_content_digest,'change_id':receipt.change_id,
        'readback_verified':False,'history_verified':False}
    # Keep a real commit receipt even if a later readback fails.
    try:
        fresh=inputs.dynamic_skill(role,variables={'company_id':str(company_id)})
        require(fresh.provenance().mutable is False,'readonly_readback_required')
        require(fresh.content_digest()==receipt.after_content_digest,'readback_digest_mismatch')
        require(fresh.section_text(section).strip()==text.strip(),'readback_text_mismatch')
        committed['readback_verified']=True
        fresh_update=inputs.dynamic_skill(update_role,variables={'company_id':str(company_id)})
        require(fresh_update.provenance().mutable is True,'mutable_history_required')
        require(fresh_update.content_digest()==receipt.after_content_digest,'history_baseline_mismatch')
        latest=fresh_update.history(limit=50).latest_change()
        require(latest is not None and latest.change_id==receipt.change_id
                and latest.after_content_digest==receipt.after_content_digest,'history_receipt_mismatch')
        committed['history_verified']=True
    except Exception as error:
        committed['status']='committed_readback_unverified'
        committed.update(failure_detail(error))
    return committed

def apply_reviewed(inputs,request,*,asset_identity):
    handoff=inputs.get('reviewed_result')
    require(isinstance(handoff,dict) and set(handoff)=={'value','provenance'},'retained_result_required')
    provenance=handoff['provenance']
    require(isinstance(provenance,dict) and set(provenance)=={'source','authority','run_uuid',
        'asset_identity','output_role','checksum_sha256'},'retained_provenance_invalid')
    require(provenance['source']=='retained_asset_output' and provenance['authority']=='core_artifact'
        and provenance['asset_identity']==asset_identity and provenance['output_role']=='intelligence_dossier'
        and isinstance(provenance['run_uuid'],str) and re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',provenance['run_uuid'])
        and isinstance(provenance['checksum_sha256'],str) and re.fullmatch(r'[a-f0-9]{64}',provenance['checksum_sha256']),
        'retained_provenance_invalid')
    dossier=handoff['value']
    require(isinstance(dossier,dict) and dossier.get('business_result_state')=='review_pending','prepared_result_incomplete')
    packet=dossier.get('review_packet')
    require(isinstance(packet,dict) and packet.get('schema_version')=='pharma_prepared_review.v2'
        and packet.get('asset_identity')==asset_identity and packet.get('apply_authority') is False,
        'review_packet_invalid')
    packet_digest='sha256:'+sha256(canonical({k:v for k,v in packet.items() if k!='packet_sha256'})).hexdigest()
    require(packet.get('packet_sha256')==packet_digest,'packet_digest_mismatch')
    review=inputs['variables'].get('review_decision')
    review_fields={'schema_version','decision','reviewer_name','qualification_basis','source_run_uuid',
        'source_checksum_sha256','packet_sha256','companies'}
    require(isinstance(review,dict) and set(review)==review_fields and review.get('schema_version')=='pharma_independent_review.v1'
        and review.get('decision')=='approve','independent_review_required')
    require(all(isinstance(review[k],str) and 0<len(review[k].strip())<=500 for k in ('reviewer_name','qualification_basis')),
        'reviewer_attestation_required')
    require(review['source_run_uuid']==provenance['run_uuid'] and review['source_checksum_sha256']==provenance['checksum_sha256']
        and review['packet_sha256']==packet_digest,'review_source_mismatch')
    company_packets=packet.get('companies'); decisions=review.get('companies')
    require(isinstance(company_packets,list) and isinstance(decisions,list)
        and [c.get('company_id') for c in company_packets]==list(request.company_ids)
        and [c.get('company_id') for c in decisions]==list(request.company_ids),'company_scope_mismatch')
    context={k:v for k,v in inputs.items() if k!='reviewed_result'}
    legacy.order_records_for_request(legacy.resolve_company_context(context,company_ids=request.company_ids),request)
    methodology=legacy.load_methodology(inputs)
    require(methodology.package_digest==packet['fixed_methodology_digest'],'methodology_changed')
    prepared=[]
    # Validate every exact proposal and readonly baseline before any mutable role.
    for company,decision in zip(company_packets,decisions):
        company_id=company['company_id']
        require(set(decision)=={'company_id','memory_replacement_sha256','methodology_replacement_sha256','approved_fact_ids'},
            'review_company_shape')
        require(company.get('preparation_status')=='review_pending' and company.get('apply_authority') is False,
            'company_incomplete')
        memory=company['memory_proposal']; learning=company['methodology_proposal']
        require(memory.get('pre_review_candidate_eligible') is True,'candidate_not_eligible')
        require(decision['approved_fact_ids']==memory['fact_ids'],'fact_review_mismatch')
        for proposal,key in ((memory,'memory_replacement_sha256'),(learning,'methodology_replacement_sha256')):
            text=proposal.get('replacement_text')
            if text is None:
                require(proposal is learning and decision[key] is None,'proposal_missing')
            else:
                require(isinstance(text,str) and 0<len(text)<=24000,'proposal_text_invalid')
                value='sha256:'+sha256(text.encode()).hexdigest()
                require(value==proposal['replacement_sha256']==decision[key],'replacement_digest_mismatch')
        before=legacy._read_company_memory(inputs,company_id=company_id,allow_absent=False)
        learning_handle,_=legacy._load_methodology_learning(inputs,company_id=company_id)
        require(before['digest']==memory['baseline_content_digest'],'memory_baseline_stale')
        require(before['handle'].provenance().package_digest==memory.get('baseline_package_digest'),
                'memory_package_baseline_stale')
        if learning.get('replacement_text') is not None:
            require(learning_handle is not None and learning_handle.content_digest()==learning['baseline_content_digest'],
                'methodology_baseline_stale')
            require(learning_handle.provenance().package_digest==learning.get('baseline_package_digest'),
                    'methodology_package_baseline_stale')
        require(memory['target_section']==legacy.MEMORY_TARGET_SECTION and learning['target_section']==legacy.METHODOLOGY_LEARNING_SECTION,
            'section_scope_invalid')
        require(company['benchmark']['projected']['company_id']==company_id,'benchmark_company_mismatch')
        citations=[]
        from devtools.skill_citation import CitationRef
        for c in company['memory_apply_citations']:
            citations.append(CitationRef(locator=c['locator'],title=c.get('title'),source_kind=c['source_kind'],
                provider_family=c.get('provider_family'),provider_turn_index=c.get('provider_turn_index'),
                evidence_digest=c.get('evidence_digest'),source_pointer=tuple(c.get('source_pointer',()))))
        require(bool(citations) and len(citations)<=legacy.MAX_CITATIONS_PER_COMPANY,'citation_selection_invalid')
        prepared.append((company,citations))
    results=[]
    for company,citations in prepared:
        row={'company_id':company['company_id'],'memory':None,'methodology':None}
        for role,update_role,proposal,cites in (
            ('company_memory','company_memory_update',company['memory_proposal'],citations),
            ('company_methodology','company_methodology_update',company['methodology_proposal'],())):
            name='memory' if role=='company_memory' else 'methodology'
            if proposal.get('replacement_text') is None:
                row[name]={'status':'no_change','change_id':None}
                continue
            try:
                row[name]=_apply_section(inputs,company['company_id'],role,update_role,proposal['target_section'],
                    proposal['replacement_text'],proposal['baseline_content_digest'],proposal['baseline_package_digest'],cites)
            except Exception as error:
                # Do not retry a possibly committed upload, or hide earlier receipts.
                row[name]={'status':'apply_failed_or_unconfirmed','change_id':None,**failure_detail(error)}
                break
            if row[name]['status']=='committed_readback_unverified':
                break
        results.append(row)
    complete=all(all(c.get(k) is not None and c[k]['status'] in {'applied','no_change'} for k in ('memory','methodology')) for c in results)
    output={'schema_version':'pharma_reviewed_apply.v1','status':'completed' if complete else 'partial_or_unconfirmed',
        'requested_company_count':len(request.company_ids),
        'completed_company_count':sum(all(c.get(k) is not None and c[k]['status'] in {'applied','no_change'} for k in ('memory','methodology')) for c in results),
        'failed_company_count':sum(any(c.get(k) is None or c[k]['status'] not in {'applied','no_change'} for k in ('memory','methodology')) for c in results),
        'source_run_uuid':provenance['run_uuid'],'source_checksum_sha256':provenance['checksum_sha256'],
        'packet_sha256':packet_digest,'independent_review_status':'approved_by_caller',
        'reviewer_name':review['reviewer_name'],'qualification_basis':review['qualification_basis'],
        'company_results':results,'agent_call_count':0,'storage_authority':'core_dynamic_skill',
        'cross_skill_atomic':False,'publication_complete':complete}
    return {'response_version':'1','status':'success','outputs':{'intelligence_dossier':output},
        'metrics':{'agent_call_count':0,'memory_mutations_made':sum(c['memory'] is not None and c['memory']['status']=='applied' for c in results),
        'methodology_learning_mutations_made':sum(c['methodology'] is not None and c['methodology']['status']=='applied' for c in results)}}
