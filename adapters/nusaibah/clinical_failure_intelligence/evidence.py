"""Source-window identity and literal support checks, not semantic truth tests."""
from __future__ import annotations
from copy import deepcopy
from typing import Any
if __package__:
    from .contracts import (ContractError, digest, identifier, identifiers, iso_date,
                            object_fields, require, text, text_digest)
else:
    from contracts import (ContractError, digest, identifier, identifiers, iso_date,
                           object_fields, require, text, text_digest)

SOURCE_TYPES = {"trial_registry", "original_research", "regulator", "sponsor",
                "news", "review", "supplied_assertion"}
EXTENTS = {"registry_record", "abstract", "full_text", "excerpt", "supplied_assertion"}


class EvidenceLedger:
    """Run-local source inventory with explicit aliases and immutable evidence IDs."""
    def __init__(self, subject_id: str, as_of_date: str, rows: list[dict]) -> None:
        self.subject_id = subject_id
        self.as_of_date = as_of_date
        self.items: dict[str, dict] = {}
        self.aliases: dict[str, str] = {}
        self._keys: dict[str, str] = {}
        for row in rows:
            self.add(row)

    def add(self, value: Any) -> str:
        """Admit resolved source data; model-authored source leads never call this."""
        row = object_fields(value, {"evidence_id", "source_id", "subject_id", "source_type",
            "source_version", "published_on", "accessible_extent", "text", "trial_ids"},
            {"reference", "title", "declared_text_digest"})
        eid = identifier(row["evidence_id"])
        identifier(row["source_id"])
        require(row["subject_id"] == self.subject_id, "clinical_evidence_subject_mismatch")
        require(isinstance(row["source_type"], str) and row["source_type"] in SOURCE_TYPES,
                "clinical_source_type_invalid")
        require(isinstance(row["accessible_extent"], str) and row["accessible_extent"] in EXTENTS,
                "clinical_evidence_extent_invalid")
        text(row["source_version"], maximum=128)
        text(row["text"], maximum=12000)
        for field in ("reference", "title"):
            if row.get(field) is not None:
                text(row[field], maximum=4096)
        identifiers(row["trial_ids"], maximum=32)
        if row["published_on"] is not None:
            require(iso_date(row["published_on"]) <= self.as_of_date, "clinical_evidence_temporal_leak")
        checksum = text_digest(row["text"])
        require(row.get("declared_text_digest", checksum) == checksum, "clinical_evidence_digest_mismatch")
        normalized = deepcopy(row)
        normalized.pop("declared_text_digest", None)
        normalized.update(text_digest=checksum, origin="resolved_context", verification="source_available")
        identity_keys = ("source_id", "source_version", "text_digest", "subject_id",
                         "published_on", "accessible_extent", "source_type", "trial_ids")
        key = digest({k: normalized[k] for k in identity_keys})
        if eid in self.aliases:
            old = self.items[self.aliases[eid]]
            require(all(old[k] == normalized[k] for k in identity_keys), "clinical_evidence_id_collision")
            return self.aliases[eid]
        if key in self._keys:
            canonical = self._keys[key]
            self.aliases[eid] = canonical
            return canonical
        self._keys[key] = eid
        self.aliases[eid] = eid
        self.items[eid] = normalized
        return eid

    def refs(self, value: Any) -> list[str]:
        """Resolve every reference; no invented source can become evidence."""
        supplied = identifiers(value)
        require(all(ref in self.aliases for ref in supplied), "clinical_evidence_ref_unknown")
        return list(dict.fromkeys(self.aliases[ref] for ref in supplied))

    def rows(self) -> list[dict]:
        """Return stable detached views rather than mutable shared Agent state."""
        return [deepcopy(self.items[key]) for key in sorted(self.items)]

    def assert_usable(self, references: list[str]) -> None:
        """Block supplied assertions or undated sources from definitive conclusions."""
        require(bool(references), "clinical_definitive_evidence_missing")
        for ref in references:
            source = self.items[ref]
            require(source["source_type"] != "supplied_assertion" and
                    source["accessible_extent"] != "supplied_assertion" and
                    source["published_on"] is not None, "clinical_definitive_evidence_unverified")

    def validate_claims(self, rows: list, *, stage_id: str) -> tuple[list[dict], list[dict]]:
        """Keep valid siblings and flag bad spans; a literal match is not entailment."""
        require(isinstance(rows, list) and len(rows) <= 32, "clinical_claim_batch_invalid")
        seen: set[str] = set()
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("claim_id"), str):
                require(row["claim_id"] not in seen, "clinical_claim_id_duplicate")
                seen.add(row["claim_id"])
        valid, issues = [], []
        for index, original in enumerate(rows):
            try:
                row = object_fields(original, {"claim_id", "subject_id", "statement", "claim_kind",
                    "supporting_evidence_ids", "contradicting_evidence_ids", "source_spans"})
                cid = identifier(row["claim_id"])
                require(row["subject_id"] == self.subject_id, "clinical_claim_subject_mismatch")
                text(row["statement"])
                require(isinstance(row["claim_kind"], str) and row["claim_kind"] in {
                    "observation", "attributed_reason", "mechanistic_evidence", "comparative_evidence"},
                    "clinical_claim_kind_invalid")
                support = self.refs(row["supporting_evidence_ids"])
                against = self.refs(row["contradicting_evidence_ids"])
                require(isinstance(row["source_spans"], list) and len(row["source_spans"]) <= 8,
                        "clinical_spans_invalid")
                checked = []
                for span in row["source_spans"]:
                    object_fields(span, {"evidence_id", "start", "end", "quote", "text_digest"})
                    ref = self.refs([span["evidence_id"]])[0]
                    require(ref in support + against, "clinical_span_claim_mismatch")
                    source = self.items[ref]
                    start, end = span["start"], span["end"]
                    require(type(start) is int and type(end) is int and 0 <= start < end <= len(source["text"]),
                            "clinical_span_offsets_invalid")
                    require(span["text_digest"] == source["text_digest"] and
                            source["text"][start:end] == span["quote"], "clinical_span_mismatch")
                    checked.append({**span, "evidence_id": ref})
                valid.append({**deepcopy(row), "claim_id": "claim:" + digest([stage_id, cid]).split(":")[1][:32],
                    "local_claim_id": cid, "supporting_evidence_ids": support,
                    "contradicting_evidence_ids": against, "source_spans": checked,
                    "verification": "passage_checked" if checked else "unverified", "review_status": "unreviewed"})
            except ContractError as exc:
                if exc.code == "clinical_claim_subject_mismatch":
                    raise
                issues.append({"stage_id": stage_id, "item_index": index, "code": exc.code})
        return valid, issues
