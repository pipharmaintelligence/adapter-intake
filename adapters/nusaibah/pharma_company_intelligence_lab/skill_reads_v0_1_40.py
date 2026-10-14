"""Preserve whole Skill baselines; prompt packing owns model context limits."""
from devtools.dynamic_skill_runtime import DynamicSkillRuntimeError
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy

def read_section(inputs,role,section,company_id):
    try:handle=inputs.dynamic_skill(role,variables={'company_id':str(company_id)})
    except DynamicSkillRuntimeError as error:
        if error.code=='dynamic_skill_not_initialized':return None,None
        raise
    if handle.provenance().mutable is not False:raise RuntimeError('Skill baseline must resolve read-only')
    if not handle.has_section(section):raise RuntimeError('Skill baseline is missing its declared target section')
    return handle,handle.section_text(section).strip()

def read_company_memory(inputs,*,company_id,allow_absent=True):
    handle,target=read_section(inputs,'company_memory',legacy.MEMORY_TARGET_SECTION,company_id)
    if handle is None:
        if not allow_absent:raise RuntimeError('company_memory_not_initialized')
        return {'handle':None,'text':'','target_text':None,'digest':None}
    text=handle.read()
    if not isinstance(text,str) or not text.strip():raise RuntimeError('Existing company memory is empty')
    return {'handle':handle,'text':text,'target_text':target,'digest':handle.content_digest()}

def load_methodology_learning(inputs,*,company_id):
    handle,text=read_section(inputs,legacy.METHODOLOGY_SKILL_ROLE,legacy.METHODOLOGY_LEARNING_SECTION,company_id)
    return handle,text or ''
