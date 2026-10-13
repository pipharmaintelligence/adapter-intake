"""Provider-free premeasurement, atomic chunks, bounded parallelism and consolidation."""
import copy,json,time,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from threading import Barrier
from unittest.mock import patch
from types import SimpleNamespace
from agent_chunks_v0_1_33 import ChunkCoordinator,MeasuredDispatchInputs,paragraph_units,canonical,prepared_payload
from invocation_recovery_v0_1_33 import InvocationRecoveryInputs,BoundedRecoveryInputs
from orchestration_v0_1_33 import invoke_v0_1_33
from test_automatic_enrichment_v0_1_27 import EnrichmentInputs,legacy,_fake_citations
from test_invocation_revival_v0_1_30 import invalid_json

class ChunkInputs(EnrichmentInputs):
    def __init__(self):
        super().__init__();self['variables']['company_ids']=[13]
        self.set_company_records([{'id':13,'company':'Tabuk Pharmaceuticals','country':'SA'}])
    def invoke_agent(self,role,*,input,on_error='raise'):
        envelope=super().invoke_agent(role,input=input,on_error=on_error)
        if role==legacy.SYNTHESIS_ROLE:
            # The historical fixture repeats first/last when a piece has one
            # fact. Emit the actual contract's unique IDs instead.
            envelope['result']['content'][0]['value']['memory_candidate']['fact_ids']=list(dict.fromkeys(input['allowed_memory_fact_ids']))
        return envelope

def invoke(inputs):
    with patch.object(legacy,'_agent_citations',side_effect=_fake_citations):
        return invoke_v0_1_33(inputs,asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.33')

class ParagraphChunkTests(unittest.TestCase):
    def test_exact_paragraph_offsets_and_subsection_boundaries(self):
        source='# Identity\nName, with a qualifier.\n\nAddress, dated 2026.\n## Product\nProduct text.\n\nSecond paragraph.'
        units=paragraph_units(source)
        self.assertEqual(source,''.join(u['text'] for u in units))
        self.assertEqual(['Identity','Identity','Product','Product'],[u['subsection'] for u in units])
        self.assertTrue(all(source[u['source_start']:u['source_end']]==u['text'] for u in units))
    def test_indivisible_paragraph_is_not_character_clipped_and_other_work_survives(self):
        engine=ChunkCoordinator(input_chars=8000)
        units=[{'unit_id':'long','text':'x'*9000},{'unit_id':'small','text':'short paragraph.'}]
        packets,omitted=engine.partition(legacy.STRATEGIC_ROLE,{'company_id':13},units,
            lambda p,r:{**p,'paragraphs':r})
        self.assertEqual(1,len(packets));self.assertEqual('short paragraph.',packets[0]['paragraphs'][0]['text'])
        self.assertEqual(1,len(omitted));self.assertEqual(0,engine.calls)
    def test_every_active_role_and_backup_is_measured_as_sent(self):
        roles=[legacy.PLANNER_ROLE,*legacy.RESEARCH_ROLES,legacy.STRATEGIC_ROLE,legacy.CRITIC_ROLE,
               legacy.SYNTHESIS_ROLE,legacy.RESEARCH_RESOLVER_ROLE]
        class Inputs(dict):
            def __init__(self):super().__init__();self.sent=[]
            def invoke_agent(self,role,*,input,on_error):self.sent.append((role,input));return {'ok':True}
        raw=Inputs();engine=ChunkCoordinator();measured=MeasuredDispatchInputs(raw,engine)
        for role in roles:
            measured.invoke_agent(role,input={'company_id':13,'response_contract':{},'text':'نص دقيق','original_role':'portfolio_researcher'})
        self.assertEqual(len(roles),engine.calls)
        for record,(role,payload) in zip(engine.measurements,raw.sent):
            self.assertEqual(len(canonical(payload)),record['input_chars'])
            self.assertEqual(len(canonical(payload).encode()),record['input_bytes'])
            self.assertTrue(record['within_input_budget'])
    def test_parallel_dispatch_has_one_global_ceiling_and_plan_order(self):
        engine=ChunkCoordinator(parallelism=2)
        def work(n):return engine.dispatch(legacy.STRATEGIC_ROLE,{'company_id':13},lambda:(time.sleep(.02 if n%2==0 else .005),n)[1])
        result=engine.parallel(list(range(6)),work)
        self.assertEqual(list(range(6)),[r['value'] for r in result]);self.assertEqual(2,engine.peak)
    def test_insufficient_deadline_reserves_consolidation_without_provider_call(self):
        engine=ChunkCoordinator(seconds=779,clock=lambda:0)
        with self.assertRaises(legacy.UnresolvedAgentResponse):
            engine.dispatch(legacy.SYNTHESIS_ROLE,{'company_id':13},lambda:self.fail('must not dispatch'))
        self.assertEqual(0,engine.calls)
    def test_two_parallel_same_role_failures_get_distinct_sole_backups(self):
        barrier=Barrier(2)
        class Inputs(dict):
            def __init__(self):super().__init__();self.ordinals=[]
            def invoke_agent(self,role,*,input,on_error):
                if role==legacy.PLANNER_ROLE:barrier.wait(timeout=2);raise invalid_json()
                self.ordinals.append(input['original_invocation_ordinal'])
                return {'status':'completed','result':{'content':[{'type':'json','value':{
                    'company_id':13,'role':legacy.PLANNER_ROLE,'status':'completed'}}]}}
        raw=Inputs();engine=ChunkCoordinator(parallelism=2)
        forwarded=InvocationRecoveryInputs(MeasuredDispatchInputs(raw,engine))
        bounded=BoundedRecoveryInputs(forwarded,SimpleNamespace(company_ids=(13,),memory_mode='preview'),review_passes=1,coordinator=engine)
        forwarded.bind_recovery(bounded)
        outcomes=engine.parallel([0,1],lambda n:bounded.invoke_agent(legacy.PLANNER_ROLE,input={
            'company_id':13,'response_contract':{},'chunk_execution':{'chunk_id':str(n)}}))
        self.assertTrue(all(r['status']=='completed' for r in outcomes))
        self.assertEqual([1,2],sorted(raw.ordinals));self.assertEqual(4,engine.calls)
        self.assertEqual(2,bounded.company_agent_counts(13)[legacy.RESEARCH_RESOLVER_ROLE])
    def test_single_company_complete_path_has_all_inputs_measured_and_no_benchmark(self):
        inputs=ChunkInputs();result=invoke(inputs)
        row=result['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'])
        proof=row['agent_input_preflight'];self.assertTrue(proof['measurements'])
        self.assertTrue(all(r['within_input_budget'] for r in proof['measurements']))
        self.assertLessEqual(proof['observed_peak_parallel_calls'],2)
        self.assertNotIn(legacy.BENCHMARK_ROLE,inputs.role_calls)
        self.assertEqual(1,row['portfolio_review_pass_count'])
    def test_large_interpretations_and_critic_notes_are_scoped_before_synthesis(self):
        class Large(ChunkInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                envelope=super().invoke_agent(role,input=input,on_error=on_error)
                value=envelope['result']['content'][0]['value']
                if role==legacy.STRATEGIC_ROLE:
                    value['implications']=[str(n)+':'+('qualified interpretation. '*50) for n in range(8)]
                if role==legacy.CRITIC_ROLE:
                    value['citation_coverage']['notes']='Qualified coverage. '*80
                    for r in value['unmet_plan_requirements']:r['notes']='Scoped assessment. '*80
                return envelope
        inputs=Large();result=invoke(inputs);row=result['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'])
        synth=[r for r in row['agent_input_preflight']['measurements'] if r['role']==legacy.SYNTHESIS_ROLE]
        self.assertGreater(len(synth),1);self.assertTrue(all(r['within_input_budget'] for r in synth))
    def test_negative_section_verdicts_are_not_consolidated_into_passes(self):
        class Negative(ChunkInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                envelope=super().invoke_agent(role,input=input,on_error=on_error)
                if role==legacy.CRITIC_ROLE:
                    envelope['result']['content'][0]['value']['recommendation']='fail'
                return envelope
        inputs=Negative();result=invoke(inputs)
        self.assertEqual('success',result['status']);self.assertFalse(result['outputs']['intelligence_dossier']['publication_complete'])
        self.assertEqual([],inputs.mutables)

    def test_shared_call_limit_retains_incomplete_result_without_extra_dispatch(self):
        inputs=ChunkInputs();inputs['variables']['agent_chunk_max_calls']=13
        result=invoke(inputs)
        self.assertEqual('success',result['status'])
        self.assertLessEqual(len(inputs.role_calls),13)
        self.assertFalse(result['outputs']['intelligence_dossier']['publication_complete'])
        self.assertEqual([],inputs.mutables)
    def test_failed_synthesis_piece_preserves_published_supported_siblings(self):
        class Failed(ChunkInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                if role==legacy.SYNTHESIS_ROLE and any(c['section_id']=='company_profile' for c in input['research_evidence']['claims']):
                    raise invalid_json()
                if role==legacy.RESEARCH_RESOLVER_ROLE:
                    raise invalid_json()
                return super().invoke_agent(role,input=input,on_error=on_error)
        inputs=Failed();result=invoke(inputs);row=result['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertTrue(row['research_incomplete']);self.assertTrue(row['chunk_phase_issues'])
        self.assertNotIn('company_profile',row['section_enrichment']['sections'])
    def test_wrong_fact_reference_is_local_not_an_asset_failure(self):
        class Wrong(ChunkInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                envelope=super().invoke_agent(role,input=input,on_error=on_error)
                if role==legacy.SYNTHESIS_ROLE and any(c['section_id']=='company_profile' for c in input['research_evidence']['claims']):
                    envelope['result']['content'][0]['value']['memory_candidate']['fact_ids']=['unknown-id']
                return envelope
        result=invoke(Wrong());row=result['outputs']['intelligence_dossier']['company_results'][0]
        self.assertEqual('success',result['status']);self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertTrue(row['chunk_phase_issues'])
    def test_oversized_retention_is_admitted_before_any_mutation(self):
        inputs=ChunkInputs()
        import company_preparation_v0_1_33 as preparation
        import orchestration_v0_1_33 as orchestration
        original=preparation.prepare_company_v0_1_33
        def prepare(*a,**kw):
            state=original(*a,**kw)
            state['result']['large_nondegradable_evidence']='x'*(512*1024)
            return state
        with patch.object(orchestration,'prepare_company_v0_1_33',side_effect=prepare):
            result=invoke(inputs)
        self.assertEqual([],inputs.mutables)
        row=result['outputs']['intelligence_dossier']['company_results'][0]
        self.assertEqual('incomplete',row['retention_admission']['status'])
        self.assertTrue(row['retention_admission']['publication_withheld'])
        self.assertLess(len(canonical(result).encode()),512*1024)
    def test_scoped_plan_uses_actual_research_focus_contract(self):
        from downstream_chunks_v0_1_33 import ScopedPlan
        plan=SimpleNamespace(to_agent_input=lambda:{'research_focus':[
            {'role':r,'questions':['qualified question']} for r in legacy.RESEARCH_ROLES]})
        scoped=ScopedPlan(plan,legacy.RESEARCH_ROLE_SECTIONS[legacy.RESEARCH_ROLES[0]]).to_agent_input()
        self.assertEqual([legacy.RESEARCH_ROLES[0]],[r['role'] for r in scoped['research_focus']])
    def test_many_research_chunks_cannot_starve_downstream_roles(self):
        engine=ChunkCoordinator(parallelism=2)
        outcomes=engine.parallel(list(range(60)),lambda n:engine.dispatch('market_researcher',
            {'company_id':13},lambda:n))
        self.assertEqual(60,len(outcomes))
        self.assertEqual(6,sum(r['status']=='completed' for r in outcomes))
        engine.dispatch(legacy.STRATEGIC_ROLE,{'company_id':13},lambda:True)
        engine.dispatch(legacy.CRITIC_ROLE,{'company_id':13},lambda:True)
        engine.dispatch(legacy.SYNTHESIS_ROLE,{'company_id':13},lambda:True)
        self.assertEqual(9,engine.calls)
        self.assertTrue(all(r['diagnostic'] for r in outcomes if r['status']=='unresolved'))
    def test_deferred_chunks_do_not_exhaust_runtime_attempt_counters(self):
        class Inputs(dict):
            def invoke_agent(self,role,*,input,on_error):return {'ok':True}
        engine=ChunkCoordinator();raw=Inputs()
        bounded=BoundedRecoveryInputs(MeasuredDispatchInputs(raw,engine),
            SimpleNamespace(company_ids=(13,),memory_mode='preview'),review_passes=1,coordinator=engine)
        for role in legacy.RESEARCH_ROLES:
            results=engine.parallel(list(range(60)),lambda n:bounded.invoke_agent(role,input={'company_id':13}))
            self.assertEqual(60,len(results))
            self.assertEqual(6,sum(r['status']=='completed' for r in results))
        for role in (legacy.STRATEGIC_ROLE,legacy.CRITIC_ROLE,legacy.SYNTHESIS_ROLE):
            bounded.invoke_agent(role,input={'company_id':13})
        self.assertEqual(21,engine.calls)
        self.assertEqual(21,sum(bounded.company_agent_counts(13).values()))
    def test_authority_rejection_still_propagates_without_backup_or_write(self):
        from devtools.runtime_agent_invocation import RuntimeAgentInvocationError
        class Authority(ChunkInputs):
            def invoke_agent(self,role,*,input,on_error='raise'):
                if role=='market_researcher':raise RuntimeAgentInvocationError('authority rejected',cause_code='provider_execution_authority_scope_mismatch')
                return super().invoke_agent(role,input=input,on_error=on_error)
        inputs=Authority()
        with self.assertRaises(RuntimeAgentInvocationError):invoke(inputs)
        self.assertEqual([],inputs.mutables)

if __name__=='__main__':unittest.main()
