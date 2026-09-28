from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

try:
    from .dossier_contract import CANONICAL_SECTIONS, DOSSIER_SCHEMA_VERSION
    from .memory_contract import MAX_MEMORY_CANDIDATE_CHARS, MAX_MEMORY_FACT_IDS, MEMORY_TARGET_SECTION
except ImportError:  # pragma: no cover - local adapter-root execution path
    from dossier_contract import CANONICAL_SECTIONS, DOSSIER_SCHEMA_VERSION
    from memory_contract import MAX_MEMORY_CANDIDATE_CHARS, MAX_MEMORY_FACT_IDS, MEMORY_TARGET_SECTION

SKILL_REF = "nusaibah.pharma-intelligence-methodology"
SKILL_VERSION = "1.0.0"


@dataclass(frozen=True)
class MethodologyResources:
    """Validated deterministic resources attached to the fixed methodology Skill."""

    benchmark_questions: tuple[dict[str, str], ...]
    memory_policy: dict[str, Any]
    package_digest: str


def load_methodology(inputs: Any) -> MethodologyResources:
    """Resolve and validate the fixed Skill plus machine-readable resources."""
    skill = inputs.skill(SKILL_REF)
    validation = skill.validate()
    if validation.status != "ready":
        raise RuntimeError("Fixed methodology Skill is not ready.")
    if validation.skill_ref != SKILL_REF or validation.version != SKILL_VERSION:
        raise RuntimeError("Fixed methodology Skill identity mismatch.")

    dossier = _json_resource(skill, "references/dossier-schema.json")
    _validate_dossier_resource(dossier)

    benchmark = _json_resource(skill, "references/benchmark-questions.json")
    questions = _validate_benchmark_resource(benchmark)

    memory = _json_resource(skill, "references/memory-policy.json")
    _validate_memory_policy(memory)

    evidence_policy = skill.read_resource("references/evidence-policy.md")
    if not isinstance(evidence_policy, str) or not evidence_policy.strip():
        raise RuntimeError("Fixed methodology evidence policy is empty.")

    return MethodologyResources(
        benchmark_questions=questions,
        memory_policy=memory,
        package_digest=validation.package_digest,
    )


def _json_resource(skill: Any, path: str) -> dict[str, Any]:
    text = skill.read_resource(path)
    try:
        value = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Fixed methodology resource is invalid: {path}.") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Fixed methodology resource must be an object: {path}.")
    return value


def _validate_dossier_resource(value: dict[str, Any]) -> None:
    if value.get("schema_version") != DOSSIER_SCHEMA_VERSION:
        raise RuntimeError("Fixed methodology dossier schema version mismatch.")
    sections = value.get("sections")
    if not isinstance(sections, list) or len(sections) != len(CANONICAL_SECTIONS):
        raise RuntimeError("Fixed methodology dossier section count mismatch.")

    for raw, spec in zip(sections, CANONICAL_SECTIONS, strict=True):
        if not isinstance(raw, dict):
            raise RuntimeError("Fixed methodology dossier section is invalid.")
        if raw.get("section_id") != spec.section_id or raw.get("title") != spec.title:
            raise RuntimeError("Fixed methodology dossier section identity drift detected.")
        raw_subsections = raw.get("subsections")
        if not isinstance(raw_subsections, list) or len(raw_subsections) != len(spec.subsections):
            raise RuntimeError("Fixed methodology dossier subsection count mismatch.")
        for raw_sub, sub_spec in zip(raw_subsections, spec.subsections, strict=True):
            if (
                not isinstance(raw_sub, dict)
                or raw_sub.get("subsection_id") != sub_spec.subsection_id
                or raw_sub.get("title") != sub_spec.title
            ):
                raise RuntimeError("Fixed methodology dossier subsection identity drift detected.")


def _validate_benchmark_resource(value: dict[str, Any]) -> tuple[dict[str, str], ...]:
    if value.get("schema_version") != "pharma_company_memory_benchmark.v1":
        raise RuntimeError("Fixed methodology benchmark schema mismatch.")
    questions = value.get("questions")
    if not isinstance(questions, list) or not questions or len(questions) > 32:
        raise RuntimeError("Fixed methodology benchmark questions are invalid.")

    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in questions:
        if not isinstance(raw, dict):
            raise RuntimeError("Fixed methodology benchmark question is invalid.")
        question_id = raw.get("question_id")
        question = raw.get("question")
        if (
            not isinstance(question_id, str)
            or not question_id.strip()
            or question_id in seen
            or not isinstance(question, str)
            or not question.strip()
        ):
            raise RuntimeError("Fixed methodology benchmark question is invalid.")
        seen.add(question_id)
        normalized.append({"question_id": question_id.strip(), "question": question.strip()})
    return tuple(normalized)


def _validate_memory_policy(value: dict[str, Any]) -> None:
    expected = {
        "schema_version": "pharma_company_memory_policy.v1",
        "target_section": MEMORY_TARGET_SECTION,
        "max_candidate_chars": MAX_MEMORY_CANDIDATE_CHARS,
        "max_fact_ids": MAX_MEMORY_FACT_IDS,
        "require_company_id_match": True,
        "require_novelty": True,
        "require_deduplication": True,
        "require_quality_gate": True,
        "require_expected_digest_on_apply": True,
        "require_fresh_readback": True,
        "require_history_verification": True,
    }
    if any(value.get(key) != expected_value for key, expected_value in expected.items()):
        raise RuntimeError("Fixed methodology memory policy drift detected.")
