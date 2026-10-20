"""No provider calls: full-composition planning, complete windows and coexistence."""
from copy import deepcopy
import hashlib, json, unittest
from fakes import ASSET_ROOT, FakeInputs, example_inputs
from clinical_failure_intelligence import contracts_v0_1_3 as old
from clinical_failure_intelligence.contracts_v0_1_4 import canonical_bytes, parse_request
from clinical_failure_intelligence.runtime_access_v0_1_4 import AgentRunner
from clinical_failure_intelligence.policies_v0_1_4 import Budget
from clinical_failure_intelligence.analysis_packets_v0_1_4 import evidence_batches
from clinical_failure_intelligence.orchestration_v0_1_4 import run_analysis

class BudgetInputs(FakeInputs):
    def __init__(self, *args, cap=60000, **kwargs):
        super().__init__(*args, **kwargs)
        self.cap = cap
        self.budget_roles = []
    def agent_input_budget(self, role):
        assert not self.calls, "Budget inspection must precede the first paid call"
        self.budget_roles.append(role)
        return {"schema_version":"agent_input_budget.v1", "scope":"single_step_initial_request",
                "max_input_json_chars":self.cap, "max_input_json_bytes":262144}
    def invoke_agent(self, role, *, input, on_error="raise"):
        assert len(self.budget_roles) == 7
        assert len(canonical_bytes(input).decode()) <= self.cap
        return super().invoke_agent(role, input=input, on_error=on_error)

class Version014Tests(unittest.TestCase):
    def test_previous_version_bytes_and_manifest_contract_remain_immutable(self):
        frozen = json.loads((ASSET_ROOT/'tests/reference/published_013_frozen.json').read_text())
        for name, sha in frozen['files'].items():
            self.assertEqual(sha, hashlib.sha256((ASSET_ROOT/name).read_bytes()).hexdigest(), name)
        manifest = json.loads((ASSET_ROOT/'clinical_failure_intelligence.asset.json').read_text())
        self.assertEqual(frozen['manifest_contract'], manifest['versions']['0.1.3'])
        self.assertEqual('0.1.3', old.VERSION)

    def test_small_case_and_cohort_keep_business_and_memory_rules(self):
        for mode in ['mechanistic_case', 'cohort_pattern']:
            inputs = BudgetInputs(example_inputs(mode))
            result = run_analysis(inputs)['outputs']['clinical_intelligence']
            self.assertEqual('nusaibah.clinical_failure_intelligence@0.1.4', result['asset'])
            self.assertFalse(result['memory_update']['write_attempted'])
            self.assertEqual('not_attested', result['persistence']['status'])
            self.assertTrue(inputs.calls)

    def test_461_whole_unicode_windows_fit_both_limits_without_mutation(self):
        request = parse_request(example_inputs())
        for cap in [12000, 60000, 150000]:
            runner = AgentRunner(BudgetInputs(cap=cap), Budget())
            runner.prepare_input_budgets()
            rows = [{'evidence_id':str(i), 'text':('μ😀 {source} \"text\" '*50)+str(i)} for i in range(461)]
            before = canonical_bytes(rows)
            packet = lambda chunk: runner.packet('trial_researcher', request, task_id='trial:planning',
                obligations=['claim:planning'], packet_data={'evidence_packet':chunk})
            chunks = evidence_batches(rows, packet, max_bytes=120000,
                fits=lambda value: runner.packet_fits('trial_researcher', value))
            self.assertEqual(rows, [row for chunk in chunks for row in chunk])
            self.assertEqual(before, canonical_bytes(rows))
            self.assertTrue(all(runner.packet_fits('trial_researcher', packet(chunk)) for chunk in chunks))

    def test_too_small_policy_or_missing_optional_sdk_capability_spends_nothing(self):
        for inputs in [BudgetInputs(example_inputs(), cap=10), FakeInputs(example_inputs())]:
            result = run_analysis(inputs)['outputs']['clinical_intelligence']
            self.assertFalse(inputs.calls)
            self.assertEqual(2, len(result['evidence']))
            self.assertTrue(any(issue['code']=='clinical_agent_input_preflight_failed' for issue in result['quality']['issues']))
            self.assertFalse(result['memory_update']['write_attempted'])

    def test_atomic_oversize_evidence_is_preserved_and_deferred_before_call(self):
        runner = AgentRunner(BudgetInputs(cap=4000), Budget()); runner.prepare_input_budgets()
        request = parse_request(example_inputs())
        packet = {'evidence_packet':[{'evidence_id':'whole', 'text':'μ'*10000}]}
        before = canonical_bytes(packet)
        stage = runner.call('trial_researcher', request, task_id='atomic', obligations=['claim'], packet_data=packet)
        self.assertEqual('deferred', stage.status)
        self.assertEqual(0, runner.budget.calls)
        self.assertEqual(before, canonical_bytes(packet))
        self.assertFalse(runner.inputs.calls)

    def test_provider_free_preflight_remains_available_on_legacy_inputs(self):
        value = example_inputs(); value['variables']['preflight_only'] = True
        inputs = FakeInputs(value)
        result = run_analysis(inputs)
        self.assertEqual(0, result['metrics']['logical_agent_calls'])
        self.assertFalse(inputs.calls)


    def test_known_initial_call_plan_does_not_spend_past_existing_call_ceiling(self):
        from clinical_failure_intelligence.policies_v0_1_4 import ExecutionPolicy
        inputs = BudgetInputs(example_inputs())
        result = run_analysis(inputs, policy=ExecutionPolicy(max_agent_calls=1))
        self.assertFalse(inputs.calls)
        value = result['outputs']['clinical_intelligence']
        self.assertEqual(2, len(value['evidence']))
        self.assertTrue(any(issue['code']=='clinical_agent_input_preflight_failed' for issue in value['quality']['issues']))
        self.assertFalse(value['memory_update']['write_attempted'])

    def test_known_analysis_closure_is_checked_before_research_calls(self):
        class UnequalInputs(BudgetInputs):
            def agent_input_budget(self, role):
                value = super().agent_input_budget(role)
                if role == 'hypothesis_analyst':
                    value['max_input_json_chars'] = 1
                return value
        inputs = UnequalInputs(example_inputs())
        result = run_analysis(inputs)['outputs']['clinical_intelligence']
        self.assertFalse(inputs.calls)
        self.assertEqual(2, len(result['evidence']))
