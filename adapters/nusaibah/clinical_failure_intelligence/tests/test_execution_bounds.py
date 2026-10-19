"""Scientific packet coverage and bounded reasoning; synthetic, no providers."""
from copy import deepcopy
import unittest
from fakes import FakeInputs, example_inputs
from clinical_failure_intelligence.analysis_packets import evidence_batches, closed_packet, namespace_candidates
from clinical_failure_intelligence.contracts import canonical_bytes
from clinical_failure_intelligence.orchestration import run_analysis
from clinical_failure_intelligence.policies import Budget, ExecutionPolicy, DeferredWork
from clinical_failure_intelligence.runtime_access import StageResult


class BoundsTests(unittest.TestCase):
    def test_complete_windows_prioritize_results_and_do_not_drop_locations(self):
        rows=[{'evidence_id':str(i),'text':'whole paragraph '*20,'source_context':
               {'source_pointer':'/contactsLocationsModule/'+str(i)}} for i in range(8)]
        rows.append({'evidence_id':'outcome','text':'complete outcome','source_context':
                     {'source_pointer':'/resultsSection/outcomeMeasuresModule'}})
        chunks=evidence_batches(rows,lambda x:{'prompt':'x'*100,'evidence':x},max_bytes=900)
        self.assertEqual('outcome',chunks[0][0]['evidence_id'])
        self.assertEqual({r['evidence_id'] for r in rows},{r['evidence_id'] for c in chunks for r in c})
        self.assertEqual(len(rows),sum(map(len,chunks)))
        self.assertTrue(all(len(canonical_bytes({'prompt':'x'*100,'evidence':chunk}))<=900 for chunk in chunks))
    def test_claim_and_outcome_evidence_closure_is_complete(self):
        evidence=[{'evidence_id':str(i),'text':'whole'} for i in range(3)]
        claims=[{'supporting_evidence_ids':['0'],'contradicting_evidence_ids':['1']}]
        packet=closed_packet(evidence[:1],evidence,claims,{},outcomes=[])
        self.assertEqual(['0','1'],[r['evidence_id'] for r in packet['evidence_packet']])
        self.assertFalse(packet['evidence_scope']['independent_exhaustiveness_claim'])
        self.assertFalse(packet['evidence_scope']['complete_evidence_in_packet'])
    def test_research_cannot_cite_an_existing_ledger_window_it_did_not_receive(self):
        def forged(payload,packet):
            if packet['role']=='trial_researcher':
                payload['items'][0]['contradicting_evidence_ids']=['E_PAPER']
            return payload
        value=run_analysis(FakeInputs(transforms={'trial_researcher':forged}))['outputs']['clinical_intelligence']
        self.assertIn('clinical_stage_evidence_not_supplied',{x['code'] for x in value['quality']['issues']})
        self.assertFalse(any(x.get('stage_id')=='trial_researcher:0:0' for x in value['research_claims']))
    def test_reflection_task_dedup_round_and_extra_call_ceiling(self):
        budget=Budget()
        self.assertTrue(budget.refine_once())
        self.assertTrue(budget.reflection_task('trial_researcher','Check outcome.','revision1'))
        self.assertFalse(budget.reflection_task('trial_researcher',' CHECK   outcome. ','revision1'))
        self.assertTrue(budget.reflection_task('trial_researcher','Check outcome.','revision2'))
        self.assertFalse(budget.reflection_task('event_researcher','Other question','revision3'))
        for _ in range(4):budget.reserve()
        with self.assertRaisesRegex(DeferredWork,'reflection_call_budget'):budget.reserve()
        self.assertFalse(budget.refine_once())
        budget.finish_reflection();budget.reserve()
        self.assertEqual(4,budget.proof()['reflection_agent_calls'])
        self.assertEqual(2,budget.proof()['reflection_tasks'])
    def test_grounded_search_per_role_and_global_limits(self):
        budget=Budget()
        for role in ('trial_researcher','literature_researcher','event_researcher'):
            budget.reserve_search(role);budget.reserve_search(role)
            with self.assertRaisesRegex(DeferredWork,'search_query_budget'):budget.reserve_search(role)
        self.assertEqual(6,budget.proof()['grounded_search_tasks'])
    def test_batch_local_ids_and_dependencies_are_disjoint(self):
        stage=StageResult('test','outcome_adjudicator','completed','digest',{'items':[
            {'item_id':'same','depends_on':[]},{'item_id':'second','depends_on':['same']}]},{})
        other=deepcopy(stage)
        namespace_candidates(stage,'outcome',0,multiple=True)
        namespace_candidates(other,'outcome',1,multiple=True)
        self.assertNotEqual(stage.payload['items'][0]['item_id'],other.payload['items'][0]['item_id'])
        self.assertEqual([stage.payload['items'][0]['item_id']],stage.payload['items'][1]['depends_on'])
    def test_no_progress_stops_reflection_without_repeating_analysis(self):
        raw=example_inputs();raw['variables']['enable_refinement']=True
        def follow(payload,packet):
            if packet.get('review_kind')!='product_memory_edits':
                payload['followup_requests']=[{'role':'literature_researcher','question':'Check exposure.',
                                               'affected_item_ids':['H_SYN']}]
            return payload
        fake=FakeInputs(raw,transforms={'evidence_critic':follow})
        result=run_analysis(fake)['outputs']['clinical_intelligence']
        self.assertIn('clinical_reflection_no_progress',{x['code'] for x in result['quality']['issues']})
        self.assertEqual(1,result['execution']['reflection_agent_calls'])
        self.assertEqual(1,sum(role=='hypothesis_analyst' for role,_ in fake.calls))
        self.assertLessEqual(sum(role=='product_memory_editor' for role,_ in fake.calls),1)
    def test_large_scientific_snapshot_reaches_all_stages_with_complete_packets(self):
        raw=example_inputs()
        raw['variables'].update(memory_mode='off',supplementary_search=False,enable_refinement=False)
        for i in range(18):
            raw['clinical_context']['evidence'].append({**raw['clinical_context']['evidence'][0],
                'evidence_id':'LARGE_'+str(i),'source_id':'REGISTRY_'+str(i),
                'text':'Synthetic complete evidence window '+str(i)+': '+'x'*11000})
        fake=FakeInputs(raw)
        result=run_analysis(fake)['outputs']['clinical_intelligence']
        expected={row['evidence_id'] for row in result['evidence']}
        for role in ('outcome_adjudicator','hypothesis_analyst'):
            packets=[packet for selected,packet in fake.calls if selected==role]
            self.assertGreater(len(packets),1)
            supplied={row['evidence_id'] for packet in packets for row in packet['evidence_packet']}
            self.assertEqual(expected,supplied)
        self.assertLessEqual(len(fake.calls),32)
        self.assertTrue(all(len(canonical_bytes(packet))<=120000 for _,packet in fake.calls))
        self.assertFalse(any(stage.get('code')=='clinical_packet_requires_partitioning' for stage in result['execution']['stages']))
