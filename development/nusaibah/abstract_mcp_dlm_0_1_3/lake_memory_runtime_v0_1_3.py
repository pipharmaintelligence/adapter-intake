"""Use existing RuntimeInputs Skill APIs; authority and persistence stay server-owned.

The scope projection and implementation-observation role are explicit pending
integration contracts. This candidate is intentionally not registered/admitted.
"""
from __future__ import annotations

import re
from typing import Any

try:
    from . import lake_memory_contract_v0_1_3 as c, lake_memory_domain_v0_1_3 as d
except ImportError:
    import lake_memory_contract_v0_1_3 as c
    import lake_memory_domain_v0_1_3 as d


def _load(inputs: Any, scope: dict[str, Any], kind: str, mutable: bool = False) -> tuple[Any, dict[str, Any], str | None]:
    role = "lake_" + kind + ("_update" if mutable else "")
    resolver = getattr(inputs, "dynamic_skill", None)
    if not callable(resolver):
        raise c.MemoryError("skill_bridge_unavailable")
    try:
        handle = resolver(role)  # Prebound trusted selector; NEVER public variables.
    except Exception as error:
        if getattr(error, "code", None) == "dynamic_skill_not_initialized":
            return None, d.empty(scope, kind), None
        raise c.MemoryError("read_failed") from None
    try:
        proof = handle.provenance()
        expected = scope["write_selector_digest" if mutable else "read_selector_digest"]
        if proof.kind != "dynamic" or proof.role != role or proof.mutable is not mutable or proof.selector_digest != expected:
            raise c.MemoryError("role_scope_mismatch")
        c.validate(proof.package_digest, c.DIGEST, "package_identity_missing")
        before = handle.content_digest()
        c.validate(before, c.DIGEST, "digest_invalid")
        if c.text_digest(handle.read()) != before:
            raise c.MemoryError("digest_mismatch")
        return handle, d.parse(handle.section_text("State"), scope, kind), before
    except c.MemoryError:
        raise
    except Exception:
        raise c.MemoryError("skill_view_invalid") from None


def _receipt(receipt: Any) -> dict[str, Any]:
    result = {"change_id": receipt.change_id, "changed_at": receipt.changed_at.isoformat(),
              "before_digest": receipt.before_content_digest, "after_digest": receipt.after_content_digest}
    c.validate(result["change_id"], c.ID, "receipt_invalid")
    c.validate(result["changed_at"], c.TIME, "receipt_invalid")
    for key in ("before_digest", "after_digest"):
        c.validate(result[key], c.DIGEST, "receipt_invalid")
    return result


def _history(handle: Any, scope: dict[str, Any], kind: str, request: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if not scope["history_allowed"] or handle.provenance().history_scope != "committed_partition_mutations":
        return "history_unavailable", {"records": [], "has_more": None, "coverage": "unavailable"}
    try:
        history = handle.history(limit=request.get("page_size", 20), before_change_id=request.get("before_change_id"))
        snapshots = {s.snapshot_id: d.parse(s.document.section_text("State"), scope, kind) for s in history.snapshots}
        receipts = sorted(history.receipts, key=lambda item: (item.changed_at, item.change_id), reverse=True)
        if len(receipts) > request.get("page_size", 20):
            raise c.MemoryError("history_limit_exceeded")
        rows = []
        for receipt in receipts:
            row = _receipt(receipt)
            if "record_id" in request:
                query = {"view": "detail", "record_id": request["record_id"], "page_size": 1}
                before = d.project(snapshots[receipt.before_snapshot_id], query)["records"]
                after = d.project(snapshots[receipt.after_snapshot_id], query)["records"]
                if before == after:
                    continue
                row.update(before_record=before[0] if before else None, after_record=after[0] if after else None)
            rows.append(row)
        return "completed", {"records": rows, "has_more": None, "coverage": "bounded_history_segment",
                              "next_before_change_id": receipts[-1].change_id if receipts else None}
    except c.MemoryError:
        raise
    except Exception:
        raise c.MemoryError("history_failed") from None


def _observe(inputs: Any, request: dict[str, Any], state: dict[str, Any]) -> Any:
    row = state["plans"].get(request["plan_id"])
    if row is None:
        raise c.MemoryError("plan_not_found")
    invoker = getattr(inputs, "invoke_tool", None)
    if not callable(invoker):
        raise c.MemoryError("core_observation_unavailable")
    try:
        result = invoker("dlm_node_implementation", input={"lake_id": request["lake_id"], "node_key": request["node_key"],
            "plan_id": request["plan_id"], "plan_digest": row["plan_digest"],
            "acceptance_criteria": row["definition"]["acceptance_criteria"]}, on_error="raise")
        proof = result["provenance"]
        if (result["status"] != "completed" or result["operation"] != "invoke"
                or result["tool_handle"] != "@tool.abstract_mcp_dlm" or result["tool_server_ref"] != "mcp.abstract_dlm"
                or result["capability_ref"] != "dlm.nodes.implementation" or not isinstance(result["records"], list)
                or len(result["records"]) != 1 or proof["role"] != "dlm_node_implementation"
                or proof["runtime_mcp_tool"] is not True or proof["cache_hit"] is not False
                or type(proof["record_count"]) is not int or proof["record_count"] != 1
                or type(proof["duration_ms"]) is not int or proof["duration_ms"] < 0
                or re.fullmatch(r"mti_(?:[a-f0-9]{32}|[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})", proof["invocation_id"]) is None):
            raise c.MemoryError("core_projection_invalid")
        return result["records"][0]
    except c.MemoryError:
        raise
    except Exception:
        raise c.MemoryError("core_observation_failed") from None


def _readback(inputs: Any, scope: dict[str, Any], kind: str, candidate: dict[str, Any], after: str, change_id: str | None) -> tuple[bool, bool]:
    try:
        _, fresh, current = _load(inputs, scope, kind)
        if fresh != candidate or current != after:
            return False, False
    except Exception:
        return False, False
    history_verified = False
    if change_id is not None and scope["history_allowed"]:
        try:
            writer, _, _ = _load(inputs, scope, kind, True)
            history = writer.history(limit=1)
            for snapshot in history.snapshots:
                d.parse(snapshot.document.section_text("State"), scope, kind)
            history_verified = any(item.change_id == change_id and item.after_content_digest == after for item in history.receipts)
        except Exception:
            history_verified = False
    return True, history_verified


def _commit(inputs: Any, scope: dict[str, Any], kind: str, candidate: dict[str, Any], before: str | None) -> tuple[str, dict[str, Any]]:
    writer, _, current = _load(inputs, scope, kind, True)
    if current != before:
        raise c.MemoryError("stale_write")
    unknown = {"readback_verified": False, "history_verified": False, "reconciliation_required": True}
    if writer is None:
        if not scope["allow_initialize"]:
            raise c.MemoryError("initialization_not_admitted")
        initializer = getattr(inputs, "initialize_dynamic_skill", None)
        if not callable(initializer):
            raise c.MemoryError("initialization_unavailable")
        text = d.initial_markdown(candidate)
        after = c.text_digest(text)
        try:
            receipt = initializer("lake_" + kind + "_update", markdown=text)
        except Exception:
            return "mutation_outcome_unknown", unknown
        if not isinstance(receipt, dict) or receipt.get("status") not in ("initialized", "initialized_readback_unverified") or receipt.get("after_digest") != after:
            return "mutation_outcome_unknown", unknown
        verified, _ = _readback(inputs, scope, kind, candidate, after, None)
        return "initialized" if verified else "committed_readback_unverified", {
            "receipt": {"change_id": None, "before_digest": None, "after_digest": after, "mutation_kind": "initialization"},
            "readback_verified": verified, "history_verified": False, "reconciliation_required": not verified,
            "history_note": "First upload is not a committed update receipt."}
    changes = writer.new_changeset().replace_section("State", d.block(candidate))
    preview = writer.preview(changes)
    if d.parse(preview.document.section_text("State"), scope, kind) != candidate:
        raise c.MemoryError("runtime_preview_mismatch")
    after = preview.diff.new_digest
    if c.text_digest(preview.source) != after:
        raise c.MemoryError("runtime_preview_mismatch")
    try:
        receipt = _receipt(writer.apply(changes, expected_digest=before))
    except Exception as error:
        if getattr(error, "code", None) == "dynamic_skill_expected_digest_mismatch":
            raise c.MemoryError("stale_write") from None
        return "mutation_outcome_unknown", unknown
    if receipt["before_digest"] != before or receipt["after_digest"] != after:
        return "mutation_outcome_unknown", unknown
    verified, history = _readback(inputs, scope, kind, candidate, after, receipt["change_id"])
    return "committed" if verified else "committed_readback_unverified", {
        "receipt": receipt, "readback_verified": verified, "history_verified": history,
        "reconciliation_required": not verified or not history}


def _response(request: dict[str, Any], kind: str, status: str, data: dict[str, Any]) -> dict[str, Any]:
    result = {"response_version": "1", "status": "success", "outputs": {"tool_results": {
        "schema_version": "dlm_lake_memory_result.v1", "operation": request["operation"], "status": status,
        "lake_id": request["lake_id"], "memory_kind": kind, "scope": "authenticated_client", "data": data}},
        "logs": [], "metrics": {"tool_result_count": 1}}
    c.safe_content(result)
    if len(c.canonical(result).encode("utf-8")) > c.MAX_RESULT_BYTES:
        raise c.MemoryError("response_limit_exceeded")
    return result


def invoke_memory(inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
    """One synchronous semantic call. No provider, network, output publication or retry."""
    if not isinstance(inputs, dict) or set(inputs) != {"tool_request"}:
        raise c.MemoryError("input_roles_invalid")
    request = c.request_contract(inputs["tool_request"])
    scope = c.trusted_scope(context, request)
    kind = c.memory_kind(request)
    reader, state, before = _load(inputs, scope, kind)
    if request["operation"] == "memory.context":
        if reader is None:
            return _response(request, kind, "not_initialized", {"current_digest": None, "records": [], "coverage": "not_initialized"})
        status, data = _history(reader, scope, kind, request) if request.get("view") == "history" else ("completed", d.project(state, request))
        return _response(request, kind, status, {"current_digest": before, **data})
    if "expected_digest" in request and request["expected_digest"] != before:
        raise c.MemoryError("stale_write")
    operation = request["operation"]
    if operation == "memory.knowledge.update":
        candidate = d.knowledge_update(state, request)
        record_id = request["assertion"]["assertion_id"]
    elif operation == "memory.plan.upsert":
        candidate = d.plan_upsert(state, request)
        record_id = request["plan"]["plan_id"]
    else:
        candidate = d.reconcile(state, request, _observe(inputs, request, state), scope)
        record_id = request["plan_id"]
    d.validate_state(candidate, scope, kind)
    proposal = d.proposal_digest(request, candidate, before)
    data = {"before_digest": before, "proposal_digest": proposal, "changed": candidate != state,
            "initialization_required": reader is None}
    if request.get("mode", "preview") != "apply":
        return _response(request, kind, "preview_ready", {**data,
            "preview": d.project(candidate, {"view": "detail", "record_id": record_id, "page_size": 1})})
    if request["proposal_digest"] != proposal:
        raise c.MemoryError("proposal_mismatch")
    if candidate == state:
        return _response(request, kind, "unchanged", {**data, "receipt": None, "readback_verified": True, "history_verified": False})
    _response(request, kind, "preview_ready", data)  # Budget check before a side effect.
    status, committed = _commit(inputs, scope, kind, candidate, before)
    return _response(request, kind, status, {**data, **committed})
