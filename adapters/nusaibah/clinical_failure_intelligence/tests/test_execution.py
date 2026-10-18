"""End-to-end provider-free runs, sibling preservation and shared execution limits."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from fakes import FakeInputs, CodedFailure, MemoryView, example_inputs
from clinical_failure_intelligence.contracts import ContractError, parse_request
from clinical_failure_intelligence.memory import commit_memory_change
from clinical_failure_intelligence.orchestration import run_analysis, partition_evidence
from clinical_failure_intelligence.policies import Budget, DeferredWork, ExecutionPolicy
from clinical_failure_intelligence.runtime_access import AgentRunner
from clinical_failure_intelligence.rendering import validate_result


def result(fake=None, **kwargs):
    return run_analysis(fake or FakeInputs(), **kwargs)['outputs']['clinical_intelligence']


class ExecutionTests(unittest.TestCase):
    def test_complete_fixture_six_agents_no_writes(self):
        fake = FakeInputs(); value = result(fake)
        self.assertEqual(8, len(fake.calls)); self.assertEqual('completed', value['quality']['status'])
        self.assertFalse(value['memory_update']['write_attempted']); self.assertEqual('not_attested', value['persistence']['status'])
        self.assertFalse(value['quality']['external_truth_verified'])
    def test_text_kind_wrapped_json_completes(self):
        self.assertEqual('completed', result(FakeInputs(response_kind='text'))['quality']['status'])
    def test_no_network_or_storage_transport(self):
        with patch('socket.socket.connect', side_effect=AssertionError('network forbidden')):
            self.assertEqual(8, result()['execution']['logical_agent_calls'])
    def test_known_optional_failure_preserves_work(self):
        fake = FakeInputs(faults={'event_researcher': CodedFailure('agent_execution_provider_retry_exhausted', 'provider_execution_transport_timeout')})
        value = result(fake); self.assertEqual('partial', value['quality']['status'])
        self.assertTrue(value['hypothesis_results']); self.assertEqual(8, len(fake.calls))
    def test_unknown_or_authority_failure_does_not_escape(self):
        for error in (RuntimeError('unknown'), CodedFailure('agent_execution_provider_retry_exhausted', 'authority_revoked')):
            with self.assertRaisesRegex(ContractError, 'runtime_blocked'): result(FakeInputs(faults={'event_researcher': error}))
    def test_critic_unavailable_preserves_candidates(self):
        fake = FakeInputs(faults={'evidence_critic': CodedFailure('agent_execution_provider_retry_exhausted', 'provider_execution_vertex_unavailable')})
        value = result(fake); self.assertTrue(value['hypothesis_results'])
        self.assertTrue(all(not x['accepted'] for x in value['hypothesis_results']))
        self.assertEqual('no_change', value['memory_update']['status'])
    def test_empty_critic_coverage_not_complete(self):
        fake = FakeInputs(transforms={'evidence_critic': lambda p, _: {**p, 'coverage': []}})
        value = result(fake); self.assertEqual('partial', value['quality']['status']); self.assertFalse(value['hypothesis_results'][0]['accepted'])
    def test_excluded_required_obligation_invalid(self):
        def wrong(p, _):
            p['coverage'][0]['status'] = 'excluded_by_scope'; return p
        self.assertEqual('partial', result(FakeInputs(transforms={'evidence_critic': wrong}))['quality']['status'])
    def test_bad_critic_item_keeps_research(self):
        def wrong(p, _):
            p['items'][0]['item_id'] = 'UNKNOWN'; return p
        value = result(FakeInputs(transforms={'evidence_critic': wrong}))
        self.assertTrue(value['research_claims'])
        # The missing verdict withholds its item, not independent valid siblings.
        self.assertFalse(value['case_assessments'][0]['accepted'])
        self.assertTrue(value['hypothesis_results'][0]['accepted'])
        self.assertTrue(any(x['code'] == 'clinical_critic_identity_invalid' for x in value['quality']['issues']))
    def test_wrong_agent_subject_hard_fails(self):
        with self.assertRaisesRegex(ContractError, 'identity_mismatch'):
            result(FakeInputs(transforms={'event_researcher': lambda p, _: {**p, 'subject_id': 'OTHER'}}))
    def test_bad_research_item_keeps_sibling(self):
        def wrong(p, _):
            p['items'].append({'claim_id': 'bad'}); return p
        value = result(FakeInputs(transforms={'trial_researcher': wrong}))
        self.assertTrue(value['research_claims']); self.assertEqual('partial', value['quality']['status'])
    def test_missing_seed_not_hidden(self):
        raw = example_inputs(); raw['clinical_context']['source_assertions'].append({'assertion_id': 'OTHER_SEED', 'statement': 'Second original question.', 'source_ref': 'synthetic'})
        value = result(FakeInputs(raw)); self.assertTrue(any(x['code'] == 'clinical_seed_coverage_incomplete' for x in value['quality']['issues']))
    def test_missing_outcome_dimension_not_hidden(self):
        value = result(FakeInputs(transforms={'outcome_adjudicator': lambda p, _: {**p, 'items': p['items'][:-1]}}))
        self.assertTrue(any(x['code'] == 'clinical_outcome_coverage_incomplete' for x in value['quality']['issues']))
    def test_shared_budget_reserves_downstream(self):
        value = result(policy=ExecutionPolicy(max_agent_calls=5))
        self.assertLessEqual(value['execution']['logical_agent_calls'], 5); self.assertEqual('partial', value['quality']['status'])
    def test_oversize_packet_deferred_not_truncated(self):
        value = result(policy=ExecutionPolicy(max_packet_bytes=1024))
        self.assertEqual(0, value['execution']['logical_agent_calls']); self.assertEqual('partial', value['quality']['status'])
    def test_chunks_preserve_all_whole_records(self):
        rows = [{'id': str(i), 'text': 'x' * 100} for i in range(20)]
        chunks = partition_evidence(rows, maximum_bytes=500)
        self.assertEqual(rows, [r for chunk in chunks for r in chunk]); self.assertGreater(len(chunks), 1)
    def test_one_targeted_refinement_only(self):
        raw = example_inputs(); raw['variables']['enable_refinement'] = True
        def follow(p, _):
            p['followup_requests'] = [{'role': 'literature_researcher', 'question': 'Check measured exposure.', 'affected_item_ids': ['H_SYN']}]; return p
        fake = FakeInputs(raw, transforms={'evidence_critic': follow}); value = result(fake)
        self.assertEqual(1, value['execution']['refinement_rounds']); self.assertEqual(12, len(fake.calls))
        self.assertEqual(1, sum(role == 'trial_researcher' for role, _ in fake.calls))
    def test_refinement_omission_keeps_old_candidate(self):
        raw = example_inputs(); raw['variables']['enable_refinement'] = True
        def analyst(p, packet):
            if packet['task_id'].endswith(':1'): p['items'] = []
            return p
        def follow(p, packet):
            if packet['task_id'].endswith(':0'): p['followup_requests'] = [{'role': 'literature_researcher', 'question': 'Check exposure.', 'affected_item_ids': ['H_SYN']}]
            return p
        value = result(FakeInputs(raw, transforms={'hypothesis_analyst': analyst, 'evidence_critic': follow}))
        self.assertEqual('H_SYN', value['hypothesis_results'][0]['item_id']); self.assertFalse(value['hypothesis_results'][0]['accepted'])
    def test_invalid_followup_scope_rejected(self):
        raw = example_inputs(); raw['variables']['enable_refinement'] = True
        def follow(p, _):
            p['followup_requests'] = [{'role': 'literature_researcher', 'question': 'Check.', 'affected_item_ids': ['OUTSIDE']}]; return p
        with self.assertRaisesRegex(ContractError, 'scope_invalid'): result(FakeInputs(raw, transforms={'evidence_critic': follow}))
    def test_missing_cohort_denominator_explicit(self):
        raw = example_inputs('cohort_pattern'); raw['clinical_context']['cohort']['denominator_complete'] = False
        value = result(FakeInputs(raw)); self.assertEqual('not_run', value['cohort_statistics']['status']); self.assertEqual('partial', value['quality']['status'])
    def test_repeat_graph_and_identity_stable(self):
        a, b = result(), result(); self.assertEqual(a['reason_graph'], b['reason_graph']); self.assertEqual(a['assessment_id'], b['assessment_id'])
    def test_graph_dangling_and_fake_persistence_rejected(self):
        value = result(); value['reason_graph']['edges'][0]['to'] = 'MISSING'
        with self.assertRaisesRegex(ContractError, 'dangling'): validate_result(value)
        value = result(); value['persistence']['status'] = 'saved'
        with self.assertRaisesRegex(ContractError, 'not_attested'): validate_result(value)
    def test_report_matches_source_model_headings(self):
        report = result()['report_markdown']
        for title in ('Original supplied hypothesis', 'General Research Observation', 'Example Drugs', 'Indicators to Measure and Validate', 'Alternative explanations'):
            self.assertIn(title, report)
    def test_no_durable_resume_claim(self):
        self.assertFalse(result()['execution']['resume']['available'])
    def test_invalid_dependencies_preserved_as_unresolved(self):
        def bad(p, _):
            p['items'][0]['depends_on'] = ['MISSING']; return p
        value = result(FakeInputs(transforms={'hypothesis_analyst': bad}))
        self.assertEqual(['MISSING'], value['hypothesis_results'][0]['unresolved_dependency_ids'])
        self.assertFalse(value['hypothesis_results'][0]['accepted']); validate_result(value)
    def test_required_roles_report_all_chunks_not_last_only(self):
        raw = example_inputs()
        for i in range(4):
            raw['clinical_context']['evidence'].append({**raw['clinical_context']['evidence'][0], 'evidence_id': f'EX{i}', 'source_id': f'SRC{i}', 'text': 'x' * 11000})
        def first_chunk_incomplete(payload, packet):
            if packet['task_id'] == 'trial_researcher:0:0':
                payload['coverage'][0]['status'] = 'unresolved'
            return payload
        value = result(FakeInputs(raw, transforms={'trial_researcher': first_chunk_incomplete}))
        trial_stages = [stage for stage in value['execution']['stages'] if stage['role'] == 'trial_researcher']
        self.assertGreater(len(trial_stages), 1)
        self.assertEqual('completed', trial_stages[-1]['status'])
        self.assertFalse(value['quality']['required_roles_completed']['trial_researcher'])


class BudgetAndRunnerTests(unittest.TestCase):
    def test_budget_shared_concurrently(self):
        budget = Budget(ExecutionPolicy(max_agent_calls=5))
        def reserve(_):
            try: budget.reserve(); return True
            except DeferredWork: return False
        with ThreadPoolExecutor(max_workers=8) as pool: counts = list(pool.map(reserve, range(20)))
        self.assertEqual(5, sum(counts)); self.assertEqual(5, budget.calls)
    def test_completion_reserve_prevents_late_dispatch(self):
        clock = [0.]; budget = Budget(clock=lambda: clock[0]); clock[0] = 1600
        with self.assertRaisesRegex(DeferredWork, 'completion_reserve'): budget.reserve()
        self.assertEqual(0, budget.calls)
    def test_invalid_limits_rejected(self):
        for policy in (ExecutionPolicy(max_agent_calls=-1), ExecutionPolicy(research_concurrency=3), ExecutionPolicy(deadline_seconds=float('nan'))):
            with self.assertRaises(ContractError): Budget(policy)
    def test_reference_allowance_shared(self):
        budget = Budget(ExecutionPolicy(max_reference_reads=1)); budget.reserve(kind='reference')
        with self.assertRaisesRegex(DeferredWork, 'reference_budget'): budget.reserve(kind='reference')
        self.assertEqual(1, budget.reads)
    def test_identical_inflight_task_reused_once(self):
        fake = FakeInputs(); request = parse_request(fake); runner = AgentRunner(fake, Budget())
        def run(_):
            return runner.call('event_researcher', request, task_id='same', obligations=['q'], packet_data={'evidence_packet': []})
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(run, range(2)))
        self.assertEqual(1, len(fake.calls)); self.assertEqual(1, sum(x.cache_hit for x in results))
    def test_changed_input_invalidates_cache(self):
        fake = FakeInputs(); request = parse_request(fake); runner = AgentRunner(fake, Budget())
        for value in (1, 2): runner.call('event_researcher', request, task_id='same', obligations=['q'], packet_data={'evidence_packet': [], 'revision': value})
        self.assertEqual(2, len(fake.calls))
    def test_task_identity_cannot_be_overridden(self):
        fake = FakeInputs(); runner = AgentRunner(fake, Budget())
        with self.assertRaisesRegex(ContractError, 'override_forbidden'):
            runner.call('event_researcher', parse_request(fake), task_id='same', obligations=['q'], packet_data={'role': 'other'})
    def test_malformed_json_keeps_semantic_metadata(self):
        class Malformed(FakeInputs):
            def invoke_agent(self, role, *, input, on_error):
                value = super().invoke_agent(role, input=input, on_error=on_error)
                value['result'].update(kind='text', content=[{'type': 'text', 'text': '{broken'}]); return value
        fake = Malformed(); runner = AgentRunner(fake, Budget())
        stage = runner.call('event_researcher', parse_request(fake), task_id='same', obligations=['q'], packet_data={'evidence_packet': []})
        self.assertEqual('failed', stage.status); self.assertEqual('synthetic-model', stage.semantic_metadata['model'])


class MemoryTests(unittest.TestCase):
    def test_only_exact_first_run_absence_continues(self):
        value = result(FakeInputs(memory=CodedFailure('dynamic_skill_not_initialized')))
        self.assertFalse(value['memory_update']['write_attempted'])
        with self.assertRaisesRegex(ContractError, 'read_blocked'): result(FakeInputs(memory=CodedFailure('node_not_found')))
    def test_cohort_not_misfiled_under_drug_class(self):
        fake = FakeInputs(example_inputs('cohort_pattern')); value = result(fake)
        self.assertEqual([], fake.memory_calls); self.assertEqual('not_requested', value['memory_update']['status'])
    def test_mutable_handle_rejected_by_readonly_path(self):
        with self.assertRaisesRegex(ContractError, 'readonly_memory_required'): result(FakeInputs(memory=MemoryView(mutable=True)))
    def test_prior_memory_is_not_fresh_evidence(self):
        fake = FakeInputs(); value = result(fake)
        self.assertFalse(any(e['source_id'] == 'group_memory' for e in value['evidence']))
        self.assertEqual('prior_memory_not_fresh_evidence', fake.calls[0][1]['memory_context']['origin'])
    def test_large_memory_not_silently_truncated(self):
        fake = FakeInputs(memory=MemoryView('x' * 16001)); value = result(fake)
        projection = fake.calls[0][1]['memory_context']
        self.assertEqual(1, projection['omitted_count']); self.assertEqual([], projection['paragraphs'])
        self.assertTrue(value['hypothesis_results'])
    def test_guarded_commit_cannot_write(self):
        with self.assertRaisesRegex(ContractError, 'not_admitted'): commit_memory_change()
    def test_lesson_preview_and_duplicate_no_change(self):
        def learning(p, _):
            p['items'][0].update(proposed_verdict='supported', lesson='Separate the endpoint result from a possible explanation.'); return p
        value = result(FakeInputs(transforms={'hypothesis_analyst': learning}))
        proposal = value['memory_update']; self.assertEqual('preview', proposal['status']); self.assertFalse(proposal['write_attempted'])
        again = result(FakeInputs(transforms={'hypothesis_analyst': learning}, memory=MemoryView(proposal['operations'][0]['new_text'])))
        self.assertEqual('no_change', again['memory_update']['status'])
    def test_inconclusive_hypothesis_not_learned(self):
        def learning(p, _):
            p['items'][0]['lesson'] = 'Potential idea only'; return p
        value = result(FakeInputs(transforms={'hypothesis_analyst': learning}))
        self.assertFalse(value['hypothesis_results'][0]['memory_eligibility'])
        self.assertNotIn('Potential idea only', str(value['memory_update']['operations']))


if __name__ == '__main__': unittest.main()
