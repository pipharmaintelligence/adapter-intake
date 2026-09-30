from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_DIR = ROOT / "adapters" / "nusaibah" / "bedrock_agent_capability_lab"
ADAPTER_PATH = ADAPTER_DIR / "nusaibah_bedrock_agent_capability_lab_adapter.py"
MANIFEST_PATH = ADAPTER_DIR / "nusaibah_bedrock_agent_capability_lab.asset.json"
PLAN_PATH = ADAPTER_DIR / "execution_plan.py"


def _adapter_namespace(
    functions: set[str],
    constants: set[str] | None = None,
) -> dict[str, object]:
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    selected: list[ast.stmt] = []
    wanted_constants = constants or set()

    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = {
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            }
            if names & wanted_constants:
                selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in functions:
            selected.append(node)

    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, object] = {
        "Any": object,
        "SimpleNamespace": SimpleNamespace,
    }
    exec(compile(module, str(ADAPTER_PATH), "exec"), namespace)
    return namespace


def _load_plan_module():
    spec = importlib.util.spec_from_file_location("bedrock_execution_plan", PLAN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _bedrock_envelope(text: str = "ok") -> dict[str, object]:
    return {
        "status": "completed",
        "result": {
            "schema_version": "agent_result.v1",
            "text": text,
            "provider_metadata": {
                "schema_version": "agent_provider_metadata.v1",
                "turns": [
                    {
                        "step_ordinal": 0,
                        "step_handle": "provider:text_generation",
                        "turn_index": 0,
                        "outcome": "terminal",
                        "provider_family": "bedrock",
                        "transport": "converse",
                        "model": "runtime-owned",
                        "usage": {},
                    }
                ],
            },
        },
    }


def test_manifest_is_independent_bedrock_reference_asset() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["key"] == "nusaibah.bedrock_agent_capability_lab"
    assert manifest["default"] == "0.1.5"
    assert list(manifest["versions"]) == ["0.1.5"]
    assert manifest["execution"] == {
        "allowed_substrates": ["local_worker"],
        "default_substrate": "local_worker",
    }

    version = manifest["versions"]["0.1.5"]
    assert set(version["agents"]) == {"bedrock_orchestrator"}
    assert "public_web" not in version

    agent = version["agents"]["bedrock_orchestrator"]
    assert agent["contract_key"] == "agent.nusaibah.bedrock_agent_capability_lab"

    registry_entry = agent["definition"]["registry_entries"][0]
    assert registry_entry["handle"] == "provider:text_generation"
    assert registry_entry["version"] == "1.0.0"
    assert registry_entry["metadata"] == {
        "provisioning_source": "pi_1895_capability_lab"
    }

    chain = agent["definition"]["chain"]
    assert chain["metadata"] == {
        "provisioning_source": "pi_1957_bedrock_capability_lab_0_1_5"
    }
    assert chain["chain_id"] == "agent.nusaibah.bedrock_agent_capability_lab"
    assert len(chain["steps"]) == 1

    step = chain["steps"][0]
    assert step["provider"] == "bedrock"
    policy = step["provider_policy"]
    assert policy["provider"] == "bedrock"
    assert policy["model"] == "eu.anthropic.claude-sonnet-5"
    assert policy["region"] == "eu-west-1"
    assert "search_enabled" not in policy
    assert "search_mode" not in policy
    assert policy["generation_policy"] == {"max_tokens": 512, "thinking_level": "low"}

    vault = policy["provider_vault"]
    assert vault["provider_instance_ref"] == "bedrock-default"
    assert vault["provider_family"] == "bedrock"
    assert vault["capability_ref"] == "llm.generate"
    assert vault["binding_id"] == "eeec240e-a693-4e9e-8dc0-b7b3c4ea1d22"
    assert vault["execution_location"] == "eu-west-1"


def test_adapter_source_is_provider_api_blind_and_vertex_independent() -> None:
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    lower = source.lower()
    tree = ast.parse(source)

    assert 'key: ClassVar[str] = "nusaibah.bedrock_agent_capability_lab"' in source
    assert 'version: ClassVar[str] = "0.1.5"' in source
    assert 'BEDROCK_AGENT_ROLE = "bedrock_orchestrator"' in source
    assert "vertex_grounded_orchestrator" not in source
    assert "search_enabled" not in source
    assert "search_mode" not in source

    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        node.module.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imported_roots <= {
        "__future__",
        "adapters",
        "execution_plan",
        "typing",
    }

    for forbidden in (
        "requests",
        "urllib",
        "socket",
        "subprocess",
        "boto3",
        "botocore",
        "google.cloud",
        "google.auth",
        "vertexai",
        "openai",
        "anthropic",
        "bedrock-runtime",
        "authorization",
        "presigned",
        "s3://",
        "http://",
        "https://",
        "provider_vault",
        "connectorvault",
        "role_arn",
        "iam_role_arn",
        "access_key",
        "secret_key",
    ):
        assert forbidden not in lower


def test_execution_plan_allows_only_declared_bedrock_lab_roles() -> None:
    plan_module = _load_plan_module()

    plan = plan_module.validate_execution_plan(
        {
            "schema_version": "execution_plan.v1",
            "company_id": 13,
            "steps": [
                {
                    "sequence": 1,
                    "capability": "bedrock_agent",
                    "role": "bedrock_orchestrator",
                    "required": True,
                },
                {
                    "sequence": 2,
                    "capability": "runtime_tool",
                    "role": "healthcare_nlp",
                    "required": True,
                },
                {
                    "sequence": 3,
                    "capability": "dynamic_skill",
                    "role": "company_memory",
                    "required": True,
                },
            ],
        }
    )
    assert plan.company_id == 13
    assert [step.role for step in plan.steps] == [
        "bedrock_orchestrator",
        "healthcare_nlp",
        "company_memory",
    ]

    try:
        plan_module.validate_execution_plan(
            {
                "schema_version": "execution_plan.v1",
                "company_id": 13,
                "steps": [
                    {
                        "sequence": 1,
                        "capability": "bedrock_agent",
                        "role": "vertex_grounded_orchestrator",
                        "required": True,
                    }
                ],
            }
        )
    except plan_module.ExecutionPlanValidationError:
        pass
    else:
        raise AssertionError("undeclared provider role must fail closed")


def test_bedrock_agent_invocation_forwards_validated_plan_and_safe_result_contract() -> None:
    namespace = _adapter_namespace(
        {
            "_resolve_bedrock_result",
            "_invoke_bedrock_agent",
            "_execution_plan_payload",
            "_run_bedrock_agent_invocation",
        },
        {
            "BEDROCK_AGENT_ROLE",
            "MAX_AGENT_TEXT_CHARS",
        },
    )

    plan = SimpleNamespace(
        schema_version="execution_plan.v1",
        company_id=13,
        steps=(
            SimpleNamespace(
                sequence=1,
                capability="bedrock_agent",
                role="bedrock_orchestrator",
                required=True,
            ),
        ),
    )

    class Inputs:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        def invoke_agent(
            self,
            role: str,
            *,
            input: dict[str, object],
        ) -> dict[str, object]:
            self.calls.append((role, input))
            return _bedrock_envelope("Safe orchestration guidance.")

    inputs = Inputs()
    evidence = namespace["_run_bedrock_agent_invocation"](
        inputs,
        plan=plan,
    )

    assert inputs.calls == [
        (
            "bedrock_orchestrator",
            {
                "task": (
                    "Provide safe orchestration guidance derived only from the supplied "
                    "validated execution plan. Process steps in declared sequence order "
                    "and do not execute capabilities."
                ),
                "execution_plan": {
                    "schema_version": "execution_plan.v1",
                    "company_id": 13,
                    "steps": [
                        {
                            "sequence": 1,
                            "capability": "bedrock_agent",
                            "role": "bedrock_orchestrator",
                            "required": True,
                        }
                    ],
                },
            },
        )
    ]
    assert evidence["bedrock_agent_status"] == "completed"
    assert evidence["bedrock_agent_provider_family"] == "bedrock"
    assert evidence["bedrock_agent_provider_turn_count"] == 1
    assert evidence["bedrock_execution_plan_forwarded"] is True
    assert evidence["bedrock_execution_plan_step_count"] == 1
    assert evidence["bedrock_orchestration_guidance_present"] is True
    assert "bedrock_exact_response_verified" not in evidence
    assert "result" not in evidence
    assert "provider_metadata" not in evidence


def test_bedrock_result_rejects_non_bedrock_provider_turn() -> None:
    namespace = _adapter_namespace(
        {"_resolve_bedrock_result"},
        {"MAX_AGENT_TEXT_CHARS"},
    )
    envelope = _bedrock_envelope()
    envelope["result"]["provider_metadata"]["turns"][0]["provider_family"] = "vertex_ai"

    try:
        namespace["_resolve_bedrock_result"](envelope)
    except RuntimeError as exc:
        assert str(exc) == (
            "Trusted Bedrock agent resolved an unexpected provider family."
        )
    else:
        raise AssertionError("provider-family drift must fail closed")


def test_bedrock_healthcare_composition_forwards_counts_not_clinical_text() -> None:
    namespace = _adapter_namespace({"_run_bedrock_healthcare_nlp_entities"})
    captured: dict[str, object] = {}

    namespace["_run_healthcare_nlp_entities"] = lambda inputs, variables: {
        "healthcare_nlp_status": "completed",
        "healthcare_nlp_entity_mention_count": 2,
        "healthcare_nlp_entity_count": 2,
        "healthcare_nlp_relationship_count": 1,
        "healthcare_nlp_fhir_bundle_present": True,
    }

    def invoke_agent(inputs, *, business_input):
        captured["business_input"] = business_input
        return (
            {
                "bedrock_agent_status": "completed",
                "bedrock_agent_provider_family": "bedrock",
            },
            {"text": "summary"},
        )

    namespace["_invoke_bedrock_agent"] = invoke_agent
    result = namespace["_run_bedrock_healthcare_nlp_entities"](
        object(),
        {"healthcare_text": "Synthetic note: aspirin."},
    )

    assert captured["business_input"] == {
        "task": "Summarize the supplied aggregate Healthcare NLP counts only.",
        "healthcare_nlp_summary": {
            "entity_mention_count": 2,
            "entity_count": 2,
            "relationship_count": 1,
            "fhir_bundle_present": True,
        },
    }
    assert result["bedrock_healthcare_nlp_combined_verified"] is True
    assert result["bedrock_healthcare_nlp_raw_clinical_text_forwarded"] is False


def test_bedrock_dynamic_skill_mutation_is_restricted_to_synthetic_fixture() -> None:
    namespace = _adapter_namespace(
        {
            "_render_inert_bedrock_evidence",
            "_run_bedrock_dynamic_skill_mutation",
        },
        {
            "MUTATION_FIXTURE_ROLE",
            "MUTATION_FIXTURE_COMPANY_ID",
            "MAX_COMPANY_MEMORY_CHARS",
            "SYNTHETIC_ANALYSIS_SECTION",
        },
    )
    calls: dict[str, object] = {}

    namespace["_invoke_bedrock_agent"] = (
        lambda inputs, *, business_input: (
            {
                "bedrock_agent_status": "completed",
                "bedrock_agent_provider_family": "bedrock",
            },
            {"text": "Synthetic update line."},
        )
    )

    class Changes:
        def upsert_section(self, section, text):
            calls["section"] = section
            calls["text"] = text
            return self

    class Handle:
        def provenance(self):
            return SimpleNamespace(
                mutable=True,
                role="company_memory_mutation_fixture",
            )

        def read(self):
            return "# Synthetic Fixture\n\nBaseline."

        def content_digest(self):
            return "sha256:before"

        def new_changeset(self):
            return Changes()

        def preview(self, changes):
            return SimpleNamespace(
                diff=SimpleNamespace(
                    old_digest="sha256:before",
                    new_digest="sha256:after",
                )
            )

        def apply(self, changes, *, expected_digest):
            calls["expected_digest"] = expected_digest
            return SimpleNamespace(
                after_content_digest="sha256:after",
                change_id="change-1",
                operation_count=1,
            )

    class Inputs:
        def dynamic_skill(self, role, *, variables):
            calls["role"] = role
            calls["variables"] = variables
            return Handle()

    evidence = namespace["_run_bedrock_dynamic_skill_mutation"](Inputs())

    assert calls["role"] == "company_memory_mutation_fixture"
    assert calls["variables"] == {}
    assert calls["section"] == "Bedrock Synthetic Analysis"
    assert calls["text"].startswith("Bedrock synthetic analysis (evidence only):")
    assert "> Synthetic update line." in calls["text"]
    assert calls["expected_digest"] == "sha256:before"
    assert evidence["dynamic_skill_fixture_company_id"] == 900013
    assert evidence["dynamic_skill_mutation_applied"] is True


def test_manifest_reuses_canonical_fixed_skill_digest_and_runtime_capabilities() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    version = manifest["versions"]["0.1.5"]

    assert version["skills"] == [
        {
            "skill_ref": "nusaibah.capability-orchestration",
            "version": "1.0.0",
            "digest": "sha256:f21420cbffb959e43453c144ee8b78fc4fb98d80c5b017d8c7eecc6a483e5111",
        }
    ]
    assert version["runtime_skills"]["company_memory"]["mutation"] == "read_only"
    assert (
        version["runtime_skills"]["company_memory_mutation_fixture"]["mutation"]
        == "mutable"
    )
    assert version["callable_assets"]["openfda_application_lookup"]["asset_version"] == "0.1.1"
    assert list(version["runtime_tools"]) == ["healthcare_nlp"]
