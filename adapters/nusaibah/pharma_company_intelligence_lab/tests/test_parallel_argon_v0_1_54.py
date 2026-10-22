"""Provider-free concurrency, version isolation and all-role model migration."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from importlib.util import find_spec
import json
from pathlib import Path
import socket
import sys
from threading import Barrier, Event, Lock
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]

from agent_chunks_v0_1_47 import ChunkCoordinator as PreviousCoordinator
from agent_chunks_v0_1_54 import ChunkCoordinator
import legacy_preparation_helpers_v0_1_23 as legacy


class ParallelAllowanceTests(unittest.TestCase):
    def setUp(self):
        blocker = patch.object(socket.socket, 'connect', side_effect=AssertionError('unexpected network'))
        blocker.start()
        self.addCleanup(blocker.stop)

    def exercise_overlap(self, groups):
        coordinator = ChunkCoordinator()
        barrier = Barrier(16)
        release = Event()
        lock = Lock()
        entered = 0

        def work(index):
            def invoke():
                nonlocal entered
                with lock:
                    ordinal = entered
                    entered += 1
                if ordinal < 15:
                    barrier.wait(timeout=10)
                    if not release.wait(timeout=10):
                        raise AssertionError('fixture release timed out')
                return index
            return coordinator.dispatch(legacy.RESEARCH_ROLES[index % 3],
                {'company_id': 13, 'response_contract': {}}, invoke)

        with ThreadPoolExecutor(max_workers=len(groups)) as driver:
            futures = [driver.submit(coordinator.parallel, group, work) for group in groups]
            try:
                barrier.wait(timeout=10)
                self.assertEqual(15, coordinator.proof()['observed_peak_parallel_calls'])
            finally:
                release.set()
            results = [future.result(timeout=10) for future in futures]
        for group, outcomes in zip(groups, results):
            self.assertEqual(list(group), [row['value'] for row in outcomes])
            self.assertTrue(all(row['status'] == 'completed' for row in outcomes))
        self.assertEqual(18, coordinator.calls)
        self.assertEqual(0, coordinator.active)
        self.assertEqual(48, coordinator.max_calls)
        self.assertEqual(3300, coordinator.execution_seconds)
        self.assertEqual(180, coordinator.publication_reserve_seconds)
        self.assertEqual(15, coordinator.proof()['max_parallel_calls'])

    def test_fifteen_calls_overlap_and_results_keep_plan_order(self):
        self.exercise_overlap([list(range(18))])

    def test_overlapping_schedulers_share_one_fifteen_call_semaphore(self):
        self.exercise_overlap([list(range(9)), list(range(9, 18))])

    def test_allowance_is_an_integer_in_the_closed_range(self):
        for value in (1, 3, 10, 15):
            self.assertEqual(value, ChunkCoordinator(parallelism=value).parallelism)
        for value in (True, False, 0, -1, 16, 1.5, '15', None):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'agent_parallelism_must_be_1_to_15'):
                ChunkCoordinator(parallelism=value)

    def test_faster_dispatch_does_not_increase_the_shared_call_budget(self):
        coordinator = ChunkCoordinator(max_calls=13)
        calls = []
        lock = Lock()
        def work(index):
            def invoke():
                with lock:
                    calls.append(index)
                return index
            return coordinator.dispatch(legacy.RESEARCH_ROLES[index % 3], {'company_id': 13}, invoke)
        results = coordinator.parallel(list(range(18)), work)
        self.assertEqual(13, coordinator.calls)
        self.assertEqual(13, len(calls))
        self.assertEqual(5, sum(row['status'] == 'unresolved' for row in results))

    def test_publication_reserve_still_prevents_a_late_provider_call(self):
        coordinator = ChunkCoordinator(seconds=100, clock=lambda: 0)
        with self.assertRaises(legacy.UnresolvedAgentResponse):
            coordinator.dispatch(legacy.RESEARCH_ROLES[0], {'company_id': 13},
                lambda: self.fail('late provider call must not be dispatched'))
        self.assertEqual(0, coordinator.calls)

    def test_previous_published_coordinator_keeps_its_three_call_ceiling(self):
        self.assertEqual(3, PreviousCoordinator(parallelism=3).parallelism)
        with self.assertRaises(ValueError):
            PreviousCoordinator(parallelism=4)


class AllRoleArgonContractTests(unittest.TestCase):
    def test_model_migration_changes_only_models_and_affected_contract_versions(self):
        manifest = json.loads((ROOT / 'nusaibah_pharma_company_intelligence_lab.asset.json').read_text())
        previous = manifest['versions']['0.1.53']
        current = deepcopy(manifest['versions']['0.1.54'])
        self.assertEqual(9, len(current['agents']))
        migrated = []
        for role, agent in current['agents'].items():
            old = previous['agents'][role]
            changed = False
            for step, old_step in zip(agent['definition']['chain']['steps'], old['definition']['chain']['steps']):
                policy = step['provider_policy']
                self.assertEqual('gemini-4-argon', policy['model'])
                self.assertEqual('global', policy['provider_vault']['execution_location'])
                self.assertEqual(old_step['provider_policy']['generation_policy'], policy['generation_policy'])
                changed |= old_step['provider_policy']['model'] != policy['model']
                policy['model'] = old_step['provider_policy']['model']
            if changed:
                migrated.append(role)
                major, minor, patch_number = map(int, old['contract_version'].split('.'))
                self.assertEqual(f'{major}.{minor}.{patch_number + 1}', agent['contract_version'])
                self.assertEqual(agent['contract_version'], agent['definition']['chain']['version'])
                agent['contract_version'] = old['contract_version']
                agent['definition']['chain']['version'] = old['definition']['chain']['version']
            else:
                self.assertEqual(old['contract_version'], agent['contract_version'])
        self.assertEqual(7, len(migrated))
        self.assertEqual(previous, current)
        self.assertEqual('0.1.54', manifest['default'])
        dependencies = json.loads((ROOT / 'adapter.dependencies.json').read_text())
        self.assertEqual('0.1.137', dependencies['runtime_package']['minimum_version'])

    def test_role_authority_catalog_is_unchanged(self):
        old = json.loads((ROOT / 'pharma_roles_v0_1_53.json').read_text())
        new = json.loads((ROOT / 'pharma_roles_v0_1_54.json').read_text())
        self.assertEqual('0.1.54', new['target_asset_version'])
        new['target_asset_version'] = old['target_asset_version']
        self.assertEqual(old, new)


class OrchestrationParityTests(unittest.TestCase):
    def setUp(self):
        if find_spec('devtools.business_text_redaction') is None:
            self.skipTest('Requires qualification against the actual installed SDK, not intake stubs.')
        blocker = patch.object(socket.socket, 'connect', side_effect=AssertionError('unexpected network'))
        blocker.start()
        self.addCleanup(blocker.stop)

    def test_default_fifteen_preserves_canonical_publication_and_agent_count(self):
        from test_durable_batched_v0_1_51 import BatchedInputs
        from orchestration_v0_1_53 import invoke_v0_1_53
        from orchestration_v0_1_54 import invoke_v0_1_54
        before_inputs = BatchedInputs()
        after_inputs = BatchedInputs()
        before = invoke_v0_1_53(before_inputs, asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.53')
        after = invoke_v0_1_54(after_inputs, asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.54')
        row = after['outputs']['intelligence_dossier']['company_results'][0]
        self.assertTrue(row['skill_publication']['publication_complete'])
        self.assertEqual(15, row['agent_input_preflight']['max_parallel_calls'])
        self.assertEqual(3, before['outputs']['intelligence_dossier']['company_results'][0]['agent_input_preflight']['max_parallel_calls'])
        self.assertEqual(before['metrics']['agent_call_count'], after['metrics']['agent_call_count'])
        for role in ('company_memory', 'company_methodology'):
            self.assertEqual(before_inputs.store[(13, role)]['text'], after_inputs.store[(13, role)]['text'])
        self.assertNotIn(legacy.BENCHMARK_ROLE, after_inputs.role_calls)
        self.assertNotIn(legacy.PLANNER_ROLE, after_inputs.role_calls)

    def test_caller_can_request_a_lower_allowance(self):
        from test_durable_batched_v0_1_51 import BatchedInputs
        from orchestration_v0_1_54 import invoke_v0_1_54
        source = BatchedInputs()
        source['variables']['agent_chunk_parallelism'] = 1
        result = invoke_v0_1_54(source, asset_identity='nusaibah.pharma_company_intelligence_lab:0.1.54')
        proof = result['outputs']['intelligence_dossier']['company_results'][0]['agent_input_preflight']
        self.assertEqual(1, proof['max_parallel_calls'])
        self.assertEqual(1, proof['observed_peak_parallel_calls'])


if __name__ == '__main__':
    unittest.main()
