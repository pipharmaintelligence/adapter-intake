from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from system import CALLABLE_VARIABLES_INPUT_ROLE


ADAPTER_DIR = (
    Path(__file__).resolve().parents[1]
    / "adapters"
    / "nusaibah"
    / "full_dump_agent_loop"
)
sys.path.insert(0, str(ADAPTER_DIR))

from full_dump_agent_loop_adapter import AGENT_FIELDS, FullDumpAgentLoopAdapter  # noqa: E402


def invoke(records: list[dict[str, Any]], agent_ids: Any) -> dict[str, Any]:
    return FullDumpAgentLoopAdapter().invoke(
        {
            "agents": {"records": records},
            CALLABLE_VARIABLES_INPUT_ROLE: {"agent_ids": agent_ids},
        },
        {},
    )


def test_selects_records_in_requested_order_and_projects_declared_fields() -> None:
    response = invoke(
        [
            {"id": 1, "agent": "First", "description": "one", "private": "excluded"},
            {"id": 2, "agent": "Second", "description": "two"},
        ],
        [2, "1"],
    )

    output = response["outputs"]["full_dump_agent"]

    assert response["status"] == "success"
    assert output["selected_agent_ids"] == ["2", "1"]
    assert output["missing_agent_ids"] == []
    assert output["record_count"] == 2
    assert output["fields"] == list(AGENT_FIELDS)
    assert [record["id"] for record in output["records"]] == [2, 1]
    assert all("private" not in record for record in output["records"])


def test_reports_missing_ids_without_inventing_records() -> None:
    output = invoke([{"id": "known", "agent": "Known"}], ["missing", "known"])[
        "outputs"
    ]["full_dump_agent"]

    assert output["missing_agent_ids"] == ["missing"]
    assert output["record_count"] == 1
    assert output["records"][0]["id"] == "known"


def test_decodes_runtime_text_records() -> None:
    output = invoke(
        [{"text": json.dumps({"agent_id": 7, "agent": "Decoded"})}],
        [7],
    )["outputs"]["full_dump_agent"]

    assert output["record_count"] == 1
    assert output["records"][0]["agent"] == "Decoded"


@pytest.mark.parametrize(
    "agent_ids",
    [
        None,
        [],
        [1, 2, 3, 4],
        [1, 1],
        [True],
        [""],
        [{}],
    ],
)
def test_rejects_invalid_agent_id_controls(agent_ids: Any) -> None:
    with pytest.raises(ValueError):
        invoke([{"id": 1}], agent_ids)


def test_requires_callable_variables_and_runtime_record_envelope() -> None:
    adapter = FullDumpAgentLoopAdapter()

    with pytest.raises(ValueError):
        adapter.invoke({"agents": {"records": []}}, {})

    with pytest.raises(ValueError):
        adapter.invoke(
            {
                "agents": [],
                CALLABLE_VARIABLES_INPUT_ROLE: {"agent_ids": [1]},
            },
            {},
        )


def test_rejects_duplicate_or_unidentified_runtime_records() -> None:
    with pytest.raises(ValueError):
        invoke([{"id": 1}, {"agent_id": "1"}], [1])

    with pytest.raises(ValueError):
        invoke([{"agent": "No identity"}], [1])


def test_manifest_exposes_only_the_bounded_transform_contract() -> None:
    manifest = json.loads((ADAPTER_DIR / "full_dump_agent_loop.asset.json").read_text())

    assert manifest["key"] == "nusaibah.full_dump_agent_loop"
    assert manifest["default"] == "0.1.0"
    assert manifest["execution"] == {
        "allowed_substrates": ["local", "local_worker", "ecs"],
        "default_substrate": "local_worker",
        "timeout_seconds": 300,
    }

    version = manifest["versions"]["0.1.0"]
    assert set(version["inputs"]) == {"agents"}
    assert set(version["outputs"]) == {"full_dump_agent"}
    assert "output_contracts" not in version


def test_adapter_source_has_no_network_or_system_authority_imports() -> None:
    source = (ADAPTER_DIR / "full_dump_agent_loop_adapter.py").read_text()
    tree = ast.parse(source)
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

    assert imported_roots <= {"__future__", "adapters", "json", "system", "typing"}

    lowered = source.lower()
    for forbidden in ("http://", "https://", "s3://", "boto", "requests", "urllib", "socket", "subprocess"):
        assert forbidden not in lowered
