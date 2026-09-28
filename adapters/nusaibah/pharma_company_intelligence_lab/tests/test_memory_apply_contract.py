from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ASSET_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSET_ROOT))

import nusaibah_pharma_company_intelligence_lab_adapter as adapter_module  # noqa: E402
from memory_contract import MEMORY_TARGET_SECTION, MemoryCandidate  # noqa: E402


BEFORE = "sha256:" + "1" * 64
AFTER = "sha256:" + "2" * 64


class FakeChangeset:
    def replace_section(self, path: str, text: str):
        self.path = path
        self.text = text
        return self

    def add_citation(self, path: str, citation):
        return self


class FakeMutableMemory:
    def __init__(
        self,
        *,
        current_digest: str = BEFORE,
        preview_old_digest: str = BEFORE,
        preview_new_digest: str = AFTER,
    ) -> None:
        self.current_digest = current_digest
        self.preview_old_digest = preview_old_digest
        self.preview_new_digest = preview_new_digest
        self.expected_digest_seen = None

    def provenance(self):
        return SimpleNamespace(mutable=True)

    def content_digest(self) -> str:
        return self.current_digest

    def find_sections(self, section: str):
        if section != MEMORY_TARGET_SECTION:
            return []
        return [SimpleNamespace(path="/current-public-research")]

    def new_changeset(self):
        return FakeChangeset()

    def preview(self, changes):
        return SimpleNamespace(
            diff=SimpleNamespace(
                old_digest=self.preview_old_digest,
                new_digest=self.preview_new_digest,
            )
        )

    def apply(self, changes, *, expected_digest: str):
        self.expected_digest_seen = expected_digest
        return SimpleNamespace(
            after_content_digest=AFTER,
            change_id="change-1",
        )


class FakeHistory:
    def __init__(
        self,
        *,
        change_id: str = "change-1",
        after_digest: str = AFTER,
        latest_digest: str = AFTER,
    ) -> None:
        self.change_id = change_id
        self.after_digest = after_digest
        self.latest_digest = latest_digest

    def latest_change(self):
        return SimpleNamespace(
            change_id=self.change_id,
            after_content_digest=self.after_digest,
        )

    def latest(self):
        return SimpleNamespace(content_digest=self.latest_digest)


class FakeFreshMemory:
    def __init__(
        self,
        candidate: MemoryCandidate,
        *,
        digest: str = AFTER,
        history: FakeHistory | None = None,
    ) -> None:
        self.candidate = candidate
        self.digest = digest
        self._history = history or FakeHistory()

    def provenance(self):
        return SimpleNamespace(mutable=False)

    def content_digest(self) -> str:
        return self.digest

    def section_text(self, section: str) -> str:
        if section != MEMORY_TARGET_SECTION:
            raise KeyError(section)
        return self.candidate.markdown

    def read(self) -> str:
        return self.candidate.markdown

    def history(self, *, limit: int):
        self.limit = limit
        return self._history


class FakeInputs:
    def __init__(self, mutable: FakeMutableMemory, fresh: FakeFreshMemory) -> None:
        self.mutable = mutable
        self.fresh = fresh

    def dynamic_skill(self, role: str, *, variables=None):
        if role == "company_memory_update":
            return self.mutable
        if role == "company_memory":
            return self.fresh
        raise AssertionError(role)


def _state(candidate: MemoryCandidate) -> dict:
    return {
        "company_id": 13,
        "company_name": "Tabuk Pharmaceuticals",
        "before_digest": BEFORE,
        "memory_candidate": candidate,
        "citations": [],
        "benchmark_questions": (
            {"question_id": "q1", "question": "Question 1?"},
        ),
        "before_benchmark": {
            "results": [
                {
                    "question_id": "q1",
                    "coverage": "partially_covered",
                    "evidence_basis": "Before.",
                }
            ]
        },
    }


def _benchmark_after() -> dict:
    return {
        "results": [
            {
                "question_id": "q1",
                "coverage": "covered",
                "evidence_basis": "After.",
            }
        ]
    }


class MemoryApplyContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candidate = MemoryCandidate(
            company_id=13,
            target_section=MEMORY_TARGET_SECTION,
            markdown="Updated grounded memory.",
            fact_ids=("claim-1",),
        )

    def test_apply_uses_phase_one_expected_digest_and_verifies_readback_history(self) -> None:
        mutable = FakeMutableMemory()
        fresh = FakeFreshMemory(self.candidate)
        inputs = FakeInputs(mutable, fresh)

        with patch.object(adapter_module, "_run_benchmark", return_value=_benchmark_after()):
            result = adapter_module._apply_company_memory(inputs, _state(self.candidate))

        self.assertEqual(mutable.expected_digest_seen, BEFORE)
        self.assertEqual(result["memory_update_status"], "applied")
        self.assertEqual(result["memory_change_id"], "change-1")
        self.assertEqual(result["memory_after_digest"], AFTER)
        self.assertTrue(result["memory_readback_verified"])
        self.assertEqual(result["benchmark_result_basis"], "committed_memory")

    def test_rejects_mutable_digest_drift_before_apply(self) -> None:
        inputs = FakeInputs(
            FakeMutableMemory(current_digest="sha256:" + "9" * 64),
            FakeFreshMemory(self.candidate),
        )

        with self.assertRaisesRegex(RuntimeError, "differs from the Phase-1 baseline"):
            adapter_module._apply_company_memory(inputs, _state(self.candidate))

    def test_rejects_preview_baseline_digest_mismatch(self) -> None:
        inputs = FakeInputs(
            FakeMutableMemory(preview_old_digest="sha256:" + "9" * 64),
            FakeFreshMemory(self.candidate),
        )

        with self.assertRaisesRegex(RuntimeError, "preview baseline digest mismatch"):
            adapter_module._apply_company_memory(inputs, _state(self.candidate))

    def test_rejects_fresh_readback_digest_mismatch(self) -> None:
        inputs = FakeInputs(
            FakeMutableMemory(),
            FakeFreshMemory(self.candidate, digest="sha256:" + "8" * 64),
        )

        with self.assertRaisesRegex(RuntimeError, "readback digest mismatch"):
            adapter_module._apply_company_memory(inputs, _state(self.candidate))

    def test_rejects_history_change_id_mismatch(self) -> None:
        inputs = FakeInputs(
            FakeMutableMemory(),
            FakeFreshMemory(
                self.candidate,
                history=FakeHistory(change_id="wrong-change"),
            ),
        )

        with patch.object(adapter_module, "_run_benchmark", return_value=_benchmark_after()):
            with self.assertRaisesRegex(RuntimeError, "history change-id mismatch"):
                adapter_module._apply_company_memory(inputs, _state(self.candidate))

    def test_rejects_history_digest_mismatch(self) -> None:
        inputs = FakeInputs(
            FakeMutableMemory(),
            FakeFreshMemory(
                self.candidate,
                history=FakeHistory(after_digest="sha256:" + "7" * 64),
            ),
        )

        with patch.object(adapter_module, "_run_benchmark", return_value=_benchmark_after()):
            with self.assertRaisesRegex(RuntimeError, "history digest mismatch"):
                adapter_module._apply_company_memory(inputs, _state(self.candidate))


if __name__ == "__main__":
    unittest.main()
