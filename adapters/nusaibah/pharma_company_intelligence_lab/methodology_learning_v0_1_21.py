"""Review-only procedural methodology proposal for pharma adapter 0.1.21.

The proposal preserves the existing company methodology text byte-for-byte as
its prefix and appends only generic verification lessons identified during the
Company 14 review. It contains no company research facts, changes no Fixed Skill,
and grants no mutation authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

try:
    from .claim_semantics_v0_1_21 import SEMANTIC_RULES
except ImportError:  # pragma: no cover - flat intake execution
    from claim_semantics_v0_1_21 import SEMANTIC_RULES


SCHEMA_VERSION = "pharma_methodology_learning_addendum.v1"
MARKER = f"<!-- schema: {SCHEMA_VERSION} -->"
MAX_TOTAL_CHARS = 12000

_EXTRA_LESSONS = (
    (
        "claim_local_withholding",
        "Withhold only a defective claim and affected section prose; preserve unrelated supported work.",
    ),
    (
        "candidate_fact_evidence_selection",
        "Select bounded citations from retained candidate fact IDs before adding secondary evidence.",
    ),
)
LESSONS = (*_EXTRA_LESSONS, *SEMANTIC_RULES)
LESSON_TEXT_BY_ID = dict(LESSONS)


class MethodologyLearningError(ValueError):
    """Value-safe deterministic methodology proposal rejection."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class MethodologyLearningProposal:
    """One bounded, review-only complete section replacement proposal."""

    schema_version: str
    candidate: str
    rule_ids: tuple[str, ...]
    proposal_digest: str
    previous_learning_preserved: bool
    changed: bool
    apply_authority: bool


def build_methodology_learning_proposal(
    existing_text: str,
) -> MethodologyLearningProposal:
    """Append reviewed generic lessons while preserving existing text exactly."""

    if not isinstance(existing_text, str):
        raise MethodologyLearningError("methodology_learning_text_invalid")
    if len(existing_text) > MAX_TOTAL_CHARS:
        raise MethodologyLearningError("methodology_learning_text_oversized")

    rule_ids = tuple(rule_id for rule_id, _instruction in LESSONS)
    if len(set(rule_ids)) != len(rule_ids):
        raise MethodologyLearningError("methodology_learning_rule_duplicate")

    if MARKER in existing_text:
        candidate = existing_text
        changed = False
    else:
        separator = "" if not existing_text else (
            "\n\n" if not existing_text.endswith("\n") else "\n"
        )
        candidate = existing_text + separator + _render_addendum()
        changed = True

    if len(candidate) > MAX_TOTAL_CHARS:
        raise MethodologyLearningError("methodology_learning_candidate_oversized")
    if not candidate.startswith(existing_text):
        raise MethodologyLearningError("methodology_learning_history_not_preserved")

    return MethodologyLearningProposal(
        schema_version=SCHEMA_VERSION,
        candidate=candidate,
        rule_ids=rule_ids,
        proposal_digest="sha256:" + sha256(candidate.encode("utf-8")).hexdigest(),
        previous_learning_preserved=True,
        changed=changed,
        apply_authority=False,
    )


def _render_addendum() -> str:
    lines = [
        MARKER,
        "### Reviewed Procedural Lessons",
        "",
    ]
    for rule_id, instruction in LESSONS:
        lines.append(f"- [{rule_id}] {instruction}")
    lines.extend(
        [
            "",
            "- review_required: true",
            "- apply_authority: false",
            "- company_facts_included: false",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
