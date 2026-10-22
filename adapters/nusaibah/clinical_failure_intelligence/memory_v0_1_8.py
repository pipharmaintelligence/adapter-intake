"""Optional read-only class snapshots and bounded learning proposals; preview never writes."""
from __future__ import annotations
from typing import Any
if __package__:
    from .contracts_v0_1_8 import ContractError, DIGEST_RE, digest, require, text_digest
else:
    from contracts_v0_1_8 import ContractError, DIGEST_RE, digest, require, text_digest

FIXED_REF = "nusaibah.clinical-failure-methodology"
SECTION = "Lessons"


def read_methodology(inputs: Any) -> dict:
    """Consume an admitted Fixed Skill, not an arbitrary local file as authority."""
    require(callable(getattr(inputs, "skill", None)), "clinical_fixed_skill_unavailable")
    view = inputs.skill(FIXED_REF)
    sections = {name: view.section_text(name) for name in ("Evidence Rules", "Outcome Rules", "Learning Rules")}
    require(all(isinstance(v, str) and v.strip() for v in sections.values()), "clinical_methodology_invalid")
    return {"skill_ref": FIXED_REF, "version": "1.1.0", "sections": sections, "section_digest": digest(sections)}


def read_group_memory(inputs: Any, request: dict) -> dict:
    """Distinguish a genuinely absent partition from missing node or authority."""
    group_id = request["context"]["subject"]["pharmacological_group_id"]
    base = {"group_id": group_id, "text": "", "content_digest": None, "package_digest": None}
    if not request.get("enable_pharmacological_class", False) or request["memory_mode"] == "off" or group_id is None:
        return {**base, "status": "not_requested"}
    require(callable(getattr(inputs, "dynamic_skill", None)), "clinical_dynamic_skill_unavailable")
    try:
        handle = inputs.dynamic_skill("group_memory", variables={"pharmacological_group_id": group_id})
    except Exception as exc:
        if getattr(exc, "code", None) == "dynamic_skill_not_initialized":
            return {**base, "status": "not_initialized"}
        raise ContractError("clinical_group_memory_read_blocked") from None
    require(handle.provenance().mutable is False, "clinical_readonly_memory_required")
    if __package__:
        from .product_memory_v0_1_8 import read_paragraph_slice
    else:
        from product_memory_v0_1_8 import read_paragraph_slice
    selection = read_paragraph_slice(handle, [SECTION])
    section = "\n\n".join(row["text"] for row in selection["paragraphs"])
    for value in (handle.content_digest(), handle.provenance().package_digest):
        require(isinstance(value, str) and DIGEST_RE.fullmatch(value) is not None, "clinical_memory_identity_invalid")
    return {"status": "read", "group_id": group_id, "text": section,
            "content_digest": handle.content_digest(), "package_digest": handle.provenance().package_digest,
            "origin": "prior_memory_not_fresh_evidence"}


def commit_memory_change(*_: Any, **__: Any) -> None:
    """Reject until child mutation and retention-before-apply are qualified."""
    raise ContractError("clinical_memory_apply_not_admitted")
