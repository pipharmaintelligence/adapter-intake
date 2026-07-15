from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest


sys.dont_write_bytecode = True
ADAPTER_ROOT = Path(__file__).resolve().parents[1]
if str(ADAPTER_ROOT) not in sys.path:
    sys.path.insert(0, str(ADAPTER_ROOT))

from devtools.output_lifecycle import (  # noqa: E402
    NodeSnapshotSchemaProvider,
    RetentionPolicy,
    ensure_node_layout,
    new_run_manifest,
    sha256_file,
    transition_manifest,
    write_json_atomic,
    write_payload_atomic,
)
from sfda_getdrugs_adapter import SfdaGetDrugsAdapter  # noqa: E402
from sfda_self_inspection import load_node_schema  # noqa: E402


@pytest.fixture
def retention_policy() -> RetentionPolicy:
    return RetentionPolicy(
        backup_retention_count=7,
        backup_retention_days=30,
        blocked_retention_days=14,
        quarantine_retention_days=14,
        staging_retention_hours=24,
    )


@pytest.fixture
def node_root(tmp_path: Path) -> Path:
    root = tmp_path / "aws_sfda_getdrugs_daily_snapshot"
    shutil.copytree(ADAPTER_ROOT / "schema_admin" / "schema", root / "schema")
    ensure_node_layout(root)
    return root


@pytest.fixture
def schema_contract(node_root: Path) -> dict[str, Any]:
    return load_node_schema(node_root)


@pytest.fixture
def schema_snapshot(node_root: Path):
    return NodeSnapshotSchemaProvider().resolve(
        {
            "node_root": node_root,
            "schema_provider": {
                "node_key": "aws_sfda_getdrugs_daily_snapshot",
                "schema_directory": "schema",
                "snapshots_directory": "snapshots",
                "pointer_file": "current.json",
            },
        }
    )


@pytest.fixture
def adapter() -> SfdaGetDrugsAdapter:
    return SfdaGetDrugsAdapter()


def payload(*records: dict[str, Any]) -> dict[str, Any]:
    return {"records": list(records), "page_summary": {"pages_crawled": 1}}


def make_staged(
    node_root: Path,
    schema_contract: dict[str, Any],
    retention_policy: RetentionPolicy,
    *,
    run_id: str,
    extraction_date: str,
    value: dict[str, Any],
    state: str = "staged",
) -> Path:
    staged = node_root / ".staging" / run_id
    staged.mkdir(parents=True)
    manifest = new_run_manifest(
        run_id=run_id,
        extraction_date=extraction_date,
        retention_policy=retention_policy,
        schema_contract=schema_contract,
        authority={"output_role": "drugs", "core_publish_enabled": False},
    )
    write_payload_atomic(staged / "payload.json", value)
    records = value.get("records")
    manifest["output"] = {
        "role": "drugs",
        "payload_sha256": sha256_file(staged / "payload.json"),
        "record_count": len(records) if isinstance(records, list) else 0,
    }
    if state != "created":
        transition_manifest(manifest, state)
    write_json_atomic(staged / "manifest.json", manifest)
    return staged


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
