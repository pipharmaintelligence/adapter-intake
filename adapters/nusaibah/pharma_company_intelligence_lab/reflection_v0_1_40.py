"""Optional bounded reflection in memory; publish once after all requested passes."""
from dataclasses import replace
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
    from .company_preparation_v0_1_40 import prepare_company_v0_1_40
    from .claim_evidence_contract_v0_1_21 import merge_claim_evidence_indexes
    from .memory_citation_selection_v0_1_21 import select_memory_citations
    from .agent_chunks_v0_1_33 import unique
    from .section_enrichment_v0_1_40 import build_enrichment_candidate
    from .skill_reads_v0_1_40 import read_company_memory,load_methodology_learning
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy
    from company_preparation_v0_1_40 import prepare_company_v0_1_40
    from claim_evidence_contract_v0_1_21 import merge_claim_evidence_indexes
    from memory_citation_selection_v0_1_21 import select_memory_citations
    from agent_chunks_v0_1_33 import unique
    from section_enrichment_v0_1_40 import build_enrichment_candidate
    from skill_reads_v0_1_40 import read_company_memory,load_methodology_learning


def prepare_with_reflection(inputs, *, request, record, methodology, review_passes, progress):
    company_id=int(record['company_id'])
    memory=read_company_memory(inputs,company_id=company_id,allow_absent=True)
    learning=load_methodology_learning(inputs,company_id=company_id)
    working_memory=dict(memory);working_learning=learning;states=[];trace=[]
    for number in range(1,review_passes+1):
        inputs.reflection_pass=number;inputs.reflection_total=review_passes
        calls_before=sum(inputs.company_agent_counts(company_id).values())
        try:
            state=prepare_company_v0_1_40(inputs,request=request,record=record,methodology=methodology,
                review_passes=number,preflight=(working_memory,working_learning),progress=progress)
        except legacy.UnresolvedAgentResponse as error:
            if not states:raise
            states[-1]['result']['research_incomplete']=True
            states[-1]['result']['chunk_phase_issues'].append(error.diagnostic)
            trace.append({'pass_number':number,'status':'unresolved','previous_result_preserved':True,
                'diagnostic':error.diagnostic})
            break
        calls_after=sum(inputs.company_agent_counts(company_id).values())
        if number>1 and calls_before==calls_after:
            diagnostic=legacy.evidence_diagnostic(role='orchestration',stage='reflection',field='passes',rule='reflection_budget_exhausted')
            states[-1]['result']['research_incomplete']=True
            states[-1]['result']['chunk_phase_issues'].append(diagnostic)
            trace.append({'pass_number':number,'status':'not_executed_budget','previous_result_preserved':True})
            break
        states.append(state)
        trace.append({'pass_number':number,'status':'partial' if state['result']['research_incomplete'] else 'completed','accepted_claim_count':len(state['joined_research']['claims']),
            'agent_call_count':calls_after-calls_before,
            'new_fact_count':len(state['memory_candidate'].fact_ids),
            'feedback_consumed_count':len(state['result']['methodology_feedback_consumed'])})
        working_memory={**memory,'text':state['memory_candidate'].markdown,
            'target_text':state['memory_candidate'].markdown}
        working_learning=(learning[0],state['methodology_learning_candidate'] or working_learning[1])
    final=states[-1];first=states[0];claims={};indexes=[];seen=set();facts=[]
    rejected={cid for state in states for cid in state['critic']['rejected_claim_ids']}
    for state in states:
        for claim in state['joined_research']['claims']:
            if claim['claim_id'] not in rejected:claims.setdefault(claim['claim_id'],claim)
    for state in states:
        index=state['joined_research']['claim_evidence_index']
        records=tuple(r for r in index.records if r.claim_id in claims and r.accepted and r.claim_id not in seen)
        seen.update(r.claim_id for r in records);indexes.append(replace(index,records=records))
        facts.extend(state['memory_candidate'].fact_ids)
    merged=merge_claim_evidence_indexes(indexes)
    final['joined_research']={**final['joined_research'],'claims':list(claims.values()),
        'claim_evidence_index':merged,'citations':legacy._dedupe_citations([c for s in states for c in s['joined_research']['citations']])}
    candidate=replace(final['memory_candidate'],fact_ids=tuple(c for c in dict.fromkeys(facts) if c in claims))
    final['memory_candidate'],enrichment=build_enrichment_candidate(candidate,first['before_target_text'] or '',list(claims.values()))
    final['evidence_selection']=select_memory_citations(fact_ids=final['memory_candidate'].fact_ids,
        evidence_index=merged,maximum_citations=legacy.MAX_CITATIONS_PER_COMPANY)
    uncovered=set(final['evidence_selection'].uncovered_fact_ids)
    if uncovered:
        kept=replace(final['memory_candidate'],fact_ids=tuple(c for c in final['memory_candidate'].fact_ids if c not in uncovered))
        final['memory_candidate'],bounded_enrichment=build_enrichment_candidate(kept,first['before_target_text'] or '',list(claims.values()))
        bounded_enrichment['omitted_facts']+=enrichment['omitted_facts']+[
            {'claim_id':c,'reason':'publication_citation_budget'} for c in sorted(uncovered)]
        enrichment=bounded_enrichment
        final['evidence_selection']=select_memory_citations(fact_ids=final['memory_candidate'].fact_ids,
            evidence_index=merged,maximum_citations=legacy.MAX_CITATIONS_PER_COMPANY)
    final['before_digest']=first['before_digest'];final['before_target_text']=first['before_target_text']
    final['review_baselines']=first['review_baselines']
    final['candidate_changed']=final['memory_candidate'].markdown.strip()!=(first['before_target_text'] or '').strip()
    final['methodology_learning_candidate']=working_learning[1] if working_learning[1]!=learning[1] else None
    final['methodology_learning_before_text']=learning[1]
    final['critic']={**final['critic'],
        'reviewed_claim_ids':unique([c for s in states for c in s['critic']['reviewed_claim_ids']]),
        'rejected_claim_ids':sorted(rejected)}
    result=final['result']
    result.update(review_pass_trace=trace,portfolio_review_pass_count=len(states),portfolio_reflection_pass_count=len(states)-1,
        portfolio_review_passes_requested=review_passes,coverage_scope='bounded_section_tasks',
        portfolio_review_passes=review_passes,accepted_claim_count=len(claims),
        profile_claims=list(claims.values()),native_grounded_claim_count=sum(bool(c.get('native_grounding')) for c in claims.values()),
        methodology_feedback=unique([g for s in states for g in s['result']['methodology_feedback']]),
        methodology_feedback_consumed=unique([g for s in states for g in s['result']['methodology_feedback_consumed']]),
        chunk_phase_issues=unique([g for s in states for g in s['result']['chunk_phase_issues']]),
        research_incomplete=any(s['result']['research_incomplete'] for s in states))
    result['research_incomplete']=result['research_incomplete'] or bool(enrichment['omitted_facts'])
    result['profile_coverage_complete']=not result['research_incomplete']
    result['section_enrichment']=enrichment
    selection=final['evidence_selection']
    result.update(novel_fact_count=len(final['memory_candidate'].fact_ids),
        evidence_selection_complete=selection.complete,evidence_selection_digest=selection.selection_digest,
        evidence_selection_uncovered_fact_ids=list(selection.uncovered_fact_ids),
        evidence_selection_selected_citation_count=len(selection.selected_citations))
    return final
