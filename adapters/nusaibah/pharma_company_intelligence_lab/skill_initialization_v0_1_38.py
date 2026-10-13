"""Construct one verified first Skill document; storage remains runtime/Core-owned."""
try:
    from .skill_publication_v0_1_37 import EnrichmentPublicationError
except ImportError:
    from skill_publication_v0_1_37 import EnrichmentPublicationError

def initialize_section(inputs,company_id,role,update_role,section,text,citations):
    from devtools.skill_changes import SkillChangeSet
    if not isinstance(text,str) or not text.strip():
        raise EnrichmentPublicationError('initial_content_missing')
    if role not in {'company_memory','company_methodology'}:
        raise EnrichmentPublicationError('initial_role_invalid')
    expected='Current Public Research' if role=='company_memory' else 'Methodology Learning'
    if section!=expected:
        raise EnrichmentPublicationError('initial_section_invalid')
    name=role.replace('_','-')
    seed=(f'---\nname: {name}\ndescription: Evidence-backed company {company_id} {role.removeprefix("company_")}.\n'
          f'---\n# Company {company_id}\n\n## {section}\n\n')
    changes=SkillChangeSet().replace_section(section,text.rstrip()+'\n')
    for citation in citations:changes=changes.add_citation(section,citation)
    preview=changes.preview(seed)
    result=inputs.initialize_dynamic_skill(update_role,variables={'company_id':str(company_id)},markdown=preview.source)
    if result.get('status')!='initialized':return result
    if not result.get('upload_verified') or not result.get('readback_verified') or not result.get('operation_id'):
        result=dict(result);result['status']='initialized_readback_unverified';return result
    try:
        fresh=inputs.dynamic_skill(role,variables={'company_id':str(company_id)})
        expected_text=preview.document.section_text(section)
        if fresh.provenance().mutable is not False or fresh.content_digest()!=preview.diff.new_digest or fresh.section_text(section).strip()!=expected_text.strip():
            raise EnrichmentPublicationError('initial_readback_mismatch')
    except Exception as error:
        result=dict(result);result.update(status='initialized_readback_unverified',readback_verified=False,
            error_type=type(error).__name__,publication_rule=getattr(error,'rule',None))
    return result
