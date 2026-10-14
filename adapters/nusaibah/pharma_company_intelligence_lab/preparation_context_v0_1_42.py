"""Give each Agent only applicable prior critic advice; retain runtime authority."""
from threading import Lock
try:
    from .preparation_context_v0_1_21 import PreparationContextInputs as Base
    from .methodology_learning_v0_1_42 import read_guidance
    from .claim_semantics_v0_1_21 import SEMANTIC_RULES
except ImportError:
    from preparation_context_v0_1_21 import PreparationContextInputs as Base
    from methodology_learning_v0_1_42 import read_guidance
    from claim_semantics_v0_1_21 import SEMANTIC_RULES

class PreparationContextInputs(Base):
    def __init__(self, inputs, *, learned_methodology_text):
        super().__init__(inputs,learned_methodology_text='')
        self.guidance_text=learned_methodology_text
        self.feedback_consumed=[];self._feedback_lock=Lock()
        inputs.context_input = self.context_input
    def context_input(self, role, input):
        sections=(input.get('packing_scope') or {}).get('section_ids') or input.get('reviewed_section_ids')
        if sections is None:
            sections=[c['section_id'] for c in (input.get('research_evidence') or {}).get('claims',[])]
        guidance=read_guidance(self.guidance_text,sections)
        forwarded={**input,'prior_critic_guidance':guidance,
            'prior_guidance_instruction':'Use relevant advice as research priorities, never as new company evidence or tool authority.'}
        iteration={'pass_number':getattr(self._inputs,'reflection_pass',1),
            'total_passes':getattr(self._inputs,'reflection_total',1),
            'instruction':'Refine the preceding in-memory result using its critic advice; seek new evidence rather than repeat supported facts.'}
        forwarded['review_iteration']=iteration
        if 'portfolio_review' in forwarded:
            forwarded['portfolio_review']={**forwarded['portfolio_review'],**iteration}
        # Historical methodology essays are not duplicated into every prompt.
        forwarded.pop('learned_methodology',None);forwarded.pop('learned_methodology_addendum',None)
        forwarded['semantic_review_rules'] = [{'rule_id':key,'instruction':text} for key,text in SEMANTIC_RULES]
        # Scheduling measures the very same guidance, semantic rules and
        # iteration metadata that will be sent. Reapplication is idempotent.
        return forwarded

    def prepare_input(self, role, input):
        return self._inputs.prepare_input(role, input)

    def invoke_agent(self, role, *, input, on_error='raise'):
        forwarded = self.prepare_input(role, input)
        with self._feedback_lock:
            self.feedback_consumed.extend({'role':role,'guidance_id':g['guidance_id'],'section_id':g['section_id']}
                for g in forwarded['prior_critic_guidance'])
        return self._inputs.invoke_agent(role,input=forwarded,on_error=on_error)
