"""Product-first routing, exact paragraph selection and adversarial edit tests."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from fakes import CodedFailure, FakeInputs, MemoryView, example_inputs
from clinical_failure_intelligence.contracts import ContractError, parse_request, text_digest
from clinical_failure_intelligence.orchestration import run_analysis
from clinical_failure_intelligence.product_memory import (case_path, compile_product_changeset,
    memory_projection, read_product_memory, review_edit_plan, validate_edit_candidates)


def state(memory=None):
    """Read one synthetic product state without provider or storage access."""
    inputs = FakeInputs(memory=memory)
    request = parse_request(inputs)
    return inputs, request, read_product_memory(inputs, request)


def edits(snapshot, operation="append_paragraph"):
    """Build an independent delta for one known fixture paragraph or section."""
    target = snapshot["paragraphs"][0] if operation in {"keep", "enrich_paragraph", "replace_paragraph"} else None
    return [{"edit_id": "CHANGE_A", "operation": operation, "section_path": list(snapshot["section_path"]),
        "target_paragraph_id": target["paragraph_id"] if target else None,
        "before_digest": target["digest"] if target else None,
        "new_text": None if operation == "keep" else "An explicitly qualified new finding in this trial.",
        "supporting_item_ids": ["FINDING_A"], "rationale": "New event evidence only."}]


def verdict(**change):
    """Return fake semantic review, not evidence of real scientific correctness."""
    return [{"edit_id": "CHANGE_A", "accepted": True, "scope_preserved": True,
        "evidence_supported": True, "prior_content_preserved": True, "rationale": "Synthetic review.", **change}]


ACCEPTED = [{"item_id": "FINDING_A", "accepted": True}]


class ProductMemoryTests(unittest.TestCase):
    def test_legacy_product_document_requires_index_migration(self):
        class Legacy(MemoryView):
            def table_of_contents(self):
                return [SimpleNamespace(path=SimpleNamespace(parts=("Lessons",)))]
        fake = FakeInputs(memory=Legacy())
        result = run_analysis(fake)["outputs"]["clinical_intelligence"]
        self.assertEqual("deferred", result["memory_update"]["status"])
        self.assertEqual("product_memory_index_migration_required", result["memory_update"]["reason"])
        self.assertNotIn("product_memory_editor", [x[0] for x in fake.calls])

    def test_default_class_off_product_selector_only(self):
        raw = example_inputs(); raw["variables"].pop("enable_pharmacological_class")
        fake = FakeInputs(raw); result = run_analysis(fake)["outputs"]["clinical_intelligence"]
        self.assertEqual([("product_memory", {"product_id": "PRODUCT_SYN"})], fake.memory_calls)
        self.assertFalse(result["memory_update"]["class_extension"]["enabled"])

    def test_class_read_happens_after_product_editor(self):
        raw = example_inputs(); raw["variables"]["enable_pharmacological_class"] = True
        owner = self
        class Ordered(FakeInputs):
            def dynamic_skill(self, role, *, variables):
                if role == "group_memory":
                    owner.assertIn("product_memory_editor", [x[0] for x in self.calls])
                return super().dynamic_skill(role, variables=variables)
        fake = Ordered(raw); result = run_analysis(fake)["outputs"]["clinical_intelligence"]
        self.assertEqual(["product_memory", "group_memory"], [x[0] for x in fake.memory_calls])
        self.assertEqual("candidate_preview", result["memory_update"]["class_extension"]["status"])

    def test_disabled_class_never_needs_class_identity(self):
        raw = example_inputs(); raw["clinical_context"]["subject"]["pharmacological_group_id"] = None
        self.assertEqual("success", run_analysis(FakeInputs(raw))["status"])

    def test_class_flag_is_boolean_not_truthy_string(self):
        for bad in ("false", "true", 1, None):
            raw = example_inputs(); raw["variables"]["enable_pharmacological_class"] = bad
            with self.assertRaisesRegex(ContractError, "class_flag"): parse_request(FakeInputs(raw))

    def test_opt_in_without_class_identity_rejected(self):
        raw = example_inputs(); raw["variables"]["enable_pharmacological_class"] = True
        raw["clinical_context"]["subject"]["pharmacological_group_id"] = None
        with self.assertRaisesRegex(ContractError, "class_identity"): parse_request(FakeInputs(raw))

    def test_different_indication_same_product_different_section(self):
        first, req1, snap1 = state(); raw = example_inputs()
        raw["clinical_context"]["case_scope"]["indication_id"] = "IND_OTHER"
        second = FakeInputs(raw); req2 = parse_request(second); snap2 = read_product_memory(second, req2)
        self.assertEqual(first.memory_calls, second.memory_calls)
        self.assertNotEqual(case_path(req1), case_path(req2)); self.assertFalse(snap2["section_exists"])
        self.assertEqual([], snap2["paragraphs"])

    def test_different_trial_same_product_different_section(self):
        raw = example_inputs(); raw["clinical_context"]["subject"]["trial_ids"] = ["TRIAL_OTHER"]
        raw["clinical_context"]["case_scope"]["trial_id"] = "TRIAL_OTHER"
        fake = FakeInputs(raw); snap = read_product_memory(fake, parse_request(fake))
        self.assertEqual({"product_id": "PRODUCT_SYN"}, fake.memory_calls[0][1]); self.assertFalse(snap["section_exists"])

    def test_mixed_trial_invocation_must_be_split(self):
        raw = example_inputs(); raw["clinical_context"]["subject"]["trial_ids"].append("TRIAL_OTHER")
        with self.assertRaisesRegex(ContractError, "single_trial_scope"): parse_request(FakeInputs(raw))

    def test_two_events_same_case_keep_same_memory_identity(self):
        fake, request, snapshot = state(); raw = example_inputs()
        raw["variables"]["event_ids"] = raw["clinical_context"]["event_ids"] = ["EVENT_OTHER"]
        other = FakeInputs(raw); changed = read_product_memory(other, parse_request(other))
        self.assertEqual(fake.memory_calls, other.memory_calls); self.assertEqual(snapshot["section_path"], changed["section_path"])

    def test_full_read_and_section_read_are_not_called(self):
        class Strict(MemoryView):
            def read(self): raise AssertionError("full read forbidden")
            def section_text(self, _): raise AssertionError("whole section read forbidden")
        self.assertEqual("read", state(Strict())[2]["status"])

    def test_long_unrelated_document_does_not_reach_model(self):
        owner = self
        class Large(MemoryView):
            def table_of_contents(self):
                return super().table_of_contents() + [SimpleNamespace(path=SimpleNamespace(parts=("Unrelated",)))]
            def paragraphs(self, section):
                owner.assertNotEqual(["Unrelated"], section)
                return super().paragraphs(section)
        self.assertLessEqual(state(Large())[2]["selected_characters"], 12000)

    def test_relevance_ranking_does_not_reorder_source(self):
        value = "EVENT_SYN prior evidence.\n\n" + "\n\n".join("Unrelated note " + str(i) for i in range(30))
        snapshot = state(MemoryView(value))[2]
        self.assertEqual(8, len(snapshot["paragraphs"])); self.assertEqual(23, snapshot["omitted_count"])
        self.assertTrue(snapshot["paragraphs"][0]["text"].startswith("EVENT_SYN"))
        self.assertEqual(0, snapshot["paragraphs"][0]["block_ref"]["ordinal_hint"])

    def test_oversized_paragraph_is_reported_not_truncated(self):
        snapshot = state(MemoryView("x" * 16001))[2]
        self.assertEqual([], snapshot["paragraphs"]); self.assertEqual(1, snapshot["omitted_count"])
        self.assertFalse(snapshot["scope_complete"])

    def test_local_index_never_enters_agent_projection(self):
        snapshot = state()[2]; self.assertIn("_known_text_digests", snapshot)
        self.assertNotIn("_known_text_digests", memory_projection(snapshot))

    def test_cross_indication_edit_rejected(self):
        snapshot = state()[2]; rows = edits(snapshot); rows[0]["section_path"][0] = "Indication OTHER"
        with self.assertRaisesRegex(ContractError, "cross_scope"): validate_edit_candidates(rows, snapshot, ACCEPTED)

    def test_unread_target_rejected(self):
        snapshot = state()[2]; rows = edits(snapshot, "replace_paragraph"); rows[0]["target_paragraph_id"] = "unknown"
        with self.assertRaisesRegex(ContractError, "unread_target"): validate_edit_candidates(rows, snapshot, ACCEPTED)

    def test_stale_target_digest_rejected(self):
        snapshot = state()[2]; rows = edits(snapshot, "enrich_paragraph"); rows[0]["before_digest"] = text_digest("wrong")
        with self.assertRaisesRegex(ContractError, "target_stale"): validate_edit_candidates(rows, snapshot, ACCEPTED)

    def test_whole_document_rewrite_not_a_paragraph(self):
        snapshot = state()[2]; rows = edits(snapshot); rows[0]["new_text"] = "# New document\n\nReplacement"
        with self.assertRaisesRegex(ContractError, "single_paragraph"): validate_edit_candidates(rows, snapshot, ACCEPTED)

    def test_unaccepted_scientific_item_cannot_be_memory_evidence(self):
        snapshot = state()[2]
        with self.assertRaisesRegex(ContractError, "unaccepted_evidence"):
            validate_edit_candidates(edits(snapshot), snapshot, [{"item_id": "FINDING_A", "accepted": False}])

    def test_add_section_cannot_overwrite_existing_case(self):
        snapshot = state()[2]
        with self.assertRaisesRegex(ContractError, "section_operation"):
            validate_edit_candidates(edits(snapshot, "add_section"), snapshot, ACCEPTED)

    def test_missing_memory_requires_initialization_not_implied_write(self):
        _, request, snapshot = state(CodedFailure("dynamic_skill_not_initialized"))
        candidates = validate_edit_candidates(edits(snapshot, "add_section"), snapshot, ACCEPTED)
        plan = review_edit_plan(candidates, verdict(), snapshot, request)
        self.assertTrue(plan["initialization_required"]); self.assertFalse(plan["write_attempted"])

    def test_missing_critic_never_approves_edit(self):
        _, request, snapshot = state(); candidates = validate_edit_candidates(edits(snapshot), snapshot, ACCEPTED)
        plan = review_edit_plan(candidates, None, snapshot, request)
        self.assertEqual("partial", plan["status"]); self.assertEqual([], plan["operations"])

    def test_content_loss_or_scope_failure_withholds_edit(self):
        _, request, snapshot = state(); candidates = validate_edit_candidates(edits(snapshot), snapshot, ACCEPTED)
        for field in ("scope_preserved", "prior_content_preserved", "evidence_supported", "accepted"):
            self.assertEqual([], review_edit_plan(candidates, verdict(**{field: False}), snapshot, request)["operations"])

    def test_identical_text_is_no_change(self):
        _, request, snapshot = state(MemoryView("An explicitly qualified new finding in this trial."))
        candidates = validate_edit_candidates(edits(snapshot), snapshot, ACCEPTED)
        self.assertEqual("no_change", review_edit_plan(candidates, verdict(), snapshot, request)["status"])

    def test_compiler_requires_exact_baseline_and_never_applies(self):
        _, request, snapshot = state()
        candidates = validate_edit_candidates(edits(snapshot, "replace_paragraph"), snapshot, ACCEPTED)
        plan = review_edit_plan(candidates, verdict(), snapshot, request)
        class Changes:
            def __init__(self): self.operations = []
            def replace_paragraph(self, ref, text): self.operations.append(("replace_paragraph", ref, text))
        class Mutable(MemoryView):
            def __init__(self): super().__init__(mutable=True)
            def new_changeset(self): return Changes()
            def apply(self, *args, **kwargs): raise AssertionError("No live write")
        self.assertEqual("replace_paragraph", compile_product_changeset(Mutable(), plan).operations[0][0])
        changed = Mutable(); changed.content_digest = lambda: text_digest("Changed elsewhere")
        with self.assertRaisesRegex(ContractError, "baseline_stale"): compile_product_changeset(changed, plan)
        changed_plan = deepcopy(plan); changed_plan["operations"][0]["new_text"] = "Unreviewed change."
        with self.assertRaisesRegex(ContractError, "proposal_changed"): compile_product_changeset(Mutable(), changed_plan)

    def test_optional_class_failure_preserves_product_plan(self):
        raw = example_inputs(); raw["variables"]["enable_pharmacological_class"] = True
        class ClassUnavailable(FakeInputs):
            def dynamic_skill(self, role, *, variables):
                if role == "group_memory": raise CodedFailure("node_not_found")
                return super().dynamic_skill(role, variables=variables)
        result = run_analysis(ClassUnavailable(raw))["outputs"]["clinical_intelligence"]
        self.assertEqual("preview", result["memory_update"]["status"])
        self.assertEqual("blocked", result["memory_update"]["class_extension"]["status"])

    def test_same_case_two_events_share_one_product_plan(self):
        raw = example_inputs(); raw["variables"]["event_ids"] = raw["clinical_context"]["event_ids"] = ["EVENT_SYN", "EVENT_OTHER"]
        fake = FakeInputs(raw); result = run_analysis(fake)["outputs"]["clinical_intelligence"]
        self.assertEqual(["EVENT_SYN", "EVENT_OTHER"], result["memory_update"]["event_ids"])
        self.assertEqual(1, len(fake.memory_calls)); self.assertFalse(result["memory_update"]["write_attempted"])


if __name__ == "__main__": unittest.main()
