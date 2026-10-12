"""Development consumer contract tests, without providers or network."""
from __future__ import annotations
import copy
import json
import unittest
from pathlib import Path

ASSET = Path(__file__).resolve().parents[1] / "adapters/nusaibah/mcp_discovery_agent_smoke"


def subject():
    path = ASSET / "mcp_discovery_agent_smoke_adapter.py"
    source = path.read_text().replace("from adapters.base import Adapter", "class Adapter:\n    pass")
    namespace = {"__name__": "smoke_test"}
    exec(compile(source, str(path), "exec"), namespace)
    return namespace["McpDiscoveryAgentSmokeAdapter"]()


def child(count=5, lookup=None):
    result = {"status": "completed", "records": [{"lake_id": f"fixture-{i}", "name": f"Lake {i}"} for i in range(count)], "record_count": count}
    if lookup is not None:
        result["lookup"] = lookup
    return {"status": "success", "result": result, "provenance": {"callable_asset": True, "asset_key": "nusaibah.abstract_mcp_dlm", "asset_version": "0.1.1"}}


class Inputs(dict):
    def __init__(self, variables=None, *, response=None, legacy=False, mutation=None, child_error=None):
        super().__init__(variables={} if variables is None else variables)
        self.response = child() if response is None else response
        self.legacy, self.mutation, self.child_error = legacy, mutation, child_error
        self.calls = []

    def invoke_asset(self, role, *, variables, on_error):
        self.calls.append(("child", role, variables, on_error))
        if self.child_error:
            raise self.child_error
        return copy.deepcopy(self.response)

    def invoke_agent(self, role, *, input, on_error):
        self.calls.append(("agent", role, input, on_error))
        value = {"schema_version": "mcp_discovery_agent_summary.v1", "role": role, **input["observations"], "summary": "The bounded read returned its observed number of records."}
        if self.mutation:
            self.mutation(value)
        result = {"text": json.dumps(value)} if self.legacy else {"schema_version": "agent_result.v1", "kind": "json", "content": [{"type": "json", "value": value}]}
        return {"status": "completed", "result": result}


class DiscoveryAgentSmokeTest(unittest.TestCase):
    def test_new_version_declares_bounded_server_preparation_and_preserves_legacy(self):
        manifest = json.loads((ASSET / 'mcp_discovery_agent_smoke.asset.json').read_text())
        self.assertEqual(manifest['default'], '0.1.1')
        legacy = manifest['versions']['0.1.0']
        current = copy.deepcopy(manifest['versions']['0.1.1'])
        self.assertEqual(current['callable_assets']['discovery'].pop('prepared_inputs'), {
            'tool_request': {'operation': 'lakes.list', 'page_size': 5},
        })
        self.assertEqual(current, legacy)
        namespace = {'__name__': 'prepared_smoke_test'}
        base = (ASSET / 'mcp_discovery_agent_smoke_adapter.py').read_text().replace('from adapters.base import Adapter', 'class Adapter:\n    pass')
        exec(compile(base, 'base_adapter', 'exec'), namespace)
        module = (ASSET / 'mcp_discovery_agent_smoke_v0_1_1_adapter.py').read_text().replace(
            'try:\n    from .mcp_discovery_agent_smoke_adapter import McpDiscoveryAgentSmokeAdapter\nexcept ImportError:  # Existing external adapter-root discovery mode.\n    from mcp_discovery_agent_smoke_adapter import McpDiscoveryAgentSmokeAdapter', '')
        exec(compile(module, 'versioned_adapter', 'exec'), namespace)
        adapter = namespace['McpDiscoveryAgentSmokePreparedAdapter']()
        self.assertEqual(adapter.version, '0.1.1')
        self.assertEqual(adapter.invoke(Inputs(), {})['outputs']['smoke_result']['returned_record_count'], 5)

    def test_one_child_then_one_agent_receiving_only_observations(self):
        inputs = Inputs()
        result = subject().invoke(inputs, {})["outputs"]["smoke_result"]
        self.assertEqual(result["returned_record_count"], 5)
        self.assertEqual((result["child_call_count"], result["agent_call_count"]), (1, 1))
        self.assertEqual([c[0] for c in inputs.calls], ["child", "agent"])
        self.assertEqual(inputs.calls[0], ("child", "discovery", {"page_size": 5}, "raise"))
        self.assertNotIn("Lake 0", json.dumps(inputs.calls[1][2]))
        self.assertNotIn("fixture-0", json.dumps(inputs.calls[1][2]))

    def test_empty_read_is_a_success(self):
        self.assertEqual(subject().invoke(Inputs(response=child(0)), {})["outputs"]["smoke_result"]["returned_record_count"], 0)

    def test_local_php_json_text_contract_is_supported(self):
        self.assertEqual(subject().invoke(Inputs(legacy=True), {})["status"], "success")

    def test_resolution_and_confirmation_are_preserved_without_selection(self):
        for state in ("exact", "suggestions", "ambiguous", "no_match", "unresolved"):
            with self.subTest(state=state):
                inputs = Inputs({"q": " Hyser "}, response=child(1, {"status": state, "requires_confirmation": state != "exact"}))
                result = subject().invoke(inputs, {})["outputs"]["smoke_result"]
                self.assertEqual(result["lookup_status"], state)
                self.assertEqual(result["requires_confirmation"], state != "exact")
                self.assertEqual(inputs.calls[0][2], {"page_size": 5, "q": "Hyser"})
                self.assertNotIn("Hyser", json.dumps(inputs.calls[1][2]))
                self.assertEqual(len(inputs.calls), 2)

    def test_authority_and_operation_variables_reject_before_calls(self):
        for key in ("operation", "lake_id", "node_key", "actor_id", "client_id", "role", "tool_request", "model", "endpoint", "page_size"):
            with self.subTest(key=key):
                inputs = Inputs({key: "caller-value"})
                with self.assertRaises(ValueError):
                    subject().invoke(inputs, {})
                self.assertEqual(inputs.calls, [])

    def test_invalid_query_rejects_before_calls(self):
        for query in (None, 1, True, "", "  ", "x" * 121, "x\n", "https://fixture.invalid"):
            with self.subTest(query=query):
                inputs = Inputs({"q": query})
                with self.assertRaises(ValueError):
                    subject().invoke(inputs, {})
                self.assertEqual(inputs.calls, [])

    def test_failed_child_prevents_agent_and_has_no_retry(self):
        inputs = Inputs(child_error=RuntimeError("denied"))
        with self.assertRaises(RuntimeError):
            subject().invoke(inputs, {})
        self.assertEqual(len(inputs.calls), 1)

    def test_error_child_envelope_prevents_agent(self):
        inputs = Inputs(response={"status": "error", "result": None})
        with self.assertRaises(RuntimeError):
            subject().invoke(inputs, {})
        self.assertEqual(len(inputs.calls), 1)

    def test_wrong_child_identity_prevents_agent(self):
        for field, value in (("asset_key", "other.asset"), ("asset_version", "0.1.0"), ("callable_asset", False)):
            with self.subTest(field=field):
                response = child()
                response["provenance"][field] = value
                inputs = Inputs(response=response)
                with self.assertRaises(RuntimeError):
                    subject().invoke(inputs, {})
                self.assertEqual(len(inputs.calls), 1)

    def test_child_count_and_budget_are_validated(self):
        for count, records in ((True, []), (1, []), (51, [{}] * 51), (1, ["bad"]), (None, [])):
            with self.subTest(count=count):
                response = child()
                response["result"].update(record_count=count, records=records)
                with self.assertRaises(RuntimeError):
                    subject().invoke(Inputs(response=response), {})

    def test_child_byte_budget_is_enforced(self):
        response = child(1)
        response["result"]["records"][0]["name"] = "x" * 65536
        with self.assertRaises(RuntimeError):
            subject().invoke(Inputs(response=response), {})

    def test_query_requires_valid_explicit_confirmation(self):
        for lookup in ({}, {"status": "invented", "requires_confirmation": True}, {"status": "exact", "requires_confirmation": True}, {"status": "suggestions", "requires_confirmation": False}, {"status": "exact", "requires_confirmation": 0}):
            with self.subTest(lookup=lookup):
                with self.assertRaises(RuntimeError):
                    subject().invoke(Inputs({"q": "Hyper"}, response=child(1, lookup)), {})

    def test_agent_cannot_change_observations_or_identity(self):
        changes = [lambda v: v.update(returned_record_count=6), lambda v: v.update(returned_record_count=True), lambda v: v.update(requires_confirmation=True), lambda v: v.update(role="other"), lambda v: v.update(schema_version="other"), lambda v: v.update(extra="invented"), lambda v: v.update(summary="x" * 241), lambda v: v.update(summary="https://fixture.invalid")]
        for change in changes:
            with self.subTest(change=change):
                inputs = Inputs(mutation=change)
                with self.assertRaises(RuntimeError):
                    subject().invoke(inputs, {})
                self.assertEqual(len(inputs.calls), 2)

    def test_manifest_has_one_pinned_child_and_logical_agent(self):
        manifest = json.loads((ASSET / "mcp_discovery_agent_smoke.asset.json").read_text())
        version = manifest["versions"]["0.1.0"]
        self.assertEqual(set(version["callable_assets"]), {"discovery"})
        self.assertEqual(version["callable_assets"]["discovery"]["asset_version"], "0.1.1")
        self.assertEqual(set(version["agents"]), {"read_summarizer"})
        for key in ("runtime_tools", "skills", "published_skills"):
            self.assertNotIn(key, version)


if __name__ == "__main__":
    unittest.main()
