"""Publish validated enrichment through existing Core Skill capabilities, no human gate."""
import re
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .skill_publication_v0_1_27 import apply_section as _apply_section
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy
    from skill_publication_v0_1_27 import apply_section as _apply_section
from devtools.skill_citation import CitationRef

def diagnostic(error):
    code=getattr(error,'code',None)
    return {'failure_code':code if isinstance(code,str) and re.fullmatch(r'[a-z][a-z0-9_.]{0,100}',code)
            else 'skill_apply_or_readback_unconfirmed','error_type':type(error).__name__}

def no_write(reason):
    return {'status':'withheld','reason':reason,'change_id':None,'readback_verified':False,'history_verified':False}

def publish_company(inputs,state):
    row={'company_id':state['company_id'],'memory':None,'methodology':None,
        'human_approval_required':False,'storage_authority':'core_dynamic_skill','cross_skill_atomic':False}
    if state.get('incomplete_schema_preview'):
        row.update(memory=no_write('enrichment_unresolved'),methodology=no_write('enrichment_unresolved'))
        row['publication_complete']=False;return row
    candidate=state['memory_candidate'];selection=state['evidence_selection'];critic=state['critic']
    selected={c['claim_id']:c for c in state['joined_research']['claims']}
    exact=all(f in selected and selected[f].get('source_spans') for f in candidate.fact_ids)
    sections={selected[f]['section_id'] for f in candidate.fact_ids if f in selected}
    validated={o['section_id'] for o in critic.get('section_outcomes',[]) if o['status']=='validated'}
    checks={'selected_section_critic_complete':sections.issubset(validated),
            'selected_evidence_complete':selection.complete and exact,
            'benchmark_is_advisory':True,
            'baseline_preserved':state['result']['section_enrichment']['baseline_preserved'] or not state['before_target_text']}
    row['enrichment_checks']=checks
    row['benchmark_observation']=state['result'].get('benchmark_observation',{})
    if not all(checks.values()):
        row.update(memory=no_write('enrichment_validation_incomplete'),methodology=no_write('enrichment_validation_incomplete'))
        row['publication_complete']=False;return row
    memory=legacy._read_company_memory(inputs,company_id=state['company_id'],allow_absent=True)
    methodology,_=legacy._load_methodology_learning(inputs,company_id=state['company_id'])
    proposals=[('memory','company_memory','company_memory_update',candidate.target_section,candidate.markdown,
                state['before_digest'],memory['handle']),
               ('methodology','company_methodology','company_methodology_update',legacy.METHODOLOGY_LEARNING_SECTION,
                state['methodology_learning_candidate'],state['result']['methodology_learning_before_digest'],methodology)]
    # Check initialized packages and all readonly baselines before any mutation.
    for name,role,_,_,text,before,handle in proposals:
        baseline=state['review_baselines'][role]['package_digest']
        if handle is None:
            row[name]=no_write('partition_package_not_initialized')
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
                       'readback_verified':True,'history_verified':False};continue
        try:
            row[name]=_apply_section(inputs,state['company_id'],role,update_role,section,text,before,
                                    state['review_baselines'][role]['package_digest'],citations if name=='memory' else ())
        except Exception as error:
            row[name]={'status':'apply_failed_or_unconfirmed','change_id':None,**diagnostic(error)}
            break
        if row[name]['status']=='committed_readback_unverified':break
    row['publication_complete']=all(row[k] is not None and row[k]['status'] in {'applied','no_change'}
                                    for k in ('memory','methodology'))
    return row
