"""Lossless focused critic packets with independent item validation.

No extra planner/model is used. The ordinary small case stays one review call.
Large cases split only between complete assertions and retain exact evidence
references. Missing evidence is a visible gap, not a silently complete review.
"""
from __future__ import annotations
from copy import deepcopy
from typing import Any

if __package__:
    from .contracts_v0_1_5 import ContractError, canonical_bytes, require
    from .quality_v0_1_5 import review_items, validate_dependencies, enforce_consistency
else:
    from contracts_v0_1_5 import ContractError, canonical_bytes, require
    from quality_v0_1_5 import review_items, validate_dependencies, enforce_consistency


def critic_batches(items: list[dict], evidence: list[dict], common: dict,
                   max_bytes: int, max_items: int = 32, *, fits=None) -> list[dict]:
    """Factor common context once and keep each item's complete evidence closure."""
    by_id = {item["item_id"]: item for item in items}
    source_index = {row["evidence_id"]: row for row in evidence}

    def packet(batch: list[dict]) -> dict:
        keys = {item["item_id"] for item in batch}
        needed, previous = set(keys), set()
        while needed != previous:
            previous = set(needed)
            needed.update(dep for key in previous for dep in by_id[key]["depends_on"] if dep in by_id)
        candidates = [deepcopy(item) for item in batch]
        context_items = [deepcopy(by_id[key]) for key in sorted(needed - keys)]
        refs = {ref for key in needed for field in ("supporting_evidence_ids", "contradicting_evidence_ids")
                for ref in by_id[key][field]}
        require(refs <= set(source_index), "clinical_critic_source_closure_invalid")
        selected = [deepcopy(source_index[key]) for key in sorted(refs)]
        # Keep other available evidence discoverable. A model can ask for a
        # targeted follow-up; it cannot claim to have read omitted source text.
        extra = [{"evidence_id": row["evidence_id"], "source_type": row["source_type"],
                  "trial_ids": row["trial_ids"], "text_digest": row["text_digest"]}
                 for row in evidence if row["evidence_id"] not in refs]
        return {**deepcopy(common), "candidate_items": candidates,
            "dependency_context": context_items, "evidence_packet": selected,
            "other_evidence_index": extra,
            "review_packet_scope": {"assigned_item_ids": sorted(keys),
                "full_evidence_read": not extra, "no_independent_exhaustiveness_claim": True}}

    output: list[dict] = []
    current: list[dict] = []
    for item in items:
        proposed = current + [item]
        if current and (len(proposed) > max_items or len(canonical_bytes(packet(proposed))) > max_bytes or
                        (fits is not None and not fits(packet(proposed)))):
            output.append(packet(current))
            current = []
        current.append(item)
    if current:
        output.append(packet(current))
    # A single oversize item stays whole. AgentRunner will defer it without a call.
    return output


def scoped_review(items: list[dict], verdicts: Any, ledger: Any) -> tuple[list[dict], list[dict]]:
    """Keep original strict validators while isolating malformed verdict entries.

    Identity/authority of the Agent envelope is validated by AgentRunner. A bad
    business verdict cannot approve a claim or invalidate unrelated verdicts.
    Duplicate verdict identities are withheld, never resolved by first/last wins.
    """
    validate_dependencies(items)
    if verdicts is None:
        return review_items(items, None, ledger)
    require(isinstance(verdicts, list), "clinical_critic_items_invalid")
    assigned = {item["item_id"] for item in items}
    counts: dict[str, int] = {}
    for row in verdicts:
        if isinstance(row, dict) and isinstance(row.get("item_id"), str):
            counts[row["item_id"]] = counts.get(row["item_id"], 0) + 1
    good, issues = [], []
    for index, row in enumerate(verdicts):
        key = row.get("item_id") if isinstance(row, dict) else None
        if not isinstance(key, str) or key not in assigned or counts.get(key) != 1:
            issues.append({"code": "clinical_critic_identity_invalid", "verdict_index": index})
            continue
        try:
            # Validation against the full dependency set preserves premise checks.
            review_items(items, [row], ledger)
        except ContractError as error:
            if error.code == "clinical_authority_material_forbidden":
                raise
            issues.append({"code": error.code, "item_id": key})
        else:
            good.append(row)
    reviewed, errors = review_items(items, good, ledger)
    issues.extend(errors)
    issues.extend(enforce_consistency(reviewed))
    return reviewed, issues
