from __future__ import annotations

import sys
import unittest
from pathlib import Path

ASSET_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSET_ROOT))

from agent_contract import extract_agent_json  # noqa: E402


def _envelope(value: dict) -> dict:
    return {
        "status": "completed",
        "result": {
            "schema_version": "agent_result.v1",
            "kind": "json",
            "content": [{"type": "json", "value": value}],
            "text": "{}",
            "model": "fake",
            "usage": {},
            "metadata": {},
            "provider_metadata": {
                "schema_version": "agent_provider_metadata.v1",
                "turns": [],
            },
        },
    }


def _value() -> dict:
    return {
        "schema_version": "pharma_strategic_agent.v1",
        "company_id": 13,
        "role": "strategic_analyst",
        "status": "completed",
    }


class AgentEnvelopeContractTests(unittest.TestCase):
    def test_accepts_exact_completed_typed_json_identity(self) -> None:
        value, result = extract_agent_json(
            _envelope(_value()),
            expected_role="strategic_analyst",
            company_id=13,
            expected_schema_version="pharma_strategic_agent.v1",
        )

        self.assertEqual(value["company_id"], 13)
        self.assertEqual(result["kind"], "json")

    def test_rejects_wrong_role(self) -> None:
        value = _value()
        value["role"] = "evidence_critic"

        with self.assertRaisesRegex(RuntimeError, "wrong role identity"):
            extract_agent_json(
                _envelope(value),
                expected_role="strategic_analyst",
                company_id=13,
                expected_schema_version="pharma_strategic_agent.v1",
            )

    def test_rejects_wrong_business_schema(self) -> None:
        value = _value()
        value["schema_version"] = "wrong.v1"

        with self.assertRaisesRegex(RuntimeError, "unexpected business schema"):
            extract_agent_json(
                _envelope(value),
                expected_role="strategic_analyst",
                company_id=13,
                expected_schema_version="pharma_strategic_agent.v1",
            )

    def test_rejects_wrong_company(self) -> None:
        value = _value()
        value["company_id"] = 59

        with self.assertRaisesRegex(RuntimeError, "wrong company_id"):
            extract_agent_json(
                _envelope(value),
                expected_role="strategic_analyst",
                company_id=13,
                expected_schema_version="pharma_strategic_agent.v1",
            )

    def test_rejects_malformed_json_content_shape(self) -> None:
        envelope = _envelope(_value())
        envelope["result"]["content"] = [{"type": "text", "text": "{}"}]

        with self.assertRaisesRegex(RuntimeError, "invalid typed JSON content"):
            extract_agent_json(
                envelope,
                expected_role="strategic_analyst",
                company_id=13,
                expected_schema_version="pharma_strategic_agent.v1",
            )

    def test_rejects_non_completed_runtime_envelope(self) -> None:
        envelope = _envelope(_value())
        envelope["status"] = "failed"

        with self.assertRaisesRegex(RuntimeError, "did not complete"):
            extract_agent_json(
                envelope,
                expected_role="strategic_analyst",
                company_id=13,
                expected_schema_version="pharma_strategic_agent.v1",
            )


if __name__ == "__main__":
    unittest.main()
