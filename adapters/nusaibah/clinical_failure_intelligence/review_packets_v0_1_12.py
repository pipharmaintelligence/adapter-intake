"""Lossless focused critic packets with independent item validation.

No extra planner/model is used. The ordinary small case stays one review call.
Large cases split only between complete assertions and retain exact evidence
references. Missing evidence is a visible gap, not a silently complete review.
"""
from __future__ import annotations
from copy import deepcopy
from typing import Any

if __package__:
    from .contracts_v0_1_12 import ContractError, canonical_bytes, require, digest
    from .analysis_packets_v0_1_12 import agent_evidence_view
    from .case_context_v0_1_12 import case_context_ids
    from .quality_v0_1_12 import review_items, validate_dependencies, enforce_consistency
else:
    from contracts_v0_1_12 import ContractError, canonical_bytes, require, digest
    from analysis_packets_v0_1_12 import agent_evidence_view
    from case_context_v0_1_12 import case_context_ids
    from quality_v0_1_12 import review_items, validate_dependencies, enforce_consistency


def critic_batches(items: list[dict], evidence: list[dict], common: dict,
                   max_bytes: int, max_items: int = 32, *, fits=None) -> list[dict]:
    """Factor common context once and keep each item's complete evidence closure."""
    by_id = {item["item_id"]: item for item in items}
    source_index = {row["evidence_id"]: row for row in evidence}
    anchors=case_context_ids(evidence,common.get('case_trial_ids'))

    def packet(batch: list[dict]) -> dict:
        keys = {item["item_id"] for item in batch}
        needed, previous = set(keys), set()
        while needed != previous:
            previous = set(needed)
            needed.update(dep for key in previous for dep in by_id[key]["depends_on"] if dep in by_id)
        candidates = [deepcopy(item) for item in batch]
        context_items = [deepcopy(by_id[key]) for key in sorted(needed - keys)]
        refs = {ref for key in keys for field in ("supporting_evidence_ids", "contradicting_evidence_ids")
                for ref in by_id[key][field]}
        refs.update(anchors)
        require(refs <= set(source_index), "clinical_critic_source_closure_invalid")
        selected = [deepcopy(source_index[key]) for key in sorted(refs)]
        # Keep other available evidence discoverable. A model can ask for a
        # targeted follow-up; it cannot claim to have read omitted source text.
        groups = {}
        for row in evidence:
            if row["evidence_id"] not in refs:
                key = (row["source_type"], tuple(row["trial_ids"]))
                groups.setdefault(key, []).append(row["evidence_id"])
        # Same discoverable IDs/type/trial scope, factored once per group.
        # Canonical text digests stay with the original ledger and supplied rows.
        extra = [{"source_type": key[0], "trial_ids": list(key[1]), "evidence_count": len(ids), "evidence_ids_digest": digest(ids)}
                 for key, ids in sorted(groups.items())]
        return {**deepcopy(common), "candidate_items": candidates,"case_context_evidence_ids":sorted(anchors),
            "dependency_context": context_items, "evidence_packet": agent_evidence_view(selected),
            "dependency_review_policy": {
                "representation":"derived_candidate_records_not_raw_sources",
                "each_dependency_has_its_own_assigned_review":True,
                "final_acceptance_requires_all_premises_accepted":True,
                "instruction":"Dependency records retain complete derived statements and reference identities. Their unseen source text is not supplied or certified in this packet. Review only assigned candidates from their own complete supplied evidence. Premises are reviewed separately; the deterministic final join revokes acceptance when any premise is unaccepted."},
            "other_evidence_index": extra,
            "unassigned_source_policy": "Inventory summaries are discovery leads only. Full canonical IDs and text remain in the assessment ledger; no omitted source may be cited or claimed read. Request a scoped follow-up for missing evidence.",
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


def isolate_dependencies(items):
    """Quarantine invalid branches and their dependants, retaining every original item."""
    by_id = {row['item_id']:row for row in items}
    require(len(by_id)==len(items),'clinical_item_duplicate')
    reasons = {key:'clinical_dependency_unknown' for key,row in by_id.items()
               if any(ref not in by_id for ref in row['depends_on'])}
    done, path, active = set(), [], set()
    def visit(key):
        if key in active:
            for member in path[path.index(key):]:
                reasons[member] = 'clinical_dependency_cycle'
            return
        if key in done:
            return
        path.append(key);active.add(key)
        for dependency in by_id[key]['depends_on']:
            if dependency in by_id:
                visit(dependency)
        active.remove(key);path.pop();done.add(key)
    for key in by_id:
        visit(key)
    while True:
        affected = {key:'clinical_dependency_unresolved' for key,row in by_id.items()
                    if key not in reasons and any(ref in reasons for ref in row['depends_on'])}
        if not affected:
            break
        reasons.update(affected)
    valid, blocked, issues = [], [], []
    for source in items:
        row = deepcopy(source);key = row['item_id']
        if key not in reasons:
            valid.append(row);continue
        row['unresolved_dependency_ids'] = deepcopy(row['depends_on'])
        row['depends_on'] = []
        row.update(accepted=False,review_status='unreviewed',review_reason=reasons[key])
        if row['kind']=='hypothesis':
            row.update(verdict='inconclusive',memory_eligibility=False)
        blocked.append(row)
        issues.append({'code':reasons[key],'item_id':key,'unresolved_dependency_ids':row['unresolved_dependency_ids']})
    validate_dependencies(valid)
    return valid, blocked, issues


def scoped_review(items: list[dict], verdicts: Any, ledger: Any, *, assigned_ids=None) -> tuple[list[dict], list[dict]]:
    """Keep original strict validators while isolating malformed verdict entries.

    Identity/authority of the Agent envelope is validated by AgentRunner. A bad
    business verdict cannot approve a claim or invalidate unrelated verdicts.
    Duplicate verdict identities are withheld, never resolved by first/last wins.
    """
    valid, blocked, graph_issues = isolate_dependencies(items)
    mapped = {row['item_id']:row for row in valid+blocked}
    items = [mapped[row['item_id']] for row in items]
    validate_dependencies(items)
    if verdicts is None:
        return review_items(items, None, ledger, assigned_ids=assigned_ids)
    require(isinstance(verdicts, list), "clinical_critic_items_invalid")
    assigned = {item["item_id"] for item in items} if assigned_ids is None else set(assigned_ids)
    require(assigned <= {item["item_id"] for item in items}, "clinical_critic_identity_invalid")
    counts: dict[str, int] = {}
    for row in verdicts:
        if isinstance(row, dict) and isinstance(row.get("item_id"), str):
            counts[row["item_id"]] = counts.get(row["item_id"], 0) + 1
    good, issues = [], list(graph_issues)
    for index, row in enumerate(verdicts):
        key = row.get("item_id") if isinstance(row, dict) else None
        if not isinstance(key, str) or key not in assigned or counts.get(key) != 1:
            issues.append({"code": "clinical_critic_identity_invalid", "verdict_index": index})
            continue
        try:
            # Validation against the full dependency set preserves premise checks.
            review_items(items, [row], ledger, assigned_ids=assigned)
        except ContractError as error:
            if error.code == "clinical_authority_material_forbidden":
                raise
            issues.append({"code": error.code, "item_id": key})
        else:
            good.append(row)
    reviewed, errors = review_items(items, good, ledger, assigned_ids=assigned)
    issues.extend(errors)
    issues.extend(enforce_consistency(reviewed))
    return reviewed, issues
