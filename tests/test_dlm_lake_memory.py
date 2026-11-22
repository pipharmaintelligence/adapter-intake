"""Provider-free consumer regressions; fake persistence is NOT Core authorization proof."""
from __future__ import annotations
import copy
import importlib
import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "development/nusaibah/abstract_mcp_dlm_0_1_3"
sys.path.insert(0, str(CANDIDATE))
import lake_memory_contract_v0_1_3 as c
import lake_memory_domain_v0_1_3 as d
from lake_memory_runtime_v0_1_3 import invoke_memory

class RuntimeFailure(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

def knowledge(key="a1"):
    return {"operation": "memory.knowledge.update", "lake_id": "lake-1", "section_id": "concepts_and_terminology",
        "section_title": "Concepts and terminology", "assertion": {"assertion_id": key, "statement": "Suppliers have distinct roles.",
        "source_kind": "client_stated", "source_refs": [{"kind": "client_statement", "reference": "statement-1"}],
        "confirmation_state": "unconfirmed", "as_of": None, "supersedes": None}}

def plan(key="p1", node="supplier_profiles"):
    return {"plan_id": key, "capability_section": "supplier-intelligence", "intent": "create", "proposed_node_key": node,
        "title": "Supplier profiles", "description": "One profile per supplier.", "expected_outcome": "Agents identify a supplier.",
        "acceptance_criteria": [{"criterion_id": "schema", "description": "Schema matches.", "verification_kind": "schema"}],
        "proposed_schema": {"grain": "one supplier", "format": "json", "fields": [
            {"name": "supplier_id", "type": "string", "description": "Stable ID.", "required": True}],
            "primary_key": ["supplier_id"], "partition_fields": ["supplier_id"], "relationships": [], "quality_rules": []},
        "dependencies": [], "implementation_steps": ["Create and verify."], "owner": None, "priority": "normal",
        "blockers": [], "next_action": "Review schema.", "evidence_refs": [], "supersedes_plan_id": None, "status": "planned"}

def scope(request, tenant="tenant-a", **overrides):
    kind = c.memory_kind(request)
    return {"dlm_lake_memory_scope": {"schema_version": "dlm_lake_memory_scope.v1", "client_id": tenant, "actor_id": "actor-1",
        "lake_id": request["lake_id"], "operation": request["operation"],
        "mode": "read" if request["operation"] == "memory.context" else request.get("mode", "preview"),
        "request_digest": c.digest(request), "read_selector_digest": c.digest([tenant, request["lake_id"], kind, "read"]),
        "write_selector_digest": c.digest([tenant, request["lake_id"], kind, "write"]),
        "allow_initialize": True, "history_allowed": True, "visibility": "complete_authorized_lake", **overrides}}

class Document:
    def __init__(self, source):
        self.source = source
    def section_text(self, name):
        assert name == "State"
        return self.source.split("## State\n\n", 1)[1]

class Store:
    def __init__(self):
        self.docs, self.receipts, self.snapshots = {}, {}, {}
        self.reads = self.writes = self.tool_calls = 0
        self.read_error = self.bad_selector = self.bad_receipt = self.readback_failure = self.history_failure = False
        self.ambiguous_commit = self.conflict = self.cached = False
        self.history_scope = "committed_partition_mutations"
        self.observation = None

class Inputs(dict):
    def __init__(self, store, request, context):
        super().__init__(tool_request=copy.deepcopy(request))
        self.store, self.scope = store, context["dlm_lake_memory_scope"]
        self.kind = c.memory_kind(request)
        self.key = self.scope["client_id"], self.scope["lake_id"], self.kind
    def dynamic_skill(self, role, *, variables=None):
        assert variables is None, "No tenant/lake selectors in callable variables"
        if self.store.read_error or (self.store.readback_failure and self.store.writes > 0 and not role.endswith("_update")):
            raise RuntimeFailure("dynamic_skill_access_denied")
        assert role in ("lake_" + self.kind, "lake_" + self.kind + "_update")
        self.store.reads += 1
        if self.key not in self.store.docs:
            raise RuntimeFailure("dynamic_skill_not_initialized")
        return Handle(self, role)
    def initialize_dynamic_skill(self, role, *, markdown, variables=None):
        assert variables is None
        assert role.endswith("_update")
        if self.key in self.store.docs:
            raise RuntimeFailure("dynamic_skill_initialization_partition_exists")
        self.store.docs[self.key] = markdown
        self.store.writes += 1
        self.store.snapshots[self.key] = [types.SimpleNamespace(snapshot_id="s0", document=Document(markdown))]
        return {"status": "initialized", "after_digest": c.text_digest(markdown)}
    def invoke_tool(self, role, *, input, on_error):
        assert role == "dlm_node_implementation" and on_error == "raise"
        assert "client_id" not in input
        self.store.tool_calls += 1
        return {"status": "completed", "operation": "invoke", "tool_handle": "@tool.abstract_mcp_dlm",
            "tool_server_ref": "mcp.abstract_dlm", "capability_ref": "dlm.nodes.implementation",
            "records": [copy.deepcopy(self.store.observation)], "provenance": {"role": role, "runtime_mcp_tool": True,
            "cache_hit": self.store.cached, "record_count": 1, "duration_ms": 1, "invocation_id": "mti_" + "1" * 32}}

class Changes:
    def replace_section(self, name, body):
        assert name == "State"
        self.body = body
        return self

class Handle:
    def __init__(self, inputs, role):
        self.inputs, self.role = inputs, role
        self.text = inputs.store.docs[inputs.key]
    def read(self):
        return self.text
    def section_text(self, name):
        return Document(self.text).section_text(name)
    def content_digest(self):
        return c.text_digest(self.text)
    def provenance(self):
        mutable = self.role.endswith("_update")
        return types.SimpleNamespace(kind="dynamic", role=self.role, mutable=mutable,
            package_digest=c.digest(["synthetic", self.text]), history_scope=self.inputs.store.history_scope,
            selector_digest="sha256:" + "0" * 64 if self.inputs.store.bad_selector else
                self.inputs.scope["write_selector_digest" if mutable else "read_selector_digest"])
    def new_changeset(self):
        return Changes()
    def preview(self, changes):
        text = self.text.split("## State\n\n", 1)[0] + "## State\n\n" + changes.body
        return types.SimpleNamespace(source=text, document=Document(text), diff=types.SimpleNamespace(new_digest=c.text_digest(text)))
    def apply(self, changes, *, expected_digest):
        store, key = self.inputs.store, self.inputs.key
        if store.conflict or c.text_digest(store.docs[key]) != expected_digest:
            raise RuntimeFailure("dynamic_skill_expected_digest_mismatch")
        text = self.preview(changes).source
        store.docs[key] = text
        store.writes += 1
        count = len(store.snapshots[key])
        receipt = types.SimpleNamespace(change_id="change-" + str(store.writes), changed_at=datetime.now(timezone.utc),
            before_content_digest=expected_digest, after_content_digest="sha256:" + "0" * 64 if store.bad_receipt else c.text_digest(text),
            before_snapshot_id="s" + str(count - 1), after_snapshot_id="s" + str(count))
        store.receipts.setdefault(key, []).append(receipt)
        store.snapshots[key].append(types.SimpleNamespace(snapshot_id=receipt.after_snapshot_id, document=Document(text)))
        if store.ambiguous_commit:
            raise RuntimeFailure("response_lost_after_commit")
        return receipt
    def history(self, *, limit=20, before_change_id=None):
        store, key = self.inputs.store, self.inputs.key
        if store.history_failure:
            raise RuntimeFailure("dynamic_skill_history_failed")
        receipts = store.receipts.get(key, [])
        if before_change_id:
            receipts = receipts[:next((i for i, item in enumerate(receipts) if item.change_id == before_change_id), len(receipts))]
        return types.SimpleNamespace(receipts=receipts[-limit:], snapshots=store.snapshots[key])

class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
    def call(self, request, tenant="tenant-a", **overrides):
        context = scope(request, tenant, **overrides)
        return invoke_memory(Inputs(self.store, request, context), context)["outputs"]["tool_results"]
    def apply(self, request, tenant="tenant-a", **overrides):
        result = self.call(request, tenant, **overrides)["data"]
        return self.call({**request, "mode": "apply", "expected_digest": result["before_digest"],
                          "proposal_digest": result["proposal_digest"]}, tenant, **overrides)
    def read(self, kind="knowledge", tenant="tenant-a", **changes):
        return self.call({"operation": "memory.context", "lake_id": "lake-1", "memory_kind": kind, **changes}, tenant)
    def seed_plan(self):
        return self.apply({"operation": "memory.plan.upsert", "lake_id": "lake-1", "plan": plan()})
    def observed(self, **changes):
        value = c.plan_digest(plan())
        return {"schema_version": "dlm_node_implementation.v1", "client_id": "tenant-a", "lake_id": "lake-1",
            "node_key": "supplier_profiles", "plan_id": "p1", "plan_digest": value, "observed_at": "2026-11-22T12:00:00Z",
            "node_exists": True, "schema_complete": True, "actual_schema": plan()["proposed_schema"], "core_revision": "revision-1",
            "design_approval": {"status": "approved", "reference": "design-1", "plan_digest": value},
            "core_approval": {"status": "approved", "reference": "approval-1", "plan_digest": value},
            "readiness": "ready", "acceptance": [{"criterion_id": "schema", "status": "passed", "reference": "check-1"}], **changes}
    def reconcile(self):
        return self.apply({"operation": "memory.plan.reconcile", "lake_id": "lake-1", "plan_id": "p1", "node_key": "supplier_profiles"})

    def test_default_preview_no_writes(self):
        self.assertEqual("preview_ready", self.call(knowledge())["status"])
        self.assertEqual(0, self.store.writes)
    def test_initialize_then_fresh_actor_can_read(self):
        result = self.apply(knowledge())
        self.assertEqual("initialized", result["status"])
        self.assertTrue(result["data"]["readback_verified"])
        self.assertIsNone(result["data"]["receipt"]["change_id"])
        request = {"operation": "memory.context", "lake_id": "lake-1", "memory_kind": "knowledge"}
        self.assertEqual("a1", self.call(request, actor_id="actor-2")["data"]["records"][0]["assertion_id"])
    def test_clients_same_lake_are_independent(self):
        self.apply(knowledge())
        self.assertEqual("not_initialized", self.read(tenant="tenant-b")["status"])
        self.apply(knowledge("b1"), "tenant-b")
        self.assertEqual("a1", self.read()["data"]["records"][0]["assertion_id"])
        self.assertEqual("b1", self.read(tenant="tenant-b")["data"]["records"][0]["assertion_id"])
    def test_missing_scope_fails_before_read(self):
        request = knowledge()
        with self.assertRaisesRegex(c.MemoryError, "trusted_scope_unavailable"):
            invoke_memory(Inputs(self.store, request, scope(request)), {})
        self.assertEqual(0, self.store.reads)
    def test_public_authority_override_rejected(self):
        for key in ("client_id", "actor_id", "partition_values", "context", "memory_storage"):
            with self.subTest(key=key), self.assertRaises(c.MemoryError):
                self.call({**knowledge(), key: "forged"})
        self.assertEqual(0, self.store.reads)
    def test_extra_input_roles_rejected(self):
        request = knowledge(); context = scope(request)
        inputs = Inputs(self.store, request, context); inputs["variables"] = {"client_id": "other"}
        with self.assertRaisesRegex(c.MemoryError, "input_roles_invalid"):
            invoke_memory(inputs, context)
    def test_scope_request_mode_and_visibility_checks(self):
        for changes in ({"request_digest": "sha256:" + "0" * 64}, {"mode": "apply"}, {"visibility": "partial"}):
            with self.subTest(changes=changes), self.assertRaises(c.MemoryError):
                self.call(knowledge(), **changes)
    def test_wrong_selector_and_stored_tenant_fail(self):
        self.apply(knowledge()); self.store.bad_selector = True
        with self.assertRaisesRegex(c.MemoryError, "role_scope_mismatch"):
            self.read()
        self.store.bad_selector = False
        key = ("tenant-a", "lake-1", "knowledge")
        self.store.docs[key] = self.store.docs[key].replace('"tenant-a"', '"tenant-b"')
        with self.assertRaisesRegex(c.MemoryError, "partition_identity_mismatch"):
            self.read()
    def test_denial_is_not_empty_memory(self):
        self.store.read_error = True
        with self.assertRaisesRegex(c.MemoryError, "read_failed"):
            self.call(knowledge())
        self.assertEqual(0, self.store.writes)
    def test_apply_needs_preview_digest(self):
        with self.assertRaisesRegex(c.MemoryError, "apply_requires_preview"):
            self.call({**knowledge(), "mode": "apply"})
        with self.assertRaisesRegex(c.MemoryError, "proposal_mismatch"):
            self.call({**knowledge(), "mode": "apply", "expected_digest": None, "proposal_digest": "sha256:" + "0" * 64})
    def test_stale_writer_is_rejected(self):
        preview = self.call(knowledge())["data"]
        self.apply(knowledge("a2"))
        with self.assertRaisesRegex(c.MemoryError, "stale_write"):
            self.call({**knowledge(), "mode": "apply", "expected_digest": preview["before_digest"], "proposal_digest": preview["proposal_digest"]})
    def test_update_commit_history_and_noop(self):
        self.apply(knowledge())
        result = self.apply(knowledge("a2"))
        self.assertEqual("committed", result["status"])
        self.assertTrue(result["data"]["history_verified"])
        self.assertEqual("unchanged", self.apply(knowledge("a2"))["status"])
        self.assertEqual(2, self.store.writes)
    def test_uncertain_commit_is_not_retried(self):
        self.apply(knowledge()); self.store.ambiguous_commit = True
        self.assertEqual("mutation_outcome_unknown", self.apply(knowledge("a2"))["status"])
        self.assertEqual(2, self.store.writes)
    def test_bad_receipt_is_not_persistence_proof(self):
        self.apply(knowledge()); self.store.bad_receipt = True
        self.assertEqual("mutation_outcome_unknown", self.apply(knowledge("a2"))["status"])
    def test_readback_failure_preserves_commit_truth(self):
        request = knowledge(); preview = self.call(request)["data"]
        self.store.readback_failure = True
        result = self.call({**request, "mode": "apply", "expected_digest": None, "proposal_digest": preview["proposal_digest"]})
        self.assertEqual("committed_readback_unverified", result["status"])
        self.assertEqual(1, self.store.writes)
    def test_history_failure_separate_from_commit(self):
        self.apply(knowledge()); self.store.history_failure = True
        result = self.apply(knowledge("a2"))
        self.assertEqual("committed", result["status"])
        self.assertTrue(result["data"]["readback_verified"])
        self.assertFalse(result["data"]["history_verified"])
    def test_runtime_conflict_not_replayed(self):
        self.apply(knowledge()); self.store.conflict = True
        with self.assertRaisesRegex(c.MemoryError, "stale_write"):
            self.apply(knowledge("a2"))
        self.assertEqual(1, self.store.writes)
    def test_initialize_has_separate_admission(self):
        with self.assertRaisesRegex(c.MemoryError, "initialization_not_admitted"):
            self.apply(knowledge(), allow_initialize=False)
    def test_history_has_before_after_and_truthful_coverage(self):
        self.apply(knowledge()); request = knowledge(); request["assertion"]["statement"] = "Refined supplier meaning."
        self.apply(request)
        result = self.read(view="history", record_id="a1", page_size=1)["data"]
        self.assertIsNone(result["has_more"])
        self.assertNotEqual(result["records"][0]["before_record"], result["records"][0]["after_record"])
        self.assertEqual("not_initialized", self.read(tenant="tenant-b", view="history")["status"])
    def test_current_only_read_role_does_not_claim_history(self):
        self.apply(knowledge()); self.store.history_scope = "current_resolution"
        self.assertEqual("history_unavailable", self.read(view="history")["status"])
    def test_superseded_assertion_retained(self):
        self.apply(knowledge()); request = knowledge("a2"); request["assertion"]["supersedes"] = "a1"
        self.apply(request)
        rows = self.read()["data"]["records"]
        self.assertEqual(2, len(rows)); self.assertEqual("superseded", rows[0]["confirmation_state"])
    def test_plan_does_not_create_node(self):
        self.seed_plan()
        self.assertEqual("planned", self.read("engineering")["data"]["records"][0]["status"])
        self.assertEqual(0, self.store.tool_calls)
    def test_public_plan_cannot_forge_core_or_completion(self):
        for changes in ({"status": "implemented"}, {"approval": {}}, {"observation": {}}, {"completion": {}}):
            with self.subTest(changes=changes), self.assertRaises(c.MemoryError):
                self.call({"operation": "memory.plan.upsert", "lake_id": "lake-1", "plan": {**plan(), **changes}})
    def test_duplicate_plan_and_bad_dependency_rejected(self):
        self.seed_plan()
        for definition in (plan("p2"), {**plan(), "dependencies": ["p1"]}):
            with self.assertRaises(c.MemoryError):
                self.call({"operation": "memory.plan.upsert", "lake_id": "lake-1", "plan": definition})
    def test_bad_schema_references_rejected(self):
        definition = plan(); definition["proposed_schema"]["partition_fields"] = ["missing"]
        with self.assertRaisesRegex(c.MemoryError, "schema_keys_invalid"):
            self.call({"operation": "memory.plan.upsert", "lake_id": "lake-1", "plan": definition})
    def test_core_completion_then_drift_preserves_completion(self):
        self.seed_plan(); self.store.observation = self.observed(); self.reconcile()
        original = self.read("engineering", view="detail")["data"]["records"][0]
        self.assertEqual("implemented", original["status"])
        self.store.observation["actual_schema"]["fields"][0]["type"] = "integer"
        self.store.observation["observed_at"] = "2026-11-22T13:00:00Z"
        self.reconcile()
        current = self.read("engineering", view="detail")["data"]["records"][0]
        self.assertEqual("drifted", current["verification_state"])
        self.assertEqual(original["completion"], current["completion"])
    def test_unavailable_checks_do_not_complete(self):
        self.seed_plan(); self.store.observation = self.observed(readiness="unavailable"); self.reconcile()
        self.assertEqual("planned", self.read("engineering")["data"]["records"][0]["status"])
    def test_cross_client_wrong_node_and_cached_observation_rejected(self):
        self.seed_plan()
        for changes in ({"client_id": "tenant-b"}, {"node_key": "another-node"}, {"plan_digest": "sha256:" + "0" * 64}):
            self.store.observation = self.observed(**changes)
            with self.assertRaises(c.MemoryError):
                self.reconcile()
        self.store.observation = self.observed(); self.store.cached = True
        with self.assertRaises(c.MemoryError):
            self.reconcile()
    def test_changed_plan_invalidates_approval(self):
        self.seed_plan(); self.store.observation = self.observed(readiness="unavailable"); self.reconcile()
        definition = plan(); definition["description"] = "Changed design."
        self.apply({"operation": "memory.plan.upsert", "lake_id": "lake-1", "plan": definition})
        row = self.read("engineering", view="detail")["data"]["records"][0]
        self.assertIsNone(row["approval"]); self.assertEqual("stale", row["verification_state"])
    def test_unsafe_source_and_unknown_fields_rejected(self):
        for statement in ("password=example", "https://example.test", "Bearer example"):
            request = knowledge(); request["assertion"]["statement"] = statement
            with self.assertRaises(c.MemoryError):
                self.call(request)
        request = knowledge(); request["assertion"]["extra"] = True
        with self.assertRaises(c.MemoryError):
            self.call(request)
    def test_unicode_and_markdown_fence_text_are_data(self):
        request = knowledge(); request["assertion"]["statement"] = "\u0645\u0648\u0631\u062f\n```\n# Untrusted text"
        self.apply(request)
        self.assertEqual(request["assertion"]["statement"], self.read()["data"]["records"][0]["statement"])
    def test_non_string_operation_and_surrogate_rejected(self):
        for value in ([], {}, None, 1):
            with self.assertRaises(c.MemoryError):
                c.request_contract({"operation": value})
        request = knowledge(); request["assertion"]["statement"] = "\ud800"
        with self.assertRaises(c.MemoryError):
            c.request_contract(request)
    def test_changed_preview_proposal_rejected(self):
        request = knowledge(); preview = self.call(request)["data"]
        request["assertion"]["statement"] = "A different proposal."
        with self.assertRaisesRegex(c.MemoryError, "proposal_mismatch"):
            self.call({**request, "mode": "apply", "expected_digest": None, "proposal_digest": preview["proposal_digest"]})
        self.assertEqual(0, self.store.writes)
    def test_flat_and_package_imports(self):
        package = types.ModuleType("candidate_package"); package.__path__ = [str(CANDIDATE)]
        with patch.dict(sys.modules, {"candidate_package": package}):
            for name in ("lake_memory_contract_v0_1_3", "lake_memory_domain_v0_1_3", "lake_memory_runtime_v0_1_3"):
                self.assertIsNotNone(importlib.import_module("candidate_package." + name))

if __name__ == "__main__":
    unittest.main()
