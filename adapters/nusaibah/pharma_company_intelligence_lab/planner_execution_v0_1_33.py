"""Parallel bounded canonical section planning; no extra reflection pass."""
try:
    from . import legacy_preparation_helpers_v0_1_23 as legacy
except ImportError:
    import legacy_preparation_helpers_v0_1_23 as legacy

def run_planner(inputs,*,company_id,company_name_value,baseline,request,methodology,before_benchmark,learned_methodology_text):
    ordered_chunks=legacy._ordered_planner_chunks(before_benchmark)
    def work(planner_chunk):
        priority_hint = planner_chunk.get("priority_hint")
        envelope = inputs.invoke_agent(
            legacy.PLANNER_ROLE,
            input={
                "planning_stage": "section_chunk",
                "company_id": company_id,
                "company_name": company_name_value,
                "objective": request.objective,
                "research_depth": request.research_depth,
                "methodology_slice": legacy._planner_methodology_slice(
                    methodology,
                    planner_chunk=planner_chunk,
                ),
                "governed_company_baseline": baseline,
                "memory_benchmark": legacy._benchmark_slice(
                    before_benchmark,
                    planner_chunk=planner_chunk,
                ),
                "planner_chunk": {
                    key: value
                    for key, value in planner_chunk.items()
                    if key != "priority_hint"
                },
                "priority_hint": priority_hint,
                "learned_methodology": legacy._planner_learned_section(
                    learned_methodology_text,
                    section_id=planner_chunk["section_id"],
                ),
                "response_contract": legacy.planner_section_response_contract(
                    company_id=company_id,
                    planner_chunk=planner_chunk,
                    priority_hint=priority_hint,
                ),
            },
            on_error="raise",
        )
        return legacy._validated_agent_response(
            inputs, envelope, role=legacy.PLANNER_ROLE, company_id=company_id,
            contract=legacy.planner_section_response_contract(
                company_id=company_id, planner_chunk=planner_chunk, priority_hint=priority_hint),
            validator=lambda value: legacy._validate_planner_section(
                value, company_id=company_id, planner_chunk=planner_chunk),
        )

    outcomes=inputs.coordinator.parallel(ordered_chunks,work)
    if any(o['status']!='completed' for o in outcomes):
        # Do not invent an Agent planning decision. Keep the actual diagnostics;
        # incomplete planning cannot acquire broader research or write authority.
        raise legacy.UnresolvedAgentResponse(next(o['diagnostic'] for o in outcomes if o['status']!='completed'))
    validated_chunks=tuple(o['value'] for o in outcomes)
    plan=legacy._assemble_methodology_plan(company_id=company_id,methodology=methodology,
        before_benchmark=before_benchmark,planner_chunks=validated_chunks)
    return plan,len(validated_chunks),validated_chunks
