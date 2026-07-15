from __future__ import annotations

import os
import time
from pathlib import Path

from conftest import make_staged, payload
from devtools.output_lifecycle import RetentionPolicy, apply_retention_after_commit


def age(path: Path, *, days: int = 0, hours: int = 0) -> None:
    timestamp = time.time() - days * 86400 - hours * 3600
    os.utime(path, (timestamp, timestamp))


def test_backup_retention_honors_count_or_age_protection(node_root: Path) -> None:
    group = node_root / "backup" / "extraction_date=2026-07-14"
    group.mkdir(parents=True)
    for name, days in (("new-1", 5), ("new-2", 10), ("old-count-1", 40), ("old-count-2", 50), ("expired", 60)):
        item = group / name
        item.mkdir()
        age(item, days=days)
    policy = RetentionPolicy(backup_retention_count=4, backup_retention_days=30, blocked_retention_days=14, quarantine_retention_days=14, staging_retention_hours=24)
    apply_retention_after_commit(node_root, policy)
    assert {item.name for item in group.iterdir()} == {"new-1", "new-2", "old-count-1", "old-count-2"}


def test_retention_never_deletes_active_dataset(node_root: Path) -> None:
    partition = node_root / "dataset" / "extraction_date=2026-07-14"
    partition.mkdir(parents=True)
    (partition / "payload.json").write_text("{}", encoding="utf-8")
    age(partition, days=365)
    policy = RetentionPolicy(backup_retention_count=0, backup_retention_days=0, blocked_retention_days=0, quarantine_retention_days=0, staging_retention_hours=1)
    apply_retention_after_commit(node_root, policy)
    assert (partition / "payload.json").is_file()


def test_abandoned_staging_is_quarantined_before_cleanup(node_root, schema_contract, retention_policy) -> None:
    staged = make_staged(node_root, schema_contract, retention_policy, run_id="abandoned-run", extraction_date="2026-07-14", value=payload({"price": "staged"}), state="created")
    age(staged, hours=30)
    result = apply_retention_after_commit(node_root, retention_policy)
    quarantined = node_root / "quarantine" / "abandoned-run"
    assert not staged.exists()
    assert (quarantined / "payload.json").is_file()
    assert (quarantined / "inspection.json").is_file()
    assert result["abandoned_quarantined"] == 1
