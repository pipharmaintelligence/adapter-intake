from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace


ADAPTER_PATH = (
    Path(__file__).resolve().parents[1]
    / "adapters"
    / "nusaibah"
    / "agent_capability_lab"
    / "nusaibah_agent_capability_lab_adapter.py"
)


def _namespace(functions: set[str]) -> dict[str, object]:
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    constants = {
        "HEALTHCARE_NLP_TOOL_ROLE",
        "HEALTHCARE_NLP_CAPABILITY",
        "MAX_HEALTHCARE_TEXT_CHARS",
        "DEFAULT_HEALTHCARE_TEXT",
        "CANONICAL_COMPANY_ID",
    }
    selected: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = {
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            }
            if names & constants:
                selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in functions:
            selected.append(node)

    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, object] = {"Any": object}
    exec(compile(module, str(ADAPTER_PATH), "exec"), namespace)
    return namespace


class _ToolInputs:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object], str]] = []

    def invoke_tool(
        self,
        role: str,
        *,
        input: dict[str, object],
        on_error: str,
    ) -> dict[str, object]:
        self.calls.append((role, input, on_error))
        return {
            "status": "completed",
            "capability_ref": "healthcare.nlp.analyze_entities",
            "records": [
                {
                    "entityMentions": [
                        {"text": {"content": "aspirin"}},
                        {"text": {"content": "metformin"}},
                    ],
                    "entities": [
                        {"entityId": "e1"},
                        {"entityId": "e2"},
                    ],
                    "relationships": [{"confidence": 0.9}],
                    "fhirBundle": {"resourceType": "Bundle", "entry": []},
                }
            ],
            "provenance": {
                "runtime_mcp_tool": True,
                "role": "healthcare_nlp",
            },
        }


def test_healthcare_nlp_entities_calls_governed_tool_and_projects_counts_only() -> None:
    namespace = _namespace(
        {
            "_resolve_healthcare_text",
            "_summarize_healthcare_entity_record",
            "_run_healthcare_nlp_entities",
        }
    )
    inputs = _ToolInputs()

    result = namespace["_run_healthcare_nlp_entities"](
        inputs,
        {"healthcare_text": "Synthetic note: patient takes aspirin."},
    )

    assert inputs.calls == [
        (
            "healthcare_nlp",
            {"body": {"documentContent": "Synthetic note: patient takes aspirin."}},
            "raise",
        )
    ]
    assert result["healthcare_nlp_status"] == "completed"
    assert result["healthcare_nlp_runtime_provenance_verified"] is True
    assert result["healthcare_nlp_entity_mention_count"] == 2
    assert result["healthcare_nlp_entity_count"] == 2
    assert result["healthcare_nlp_relationship_count"] == 1
    assert result["healthcare_nlp_fhir_bundle_present"] is True
    assert "records" not in result
    assert "entityMentions" not in result


def test_healthcare_nlp_rejects_unexpected_capability_provenance() -> None:
    namespace = _namespace(
        {
            "_resolve_healthcare_text",
            "_summarize_healthcare_entity_record",
            "_run_healthcare_nlp_entities",
        }
    )

    class Inputs(_ToolInputs):
        def invoke_tool(self, role: str, *, input: dict[str, object], on_error: str):
            result = super().invoke_tool(role, input=input, on_error=on_error)
            result["capability_ref"] = "unexpected.capability"
            return result

    try:
        namespace["_run_healthcare_nlp_entities"](Inputs(), {})
    except RuntimeError as exc:
        assert str(exc) == "Healthcare NLP returned unexpected capability provenance."
    else:
        raise AssertionError("unexpected capability provenance must fail closed")


def test_healthcare_nlp_text_is_bounded() -> None:
    namespace = _namespace({"_resolve_healthcare_text"})

    try:
        namespace["_resolve_healthcare_text"](
            {"healthcare_text": "x" * 12001}
        )
    except ValueError as exc:
        assert "must not exceed 12000 characters" in str(exc)
    else:
        raise AssertionError("oversized healthcare text must fail closed")


def test_combined_stage_passes_aggregated_healthcare_context_to_vertex() -> None:
    namespace = _namespace({"_run_vertex_healthcare_nlp_entities"})
    captured: dict[str, object] = {}

    namespace["_run_healthcare_nlp_entities"] = lambda inputs, variables: {
        "healthcare_nlp_status": "completed",
        "healthcare_nlp_entity_mention_count": 2,
        "healthcare_nlp_entity_count": 2,
        "healthcare_nlp_relationship_count": 1,
        "healthcare_nlp_fhir_bundle_present": True,
    }
    namespace["_canonical_company_memory"] = lambda inputs: object()

    def research(inputs, memory, *, supplemental_context=None):
        captured["supplemental_context"] = supplemental_context
        return (
            {
                "vertex_certification_status": "completed",
                "vertex_certification_reference_status": "verified",
            },
            "research",
            (SimpleNamespace(locator="https://example.test"),),
        )

    namespace["_run_vertex_certification_research"] = research

    result = namespace["_run_vertex_healthcare_nlp_entities"](
        object(),
        {},
    )

    assert captured["supplemental_context"] == {
        "healthcare_nlp": {
            "entity_mention_count": 2,
            "entity_count": 2,
            "relationship_count": 1,
            "fhir_bundle_present": True,
        }
    }
    assert result["vertex_healthcare_nlp_combined_verified"] is True
    assert result["vertex_healthcare_nlp_raw_clinical_text_forwarded"] is False
    assert result["vertex_healthcare_nlp_provenance_citation_count"] == 1


def test_manifest_declares_only_the_reviewed_healthcare_runtime_tool() -> None:
    manifest_path = (
        ADAPTER_PATH.parent / "nusaibah_agent_capability_lab.asset.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = manifest["versions"]["0.1.17"]
    tools = version["runtime_tools"]

    assert list(tools) == ["healthcare_nlp"]
    tool = tools["healthcare_nlp"]
    assert tool["tool_handle"] == "@healthcare_nlp"
    assert tool["tool_server_ref"] == "provider.google.healthcare_nlp"
    assert tool["capability_ref"] == "healthcare.nlp.analyze_entities"
    assert tool["consumer_type"] == "agent_runtime"
    assert tool["operation"] == "invoke"
    assert tool["execution_mode"] == "enforced"
