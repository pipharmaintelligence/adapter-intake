"""Review synthesized paragraphs against admitted claims, with local fallback."""
from hashlib import sha256
import re
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .critic_contract_v0_1_40 import extend_contract, validate_critic
    from .critic_response_v0_1_40 import _validated_agent_response
    from .agent_response_recovery_v0_1_40 import AgentResponseDiagnosticError
    from .agent_chunks_v0_1_33 import unique
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy
    from critic_contract_v0_1_40 import extend_contract, validate_critic
    from critic_response_v0_1_40 import _validated_agent_response
    from agent_response_recovery_v0_1_40 import AgentResponseDiagnosticError
    from agent_chunks_v0_1_33 import unique

INSTRUCTION = (
    'Write a readable company profile for the supplied section/subsection only. '
    'Use connected paragraphs, not evidence bullets or a ledger. Every factual '
    'paragraph must end with one or more exact claim markers [[claim_id]] from '
    'allowed_narrative_claim_ids. Use verified and unverified research to build the profile; '
    'do not eliminate safe useful draft text for missing verification. Preserve dates, historical/current distinctions, '
    'uncertainty and entity scope. Do not add facts, implications, numerical '
    'comparisons or causal explanations beyond these claims. Use blank lines '
    'between paragraphs. Keep canonical envelope sections, with empty content '
    'outside the supplied scope. Do not put URLs, provenance fields, headings, '
    'HTML or tables in paragraph text; the adapter renders evidence separately. '
    'memory_candidate remains a compatibility field and must be an object, never null. '
    'When allowed_memory_fact_ids is empty, return fact_ids=[] in that object; '
    'do not invent verified facts. The object is not a storage write. Section paragraphs are '
    'the proposed publication content and will receive an independent check. '
    'EDITORIAL TASK: consolidate related statements into connected paragraphs '
    'organized by the supplied subsections, preserving every distinct claim once. '
    'Use two to four related sentences where useful, not one record per sentence '
    'joined without a topic. Never invent transitions, causality or implications. '
    'Give each material date once in its sentence; do not repeat equivalent ISO '
    'and written dates (for example As of 2026-02-19, As of February 19, 2026). '
    'Keep different event dates and observation dates when both are material. '
    'Keep every uncertainty, negative statement, entity and rights qualification. '
    'Missing native source metadata does not prevent this editorial task or '
    'authorize changing a claim from unverified to verified. '
    'Keep each subsection content within 3000 characters, using separate '
    'paragraphs with their exact claim markers and the strict JSON envelope.'
)
MARKER = re.compile(r'\[\[([^\[\]\n]+)\]\]')


def synthesize_packet(inputs, packet, *, company_id):
    """Version-owned sparse presentation; missing subsections may stay empty."""
    try:
        from .dossier_contract import normalize_sections
        from .memory_contract import validate_memory_candidate
        from .agent_contract import _text_list, MAX_UNCERTAINTIES
    except ImportError:
        from dossier_contract import normalize_sections
        from memory_contract import validate_memory_candidate
        from agent_contract import _text_list, MAX_UNCERTAINTIES
    def validate(value):
        sections = normalize_sections(value.get('sections'), require_all=True)
        for s in sections:
            if len(s['content'])>3000 or any(len(sub['content'])>3000 for sub in s['subsections']):
                raise ValueError('narrative_subsection_budget')
        candidate_raw = value.get('memory_candidate')
        if not isinstance(candidate_raw, dict):
            raise AgentResponseDiagnosticError(role=legacy.SYNTHESIS_ROLE,
                field='memory_candidate', rule='object_required')
        candidate=validate_memory_candidate(candidate_raw,company_id=company_id)
        return {'sections':sections,
            'residual_uncertainties':_text_list(value.get('residual_uncertainties',[]),
                'residual_uncertainties',MAX_UNCERTAINTIES)},candidate
    envelope=inputs.invoke_agent(legacy.SYNTHESIS_ROLE,input=packet,on_error='raise')
    return _validated_agent_response(inputs,envelope,role=legacy.SYNTHESIS_ROLE,
        company_id=company_id,contract=packet['response_contract'],validator=validate)


def extract_paragraphs(sections, claims):
    known = {c['claim_id']: c for c in claims}; paragraphs = []; issues = []
    for section in sections:
        sid = section['section_id']
        pieces = [(None, section.get('content', ''))] + [
            (s['subsection_id'], s.get('content', '')) for s in section.get('subsections', [])]
        for sub, content in pieces:
            for number, raw in enumerate(re.split(r'\n\s*\n', content), 1):
                if not raw.strip(): continue
                refs = unique(MARKER.findall(raw)); text = MARKER.sub('', raw).strip()
                issue = None
                if not refs or any(c not in known or known[c]['section_id'] != sid for c in refs):
                    issue = 'narrative_support_mapping_missing'
                elif not text or len(text) > 3000 or re.search(r'(?m)^\s*(?:#|[-*]\s|\d+\.\s)|https?://|<[^>]*>|\|', text):
                    issue = 'narrative_paragraph_format_invalid'
                if issue:
                    issues.append({'section': sid, 'subsection': sub, 'paragraph': number, 'issue': issue})
                    continue
                key = 'paragraph:' + sha256((sid+'|'+str(sub)+'|'+text+'|'+','.join(refs)).encode()).hexdigest()
                paragraphs.append({'paragraph_id': key, 'section_id': sid, 'subsection_id': sub,
                                   'paragraph': number, 'text': text, 'claim_ids': refs})
    return paragraphs, issues


def review_paragraphs(inputs, *, company_id, company_name, sections, claims):
    paragraphs, issues = extract_paragraphs(sections, claims)
    known = {c['claim_id']: c for c in claims}; approved = []
    drafts=[{**p,'verification_status':'unverified','basis':'synthesized_unverified_research'} for p in paragraphs
            if any(known[c].get('verification_status')!='verified' for c in p['claim_ids'])]
    paragraphs=[p for p in paragraphs if all(known[c].get('verification_status')=='verified' for c in p['claim_ids'])]
    # Each review unit is a single paragraph, with only its cited claims. It
    # shares the existing critic semaphore, deadline, call cap and sole backup.
    def attach(payload, rows):
        paragraph = rows[0]['paragraph_value']; sid = paragraph['section_id']; pid = paragraph['paragraph_id']
        support = [known[c] for c in paragraph['claim_ids']]
        contract = legacy.response_contract_for_role(legacy.CRITIC_ROLE, company_id=company_id, planner_requirement_ids=())
        contract = extend_contract(contract, sid, [pid])
        contract.update(allowed_section_ids=[sid], allowed_claim_ids=[pid], allowed_requirement_ids=[])
        contract['validation_contract'].update(missing_section_ids_allowed_values=[sid],
            unsupported_claim_ids_allowed_values=[pid], stale_claim_ids_allowed_values=[pid],
            unmet_plan_requirement_ids_allowed_values=[])
        payload.update(review_phase='narrative_entailment', reviewed_section_ids=[sid],
            reviewed_sections=legacy._section_requests((sid,)), planner_requirements=[], response_contract=contract,
            research_evidence={'claims':[{'claim_id':pid,'section_id':sid,'statement':paragraph['text'],
                'citation_locators':unique([loc for c in support for loc in c['citation_locators']]),
                'source_spans':unique([span for c in support for span in c.get('source_spans',[])])}],
                'admitted_support':support},
            enrichment_instruction=(
                'This is a paragraph entailment check, not new research. Compare every proposition '
                'in the paragraph against admitted_support. Return supported only if ALL propositions '
                'follow from those claims, including dates, historical status, uncertainty, quantities, '
                'entity scope and any inference labels. Reject invented connective/causal claims. '
                'Do not penalize missing whole-profile coverage. No external knowledge. '
                'Use the same claim_reviews JSON contract for the supplied paragraph ID; '
                'return future_guidance=[] and unresolved requirements=[] for this presentation check.'))
        value = inputs.prepare_input(legacy.CRITIC_ROLE, payload)
        value['_piece_paragraph'] = paragraph
        return value

    units = [{'section_id':p['section_id'], 'unit_id':p['paragraph_id'], 'paragraph_value':p} for p in paragraphs]
    packets = []
    for unit in units:
        # One paragraph per review. A packing callback that only reads rows[0]
        # must never receive several units and silently discard its siblings.
        pieces, _ = inputs.coordinator.partition(legacy.CRITIC_ROLE,
            {'company_id':company_id,'company_name':company_name}, [unit], attach)
        packets.extend(pieces)
    def work(packet):
        p = packet['_piece_paragraph']; pid = p['paragraph_id']; sid = p['section_id']
        envelope = inputs.invoke_agent(legacy.CRITIC_ROLE, input=packet, on_error='raise')
        verdict = _validated_agent_response(inputs, envelope, role=legacy.CRITIC_ROLE,
            company_id=company_id, contract=packet['response_contract'],
            validator=lambda v:validate_critic(v,section_id=sid,company_id=company_id,
                known_claim_ids={pid},known_section_ids={sid},known_plan_requirement_ids=set()))
        return pid not in verdict['rejected_claim_ids']
    outcomes = inputs.coordinator.parallel(packets, work)
    for packet, outcome in zip(packets, outcomes):
        p = packet['_piece_paragraph']
        if outcome['status'] == 'completed' and outcome['value']:
            approved.append({**p, 'basis':'synthesized_and_critic_reviewed','verification_status':'verified'})
        else:
            drafts.append({**p,'verification_status':'unverified','basis':'narrative_entailment_unresolved'})
            issues.append({'section':p['section_id'],'subsection':p['subsection_id'],
                'paragraph':p['paragraph'],'issue':'narrative_entailment_unresolved', 'claim_ids':p['claim_ids']})
    scheduled = {p['_piece_paragraph']['paragraph_id'] for p in packets}
    for p in paragraphs:
        if p['paragraph_id'] not in scheduled:
            issues.append({'section':p['section_id'],'subsection':p['subsection_id'],
                'paragraph':p['paragraph'],'issue':'narrative_review_input_budget', 'claim_ids':p['claim_ids']})
    return approved+drafts, issues
