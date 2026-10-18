"""Complete source-window batches, exact request sizing and explicit coverage."""
from __future__ import annotations
from copy import deepcopy
from typing import Callable

if __package__:
    from .contracts import canonical_bytes, digest, require
    from .source_bundle import prioritize_evidence
else:
    from contracts import canonical_bytes, digest, require
    from source_bundle import prioritize_evidence


def evidence_batches(rows: list[dict], build: Callable[[list[dict]], dict], *,
                     max_bytes: int, max_windows: int = 64) -> list[list[dict]]:
    """Fit the final model request, preserving every complete window exactly once.

    An individually unfittable window stays whole in its own batch; AgentRunner
    records that work as deferred, without aborting other batches or truncating.
    """
    output, current = [], []
    for row in prioritize_evidence(rows):
        proposed = current + [row]
        packet = build(proposed)
        assigned = packet.get("evidence_packet", proposed)
        if current and (len(assigned) > max_windows or len(canonical_bytes(packet)) > max_bytes):
            output.append(current)
            current = []
        current.append(row)
    if current:
        output.append(current)
    return output or [[]]


def closed_packet(rows: list[dict], inventory: list[dict], claims: list[dict], common: dict) -> dict:
    """Preserve full claim premise closure; never send a claim without its sources."""
    selected = {row["evidence_id"] for row in rows}
    index = {row["evidence_id"]: row for row in inventory}
    related = []
    for claim in claims:
        refs = set(claim["supporting_evidence_ids"] + claim["contradicting_evidence_ids"])
        if refs & selected or not refs:
            require(refs <= set(index), "clinical_analysis_source_closure_invalid")
            related.append(claim)
            selected.update(refs)
    packet_common = deepcopy(common)
    if "case_assessments" in packet_common:
        assessments = packet_common["case_assessments"]
        by_id = {item["item_id"]: item for item in assessments}
        needed = {item["item_id"] for item in assessments
            if not (item["supporting_evidence_ids"] + item["contradicting_evidence_ids"])
            or selected & set(item["supporting_evidence_ids"] + item["contradicting_evidence_ids"])}
        previous = set()
        while needed != previous:
            previous = set(needed)
            needed.update(dep for key in previous for dep in by_id[key]["depends_on"] if dep in by_id)
        chosen = [item for item in assessments if item["item_id"] in needed]
        for item in chosen:
            refs = set(item["supporting_evidence_ids"] + item["contradicting_evidence_ids"])
            require(refs <= set(index), "clinical_analysis_source_closure_invalid")
            selected.update(refs)
        packet_common["case_assessments"] = chosen
    # All additional premises remain explicit, even across a batch boundary.
    evidence = prioritize_evidence([deepcopy(index[key]) for key in index if key in selected])
    return {**packet_common, "evidence_packet": evidence, "research_claims": deepcopy(related),
        "evidence_scope": {"assigned_evidence_ids": [r["evidence_id"] for r in evidence],
            "inventory_digest": digest([r["evidence_id"] for r in inventory]),
            "total_available": len(inventory), "not_assigned_count": len(inventory) - len(evidence),
            "full_source_review": len(evidence) == len(inventory),
            "instruction": "Assess only supplied complete windows. Unassigned evidence remains unreviewed; do not infer global absence."}}
