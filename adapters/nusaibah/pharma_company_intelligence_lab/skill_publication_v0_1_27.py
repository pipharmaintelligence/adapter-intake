"""Existing Core Skill changesets with readback against exact SDK-rendered bytes."""
class EnrichmentPublicationError(ValueError):
    def __init__(self,rule):
        self.code='pharma_enrichment_publication_invalid';self.rule=rule
        super().__init__(self.code)

def require(value,rule):
    if not value:raise EnrichmentPublicationError(rule)

def apply_section(inputs,company_id,role,update_role,section,text,baseline_digest,baseline_package_digest,citations):
    update=inputs.dynamic_skill(update_role,variables={'company_id':str(company_id)})
    require(update.provenance().mutable is True,'mutable_role_required')
    require(update.content_digest()==baseline_digest,'baseline_stale')
    require(update.provenance().package_digest==baseline_package_digest,'package_baseline_stale')
    targets=update.find_sections(section);require(len(targets)==1,'section_ambiguous')
    target=targets[0].path
    changes=update.new_changeset().replace_section(target,text.rstrip()+'\n')
    for citation in citations:changes=changes.add_citation(target,citation)
    preview=update.preview(changes)
    require(preview.diff.old_digest==baseline_digest,'baseline_stale')
    expected_text=preview.document.section_text(target)
    if preview.diff.new_digest==baseline_digest:
        return {'status':'no_change','before_digest':baseline_digest,'after_digest':baseline_digest,
                'change_id':None,'readback_verified':True,'history_verified':False}
    receipt=update.apply(changes,expected_digest=baseline_digest)
    result={'status':'applied','before_digest':receipt.before_content_digest,'after_digest':receipt.after_content_digest,
            'change_id':receipt.change_id,'readback_verified':False,'history_verified':False}
    try:
        require(receipt.after_content_digest==preview.diff.new_digest,'commit_preview_digest_mismatch')
        fresh=inputs.dynamic_skill(role,variables={'company_id':str(company_id)})
        require(fresh.provenance().mutable is False,'readonly_readback_required')
        require(fresh.content_digest()==receipt.after_content_digest,'readback_digest_mismatch')
        require(fresh.section_text(section).strip()==expected_text.strip(),'readback_text_mismatch')
        result['readback_verified']=True
        fresh_update=inputs.dynamic_skill(update_role,variables={'company_id':str(company_id)})
        require(fresh_update.provenance().mutable is True,'mutable_history_required')
        require(fresh_update.content_digest()==receipt.after_content_digest,'history_baseline_mismatch')
        latest=fresh_update.history(limit=50).latest_change()
        require(latest is not None and latest.change_id==receipt.change_id
                and latest.after_content_digest==receipt.after_content_digest,'history_receipt_mismatch')
        result['history_verified']=True
    except Exception as error:
        result.update(status='committed_readback_unverified',failure_code=getattr(error,'code','skill_readback_unconfirmed'),
                      error_type=type(error).__name__)
    return result
