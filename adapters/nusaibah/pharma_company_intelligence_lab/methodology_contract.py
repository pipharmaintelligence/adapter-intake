from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

try:
    from .agent_contract import RESEARCH_ROLE_SECTIONS
    from .dossier_contract import CANONICAL_SECTIONS, DOSSIER_SCHEMA_VERSION
    from .memory_contract import MAX_MEMORY_CANDIDATE_CHARS, MAX_MEMORY_FACT_IDS, MEMORY_TARGET_SECTION
except ImportError:  # pragma: no cover - local adapter-root execution path
    from agent_contract import RESEARCH_ROLE_SECTIONS
    from dossier_contract import CANONICAL_SECTIONS, DOSSIER_SCHEMA_VERSION
    from memory_contract import MAX_MEMORY_CANDIDATE_CHARS, MAX_MEMORY_FACT_IDS, MEMORY_TARGET_SECTION

SKILL_REF = "nusaibah.pharma-intelligence-methodology"
SKILL_VERSION = "1.0.0"
PLANNER_SCHEMA_VERSION = "pharma_methodology_plan.v1"
PLANNER_ROLE = "methodology_planner"
PLANNER_PRIORITIES = frozenset({"low", "medium", "high"})
MANDATORY_RESEARCH_ROLES = tuple(RESEARCH_ROLE_SECTIONS)

MAX_METHODOLOGY_PACKET_CHARS = 24000
MAX_METHODOLOGY_RULES = 32
MAX_METHODOLOGY_RULE_CHARS = 1200
MAX_METHODOLOGY_MISSION_CHARS = 2000
MAX_PLANNER_QUESTIONS_PER_ROLE = 12
MAX_PLANNER_LIST_ITEMS = 24
MAX_PLANNER_TEXT_CHARS = 1000
MAX_PLANNER_TOTAL_CHARS = 24000

_PLANNER_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "company_id",
        "role",
        "status",
        "research_focus",
        "cross_cutting_questions",
        "known_memory_gaps",
        "expected_uncertainties",
    }
)
_PLANNER_FOCUS_KEYS = frozenset(
    {
        "role",
        "priority",
        "section_ids",
        "questions",
        "freshness_focus",
        "evidence_focus",
    }
)
_FORBIDDEN_PLANNER_CONTROL_KEY_TOKENS = frozenset(
    {
        "provider",
        "model",
        "search",
        "tool",
        "tools",
        "mutation",
        "write",
        "apply",
        "publish",
        "publication",
        "storage",
        "credential",
        "credentials",
        "binding",
        "retry",
        "queue",
        "timeout",
    }
)
_MEMORY_POLICY_KEYS = (
    "schema_version",
    "target_section",
    "max_candidate_chars",
    "max_fact_ids",
    "require_company_id_match",
    "require_novelty",
    "require_deduplication",
    "require_quality_gate",
    "require_expected_digest_on_apply",
    "require_fresh_readback",
    "require_history_verification",
)


@dataclass(frozen=True)
class MethodologyPacket:
    """Bounded planner-safe projection of the admitted Fixed Skill."""

    skill_ref: str
    skill_version: str
    skill_digest: str
    mission: str
    structural_rules: tuple[str, ...]
    evidence_rules: tuple[str, ...]
    role_boundaries: tuple[str, ...]
    company_isolation_rules: tuple[str, ...]
    memory_rules: tuple[str, ...]
    output_rules: tuple[str, ...]
    benchmark_questions: tuple[dict[str, str], ...]
    memory_policy: dict[str, Any]
    canonical_section_ids: tuple[str, ...]

    def to_agent_input(self) -> dict[str, Any]:
        """Return a fresh JSON-compatible copy suitable for Agent input."""
        return {
            "skill_ref": self.skill_ref,
            "skill_version": self.skill_version,
            "skill_digest": self.skill_digest,
            "mission": self.mission,
            "structural_rules": list(self.structural_rules),
            "evidence_rules": list(self.evidence_rules),
            "role_boundaries": list(self.role_boundaries),
            "company_isolation_rules": list(self.company_isolation_rules),
            "memory_rules": list(self.memory_rules),
            "output_rules": list(self.output_rules),
            "benchmark_questions": [dict(item) for item in self.benchmark_questions],
            "memory_policy": dict(self.memory_policy),
            "canonical_section_ids": list(self.canonical_section_ids),
        }


@dataclass(frozen=True)
class MethodologyResources:
    """Validated deterministic resources attached to the fixed methodology Skill."""

    benchmark_questions: tuple[dict[str, str], ...]
    memory_policy: dict[str, Any]
    package_digest: str
    planner_packet: MethodologyPacket


@dataclass(frozen=True)
class ResearchFocus:
    """Validated planner focus for exactly one mandatory research role."""

    role: str
    priority: str
    section_ids: tuple[str, ...]
    questions: tuple[str, ...]
    freshness_focus: tuple[str, ...]
    evidence_focus: tuple[str, ...]

    def to_agent_input(self) -> dict[str, Any]:
        """Return the bounded role-specific fragment for one researcher."""
        return {
            "role": self.role,
            "priority": self.priority,
            "section_ids": list(self.section_ids),
            "questions": list(self.questions),
            "freshness_focus": list(self.freshness_focus),
            "evidence_focus": list(self.evidence_focus),
        }


@dataclass(frozen=True)
class MethodologyPlan:
    """Validated adaptive plan with no execution or mutation authority."""

    company_id: int
    research_focus: tuple[ResearchFocus, ...]
    cross_cutting_questions: tuple[str, ...]
    known_memory_gaps: tuple[str, ...]
    expected_uncertainties: tuple[str, ...]

    def role_focus(self, role: str) -> dict[str, Any]:
        """Return one validated research-role fragment."""
        for focus in self.research_focus:
            if focus.role == role:
                return focus.to_agent_input()
        raise KeyError(role)

    def to_agent_input(self) -> dict[str, Any]:
        """Return the full validated plan for downstream non-research roles."""
        return {
            "schema_version": PLANNER_SCHEMA_VERSION,
            "company_id": self.company_id,
            "role": PLANNER_ROLE,
            "status": "completed",
            "research_focus": [focus.to_agent_input() for focus in self.research_focus],
            "cross_cutting_questions": list(self.cross_cutting_questions),
            "known_memory_gaps": list(self.known_memory_gaps),
            "expected_uncertainties": list(self.expected_uncertainties),
        }

    def requirement_catalog(self) -> tuple[dict[str, Any], ...]:
        """Return stable IDs for every validated planner requirement the critic must evaluate."""
        requirements: list[dict[str, Any]] = []

        for focus in self.research_focus:
            for kind, values in (
                ("question", focus.questions),
                ("freshness_focus", focus.freshness_focus),
                ("evidence_focus", focus.evidence_focus),
            ):
                for index, text in enumerate(values, start=1):
                    requirements.append(
                        {
                            "requirement_id": f"research.{focus.role}.{kind}.{index}",
                            "kind": kind,
                            "role": focus.role,
                            "text": text,
                            "mandatory": True,
                        }
                    )

        for kind, values in (
            ("cross_cutting_question", self.cross_cutting_questions),
            ("known_memory_gap", self.known_memory_gaps),
            ("expected_uncertainty", self.expected_uncertainties),
        ):
            for index, text in enumerate(values, start=1):
                requirements.append(
                    {
                        "requirement_id": f"{kind}.{index}",
                        "kind": kind,
                        "role": None,
                        "text": text,
                        "mandatory": True,
                    }
                )

        return tuple(requirements)

    def requirement_ids(self) -> tuple[str, ...]:
        """Return the exact requirement IDs admitted for critic output."""
        return tuple(item["requirement_id"] for item in self.requirement_catalog())


def load_methodology(inputs: Any) -> MethodologyResources:
    """Resolve the Fixed Skill and build validated deterministic methodology resources."""
    skill = inputs.skill(SKILL_REF)
    validation = skill.validate()
    if validation.status != "ready":
        raise RuntimeError("Fixed methodology Skill is not ready.")
    if validation.skill_ref != SKILL_REF or validation.version != SKILL_VERSION:
        raise RuntimeError("Fixed methodology Skill identity mismatch.")
    if not isinstance(validation.package_digest, str) or not validation.package_digest.strip():
        raise RuntimeError("Fixed methodology Skill digest is invalid.")

    dossier = _json_resource(skill, "references/dossier-schema.json")
    _validate_dossier_resource(dossier)

    benchmark = _json_resource(skill, "references/benchmark-questions.json")
    questions = _validate_benchmark_resource(benchmark)

    memory = _json_resource(skill, "references/memory-policy.json")
    _validate_memory_policy(memory)

    skill_text = skill.read()
    if not isinstance(skill_text, str) or not skill_text.strip():
        raise RuntimeError("Fixed methodology Skill text is empty.")
    evidence_policy = _text_resource(skill, "references/evidence-policy.md")
    planner_packet = _build_methodology_packet(
        skill_text=skill_text,
        evidence_policy=evidence_policy,
        benchmark_questions=questions,
        memory_policy=memory,
        package_digest=validation.package_digest.strip(),
    )

    return MethodologyResources(
        benchmark_questions=questions,
        memory_policy=_memory_policy_projection(memory),
        package_digest=validation.package_digest.strip(),
        planner_packet=planner_packet,
    )


def validate_methodology_plan(value: Any, *, company_id: int) -> MethodologyPlan:
    """Validate one planner JSON result and return deterministic bounded fragments."""
    if not isinstance(value, dict):
        raise ValueError("Methodology plan must be an object.")
    _reject_planner_control_keys(value)
    _require_exact_keys(value, _PLANNER_TOP_LEVEL_KEYS, field="methodology plan")

    if value.get("schema_version") != PLANNER_SCHEMA_VERSION:
        raise ValueError("Methodology plan schema_version is unsupported.")
    if value.get("company_id") != company_id:
        raise ValueError("Methodology plan company_id does not match the current company.")
    if value.get("role") != PLANNER_ROLE:
        raise ValueError("Methodology plan role identity is invalid.")
    if value.get("status") != "completed":
        raise ValueError("Methodology plan status must equal completed.")

    raw_focus = value.get("research_focus")
    if not isinstance(raw_focus, list) or len(raw_focus) != len(MANDATORY_RESEARCH_ROLES):
        raise ValueError("Methodology plan must contain every mandatory research role exactly once.")

    by_role: dict[str, ResearchFocus] = {}
    for raw in raw_focus:
        if not isinstance(raw, dict):
            raise ValueError("research_focus entries must be objects.")
        _reject_planner_control_keys(raw)
        _require_exact_keys(raw, _PLANNER_FOCUS_KEYS, field="research_focus entry")

        role = _token(raw.get("role"), "research_focus.role", max_chars=128)
        if role not in RESEARCH_ROLE_SECTIONS:
            raise ValueError("Methodology plan contains an unknown research role.")
        if role in by_role:
            raise ValueError("Methodology plan contains a duplicate research role.")

        priority = _token(raw.get("priority"), "research_focus.priority", max_chars=16)
        if priority not in PLANNER_PRIORITIES:
            raise ValueError("Methodology plan priority is unsupported.")

        section_ids = _token_list(
            raw.get("section_ids"),
            "research_focus.section_ids",
            maximum=len(RESEARCH_ROLE_SECTIONS[role]),
            minimum=1,
        )
        if tuple(section_ids) != RESEARCH_ROLE_SECTIONS[role]:
            raise ValueError("Methodology plan section ownership does not match the research role.")

        focus = ResearchFocus(
            role=role,
            priority=priority,
            section_ids=tuple(section_ids),
            questions=tuple(
                _bounded_text_list(
                    raw.get("questions"),
                    "research_focus.questions",
                    maximum=MAX_PLANNER_QUESTIONS_PER_ROLE,
                    minimum=1,
                )
            ),
            freshness_focus=tuple(
                _bounded_text_list(
                    raw.get("freshness_focus", []),
                    "research_focus.freshness_focus",
                    maximum=MAX_PLANNER_LIST_ITEMS,
                )
            ),
            evidence_focus=tuple(
                _bounded_text_list(
                    raw.get("evidence_focus", []),
                    "research_focus.evidence_focus",
                    maximum=MAX_PLANNER_LIST_ITEMS,
                )
            ),
        )
        by_role[role] = focus

    if set(by_role) != set(MANDATORY_RESEARCH_ROLES):
        raise ValueError("Methodology plan omitted a mandatory research role.")

    plan = MethodologyPlan(
        company_id=company_id,
        research_focus=tuple(by_role[role] for role in MANDATORY_RESEARCH_ROLES),
        cross_cutting_questions=tuple(
            _bounded_text_list(
                value.get("cross_cutting_questions", []),
                "cross_cutting_questions",
                maximum=MAX_PLANNER_LIST_ITEMS,
            )
        ),
        known_memory_gaps=tuple(
            _bounded_text_list(
                value.get("known_memory_gaps", []),
                "known_memory_gaps",
                maximum=MAX_PLANNER_LIST_ITEMS,
            )
        ),
        expected_uncertainties=tuple(
            _bounded_text_list(
                value.get("expected_uncertainties", []),
                "expected_uncertainties",
                maximum=MAX_PLANNER_LIST_ITEMS,
            )
        ),
    )
    serialized = json.dumps(plan.to_agent_input(), sort_keys=True, separators=(",", ":"))
    if len(serialized) > MAX_PLANNER_TOTAL_CHARS:
        raise ValueError("Methodology plan exceeds the total character bound.")
    return plan


def _json_resource(skill: Any, path: str) -> dict[str, Any]:
    text = skill.read_resource(path)
    try:
        value = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Fixed methodology resource is invalid: {path}.") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Fixed methodology resource must be an object: {path}.")
    return value


def _text_resource(skill: Any, path: str) -> str:
    text = skill.read_resource(path)
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError(f"Fixed methodology text resource is empty: {path}.")
    return text


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
        question_id = question_id.strip()
        question = question.strip()
        if len(question_id) > 128 or len(question) > MAX_METHODOLOGY_RULE_CHARS:
            raise RuntimeError("Fixed methodology benchmark question exceeds the planner-safe bound.")
        seen.add(question_id)
        normalized.append({"question_id": question_id, "question": question})
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


def _build_methodology_packet(
    *,
    skill_text: str,
    evidence_policy: str,
    benchmark_questions: tuple[dict[str, str], ...],
    memory_policy: dict[str, Any],
    package_digest: str,
) -> MethodologyPacket:
    mission = _bounded_methodology_text(
        _markdown_section(skill_text, "Mission"),
        field="methodology mission",
        max_chars=MAX_METHODOLOGY_MISSION_CHARS,
    )
    packet = MethodologyPacket(
        skill_ref=SKILL_REF,
        skill_version=SKILL_VERSION,
        skill_digest=package_digest,
        mission=mission,
        structural_rules=_methodology_rules(
            _markdown_section(skill_text, "Structural contract"),
            field="structural_rules",
        ),
        evidence_rules=_evidence_rules(skill_text, evidence_policy),
        role_boundaries=_methodology_rules(
            _markdown_section(skill_text, "Role boundaries"),
            field="role_boundaries",
        ),
        company_isolation_rules=_methodology_rules(
            _markdown_section(skill_text, "Company isolation"),
            field="company_isolation_rules",
        ),
        memory_rules=_methodology_rules(
            _markdown_section(skill_text, "Memory discipline"),
            field="memory_rules",
        ),
        output_rules=_methodology_rules(
            _markdown_section(skill_text, "Output discipline"),
            field="output_rules",
        ),
        benchmark_questions=tuple(dict(item) for item in benchmark_questions),
        memory_policy=_memory_policy_projection(memory_policy),
        canonical_section_ids=tuple(section.section_id for section in CANONICAL_SECTIONS),
    )
    serialized = json.dumps(packet.to_agent_input(), sort_keys=True, separators=(",", ":"))
    if len(serialized) > MAX_METHODOLOGY_PACKET_CHARS:
        raise RuntimeError("Fixed methodology planner packet exceeds the total character bound.")
    return packet


def _evidence_rules(skill_text: str, evidence_policy: str) -> tuple[str, ...]:
    rules = list(
        _methodology_rules(
            _markdown_section(skill_text, "Evidence discipline"),
            field="evidence_rules",
        )
    )
    for heading in (
        "Evidence classes",
        "Freshness",
        "Citation coverage",
        "Contradictions",
        "Missing evidence",
    ):
        for item in _methodology_rules(
            _markdown_section(evidence_policy, heading),
            field="evidence_rules",
        ):
            rules.append(f"{heading}: {item}")
    return _bounded_rule_tuple(rules, field="evidence_rules")


def _markdown_section(text: str, heading: str) -> str:
    lines = text.splitlines()
    marker = f"## {heading}"
    start: int | None = None
    collected: list[str] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if start is None:
            if stripped == marker:
                start = index + 1
            continue
        if stripped.startswith("## "):
            break
        collected.append(line)
    if start is None:
        raise RuntimeError(f"Fixed methodology text is missing required section: {heading}.")
    body = "\n".join(collected).strip()
    if not body:
        raise RuntimeError(f"Fixed methodology text section is empty: {heading}.")
    return body


def _methodology_rules(text: str, *, field: str) -> tuple[str, ...]:
    rules: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^(?:[-*]|\d+\.)\s+", "", line).strip()
        if line:
            rules.append(line)
    return _bounded_rule_tuple(rules, field=field)


def _bounded_rule_tuple(values: list[str], *, field: str) -> tuple[str, ...]:
    if not values or len(values) > MAX_METHODOLOGY_RULES:
        raise RuntimeError(f"Fixed methodology {field} is outside the allowed item bound.")
    normalized = tuple(
        _bounded_methodology_text(value, field=field, max_chars=MAX_METHODOLOGY_RULE_CHARS)
        for value in values
    )
    if len(set(normalized)) != len(normalized):
        raise RuntimeError(f"Fixed methodology {field} contains duplicate rules.")
    return normalized


def _bounded_methodology_text(value: Any, *, field: str, max_chars: int) -> str:
    if not isinstance(value, str):
        raise RuntimeError(f"Fixed methodology {field} must be text.")
    text = " ".join(value.split()).strip()
    if not text or len(text) > max_chars:
        raise RuntimeError(f"Fixed methodology {field} is outside the allowed character bound.")
    return text


def _memory_policy_projection(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in _MEMORY_POLICY_KEYS}


def _require_exact_keys(value: dict[str, Any], expected: frozenset[str], *, field: str) -> None:
    actual = set(value)
    if actual != set(expected):
        unknown = sorted(actual - set(expected))
        missing = sorted(set(expected) - actual)
        details: list[str] = []
        if unknown:
            details.append(f"unknown keys: {', '.join(unknown)}")
        if missing:
            details.append(f"missing keys: {', '.join(missing)}")
        raise ValueError(f"{field} has an invalid shape ({'; '.join(details)}).")


def _reject_planner_control_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str):
                tokens = set(re.split(r"[^a-z0-9]+", key.lower()))
                if tokens & _FORBIDDEN_PLANNER_CONTROL_KEY_TOKENS:
                    raise ValueError("Methodology plan contains a forbidden control-authority field.")
            _reject_planner_control_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_planner_control_keys(child)


def _bounded_text_list(
    value: Any,
    field: str,
    *,
    maximum: int,
    minimum: int = 0,
) -> list[str]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f"{field} must be a bounded list.")
    result = [_planner_text(item, field) for item in value]
    if len(set(result)) != len(result):
        raise ValueError(f"{field} must not contain duplicates.")
    return result


def _planner_text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must contain strings.")
    text = " ".join(value.split()).strip()
    if not text or len(text) > MAX_PLANNER_TEXT_CHARS:
        raise ValueError(f"{field} contains text outside the allowed character bound.")
    return text


def _token(value: Any, field: str, *, max_chars: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string.")
    text = value.strip()
    if not text or len(text) > max_chars or any(character.isspace() for character in text):
        raise ValueError(f"{field} must be a bounded compact token.")
    return text


def _token_list(
    value: Any,
    field: str,
    *,
    maximum: int,
    minimum: int = 0,
) -> list[str]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f"{field} must be a bounded list.")
    result = [_token(item, field, max_chars=128) for item in value]
    if len(set(result)) != len(result):
        raise ValueError(f"{field} must not contain duplicates.")
    return result
