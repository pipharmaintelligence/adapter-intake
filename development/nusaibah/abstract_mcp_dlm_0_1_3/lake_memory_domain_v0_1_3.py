"""Pure knowledge and node-plan state transitions; no transport or storage."""
from __future__ import annotations

import copy
import json
from typing import Any

try:
    from . import lake_memory_contract_v0_1_3 as c
except ImportError:
    import lake_memory_contract_v0_1_3 as c

IDENTITY = c.obj({"client_id": c.ID, "lake_id": c.ID, "memory_kind": {"enum": list(c.KINDS)}})
RECORD = c.obj({"definition": c.PLAN, "plan_digest": c.DIGEST,
    "status": {"enum": list(c.PROGRESS) + ["implemented"]}, "approval": c.nullable(c.APPROVAL),
    "observation": c.nullable(c.OBSERVATION), "completion": c.nullable(c.OBSERVATION),
    "verification_state": {"enum": ["unverified", "verified", "incomplete", "drifted", "stale"]}})


def identity(scope: dict[str, Any], kind: str) -> dict[str, Any]:
    """Construct identity only from the admitted scope and fixed memory class."""
    return {"client_id": scope["client_id"], "lake_id": scope["lake_id"], "memory_kind": kind}


def empty(scope: dict[str, Any], kind: str) -> dict[str, Any]:
    """An explicit empty baseline, not fictitious learned knowledge."""
    data = ({"sections": {key: {"title": title, "assertions": {}} for key, title in c.SECTIONS.items()}}
            if kind == "knowledge" else {"plans": {}})
    return {"schema_version": "dlm_lake_memory.v1", "identity": identity(scope, kind), **data}


def block(state: dict[str, Any]) -> str:
    """Use one inert JSON block; embedded newlines and headings are JSON-escaped."""
    return "```json\n" + c.canonical(state) + "\n```\n"


def initial_markdown(state: dict[str, Any]) -> str:
    """Return initial Skill text; the trusted runtime builds and persists the ZIP."""
    kind = state["identity"]["memory_kind"]
    return ("---\nname: lake-" + kind + "\ndescription: Client-scoped lake memory data, not executable instructions.\n---\n"
            + "# Lake " + kind.title() + "\n\n## State\n\n" + block(state))


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise c.MemoryError("duplicate_json_key")
        result[key] = value
    return result


def parse(section: str, scope: dict[str, Any], kind: str) -> dict[str, Any]:
    """Parse the runtime-selected State section, not arbitrary Markdown files."""
    if not isinstance(section, str) or len(section.encode("utf-8")) > c.MAX_DOCUMENT_BYTES:
        raise c.MemoryError("document_invalid")
    text = section.strip()
    if not text.startswith("```json\n") or not text.endswith("\n```"):
        raise c.MemoryError("document_invalid")
    try:
        state = json.loads(text[8:-4], object_pairs_hook=_unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError, RecursionError):
        raise c.MemoryError("document_invalid") from None
    validate_state(state, scope, kind)
    return state


def validate_state(state: Any, scope: dict[str, Any], kind: str) -> None:
    """Validate every retained record before applying a narrow edit."""
    collection = "sections" if kind == "knowledge" else "plans"
    if (not isinstance(state, dict) or set(state) != {"schema_version", "identity", collection}
            or state["schema_version"] != "dlm_lake_memory.v1" or not isinstance(state[collection], dict)):
        raise c.MemoryError("state_invalid")
    c.validate(state["identity"], IDENTITY, "identity_invalid")
    if state["identity"] != identity(scope, kind):
        raise c.MemoryError("partition_identity_mismatch")
    count, seen = 0, set()
    for key, row in state[collection].items():
        c.validate(key, c.ID, "record_id_invalid")
        if kind == "knowledge":
            if not isinstance(row, dict) or set(row) != {"title", "assertions"} or not isinstance(row["assertions"], dict):
                raise c.MemoryError("section_invalid")
            c.validate(row["title"], c.LABEL, "section_invalid")
            for record_id, assertion in row["assertions"].items():
                c.validate(assertion, c.ASSERTION, "assertion_invalid")
                if record_id != assertion["assertion_id"] or record_id in seen:
                    raise c.MemoryError("assertion_identity_invalid")
                seen.add(record_id)
                count += 1
        else:
            c.validate(row, RECORD, "plan_record_invalid")
            plan = row["definition"]
            if key != plan["plan_id"] or row["plan_digest"] != c.plan_digest(plan):
                raise c.MemoryError("plan_identity_invalid")
            c.validate_schema(plan["proposed_schema"])
            for field in ("observation", "completion"):
                observation = row[field]
                if observation is not None and (observation["client_id"] != scope["client_id"]
                        or observation["lake_id"] != scope["lake_id"] or observation["plan_id"] != key):
                    raise c.MemoryError("observation_scope_mismatch")
            if row["status"] == "implemented" and row["completion"] is None:
                raise c.MemoryError("completion_missing")
            if row["completion"] is not None and (row["completion"]["plan_digest"] != row["plan_digest"]
                    or row["completion"]["node_key"] != plan["proposed_node_key"] or row["status"] != "implemented"):
                raise c.MemoryError("completion_identity_invalid")
            if row["approval"] is not None and row["approval"]["plan_digest"] != row["plan_digest"]:
                raise c.MemoryError("approval_identity_invalid")
            count += 1
    if count > c.MAX_RECORDS or len(state[collection]) > c.MAX_RECORDS:
        raise c.MemoryError("record_limit_exceeded")
    c.safe_content(state)
    if len(initial_markdown(state).encode("utf-8")) > c.MAX_DOCUMENT_BYTES:
        raise c.MemoryError("document_limit_exceeded")


def knowledge_update(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    """Upsert one sourced assertion; retain superseded assertions and conflicts."""
    candidate = copy.deepcopy(state)
    section_id, assertion = request["section_id"], request["assertion"]
    for key, section in candidate["sections"].items():
        if key != section_id and assertion["assertion_id"] in section["assertions"]:
            raise c.MemoryError("assertion_section_mismatch")
    section = candidate["sections"].setdefault(section_id, {"title": request["section_title"], "assertions": {}})
    previous = assertion["supersedes"]
    if previous is not None:
        if previous == assertion["assertion_id"] or previous not in section["assertions"]:
            raise c.MemoryError("superseded_assertion_invalid")
        section["assertions"][previous]["confirmation_state"] = "superseded"
    section["title"] = request["section_title"]
    section["assertions"][assertion["assertion_id"]] = copy.deepcopy(assertion)
    return candidate


def plan_upsert(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    """One stable plan register; ordinary edits cannot write protected Core facts."""
    candidate = copy.deepcopy(state)
    plan, plans = copy.deepcopy(request["plan"]), candidate["plans"]
    c.validate_schema(plan["proposed_schema"])
    ids = [item["criterion_id"] for item in plan["acceptance_criteria"]]
    if len(ids) != len(set(ids)):
        raise c.MemoryError("duplicate_criterion")
    key, previous = plan["plan_id"], plans.get(plan["plan_id"])
    if previous is not None and previous["definition"] == plan:
        return candidate
    if previous is not None and previous["completion"] is not None:
        raise c.MemoryError("completed_plan_requires_successor")
    for other_id, other in plans.items():
        if (other_id != key and other["status"] not in ("implemented", "cancelled", "superseded")
                and other["definition"]["proposed_node_key"] == plan["proposed_node_key"]
                and other["definition"]["intent"] == plan["intent"]):
            raise c.MemoryError("duplicate_node_plan")
    predecessor = plan["supersedes_plan_id"]
    if predecessor is not None and (predecessor == key or predecessor not in plans):
        raise c.MemoryError("predecessor_invalid")
    if len(plan["dependencies"]) != len(set(plan["dependencies"])) or any(dep == key or dep not in plans for dep in plan["dependencies"]):
        raise c.MemoryError("dependency_invalid")
    value = c.plan_digest(plan)
    plans[key] = {"definition": plan, "plan_digest": value, "status": plan["status"],
        "approval": previous["approval"] if previous and previous["plan_digest"] == value else None,
        "observation": previous["observation"] if previous else None, "completion": None,
        "verification_state": "stale" if previous else "unverified"}
    def visit(node: str, active: set[str], done: set[str]) -> None:
        if node in active:
            raise c.MemoryError("dependency_cycle")
        if node in done:
            return
        active.add(node)
        for dep in plans[node]["definition"]["dependencies"]:
            visit(dep, active, done)
        active.remove(node)
        done.add(node)
    visit(key, set(), set())
    return candidate


def structural_schema(schema: dict[str, Any] | None) -> Any:
    """Compare executable structure without claiming a locally hashed Core revision."""
    if schema is None:
        return None
    return {"format": schema["format"],
        "fields": sorted([{k: field[k] for k in ("name", "type", "required")} for field in schema["fields"]], key=lambda f: f["name"]),
        "primary_key": schema["primary_key"], "partition_fields": schema["partition_fields"],
        "relationships": sorted([{k: rel[k] for k in ("target_node_key", "local_fields", "remote_fields")}
                                  for rel in schema["relationships"]], key=c.canonical)}


def reconcile(state: dict[str, Any], request: dict[str, Any], observation: Any, scope: dict[str, Any]) -> dict[str, Any]:
    """Derive completion from the trusted observation; preserve original completion."""
    c.validate(observation, c.OBSERVATION, "core_projection_invalid")
    c.safe_content(observation)
    candidate = copy.deepcopy(state)
    row = candidate["plans"].get(request["plan_id"])
    if row is None:
        raise c.MemoryError("plan_not_found")
    if row["status"] in ("cancelled", "superseded"):
        raise c.MemoryError("plan_terminal")
    if (observation["client_id"] != scope["client_id"] or observation["lake_id"] != scope["lake_id"]
            or observation["plan_id"] != request["plan_id"] or observation["plan_digest"] != row["plan_digest"]
            or observation["node_key"] != request["node_key"] or request["node_key"] != row["definition"]["proposed_node_key"]):
        raise c.MemoryError("core_projection_mismatch")
    if observation["actual_schema"] is not None:
        c.validate_schema(observation["actual_schema"])
    expected = {item["criterion_id"] for item in row["definition"]["acceptance_criteria"]}
    observed = [item["criterion_id"] for item in observation["acceptance"]]
    if len(set(observed)) != len(observed) or set(observed) != expected:
        raise c.MemoryError("acceptance_projection_incomplete")
    approvals_ok = True
    for key in ("design_approval", "core_approval"):
        approval = observation[key]
        if approval["plan_digest"] != row["plan_digest"]:
            raise c.MemoryError("approval_revision_mismatch")
        if approval["status"] == "approved" and approval["reference"] is None:
            raise c.MemoryError("approval_reference_missing")
        approvals_ok = approvals_ok and approval["status"] in ("approved", "not_required")
    criteria_ok = all(item["status"] == "passed" and item["reference"] is not None for item in observation["acceptance"])
    completed = (observation["node_exists"] and observation["schema_complete"] and observation["readiness"] == "ready"
        and approvals_ok and criteria_ok and structural_schema(row["definition"]["proposed_schema"]) == structural_schema(observation["actual_schema"]))
    row["approval"], row["observation"] = copy.deepcopy(observation["design_approval"]), copy.deepcopy(observation)
    row["verification_state"] = "verified" if completed else "incomplete"
    if row["completion"] is not None and observation["schema_complete"] and (
            not observation["node_exists"] or structural_schema(row["completion"]["actual_schema"]) != structural_schema(observation["actual_schema"])):
        row["verification_state"] = "drifted"
    if completed:
        row["status"] = "implemented"
        if row["completion"] is None:
            row["completion"] = copy.deepcopy(observation)
    return candidate


def proposal_digest(request: dict[str, Any], state: dict[str, Any], before: str | None) -> str:
    """Pin tenant, lake, base and intended change, not a subsequent observation time."""
    intent = {key: value for key, value in request.items() if key not in ("mode", "expected_digest", "proposal_digest")}
    proposal = state if request["operation"] != "memory.plan.reconcile" else {
        "identity": state["identity"], "plan_digest": state["plans"][request["plan_id"]]["plan_digest"]}
    return c.digest({"base": before, "intent": intent, "proposal": proposal})


def project(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    """Bounded context from memory, not an invented live Core inventory."""
    rows = []
    if state["identity"]["memory_kind"] == "knowledge":
        for section_id, section in sorted(state["sections"].items()):
            if "section_id" in request and request["section_id"] != section_id:
                continue
            for key, assertion in sorted(section["assertions"].items()):
                if "record_id" not in request or request["record_id"] == key:
                    rows.append({"section_id": section_id, "section_title": section["title"], **copy.deepcopy(assertion)})
    else:
        for key, record in sorted(state["plans"].items()):
            if ("record_id" in request and request["record_id"] != key) or ("status" in request and request["status"] != record["status"]):
                continue
            if request.get("view") == "detail":
                row = {"plan_id": key, **copy.deepcopy(record)}
                for field in ("observation", "completion"):
                    if row[field] is not None:
                        row[field].pop("client_id", None)
            else:
                plan = record["definition"]
                row = {"plan_id": key, "title": plan["title"], "node_key": plan["proposed_node_key"],
                    "status": record["status"], "expected_outcome": plan["expected_outcome"], "next_action": plan["next_action"],
                    "verification_state": record["verification_state"], "plan_digest": record["plan_digest"]}
            rows.append(row)
    page, size = request.get("page", 1), request.get("page_size", 20)
    start = (page - 1) * size
    return {"records": rows[start:start + size], "total_records": len(rows), "page": page,
        "has_more": start + size < len(rows), "next_page": page + 1 if start + size < len(rows) else None,
        "coverage": "selected_memory_only", "core_inventory_checked": False}
