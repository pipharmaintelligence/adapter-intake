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


def test_manifest_is_current_version_only_0_1_5_handoff() -> None:
    manifest = _manifest()

    assert manifest["key"] == "nusaibah.agent_capability_lab"
    assert manifest["default"] == "0.1.5"
    assert set(manifest["versions"]) == {"0.1.5"}
    assert manifest["execution"] == {
        "allowed_substrates": ["local_worker"],
        "default_substrate": "local_worker",
    }


def test_manifest_keeps_company_13_read_only_and_limits_mutation_fixture() -> None:
    version = _manifest()["versions"]["0.1.5"]
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
    version = _manifest()["versions"]["0.1.5"]

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


def test_adapter_source_parses_and_declares_vertex_proof_stages() -> None:
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert 'version: ClassVar[str] = "0.1.5"' in source
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
