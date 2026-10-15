"""Synthetic runtime doubles only. No provider, network, storage or real clinical data."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import threading
from types import SimpleNamespace

ASSET_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSET_ROOT.parent))
from clinical_failure_intelligence.contracts import ROLE_SCHEMA, digest, text_digest
from clinical_failure_intelligence.memory import FIXED_REF
from clinical_failure_intelligence.quality import OUTCOMES


def example_inputs(mode="mechanistic_case"):
    """Return a small synthetic case or denominator-aware cohort."""
    subject = {"subject_id": "CASE_SYN", "product_id": "PRODUCT_SYN", "product_name": "Synthetic product Alpha",
        "pharmacological_group_id": "GROUP_SYN", "indication": "Synthetic indication", "regimen": "Synthetic regimen",
        "trial_ids": ["TRIAL_SYN"]}
    sources = [{"evidence_id": "E_TRIAL", "source_id": "REGISTRY_SYN", "subject_id": "CASE_SYN",
        "source_type": "trial_registry", "source_version": "1", "published_on": "2025-01-01",
        "accessible_extent": "registry_record", "text": "The study completed. The prespecified primary endpoint was not met.",
        "trial_ids": ["TRIAL_SYN"]},
        {"evidence_id": "E_PAPER", "source_id": "PAPER_SYN", "subject_id": "CASE_SYN",
        "source_type": "original_research", "source_version": "1", "published_on": "2025-01-02",
        "accessible_extent": "abstract", "text": "Exposure varied between participants. Target engagement was not measured.",
        "trial_ids": ["TRIAL_SYN"]}]
    return {"variables": {"schema_version": "clinical_analysis_request.v1", "request_id": "REQUEST_SYN",
        "analysis_mode": mode, "subject_id": "CASE_SYN", "as_of_date": "2025-02-01", "event_ids": ["EVENT_SYN"],
        "memory_mode": "preview", "enable_refinement": False},
        "clinical_context": {"schema_version": "clinical_context.v1", "context_id": "CONTEXT_SYN", "subject": subject,
        "event_ids": ["EVENT_SYN"], "source_assertions": [{"assertion_id": "SEED_SYN", "source_ref": "synthetic_fixture",
        "statement": "An exposure limitation may contribute to a negative endpoint result.",
        "general_research_observation": "This is a synthetic candidate hypothesis, not clinical evidence.",
        "example_drugs": ["Synthetic product Alpha"], "indicators_to_measure_and_validate": ["Exposure", "Endpoint result"]}],
        "evidence": sources, "cohort": example_cohort() if mode == "cohort_pattern" else None}}


def example_cohort():
    """Return synthetic disjoint groups with explicit missing outcomes."""
    return {"snapshot_ref": "COHORT_SYN", "unit_of_analysis": "trial", "denominator_complete": True,
        "selection": "eligible_all", "metric": "success_rate", "window_start": "2024-01-01", "window_end": "2025-01-31",
        "rows": [{"unit_id": str(i), "group": group, "eligible": True, "observed_on": "2025-01-01",
                  "outcome": outcome, "attribute": None}
                 for i, (group, outcome) in enumerate([("A", "success"), ("A", "failure"), ("A", "unknown"),
                                                     ("B", "success"), ("B", "ongoing")])]}


class CodedFailure(RuntimeError):
    """Synthetic reviewed error-code/cause pair."""
    def __init__(self, code, cause=None):
        self.code = self.failure_code = code
        self.cause_code = cause
        super().__init__(code)


class MemoryView:
    """Read-only in-memory fixture; no mutation methods exist."""
    def __init__(self, text="Existing scoped guidance.", mutable=False):
        self.text = text
        self.mutable = mutable
    def section_text(self, section):
        assert section == "Lessons"
        return self.text
    def content_digest(self):
        return text_digest(self.text)
    def provenance(self):
        return SimpleNamespace(mutable=self.mutable, package_digest=digest({"Lessons": self.text}))


class FixedView:
    """Read the fixture package; this does not attest runtime admission."""
    def section_text(self, section):
        source = (ASSET_ROOT / "skills/clinical-failure-methodology/SKILL.md").read_text()
        return source.split("## " + section + "\n", 1)[1].split("\n## ", 1)[0]


class FakeInputs(dict):
    """Inject semantic envelopes without impersonating SDK or live admission."""
    def __init__(self, data=None, *, faults=None, transforms=None, memory=None, response_kind="json"):
        super().__init__(deepcopy(data if data is not None else example_inputs()))
        self.faults = faults or {}
        self.transforms = transforms or {}
        self.memory = memory or MemoryView()
        self.response_kind = response_kind
        self.calls = []
        self.memory_calls = []
        self.lock = threading.Lock()
    def skill(self, selector):
        assert selector == FIXED_REF
        return FixedView()
    def dynamic_skill(self, role, *, variables):
        self.memory_calls.append((role, variables))
        assert role == "group_memory"
        assert variables == {"pharmacological_group_id": "GROUP_SYN"}
        if isinstance(self.memory, Exception):
            raise self.memory
        return self.memory
    def invoke_agent(self, role, *, input, on_error):
        assert on_error == "raise"
        with self.lock:
            self.calls.append((role, deepcopy(input)))
        if role in self.faults:
            raise self.faults[role]
        payload = self.role_payload(role, input)
        if role in self.transforms:
            payload = self.transforms[role](payload, input)
        block = {"type": "text", "text": "```json\n" + json.dumps(payload) + "\n```"} if self.response_kind == "text" else {"type": "json", "value": payload}
        return {"status": "completed", "result": {"schema_version": "agent_result.v1", "kind": self.response_kind,
            "content": [block], "model": "synthetic-model", "usage": {"input_tokens": 1},
            "metadata": {"synthetic": True},
            "provider_metadata": {"schema_version": "agent_provider_metadata.v1", "turns": []}}}
    def role_payload(self, role, packet):
        items = []
        if role.endswith("researcher"):
            for i, e in enumerate(packet["evidence_packet"]):
                items.append({"claim_id": "claim_" + str(i), "subject_id": "CASE_SYN", "statement": e["text"],
                    "claim_kind": "observation", "supporting_evidence_ids": [e["evidence_id"]],
                    "contradicting_evidence_ids": [], "source_spans": [{"evidence_id": e["evidence_id"], "start": 0,
                        "end": len(e["text"]), "quote": e["text"], "text_digest": e["text_digest"]}]})
        elif role == "outcome_adjudicator":
            for dimension in OUTCOMES:
                value = "completed" if dimension == "study_disposition" else "not_met" if dimension == "primary_endpoint_result" else "unknown"
                items.append({"item_id": "outcome_" + dimension, "subject_id": "CASE_SYN", "dimension": dimension,
                    "value": value, "statement": dimension + ": " + value, "trial_ids": ["TRIAL_SYN"],
                    "supporting_evidence_ids": ["E_TRIAL"], "contradicting_evidence_ids": [], "depends_on": []})
        elif role == "hypothesis_analyst":
            items = [{"item_id": "H_SYN", "subject_id": "CASE_SYN", "statement": "Exposure may contribute; the supplied data do not establish causation.",
                "supporting_evidence_ids": ["E_PAPER"], "contradicting_evidence_ids": [],
                "depends_on": ["outcome_primary_endpoint_result"], "source_assertion_id": "SEED_SYN",
                "reason_code": "pk_pd_exposure_dose", "scope": "Synthetic indication and regimen only",
                "proposed_verdict": "inconclusive", "alternative_explanations": ["Target biology", "Endpoint design"],
                "validation_indicators": ["Measure exposure", "Measure target engagement"],
                "falsification_condition": "Adequate exposure with unchanged outcomes would challenge the explanation.", "lesson": None}]
        elif role == "evidence_critic":
            items = [{"item_id": i["item_id"], "verdict": "accepted", "rationale": "Synthetic scoped review only.",
                "supporting_evidence_ids": i["supporting_evidence_ids"], "contradicting_evidence_ids": i["contradicting_evidence_ids"],
                "scope_preserved": True} for i in packet["candidate_items"]]
        return {"schema_version": ROLE_SCHEMA, "task_id": packet["task_id"], "subject_id": "CASE_SYN", "role": role,
            "coverage": [{"obligation_id": key, "status": "completed"} for key in packet["assigned_obligation_ids"]],
            "items": items, "followup_requests": []}
