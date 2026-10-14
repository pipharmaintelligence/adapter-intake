"""Publish validated enrichment through existing Core Skill capabilities, no human gate."""
import re
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .skill_publication_v0_1_42 import apply_section as _apply_section,EnrichmentPublicationError
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy
    from skill_publication_v0_1_42 import apply_section as _apply_section,EnrichmentPublicationError
from devtools.skill_citation import CitationRef
try:
    from .skill_initialization_v0_1_42 import initialize_section
    from .skill_reads_v0_1_40 import read_company_memory,load_methodology_learning
except ImportError:
    from skill_initialization_v0_1_42 import initialize_section
    from skill_reads_v0_1_40 import read_company_memory,load_methodology_learning

def diagnostic(error):
    code=getattr(error,'code',None)
    return {'failure_code':code if isinstance(code,str) and re.fullmatch(r'[a-z][a-z0-9_.]{0,100}',code)
            else 'skill_apply_or_readback_unconfirmed','error_type':type(error).__name__,
            'publication_rule':error.rule if isinstance(error,EnrichmentPublicationError) else None}

def no_write(reason):
    return {'status':'withheld','reason':reason,'change_id':None,'readback_verified':False,'history_verified':False}

def _publish_supported(inputs,state):
    row={'company_id':state['company_id'],'memory':None,'methodology':None,
        'human_approval_required':False,'storage_authority':'core_dynamic_skill','cross_skill_atomic':False}
    if state.get('incomplete_schema_preview'):
        row.update(memory=no_write('enrichment_unresolved'),methodology=no_write('enrichment_unresolved'))
        row['publication_complete']=False;return row
    candidate=state['memory_candidate'];selection=state['evidence_selection'];critic=state['critic']
    selected={c['claim_id']:c for c in state['joined_research']['claims']}
    exact=all(f in selected and (selected[f].get('source_spans') or selected[f].get('native_grounding')) for f in candidate.fact_ids)
    sections={selected[f]['section_id'] for f in candidate.fact_ids if f in selected}
    reviewed=set(critic.get('reviewed_claim_ids',[]))-set(critic.get('rejected_claim_ids',[]))
    checks={'selected_claim_critic_complete':set(candidate.fact_ids).issubset(reviewed),
            'selected_evidence_complete':(selection.complete or not candidate.fact_ids) and exact,
                        'baseline_preserved':state['result']['section_enrichment']['baseline_preserved'] or not state['before_target_text']}
    row['enrichment_checks']=checks
    row['benchmark_observation']=state['result'].get('benchmark_observation',{})
    if not all(checks.values()):
        row.update(memory=no_write('enrichment_validation_incomplete'),methodology=no_write('enrichment_validation_incomplete'))
        row['publication_complete']=False;return row
    memory=read_company_memory(inputs,company_id=state['company_id'],allow_absent=True)
    methodology,_=load_methodology_learning(inputs,company_id=state['company_id'])
    proposals=[('memory','company_memory','company_memory_update',candidate.target_section,candidate.markdown,
                state['before_digest'],memory['handle']),
               ('methodology','company_methodology','company_methodology_update',legacy.METHODOLOGY_LEARNING_SECTION,
                state['methodology_learning_candidate'],state['result']['methodology_learning_before_digest'],methodology)]
    # Check initialized packages and all readonly baselines before any mutation.
    for name,role,_,_,text,before,handle in proposals:
        baseline=state['review_baselines'][role]['package_digest']
        if handle is None:
            # Absence is a valid first-run baseline. Existing baselines still
            # receive the unchanged digest/package checks before any write.
            if before is not None or baseline is not None:
                row.update(memory=no_write('baseline_changed'),methodology=no_write('baseline_changed'))
                row['publication_complete']=False;return row
            continue
        if (not isinstance(baseline,str) or handle.content_digest()!=before
            or handle.provenance().package_digest!=baseline):
            row.update(memory=no_write('baseline_changed'),methodology=no_write('baseline_changed'))
            row['publication_complete']=False;return row
    citations=[]
    for ref in selection.public_citations():
        citations.append(CitationRef(locator=ref['locator'],title=ref.get('title'),source_kind=ref['source_kind'],
            provider_family=ref.get('provider_family'),provider_turn_index=ref.get('provider_turn_index'),
            evidence_digest=ref.get('evidence_digest'),source_pointer=tuple(ref.get('source_pointer',()))))
    for name,role,update_role,section,text,before,_ in proposals:
        if row[name] is not None:continue
        if text is None or (name=='memory' and not state['candidate_changed']):
            row[name]={'status':'no_change','change_id':None,'before_digest':before,'after_digest':before,
                       'readback_verified':before is not None,'history_verified':False,
                       'reason':'no_supported_new_facts' if name=='memory' else 'no_new_critic_guidance'};continue
        try:
            if before is None:
                require_facts = name=='memory' and not candidate.fact_ids and not state['result']['section_enrichment'].get('unverified_research')
                if require_facts:
                    row[name]=no_write('initial_memory_evidence_missing');continue
                row[name]=initialize_section(inputs,state['company_id'],role,update_role,section,text,
                                             citations if name=='memory' else (), company_name=state['company_name'])
            else:
                row[name]=_apply_section(inputs,state['company_id'],role,update_role,section,text,before,
                                        state['review_baselines'][role]['package_digest'],citations if name=='memory' else (), company_name=state['company_name'])
        except Exception as error:
            row[name]={'status':'apply_failed_or_unconfirmed','change_id':None,**diagnostic(error)}
            break
        if row[name]['status'] in {'committed_readback_unverified','initialized_readback_unverified'}:break
    row['publication_complete']=all(row[k] is not None and row[k]['status'] in {'applied','initialized','no_change'}
                                    for k in ('memory','methodology'))
    return row


def publish_company(inputs,state):
    try:
        from .no_enrichment_v0_1_39 import no_enrichment_publication
        from .continuation_v0_1_39 import allow_incomplete_continuation
    except ImportError:
        from no_enrichment_v0_1_39 import no_enrichment_publication
        from continuation_v0_1_39 import allow_incomplete_continuation
    if state.get('no_supported_enrichment') and not state['result'].get('section_enrichment',{}).get('unverified_research'):
        return no_enrichment_publication(inputs,state)
    if state.get('memory_candidate') is not None and not state['memory_candidate'].fact_ids and not state['result']['section_enrichment'].get('unverified_research'):
        state={**state,'candidate_changed':False}
    return allow_incomplete_continuation(_publish_supported(inputs,state))
