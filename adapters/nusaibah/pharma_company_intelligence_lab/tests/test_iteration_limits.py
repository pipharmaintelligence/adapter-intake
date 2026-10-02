from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from threading import Barrier
from types import ModuleType
import unittest
from unittest.mock import patch

ASSET_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSET_ROOT))

# This budget test needs only the Adapter base type, not an installed runtime.
# Full orchestration tests separately exercise the real runtime helper imports.
try:
    from adapters.base import Adapter
except ModuleNotFoundError as error:
    if error.name not in {"adapters", "adapters.base"}:
        raise
    package = ModuleType("adapters")
    base = ModuleType("adapters.base")
    base.Adapter = object
    package.base = base
    with patch.dict(sys.modules, {"adapters": package, "adapters.base": base}):
        import nusaibah_pharma_company_intelligence_lab_adapter as adapter
else:
    import nusaibah_pharma_company_intelligence_lab_adapter as adapter


class RecordingRuntime:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[tuple[str, int]] = []
        self.fail = fail

    def invoke_agent(self, role, *, input, on_error):
        self.calls.append((role, input["company_id"]))
        if self.fail:
            raise RuntimeError("synthetic invocation failure")
        return "completed"


def bounded(runtime, company_ids=(13,), mode="preview"):
    request = adapter.validate_batch_request({
        "variables": {"company_ids": list(company_ids), "memory_mode": mode},
    })
    return adapter._BoundedAgentInputs(runtime, request)


class AgentIterationLimitTests(unittest.TestCase):
    def exercise_company(self, inputs, company_id, *, mode):
        roles = [
            "memory_benchmark_reviewer",
            *(["methodology_planner"] * 4),
            "portfolio_researcher", "market_researcher", "regulatory_risk_researcher",
            "strategic_analyst", "evidence_critic", "intelligence_synthesizer",
            "memory_benchmark_reviewer",
        ]
        if mode == "apply":
            roles.append("memory_benchmark_reviewer")
        for role in roles:
            inputs.invoke_agent(role, input={"company_id": company_id})

    def test_maximum_batch_completes_at_60_preview_or_65_apply_calls(self):
        for mode, expected in [("preview", 60), ("apply", 65)]:
            with self.subTest(mode=mode):
                runtime = RecordingRuntime()
                inputs = bounded(runtime, (1, 2, 3, 4, 5), mode)
                for company_id in (1, 2, 3, 4, 5):
                    self.exercise_company(inputs, company_id, mode=mode)
                self.assertEqual(inputs.agent_call_count, expected)
                self.assertEqual(inputs.agent_call_limit, expected)
                with self.assertRaisesRegex(adapter.AgentContractValidationError, "iteration limit"):
                    inputs.invoke_agent("memory_benchmark_reviewer", input={"company_id": 1})
                self.assertEqual(len(runtime.calls), expected)

    def test_fifth_planner_call_is_rejected_before_dispatch(self):
        runtime = RecordingRuntime()
        inputs = bounded(runtime)
        for _ in range(4):
            inputs.invoke_agent("methodology_planner", input={"company_id": 13})
        with self.assertRaises(adapter.AgentContractValidationError) as caught:
            inputs.invoke_agent("methodology_planner", input={"company_id": 13})
        self.assertEqual(caught.exception.code, "pharma_agent_business_schema_invalid")
        self.assertEqual(len(runtime.calls), 4)

    def test_parallel_duplicate_role_cannot_race_past_its_limit(self):
        runtime = RecordingRuntime()
        inputs = bounded(runtime)
        start = Barrier(8)

        def invoke(_):
            start.wait(timeout=5)
            try:
                inputs.invoke_agent("portfolio_researcher", input={"company_id": 13})
                return True
            except adapter.AgentContractValidationError:
                return False

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(invoke, range(8)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(len(runtime.calls), 1)

    def test_failed_dispatch_is_counted_and_not_retried_by_adapter(self):
        runtime = RecordingRuntime(fail=True)
        inputs = bounded(runtime)
        with self.assertRaisesRegex(RuntimeError, "synthetic invocation"):
            inputs.invoke_agent("market_researcher", input={"company_id": 13})
        with self.assertRaises(adapter.AgentContractValidationError):
            inputs.invoke_agent("market_researcher", input={"company_id": 13})
        self.assertEqual(len(runtime.calls), 1)

    def test_unknown_role_or_company_cannot_consume_another_company_budget(self):
        runtime = RecordingRuntime()
        inputs = bounded(runtime)
        for role, company_id in [("market_researcher", 59), ("extra_role", 13), ("market_researcher", True)]:
            with self.subTest(role=role, company_id=company_id):
                with self.assertRaises(adapter.AgentContractValidationError):
                    inputs.invoke_agent(role, input={"company_id": company_id})
        self.assertEqual(runtime.calls, [])

    def test_new_run_gets_a_fresh_budget(self):
        runtime = RecordingRuntime()
        for _ in range(2):
            inputs = bounded(runtime)
            self.exercise_company(inputs, 13, mode="preview")
            self.assertEqual(inputs.agent_call_count, 12)
        self.assertEqual(len(runtime.calls), 24)

    def test_commit_preflight_rejects_insufficient_remaining_benchmark_budget(self):
        runtime = RecordingRuntime()
        inputs = bounded(runtime, mode="apply")
        self.exercise_company(inputs, 13, mode="preview")
        inputs.require_commit_benchmark_capacity([13])
        inputs.invoke_agent("memory_benchmark_reviewer", input={"company_id": 13})
        with self.assertRaises(adapter.AgentContractValidationError):
            inputs.require_commit_benchmark_capacity([13])
        self.assertEqual(len(runtime.calls), 13)

    def test_excess_resolved_companies_fail_before_normalization(self):
        with self.assertRaises(adapter.AgentContractValidationError):
            adapter.resolve_company_records({"companies": [{"id": index} for index in range(1, 7)]})


if __name__ == "__main__":
    unittest.main()
