"""Product-scoped paragraph selection and reviewed change plans; no persistence.

The runtime may hydrate a complete Skill package. Only exact case paragraphs are
projected to Agents; neither full-document reads nor whole-section rewrites are
used here. SDK changesets are compiled separately, never applied by this release.
"""
from __future__ import annotations
from copy import deepcopy
from typing import Any
import re
if __package__:
    from .contracts_v0_1_3 import ContractError, DIGEST_RE, digest, identifier, identifiers, object_fields, require, text, text_digest
else:
    from contracts_v0_1_3 import ContractError, DIGEST_RE, digest, identifier, identifiers, object_fields, require, text, text_digest

MAX_PARAGRAPHS = 8
MAX_PARAGRAPH_CHARS = 3000
MAX_CONTEXT_CHARS = 12000
EDIT_OPERATIONS = {"keep", "enrich_paragraph", "replace_paragraph", "append_paragraph", "add_section"}


def case_path(request: dict) -> list[str]:
    """Address one indication/trial/regimen inside the product, never a class."""
    scope = request["context"].get("case_scope")
    require(isinstance(scope, dict), "clinical_product_memory_scope_required")
    # Event scopes are distinct from trial identities; missing data is not a trial ID.
    trial_section = ("Trial " + scope["trial_id"] if scope["trial_id"] is not None
                     else "Event " + scope["event_id"] + " trial unreported")
    regimen_section = ("Regimen " + scope["regimen_id"] if scope["regimen_id"] is not None
                       else "Regimen unreported")
    return ["Indication " + scope["indication_id"], trial_section, regimen_section, "Assessment"]


def _parts(path: Any) -> list[str]:
    """Use the SDK's structured heading identity rather than parsing display text."""
    values = list(path.parts)
    require(all(isinstance(x, str) and x for x in values), "clinical_memory_section_invalid")
    return values


def read_paragraph_slice(handle: Any, section_path: list[str], *, priority_terms: tuple[str, ...] = ()) -> dict:
    """Project complete paragraphs and compact omission metadata from one section."""
    require(handle.provenance().mutable is False, "clinical_readonly_memory_required")
    content_digest, package_digest = handle.content_digest(), handle.provenance().package_digest
    for value in (content_digest, package_digest):
        require(isinstance(value, str) and DIGEST_RE.fullmatch(value) is not None,
                "clinical_memory_identity_invalid")
    toc = handle.table_of_contents()
    paths = [_parts(row.path) for row in toc]
    for size in range(1, len(section_path) + 1):
        require(paths.count(section_path[:size]) <= 1, "clinical_memory_section_ambiguous")
    exists = section_path in paths
    paragraphs = handle.paragraphs(section_path) if exists else ()
    selected, omitted, all_digests = [], [], set()
    used = 0
    # Rank the prompt selection only. Document order and SDK block identities stay unchanged.
    def rank(block: Any) -> tuple[int, int]:
        words = set(re.findall(r"[a-z0-9_:-]+", block.text.casefold()))
        score = sum(term.casefold() in words for term in priority_terms)
        return (-score, -block.ref.ordinal_hint)
    for block in sorted(paragraphs, key=rank):
        require(block.kind == "paragraph" and _parts(block.ref.section) == section_path,
                "clinical_memory_block_scope_invalid")
        require(block.ref.digest == text_digest(block.text), "clinical_memory_block_digest_mismatch")
        ref = block.ref
        projected_ref = {"section": section_path, "kind": "paragraph", "ordinal_hint": ref.ordinal_hint,
                         "digest": ref.digest, "previous_digest": ref.previous_digest,
                         "next_digest": ref.next_digest}
        pid = "paragraph:" + digest(projected_ref).split(":")[1][:24]
        all_digests.add(text_digest(block.text.strip()))
        if len(selected) >= MAX_PARAGRAPHS or len(block.text) > MAX_PARAGRAPH_CHARS or used + len(block.text) > MAX_CONTEXT_CHARS:
            omitted.append({"paragraph_id": pid, "digest": ref.digest, "characters": len(block.text)})
            continue
        selected.append({"paragraph_id": pid, "block_ref": projected_ref,
                         "text": block.text, "digest": ref.digest})
        used += len(block.text)
    return {"content_digest": content_digest, "package_digest": package_digest,
        "section_path": section_path, "section_exists": exists,
        "existing_parent_paths": [section_path[:i] for i in range(1, len(section_path)) if section_path[:i] in paths],
        "paragraphs": selected, "selected_characters": used, "total_paragraphs": len(paragraphs),
        "omitted_count": len(omitted), "omitted_preview": omitted[:8], "scope_complete": not omitted,
        "origin": "prior_memory_not_fresh_evidence", "_known_text_digests": all_digests}


def read_product_memory(inputs: Any, request: dict) -> dict:
    """Resolve product_id first; indication and trial are internal document scopes."""
    product_id = request["context"]["subject"]["product_id"]
    base = {"status": "not_requested", "product_id": product_id, "paragraphs": [],
            "content_digest": None, "package_digest": None, "section_path": [],
            "section_exists": False, "existing_parent_paths": [], "scope_complete": True,
            "origin": "prior_memory_not_fresh_evidence", "_known_text_digests": set()}
    if request["memory_mode"] == "off" or request["analysis_mode"] == "cohort_pattern":
        return base
    path = case_path(request)
    require(callable(getattr(inputs, "dynamic_skill", None)), "clinical_dynamic_skill_unavailable")
    try:
        handle = inputs.dynamic_skill("product_memory", variables={"product_id": product_id})
    except Exception as exc:
        if getattr(exc, "code", None) == "dynamic_skill_not_initialized":
            return {**base, "status": "not_initialized", "section_path": path}
        raise ContractError("clinical_product_memory_read_blocked") from None
    # A legacy unindexed product document is not an empty case. Migrate it explicitly.
    if ["Product memory v1"] not in [_parts(row.path) for row in handle.table_of_contents()]:
        return {**base, "status": "requires_index_migration", "section_path": path, "scope_complete": False}
    query_words = re.findall(r"[a-z0-9_:-]+", " ".join(x["statement"] for x in request["context"]["source_assertions"]).casefold())
    stop_words = {"this", "that", "with", "from", "there", "which", "would", "could", "should", "about"}
    terms = tuple(request["event_ids"]) + tuple(dict.fromkeys(x for x in query_words if len(x) > 4 and x not in stop_words))[:16]
    return {**base, **read_paragraph_slice(handle, path, priority_terms=terms), "status": "read"}


def memory_projection(snapshot: dict) -> dict:
    """Exclude private local deduplication state and expose only bounded content."""
    return deepcopy({key: value for key, value in snapshot.items() if not key.startswith("_")})


def editor_contract() -> dict:
    """Return the closed edit-item contract consumed by the Gemini role."""
    return {"required_fields": ["edit_id", "operation", "target_paragraph_id", "before_digest",
        "section_path", "new_text", "supporting_item_ids", "rationale"],
        "operations": sorted(EDIT_OPERATIONS), "max_items": 8,
        "new_text_max_chars": MAX_PARAGRAPH_CHARS,
        "rules": ["Return delta operations, not the complete Skill.",
                  "Change only the supplied product and exact section_path.",
                  "Every replacement must target a supplied complete paragraph and its exact digest.",
                  "Use keep for unchanged knowledge. Preserve previous valid facts and qualifications."]}


def validate_edit_candidates(rows: Any, snapshot: dict, accepted_items: list[dict]) -> list[dict]:
    """Require exact scoped targets and supported inputs before semantic review."""
    require(isinstance(rows, list) and len(rows) <= 8, "clinical_memory_edits_invalid")
    selected = {p["paragraph_id"]: p for p in snapshot["paragraphs"]}
    accepted = {x["item_id"] for x in accepted_items if x["accepted"]}
    seen, touched, candidates = set(), set(), []
    for raw in rows:
        item = object_fields(raw, set(editor_contract()["required_fields"]))
        eid = identifier(item["edit_id"])
        require(eid not in seen, "clinical_memory_edit_duplicate")
        seen.add(eid)
        op = item["operation"]
        require(isinstance(op, str) and op in EDIT_OPERATIONS, "clinical_memory_operation_invalid")
        require(item["section_path"] == snapshot["section_path"], "clinical_memory_edit_cross_scope")
        refs = identifiers(item["supporting_item_ids"], allow_empty=op == "keep")
        require(set(refs) <= accepted, "clinical_memory_unaccepted_evidence")
        text(item["rationale"], maximum=1500)
        pid = item["target_paragraph_id"]
        if op in {"keep", "enrich_paragraph", "replace_paragraph"}:
            require(isinstance(pid, str) and pid in selected, "clinical_memory_unread_target")
            require(pid not in touched, "clinical_memory_target_repeated")
            touched.add(pid)
            require(item["before_digest"] == selected[pid]["digest"], "clinical_memory_target_stale")
        else:
            require(pid is None and item["before_digest"] is None, "clinical_memory_append_target_invalid")
            require(snapshot["section_exists"] == (op == "append_paragraph"), "clinical_memory_section_operation_invalid")
        if op == "keep":
            require(item["new_text"] is None, "clinical_memory_keep_has_text")
        else:
            paragraph = text(item["new_text"], maximum=MAX_PARAGRAPH_CHARS)
            require("\n" not in paragraph and "\r" not in paragraph and not paragraph.lstrip().startswith(("#", "```", "<!--")),
                    "clinical_memory_single_paragraph_required")
        candidate = deepcopy(item)
        candidate["block_ref"] = selected[pid]["block_ref"] if pid is not None else None
        candidate["old_text"] = selected[pid]["text"] if pid is not None else None
        candidates.append(candidate)
    return candidates


def review_edit_plan(candidates: list[dict], verdicts: Any, snapshot: dict, request: dict) -> dict:
    """Keep science, edit review, write intent and write receipt as different states."""
    base = {"status": "no_change", "write_attempted": False, "product_id": snapshot["product_id"],
        "section_path": snapshot["section_path"], "before_content_digest": snapshot["content_digest"],
        "before_package_digest": snapshot["package_digest"], "operations": [], "withheld_edits": [],
        "initialization_required": snapshot["status"] == "not_initialized", "readback_verified": False,
        "change_id": None, "scope_complete": snapshot["scope_complete"],
        "event_ids": request["event_ids"], "input_revision_digest": digest(request["context"]),
        "execution_receipt": None}
    if snapshot["status"] == "not_requested":
        return {**base, "status": "not_requested"}
    if snapshot["status"] == "requires_index_migration":
        return {**base, "status": "deferred", "reason": "product_memory_index_migration_required"}
    if not candidates:
        base["initialization_required"] = False
        return base
    require(verdicts is None or isinstance(verdicts, list), "clinical_memory_review_invalid")
    mapped, assigned = {}, {item["edit_id"] for item in candidates}
    for raw in verdicts or []:
        row = object_fields(raw, {"edit_id", "accepted", "scope_preserved", "evidence_supported",
                                  "prior_content_preserved", "rationale"})
        require(row["edit_id"] in assigned and row["edit_id"] not in mapped, "clinical_memory_review_identity_invalid")
        for field in ("accepted", "scope_preserved", "evidence_supported", "prior_content_preserved"):
            require(type(row[field]) is bool, "clinical_memory_review_boolean_invalid")
        text(row["rationale"], maximum=2000)
        mapped[row["edit_id"]] = row
    seen_text = set(snapshot["_known_text_digests"])
    for item in candidates:
        decision = mapped.get(item["edit_id"])
        if decision is None or not all(decision[k] for k in ("accepted", "scope_preserved", "evidence_supported", "prior_content_preserved")):
            base["withheld_edits"].append({"edit_id": item["edit_id"], "reason": "memory_edit_not_fully_reviewed"})
            continue
        if item["operation"] == "keep":
            continue
        key = text_digest(item["new_text"].strip())
        if key in seen_text:
            continue
        seen_text.add(key)
        base["operations"].append({**deepcopy(item), "review": deepcopy(decision)})
    base["status"] = "partial" if base["withheld_edits"] else "preview" if base["operations"] else "no_change"
    base["proposal_digest"] = digest({k: base[k] for k in ("product_id", "section_path", "before_content_digest",
        "before_package_digest", "input_revision_digest", "operations")})
    return base


def compile_product_changeset(handle: Any, plan: dict) -> Any:
    """Compile a reviewed plan with existing SDK operations; never call apply().

    This helper is not invoked in the current preview execution path. A mutable
    handle, retained-analysis barrier and live runtime proof are prerequisites.
    """
    require(plan["status"] == "preview" and not plan["initialization_required"], "clinical_memory_plan_not_compilable")
    # Detect accidental plan edits after critic review. This is an integrity
    # check, not a signature or a replacement for runtime permission to write.
    expected = digest({k: plan[k] for k in ("product_id", "section_path", "before_content_digest",
        "before_package_digest", "input_revision_digest", "operations")})
    require(plan.get("proposal_digest") == expected, "clinical_memory_proposal_changed")
    require(handle.provenance().mutable is True, "clinical_mutable_memory_required")
    require(handle.content_digest() == plan["before_content_digest"] and
            handle.provenance().package_digest == plan["before_package_digest"], "clinical_memory_baseline_stale")
    changes = handle.new_changeset()
    created = set()
    for item in plan["operations"]:
        require(item["operation"] in EDIT_OPERATIONS - {"keep"}, "clinical_memory_operation_invalid")
        require(all(item.get("review", {}).get(k) is True for k in
                    ("accepted", "scope_preserved", "evidence_supported", "prior_content_preserved")),
                "clinical_memory_edit_not_reviewed")
        path = item["section_path"]
        require(path == plan["section_path"], "clinical_memory_edit_cross_scope")
        if item["operation"] == "add_section":
            for i in range(1, len(path) + 1):
                prefix = tuple(path[:i])
                if prefix not in created and not handle.has_section(prefix):
                    changes.add_section(prefix, "")
                    created.add(prefix)
            changes.append_paragraph(path, item["new_text"])
        elif item["operation"] == "append_paragraph":
            changes.append_paragraph(path, item["new_text"])
        else:
            candidates = [p for p in handle.paragraphs(path) if p.ref.digest == item["before_digest"]
                          and p.ref.ordinal_hint == item["block_ref"]["ordinal_hint"]]
            require(len(candidates) == 1, "clinical_memory_target_stale")
            changes.replace_paragraph(candidates[0].ref, item["new_text"])
    return changes
