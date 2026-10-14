"""Persist critic advice for later research, not a second methodology-writing call."""
from hashlib import sha256
import json,re
try:
    from .methodology_learning_v0_1_21 import MethodologyLearningProposal,MAX_TOTAL_CHARS
except ImportError:
    from methodology_learning_v0_1_21 import MethodologyLearningProposal,MAX_TOTAL_CHARS

SCHEMA='pharma_future_research_guidance.v1'
PATTERN=r'<!-- pharma-guidance:v1 (\{[^\n]*\}) -->'
RESOLVED=r'<!-- pharma-guidance-resolved:v1 ([a-f0-9]{64}) -->'

def fingerprint(row):
    return sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def read_guidance(text, sections=None, *, include_resolved=False):
    result=[]
    resolved=set(re.findall(RESOLVED,text or ''))
    for encoded in re.findall(PATTERN,text or ''):
        try: row=json.loads(encoded)
        except (ValueError,TypeError): continue
        if row.get('schema_version')!=SCHEMA or row.get('origin')!='section_critic':continue
        if not include_resolved and row.get('guidance_id') in resolved:continue
        if sections is not None and row.get('section_id') not in sections:continue
        if all(isinstance(row.get(k),str) and 0<len(row[k])<=400 for k in ('observation','next_action','success_check')):
            result.append(row)
    return result[-16:]

def build_methodology_learning_proposal(existing_text, *, feedback, resolved=()):
    candidate=existing_text;added=[];omitted=0
    prior=read_guidance(existing_text,include_resolved=True)
    existing={r.get('guidance_id') for r in prior}
    def action_key(row):
        norm=lambda text:' '.join(re.findall(r'\w+',text.casefold()))
        return (row.get('section_id'),row.get('subsection_id'),norm(row['next_action']),norm(row['success_check']))
    actions={action_key(row) for row in prior if row.get('guidance_id') not in resolved}
    already_resolved=set(re.findall(RESOLVED,existing_text))
    for key in resolved:
        if key not in existing or key in already_resolved:continue
        block='\n\n<!-- pharma-guidance-resolved:v1 '+key+' -->'
        if len(candidate)+len(block)>MAX_TOTAL_CHARS:omitted+=1;continue
        candidate+=block;added.append('resolved:'+key);already_resolved.add(key)
    for row in feedback:
        key=fingerprint(row)
        action=action_key(row)
        if key in existing or action in actions:continue
        record={'schema_version':SCHEMA,'guidance_id':key,**row}
        # Escape comment terminators without changing the decoded guidance.
        encoded=json.dumps(record,ensure_ascii=True,separators=(',',':')).replace('-->','--\\u003e')
        line=lambda value:' '.join(value.split()).replace('<','&lt;').replace('>','&gt;')
        block=('\n\n#### Future research: '+line(row['section_id'])+'\n\n'
            +'- Observation: '+line(row['observation'])+'\n'
            +'- Next action: '+line(row['next_action'])+'\n'
            +'- Success check: '+line(row['success_check'])+'\n'
            +'<!-- pharma-guidance:v1 '+encoded+' -->')
        if len(candidate)+len(block)>MAX_TOTAL_CHARS:
            omitted+=1;continue
        candidate+=block;added.append(key);existing.add(key);actions.add(action)
    return MethodologyLearningProposal(SCHEMA,candidate,tuple(added),'sha256:'+sha256(candidate.encode()).hexdigest(),
        candidate.startswith(existing_text),False,bool(added),False,
        'methodology_guidance_budget_reached' if omitted else None)
