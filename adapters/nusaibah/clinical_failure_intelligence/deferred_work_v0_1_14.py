"""Durable pending-work data in the result; never a signed retry instruction."""

from copy import deepcopy

if __package__:
    from .contracts_v0_1_14 import digest, require, canonical_bytes
    from .analysis_packets_v0_1_14 import agent_evidence_view
else:
    from contracts_v0_1_14 import digest, require, canonical_bytes
    from analysis_packets_v0_1_14 import agent_evidence_view


def _intern_context(value, objects):
    """Lossless shared context only; references grant no execution authority."""
    if isinstance(value, dict) and set(value) == {"$context"}:
        wrapper = {"kind": "clinical_packet_literal.v1", "value": deepcopy(value)}
        key = digest(wrapper)
        objects.setdefault(key, wrapper)
        return {"$context": key}
    if isinstance(value, dict):
        packed = {key: _intern_context(item, objects) for key, item in value.items()}
    elif isinstance(value, list):
        packed = [_intern_context(item, objects) for item in value]
    else:
        return deepcopy(value)
    if len(canonical_bytes(packed)) < 384:
        return packed
    wrapper = {"kind": "clinical_packet_context.v1", "value": packed}
    key = digest(wrapper)
    objects.setdefault(key, wrapper)
    return {"$context": key}


def _restore_context(value, objects, active=()):
    if isinstance(value, dict) and set(value) == {"$context"}:
        key = value["$context"]
        require(
            isinstance(key, str) and key not in active and len(active) < 64,
            "clinical_deferred_context_changed",
        )
        wrapper = objects.get(key)
        require(
            isinstance(wrapper, dict)
            and set(wrapper) == {"kind", "value"}
            and wrapper["kind"]
            in {"clinical_packet_context.v1", "clinical_packet_literal.v1"}
            and digest(wrapper) == key,
            "clinical_deferred_context_changed",
        )
        if wrapper["kind"] == "clinical_packet_literal.v1":
            return deepcopy(wrapper["value"])
        return _restore_context(wrapper["value"], objects, active + (key,))
    if isinstance(value, dict):
        return {
            key: _restore_context(item, objects, active) for key, item in value.items()
        }
    if isinstance(value, list):
        return [_restore_context(item, objects, active) for item in value]
    return deepcopy(value)


def freeze_packet(packet, objects):
    """Store exact non-source context, while referring to the single canonical ledger."""
    value = deepcopy(packet)
    aliases = value.get("reference_aliases", {}).get("evidence", {})
    if "evidence_packet" in value:
        value["evidence_packet"] = [
            {
                "$evidence": aliases.get(row["evidence_id"], row["evidence_id"]),
                "packet_evidence_id": row["evidence_id"],
                "digest": digest(row),
            }
            for row in value["evidence_packet"]
        ]
    for field in ("candidate_items", "dependency_context", "accepted_items"):
        if field in value:
            refs = []
            for row in value[field]:
                key = digest(row)
                objects.setdefault(key, deepcopy(row))
                refs.append({"$object": key})
            value[field] = refs
    return {key: _intern_context(item, objects) for key, item in value.items()}


def hydrate_task(task, deferred, evidence):
    """Provider-free exact reconstruction; source or context drift is rejected."""
    require(
        digest(evidence) == deferred["source_ledger_digest"],
        "clinical_deferred_source_changed",
    )
    value = _restore_context(task["input_packet"], deferred["objects"])
    source = {row["evidence_id"]: row for row in agent_evidence_view(evidence)}
    rows = []
    for ref in value.get("evidence_packet", []):
        require(ref["$evidence"] in source, "clinical_deferred_source_missing")
        row = deepcopy(source[ref["$evidence"]])
        row["evidence_id"] = ref["packet_evidence_id"]
        require(digest(row) == ref["digest"], "clinical_deferred_source_changed")
        rows.append(row)
    if "evidence_packet" in value:
        value["evidence_packet"] = rows
    for field in ("candidate_items", "dependency_context", "accepted_items"):
        if field in value:
            result = []
            for ref in value[field]:
                key = ref["$object"]
                row = deferred["objects"].get(key)
                require(
                    row is not None and digest(row) == key,
                    "clinical_deferred_context_changed",
                )
                result.append(deepcopy(row))
            value[field] = result
    require(digest(value) == task["input_digest"], "clinical_deferred_input_changed")
    return value


def deferred_work(result, packets, rejected_candidates=(), followups=()):
    """Keep tasks and unresolved candidates even when no more paid work is admitted."""
    tasks, objects = [], {}
    seen = set()
    for stage in (
        result["execution"]["stages"]
        + result["execution"]["input_reconciliation"]["stages"]
    ):
        unresolved = stage.get("unresolved_obligation_ids", [])
        if stage["status"] == "completed" or stage["input_digest"] in seen:
            continue
        seen.add(stage["input_digest"])
        packet = packets.get(stage["input_digest"])
        tasks.append(
            {
                "work_id": "work:"
                + digest([stage["task_id"], stage["input_digest"]]).split(":")[1][:32],
                "kind": (
                    "scientific_gap" if stage["status"] == "partial" else "stage_task"
                ),
                "task_id": stage["task_id"],
                "role": stage["role"],
                "status": stage["status"],
                "reason": stage["code"] or "clinical_scientific_obligation_unresolved",
                "unresolved_obligation_ids": deepcopy(unresolved),
                "input_digest": stage["input_digest"],
                "input_packet": freeze_packet(packet, objects) if packet else None,
                "requires_new_evidence": stage["status"] == "partial",
                "retry_authorized": False,
            }
        )
    for item in result["case_assessments"] + result["hypothesis_results"]:
        if item["review_status"] == "unreviewed":
            key = digest(item)
            objects.setdefault(key, deepcopy(item))
            tasks.append(
                {
                    "work_id": "candidate:"
                    + digest(item["item_id"]).split(":")[1][:32],
                    "kind": "candidate_review",
                    "item_id": item["item_id"],
                    "role": "evidence_critic",
                    "reason": item.get("review_reason")
                    or "clinical_critic_item_not_reviewed",
                    "candidate_ref": key,
                    "unresolved_dependency_ids": deepcopy(
                        item.get("unresolved_dependency_ids", [])
                    ),
                    "retry_authorized": False,
                }
            )
    for rejected in rejected_candidates:
        key = digest(rejected["candidate"])
        objects.setdefault(key, deepcopy(rejected["candidate"]))
        tasks.append(
            {
                "work_id": "rejected:"
                + digest([rejected["stage_id"], key]).split(":")[1][:32],
                "kind": "candidate_reconciliation",
                "role": rejected["role"],
                "stage_id": rejected["stage_id"],
                "reason": rejected["reason"],
                "candidate_ref": key,
                "assigned_evidence_ids": rejected["assigned_evidence_ids"],
                "input_digest": rejected["input_digest"],
                "retry_authorized": False,
            }
        )
    followup_keys = set()
    for followup in followups:
        key = digest(followup)
        if key in followup_keys:
            continue
        followup_keys.add(key)
        tasks.append(
            {
                "work_id": "followup:" + key.split(":")[1][:32],
                "kind": "followup_request",
                "role": followup["role"],
                "reason": "clinical_scoped_followup_deferred",
                "question": followup["question"],
                "affected_item_ids": deepcopy(followup["affected_item_ids"]),
                "retry_authorized": False,
            }
        )
    return {
        "schema_version": "clinical_deferred_work.v1",
        "assessment_id": result["assessment_id"],
        "source_ledger_digest": digest(result["evidence"]),
        "tasks": tasks,
        "objects": objects,
        "storage": "canonical_assessment_artifact",
        "publication_confirmed": False,
        "resume_policy": "Explicit later selection, fresh governed input/admission and current policy required; this data grants no execution authority.",
        "automatic_replay": False,
    }


def execution_disposition(result):
    """Separate paid invocation, scientific coverage and retained future work."""
    stages = result["execution"]["stages"]
    return {
        "invocations_returned": sum(
            row["status"] in {"completed", "partial"} for row in stages
        ),
        "scientifically_unresolved_tasks": sum(
            row["status"] == "partial" for row in stages
        ),
        "deferred_or_failed_tasks": sum(
            row["status"] in {"deferred", "failed"} for row in stages
        ),
        "candidate_count": len(result["case_assessments"])
        + len(result["hypothesis_results"]),
        "reviewed_candidates": sum(
            row["review_status"] == "automated_reviewed"
            for row in result["case_assessments"] + result["hypothesis_results"]
        ),
        "deferred_work_count": len(result["deferred_work"]["tasks"]),
        "scientific_accuracy_certified": False,
    }
