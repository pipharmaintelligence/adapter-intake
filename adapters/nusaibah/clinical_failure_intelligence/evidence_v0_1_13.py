"""Source-window identity and literal support checks, not semantic truth tests."""
from __future__ import annotations
from copy import deepcopy
from typing import Any
if __package__:
    from .contracts_v0_1_13 import (ContractError, digest, identifier, identifiers, iso_date,
                            object_fields, require, text, text_digest)
else:
    from contracts_v0_1_13 import (ContractError, digest, identifier, identifiers, iso_date,
                           object_fields, require, text, text_digest)

SOURCE_TYPES = {"trial_registry", "original_research", "regulator", "sponsor",
                "news", "review", "publication", "supplied_assertion"}
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
            {"reference", "title", "declared_text_digest", "source_context"})
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
        context = row.get("source_context")
        if context is not None:
            require(isinstance(context, dict), "clinical_source_context_invalid")
            require(context.get("purpose") in {"case", "comparator", "mechanism"},
                    "clinical_source_purpose_invalid")
            interval = context.get("publication_interval")
            require(isinstance(interval, dict), "clinical_source_interval_invalid")
            earliest, latest = interval.get("start"), interval.get("end")
            require((earliest is None) == (latest is None), "clinical_source_interval_invalid")
            if latest is not None:
                require(iso_date(earliest) <= iso_date(latest), "clinical_source_interval_invalid")
            # Never trust an upstream temporal label in place of source dates.
            expected_temporal = ("unknown" if latest is None else
                "eligible_by_source_date" if latest <= self.as_of_date else
                "after_cutoff" if earliest > self.as_of_date else "overlaps_cutoff")
            require(context.get("temporal_status") == expected_temporal and expected_temporal != "after_cutoff",
                    "clinical_evidence_temporal_leak")
        normalized = deepcopy(row)
        normalized.pop("declared_text_digest", None)
        normalized.update(text_digest=checksum, origin="resolved_context", verification="source_available")
        identity_keys = ("source_id", "source_version", "text_digest", "subject_id",
                         "published_on", "accessible_extent", "source_type", "trial_ids")
        key = digest({**{k: normalized[k] for k in identity_keys},
                      "source_context": normalized.get("source_context")})
        if eid in self.aliases:
            old = self.items[self.aliases[eid]]
            require(all(old[k] == normalized[k] for k in identity_keys) and
                    old.get("source_context") == normalized.get("source_context"), "clinical_evidence_id_collision")
            return self.aliases[eid]
        if key in self._keys:
            canonical = self._keys[key]
            self.aliases[eid] = canonical
            return canonical
        self._keys[key] = eid
        self.items[eid] = normalized
        self.aliases[eid] = eid
        return eid

    def refs(self, value: Any) -> list[str]:
        """Resolve every reference; no invented source can become evidence."""
        supplied = identifiers(value)
        require(all(ref in self.aliases for ref in supplied), "clinical_evidence_ref_unknown")
        return list(dict.fromkeys(self.aliases[ref] for ref in supplied))

    def rows(self) -> list[dict]:
        """Return stable detached views rather than mutable shared Agent state."""
        return [deepcopy(self.items[key]) for key in sorted(self.items)]

    def assert_usable(self, references: list[str], *, outcome_dimension: str | None = None) -> None:
        """Require usable evidence without equating source access with scientific truth.

        Protocol endpoints cannot establish that an endpoint was met/not met.
        Comparator/mechanism context cannot establish this case's outcome. An
        article carrying a notice or uncertain date remains review context only.
        Legacy resolved evidence retains its original date-based contract.
        """
        require(bool(references), "clinical_definitive_evidence_missing")
        outcome_support = False
        for ref in references:
            source = self.items[ref]
            context = source.get("source_context")
            dated = source["published_on"] is not None
            if context is not None:
                dated = context["temporal_status"] == "eligible_by_source_date"
                require(context.get("integrity_status") != "notice_reported",
                        "clinical_publication_notice_requires_review")
                if outcome_dimension:
                    require(context["purpose"] == "case", "clinical_outcome_comparator_not_case")
                    use = context.get("evidence_use")
                    if outcome_dimension in {"primary_endpoint_result", "safety_assessment"}:
                        outcome_support |= use in {"posted_results", "safety_results", "publication_text"}
                    else:
                        outcome_support = True
            else:
                outcome_support = True
            require(source["source_type"] != "supplied_assertion" and
                    source["accessible_extent"] != "supplied_assertion" and dated,
                    "clinical_definitive_evidence_unverified")
        if outcome_dimension:
            require(outcome_support, "clinical_outcome_result_evidence_required")

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
                checked, adjustments = [], []
                for span_index, span in enumerate(row["source_spans"]):
                    object_fields(span, {"evidence_id", "start", "end", "quote", "text_digest"})
                    ref = self.refs([span["evidence_id"]])[0]
                    require(ref in support + against, "clinical_span_claim_mismatch")
                    source = self.items[ref]
                    start, end = span["start"], span["end"]
                    # The digest is supplied with the authoritative window; it
                    # must never be invented/repaired from another source.
                    require(span["text_digest"] == source["text_digest"], "clinical_span_mismatch")
                    quote = span["quote"]
                    require(isinstance(quote, str) and bool(quote), "clinical_span_mismatch")
                    offsets_valid = type(start) is int and type(end) is int and 0 <= start < end <= len(source["text"])
                    if not offsets_valid or source["text"][start:end] != quote:
                        first = source["text"].find(quote)
                        # A unique literal quotation can authoritatively repair
                        # byte/UTF16/off-by-one offsets without another model call.
                        # Ambiguity, paraphrase, units, negation and symbols are
                        # never guessed or normalized into a different quotation.
                        require(first >= 0 and source["text"].find(quote, first+1) < 0,
                                "clinical_span_mismatch" if offsets_valid else "clinical_span_offsets_invalid")
                        start, end = first, first+len(quote)
                        adjustments.append({"span_index": span_index, "method": "unique_verbatim_reanchor"})
                    checked.append({**span, "start": start, "end": end, "evidence_id": ref})
                valid.append({**deepcopy(row), "claim_id": "claim:" + digest([stage_id, cid]).split(":")[1][:32],
                    "local_claim_id": cid, "supporting_evidence_ids": support,
                    "contradicting_evidence_ids": against, "source_spans": checked,
                    "verification": "passage_checked" if checked else "unverified", "review_status": "unreviewed",
                    **({"anchor_adjustments": adjustments} if adjustments else {})})
            except ContractError as exc:
                if exc.code == "clinical_claim_subject_mismatch":
                    raise
                issues.append({"stage_id": stage_id, "item_index": index, "code": exc.code})
        return valid, issues
