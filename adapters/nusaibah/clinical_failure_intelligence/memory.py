"""Read-only group snapshots and bounded learning proposals; preview never writes."""
from __future__ import annotations
import html
from typing import Any
if __package__:
    from .contracts import ContractError, DIGEST_RE, digest, require, text_digest
else:
    from contracts import ContractError, DIGEST_RE, digest, require, text_digest

FIXED_REF = "nusaibah.clinical-failure-methodology"
SECTION = "Lessons"


def read_methodology(inputs: Any) -> dict:
    """Consume an admitted Fixed Skill, not an arbitrary local file as authority."""
    require(callable(getattr(inputs, "skill", None)), "clinical_fixed_skill_unavailable")
    view = inputs.skill(FIXED_REF)
    sections = {name: view.section_text(name) for name in ("Evidence Rules", "Outcome Rules", "Learning Rules")}
    require(all(isinstance(v, str) and v.strip() for v in sections.values()), "clinical_methodology_invalid")
    return {"skill_ref": FIXED_REF, "version": "1.0.0", "sections": sections, "section_digest": digest(sections)}


def read_group_memory(inputs: Any, request: dict) -> dict:
    """Distinguish a genuinely absent partition from missing node or authority."""
    group_id = request["context"]["subject"]["pharmacological_group_id"]
    base = {"group_id": group_id, "text": "", "content_digest": None, "package_digest": None}
    if request["memory_mode"] == "off" or group_id is None or request["analysis_mode"] == "cohort_pattern":
        return {**base, "status": "not_requested"}
    require(callable(getattr(inputs, "dynamic_skill", None)), "clinical_dynamic_skill_unavailable")
    try:
        handle = inputs.dynamic_skill("group_memory", variables={"pharmacological_group_id": group_id})
    except Exception as exc:
        if getattr(exc, "code", None) == "dynamic_skill_not_initialized":
            return {**base, "status": "not_initialized"}
        raise ContractError("clinical_group_memory_read_blocked") from None
    require(handle.provenance().mutable is False, "clinical_readonly_memory_required")
    section = handle.section_text(SECTION)
    require(isinstance(section, str) and len(section) <= 16000, "clinical_memory_requires_compaction")
    for value in (handle.content_digest(), handle.provenance().package_digest):
        require(isinstance(value, str) and DIGEST_RE.fullmatch(value) is not None, "clinical_memory_identity_invalid")
    return {"status": "read", "group_id": group_id, "text": section,
            "content_digest": handle.content_digest(), "package_digest": handle.provenance().package_digest,
            "origin": "prior_memory_not_fresh_evidence"}


def propose_memory_change(snapshot: dict, hypotheses: list[dict], *, mode: str) -> dict:
    """Preserve earlier lessons once; qualified learning remains a non-writing proposal."""
    base = {"status": "not_requested" if mode == "off" or snapshot["status"] == "not_requested" else "preview",
        "write_attempted": False, "group_id": snapshot["group_id"],
        "before_content_digest": snapshot["content_digest"], "before_package_digest": snapshot["package_digest"],
        "lessons": [], "proposed_section": None, "readback_verified": False, "change_id": None}
    if base["status"] == "not_requested":
        return base
    proposed = snapshot["text"]
    for item in hypotheses:
        if not item["memory_eligibility"]:
            continue
        lesson = {"text": item["lesson"], "scope": item["scope"], "hypothesis_id": item["item_id"],
                  "supporting_evidence_ids": item["supporting_evidence_ids"],
                  "counterevidence_ids": item["contradicting_evidence_ids"],
                  "alternatives": item["alternative_explanations"]}
        identity = digest({k: v for k, v in lesson.items() if k != "hypothesis_id"})
        marker = "<!-- clinical-lesson " + identity + " -->"
        if marker in proposed:
            continue
        def literal(value: str) -> str:
            return html.escape(value).replace("\n", " ")
        piece = "\n\n" + marker + "\n" + literal(lesson["text"]) + "\nScope: " + literal(lesson["scope"])
        piece += "\nEvidence: " + ", ".join(lesson["supporting_evidence_ids"])
        piece += "\nAlternatives: " + literal("; ".join(lesson["alternatives"]))
        if lesson["counterevidence_ids"]:
            piece += "\nCounterevidence: " + ", ".join(lesson["counterevidence_ids"])
        if len(proposed + piece) > 16000:
            return {**base, "status": "deferred_size", "reason": "memory_compaction_review_required"}
        proposed += piece
        base["lessons"].append(lesson)
    if not base["lessons"]:
        return {**base, "status": "no_change"}
    return {**base, "proposed_section": proposed, "proposal_digest": text_digest(proposed),
            "initialization_required": snapshot["status"] == "not_initialized"}


def commit_memory_change(*_: Any, **__: Any) -> None:
    """Reject until child mutation and retention-before-apply are qualified."""
    raise ContractError("clinical_memory_apply_not_admitted")
