"""Route canonical research tasks without paying an Agent to restate methodology."""
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .continuation_v0_1_39 import partial_plan
    from .dossier_contract import SECTION_BY_ID
    from .methodology_learning_v0_1_40 import read_guidance
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy
    from continuation_v0_1_39 import partial_plan
    from dossier_contract import SECTION_BY_ID
    from methodology_learning_v0_1_40 import read_guidance

def run_planner(inputs, *, company_id, learned_methodology_text, progress=None, **kwargs):
    chunks=[]
    for role,sections in legacy.RESEARCH_ROLE_SECTIONS.items():
        for section_id in sections:
            spec=SECTION_BY_ID[section_id]
            advice=read_guidance(learned_methodology_text,[section_id])
            questions=['Research '+s.title+' for the exact target company; distinguish historical and current evidence.' for s in spec.subsections]
            chunks.append({'section_id':section_id,'research_role':role,'priority':'high',
                'questions':questions+[g['next_action'] for g in advice[:2]],
                'freshness_focus':['Establish the date and entity scope of each material statement.'],
                'evidence_focus':['Use grounded discovery and inspect readable primary evidence when available.']})
    inputs.planner_diagnostics=[]
    if progress is not None:progress['planner_diagnostics']=[]
    return partial_plan(company_id,tuple(chunks)),0,tuple(chunks)
