"""Bounded read projection over already-admitted Skill views."""
from __future__ import annotations

import json
import re
from typing import Any, ClassVar

from adapters.base import Adapter


MAX_TEXT_BYTES = 8192
MAX_RESULT_BYTES = 32768
MAX_SECTIONS = 20
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SELECTOR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,190}$")


class SkillReaderError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _text(value: Any, maximum: int = 240) -> str:
    if (not isinstance(value, str) or not value or value != value.strip()
            or len(value) > maximum or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise SkillReaderError("skill_reader_request_invalid")
    return value


def _request(value: Any) -> dict[str, Any]:
    allowed = {"source_kind", "selector", "read", "section", "resource", "selectors", "expected_digest"}
    if not isinstance(value, dict) or set(value) - allowed:
        raise SkillReaderError("skill_reader_request_invalid")
    kind = value.get("source_kind")
    read = value.get("read", "sections")
    if kind not in {"fixed", "dynamic"} or read not in {"sections", "section", "resource", "document"}:
        raise SkillReaderError("skill_reader_request_invalid")
    selector = _text(value.get("selector"), 191)
    if not _SELECTOR.fullmatch(selector):
        raise SkillReaderError("skill_reader_request_invalid")
    selectors = value.get("selectors", {})
    if not isinstance(selectors, dict) or len(selectors) > 16:
        raise SkillReaderError("skill_reader_request_invalid")
    for key, item in selectors.items():
        if (not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,95}", key)
                or isinstance(item, bool) or not isinstance(item, (str, int))):
            raise SkillReaderError("skill_reader_request_invalid")
        if len(str(item)) > 128 or not str(item) or str(item) != str(item).strip():
            raise SkillReaderError("skill_reader_request_invalid")
    if kind == "fixed" and selectors:
        raise SkillReaderError("skill_reader_request_invalid")
    expected = value.get("expected_digest")
    if expected is not None and (not isinstance(expected, str) or not _DIGEST.fullmatch(expected)):
        raise SkillReaderError("skill_reader_request_invalid")
    if read == "section":
        section = value.get("section")
        if isinstance(section, str):
            _text(section)
        elif isinstance(section, list) and 1 <= len(section) <= 6:
            for part in section:
                _text(part)
        else:
            raise SkillReaderError("skill_reader_request_invalid")
    elif "section" in value:
        raise SkillReaderError("skill_reader_request_invalid")
    if read == "resource":
        path = _text(value.get("resource"))
        if ("\\" in path or ":" in path or path.startswith("/")
                or any(part in {"", ".", ".."} or part.startswith(".") for part in path.split("/"))):
            raise SkillReaderError("skill_reader_resource_invalid")
    elif "resource" in value:
        raise SkillReaderError("skill_reader_request_invalid")
    return {**value, "source_kind": kind, "selector": selector, "read": read, "selectors": dict(selectors)}


def read_skill(inputs: Any, request: Any) -> dict[str, Any]:
    """Read only through the consuming runtime's existing admitted views."""
    query = _request(request)
    try:
        if query["source_kind"] == "fixed":
            view = inputs.skill(query["selector"])
            validation = view.validate()
            if validation.status != "ready":
                raise SkillReaderError("skill_reader_source_unavailable")
        else:
            view = inputs.dynamic_skill(query["selector"], variables=query["selectors"])
        provenance = view.provenance()
        if getattr(provenance, "mutable", False) is not False:
            raise SkillReaderError("skill_reader_mutable_source_rejected")
        digest = view.content_digest()
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest) or provenance.content_digest != digest:
            raise SkillReaderError("skill_reader_integrity_invalid")
        if query.get("expected_digest") is not None and query["expected_digest"] != digest:
            raise SkillReaderError("skill_reader_snapshot_changed")
        identity = {
            "content_digest": digest,
            "package_digest": getattr(provenance, "package_digest", None),
            "skill_ref": getattr(provenance, "skill_ref", None),
            "version": getattr(provenance, "version", None),
            "snapshot_id": getattr(provenance, "snapshot_id", None),
            "observed_at": None,
        }
        if query["source_kind"] == "dynamic":
            snapshot = view.snapshot()
            if snapshot.content_digest != digest or snapshot.snapshot_id != identity["snapshot_id"]:
                raise SkillReaderError("skill_reader_integrity_invalid")
            identity["observed_at"] = provenance.observed_at.isoformat()
        sections: list[dict[str, Any]] = []
        text = None
        section = None
        resource = None
        has_more = False
        if query["read"] == "sections":
            available = view.list_sections()
            has_more = len(available) > MAX_SECTIONS
            sections = [{"path": list(item.path.parts)} for item in available[:MAX_SECTIONS]]
        elif query["read"] == "section":
            if not view.has_section(query["section"]):
                raise SkillReaderError("skill_reader_section_unavailable")
            section = list(view.section(query["section"]).path.parts)
            text = view.section_text(query["section"])
        elif query["read"] == "resource":
            resource = query["resource"]
            if not view.resource_exists(resource):
                raise SkillReaderError("skill_reader_resource_unavailable")
            text = view.read_resource(resource)
        else:
            text = view.read()
        if text is not None and not isinstance(text, str):
            raise SkillReaderError("skill_reader_integrity_invalid")
        byte_count = len(text.encode("utf-8")) if text is not None else 0
        if byte_count > MAX_TEXT_BYTES:
            raise SkillReaderError("skill_reader_text_limit_exceeded")
        result = {
            "schema_version": "skill_read_result.v1", "status": "ready",
            "source_kind": query["source_kind"], "selector": query["selector"],
            "identity": identity, "resolution": "execution_snapshot",
            "read": query["read"], "section": section, "resource": resource,
            "text": text, "byte_count": byte_count, "sections": sections, "has_more": has_more,
            "retention": "workflow_result",
        }
        if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > MAX_RESULT_BYTES:
            raise SkillReaderError("skill_reader_result_limit_exceeded")
        return result
    except SkillReaderError:
        raise
    except Exception:
        # Runtime exceptions can contain paths or source text. Keep only a stable code.
        raise SkillReaderError("skill_reader_source_unavailable") from None


class SkillReaderAdapter(Adapter):
    key: ClassVar[str] = "nusaibah.skill_reader"
    version: ClassVar[str] = "0.1.0"

    def invoke(self, inputs: Any, context: dict[str, Any]) -> dict[str, Any]:
        del context
        result = read_skill(inputs, inputs.get("variables"))
        return {"response_version": "1", "status": "success", "outputs": {"skill_result": result},
                "metrics": {"skill_reads": 1, "agent_calls": 0, "mutation_calls": 0}}
