import copy
import json
import unittest
from types import SimpleNamespace
from test_mcp_discovery_agent_smoke import ASSET, Inputs


def subject():
    base = {"__name__": "base_test"}
    source = (ASSET / "mcp_discovery_agent_smoke_adapter.py").read_text().replace("from adapters.base import Adapter", "class Adapter:\n    pass")
    exec(compile(source, "base_adapter", "exec"), base)
    source = (ASSET / "mcp_discovery_agent_smoke_v0_1_2_adapter.py").read_text()
    start, end = source.index("try:\n"), source.index('AGENT_ORCHESTRATION_OWNER')
    source = source[:start] + source[end:]
    namespace = {"__name__": "bedrock_text_test", "base": SimpleNamespace(**base)}
    exec(compile(source, "bedrock_adapter", "exec"), namespace)
    return namespace["McpDiscoveryAgentSmokeBedrockAdapter"]()


class TextInputs(Inputs):
    def invoke_agent(self, *args, **kwargs):
        result = super().invoke_agent(*args, **kwargs)
        value = result["result"]["content"][0]["value"]
        result["result"] = {"schema_version": "agent_result.v1", "kind": "text", "content": [{"type": "text", "text": json.dumps(value)}]}
        return result


class BedrockTextCompatibilityTest(unittest.TestCase):
    def test_signed_bedrock_text_uses_the_same_closed_business_contract(self):
        inputs = TextInputs()
        response = subject().invoke(inputs, {})
        self.assertEqual(response["outputs"]["smoke_result"]["returned_record_count"], 5)
        self.assertEqual([call[0] for call in inputs.calls], ["child", "agent"])

    def test_existing_json_and_local_text_responses_remain_accepted(self):
        for inputs in (Inputs(), Inputs(legacy=True)):
            self.assertEqual(subject().invoke(inputs, {})["status"], "success")

    def test_mismatched_observations_are_still_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "observation_mismatch"):
            subject().invoke(TextInputs(mutation=lambda value: value.update(returned_record_count=99)), {})

    def test_malformed_and_ambiguous_text_never_become_success(self):
        for text in ('```json\n{}\n```', '[{}]', '{"summary":"one","summary":"two"}', 'x' * 2049):
            class Bad(TextInputs):
                def invoke_agent(self, *args, **kwargs):
                    response = super().invoke_agent(*args, **kwargs)
                    response["result"]["content"][0]["text"] = text
                    return response
            with self.subTest(text_length=len(text)), self.assertRaises((RuntimeError, ValueError)):
                subject().invoke(Bad(), {})

    def test_multiple_text_blocks_are_rejected(self):
        class Bad(TextInputs):
            def invoke_agent(self, *args, **kwargs):
                response = super().invoke_agent(*args, **kwargs)
                response["result"]["content"].append(copy.deepcopy(response["result"]["content"][0]))
                return response
        with self.assertRaisesRegex(RuntimeError, "content_invalid"):
            subject().invoke(Bad(), {})
