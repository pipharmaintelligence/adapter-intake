from __future__ import annotations

import ast
import json
from pathlib import Path


ADAPTER_DIR = (
    Path(__file__).resolve().parents[1]
    / "adapters"
    / "nusaibah"
    / "agent_capability_lab"
)
MANIFEST_PATH = ADAPTER_DIR / "nusaibah_agent_capability_lab.asset.json"
ADAPTER_PATH = ADAPTER_DIR / "nusaibah_agent_capability_lab_adapter.py"


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_is_current_version_only_0_1_6_handoff() -> None:
    manifest = _manifest()

    assert manifest["key"] == "nusaibah.agent_capability_lab"
    assert manifest["default"] == "0.1.6"
    assert set(manifest["versions"]) == {"0.1.6"}
    assert manifest["execution"] == {
        "allowed_substrates": ["local_worker"],
        "default_substrate": "local_worker",
    }


def test_manifest_keeps_company_13_read_only_and_limits_mutation_fixture() -> None:
    version = _manifest()["versions"]["0.1.6"]
    runtime_skills = version["runtime_skills"]

    canonical = runtime_skills["company_memory"]
    assert canonical["source"] == {
        "lake_ref": "googl123",
        "node_key": "company_memory",
    }
    assert canonical["resolution"] == "current"
    assert canonical["mutation"] == "read_only"
    assert canonical["partition"] == {
        "company_id": {"from_variable": "company_id"}
    }

    fixture = runtime_skills["company_memory_mutation_fixture"]
    assert fixture["source"] == canonical["source"]
    assert fixture["resolution"] == "current"
    assert fixture["mutation"] == "mutable"
    assert fixture["partition"] == {
        "company_id": {"value": "900013"}
    }


def test_manifest_declares_grounded_vertex_reference_read_and_future_agents() -> None:
    version = _manifest()["versions"]["0.1.6"]

    assert version["public_web"] == {
        "profiles": ["reference_read"],
        "modes": ["http"],
    }
    assert set(version["agents"]) == {
        "capability_orchestrator",
        "vertex_grounded_orchestrator",
        "bedrock_orchestrator",
        "openai_orchestrator",
    }
    assert (
        version["agents"]["vertex_grounded_orchestrator"]["contract_key"]
        == "agent.nusaibah.agent_capability_lab_vertex_grounded"
    )

    # PI-1940 migration is intentionally Vertex-first. Other logical roles
    # remain declared identities but do not acquire packaged runtime definitions.
    assert "definition" not in version["agents"]["capability_orchestrator"]
    assert "definition" not in version["agents"]["bedrock_orchestrator"]
    assert "definition" not in version["agents"]["openai_orchestrator"]


def test_vertex_role_carries_exact_version_local_packaged_definition() -> None:
    definition = (
        _manifest()["versions"]["0.1.6"]["agents"]
        ["vertex_grounded_orchestrator"]["definition"]
    )

    assert set(definition) == {"registry_entries", "chain"}
    assert definition["registry_entries"] == [
        {
            "handle": "provider:text_generation",
            "type": "provider_execution",
            "version": "1.0.0",
            "visibility": "internal",
            "status": "active",
            "capabilities": ["text_generation"],
            "input_schema_version": None,
            "output_schema_version": None,
            "runtime": None,
            "safety_policy": {
                "store_prompt": False,
                "store_output": False,
            },
            "provenance_policy": {"record_step": True},
            "access_policy": None,
            "metadata": {
                "provisioning_source": "pi_1939_capability_lab_0_1_6"
            },
        }
    ]

    chain = definition["chain"]
    assert chain["chain_id"] == (
        "agent.nusaibah.agent_capability_lab_vertex_grounded"
    )
    assert chain["version"] == "1.0.0"
    assert "owner_client_id" not in chain
    assert chain["visibility"] == "internal"
    assert chain["status"] == "active"

    assert len(chain["steps"]) == 1
    step = chain["steps"][0]
    assert step["step_handle"] == "provider:text_generation"
    assert step["required_capability"] == "text_generation"
    assert step["provider"] == "vertex_ai"

    policy = step["provider_policy"]
    assert policy["provider"] == "vertex_ai"
    assert policy["model"] == "gemini-2.5-pro"
    assert policy["search_enabled"] is True
    assert policy["search_mode"] == "provider_grounding"
    assert policy["citation_policy"] == "refs_only"

    vault = policy["provider_vault"]
    assert vault == {
        "provider_instance_ref": "vertex-primary",
        "provider_family": "vertex_ai",
        "capability_ref": "llm.generate",
        "binding_id": "330c2e62-8445-44e6-8842-1cfe08a55900",
        "execution_project_id": "laravelai-490700",
        "execution_location": "us-central1",
        "policy_flags": {"mode": "read_only"},
    }
    assert "client_id" not in vault


def test_adapter_source_parses_and_declares_vertex_proof_stages() -> None:
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert 'version: ClassVar[str] = "0.1.6"' in source
    assert '"vertex_grounded_citation"' in source
    assert '"vertex_grounded_dynamic_skill"' in source
    assert '"dynamic_skill_commit_verify"' in source
    assert 'CANONICAL_COMPANY_ID = "13"' in source
    assert 'MUTATION_FIXTURE_COMPANY_ID = "900013"' in source

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
        "devtools",
        "execution_plan",
        "typing",
    }


def test_adapter_does_not_acquire_network_provider_core_or_storage_authority() -> None:
    source = ADAPTER_PATH.read_text(encoding="utf-8").lower()

    for forbidden in (
        "requests",
        "urllib",
        "socket",
        "subprocess",
        "boto",
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
    ):
        assert forbidden not in source


def test_adapter_uses_only_governed_runtime_composition_surfaces() -> None:
    source = ADAPTER_PATH.read_text(encoding="utf-8")

    assert "inputs.dynamic_skill(" in source
    assert "invoke_agent(" in source
    assert "inputs.open_reference(" in source
    assert "AgentCitationView.from_agent_result" in source
    assert "handle.new_changeset().add_citation" in source
    assert "handle.apply(changes, expected_digest=before_digest)" in source
    assert "handle.history(" in source
