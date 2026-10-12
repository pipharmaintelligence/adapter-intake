"""Benchmark the full deterministic Skill projection, not only its replacement section."""
try:
    from .candidate_validation_v0_1_21 import CandidateContractError
except ImportError:
    from candidate_validation_v0_1_21 import CandidateContractError

def projected_memory_document(handle,candidate,citations):
    if handle is None:return candidate.markdown
    from devtools.skill_changes import SkillChangeSet
    from devtools.skill_citation import CitationRef
    targets=handle.find_sections(candidate.target_section)
    if len(targets)!=1:
        raise CandidateContractError(rule='memory_target_section_ambiguous',field='memory_candidate.target_section')
    target=targets[0].path
    before=handle.section_text(target).rstrip()
    if before and not candidate.markdown.startswith(before):
        raise CandidateContractError(rule='memory_baseline_not_preserved',field='memory_candidate.markdown')
    changes=SkillChangeSet().replace_section(target,candidate.markdown.rstrip()+'\n')
    for c in citations:
        changes=changes.add_citation(target,CitationRef(locator=c['locator'],title=c.get('title'),
            source_kind=c['source_kind'],provider_family=c.get('provider_family'),provider_turn_index=c.get('provider_turn_index'),
            evidence_digest=c.get('evidence_digest'),source_pointer=tuple(c.get('source_pointer',()))))
    return changes.preview(handle.read()).source
